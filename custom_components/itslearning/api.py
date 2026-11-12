"""Client for itslearning with login through Skolfederation (SAML IdP).

The flow mirrors what the itslearning mobile app does:

1. Open the OAuth2 authorize page with the app's client id.
2. itslearning shows its login page; we "click" the Skolfederation button
   (an ASP.NET postback).
3. We land on the municipality's IdP (for Nässjö: Höglandsportalen, a Nexus
   gateway). We pick "Användarnamn och lösenord" and post the credentials.
4. SAML auto-post forms bounce us back to itslearning, which finally
   redirects to the app's custom scheme with an authorization code.
5. The code is exchanged for an access token + refresh token.

This module has no Home Assistant dependency, so it can be tested on its own
(see test_login.py in the repository root).
"""
from __future__ import annotations

import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import aiohttp
from yarl import URL

_LOGGER = logging.getLogger(__name__)

CLIENT_ID = "10ae9d30-1853-48ff-81cb-47b58a325685"
REDIRECT_URI = "itsl-itslearning://login"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)
MAX_STEPS = 25
FEDERATION_HINT = "Skolfederation"
PASSWORD_AUTHMECH_HINTS = ("anv%c3%a4ndarnamn", "användarnamn", "username", "password", "l%c3%b6senord")
COMPLETED_STATUSES = {"completed", "finished", "submitted", "done", "handedin", "evaluated", "assessed"}


class ItslearningError(Exception):
    """Base error."""


class ItslearningAuthError(ItslearningError):
    """Wrong credentials or the login flow could not be completed."""


class ItslearningConnectionError(ItslearningError):
    """Network problem or unexpected server answer."""


# --------------------------------------------------------------------------- #
# Minimal HTML parsing (stdlib only, so no extra requirements in HA)
# --------------------------------------------------------------------------- #
@dataclass
class _Form:
    action: str | None
    method: str
    inputs: list[dict[str, str]] = field(default_factory=list)

    def has_password(self) -> bool:
        return any(i.get("type") == "password" and i.get("name") for i in self.inputs)

    def is_saml(self) -> bool:
        names = {i.get("name", "") for i in self.inputs}
        return bool(names & {"SAMLResponse", "SAMLRequest", "RelayState", "wresult", "code", "id_token"})


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[_Form] = []
        self.links: list[tuple[str, str]] = []
        self.title = ""
        self._form: _Form | None = None
        self._link_href: str | None = None
        self._link_text: list[str] = []
        self._in_title = False
        self.meta_refresh: str | None = None
        self.text: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "form":
            self._form = _Form(a.get("action"), (a.get("method") or "get").lower())
            self.forms.append(self._form)
        elif tag in ("input", "button", "select", "textarea") and self._form is not None:
            if tag == "input" or a.get("name"):
                self._form.inputs.append(
                    {"name": a.get("name", ""), "type": a.get("type", "text").lower(), "value": a.get("value", "")}
                )
        elif tag == "a":
            self._link_href = a.get("href", "")
            self._link_text = []
        elif tag == "title":
            self._in_title = True
        elif tag in ("script", "style"):
            self._skip += 1
        elif tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            m = re.search(r"url\s*=\s*['\"]?([^'\";]+)", a.get("content", ""), re.I)
            if m:
                self.meta_refresh = m.group(1).strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._form = None
        elif tag == "a" and self._link_href is not None:
            self.links.append((self._link_href, " ".join("".join(self._link_text).split())))
            self._link_href = None
        elif tag == "title":
            self._in_title = False
        elif tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._link_href is not None:
            self._link_text.append(data)
        if self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self.text.append(data.strip())

    def forms_with_saml(self) -> bool:
        return any(f.is_saml() for f in self.forms)

    @property
    def visible_text(self) -> str:
        return " ".join(" ".join(self.text).split())


def _short(url: str) -> str:
    """host + path, without query (no tokens or SAML data in logs)."""
    p = urlparse(url)
    return f"{p.netloc}{p.path}"


def _parse(html: str) -> _PageParser:
    p = _PageParser()
    p.feed(html)
    return p


def _form_fields(form: _Form) -> dict[str, str]:
    data: dict[str, str] = {}
    for i in form.inputs:
        name = i.get("name")
        if not name or i.get("type") in ("submit", "button", "image", "reset"):
            continue
        if i.get("type") in ("checkbox", "radio"):
            continue
        data[name] = i.get("value", "")
    return data


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: float

    @property
    def valid(self) -> bool:
        return bool(self.access_token) and time.time() < self.expires_at - 60

    def as_dict(self) -> dict[str, Any]:
        return {"access_token": self.access_token, "refresh_token": self.refresh_token, "expires_at": self.expires_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Tokens | None":
        if not d or not d.get("refresh_token"):
            return None
        return cls(d.get("access_token", ""), d["refresh_token"], float(d.get("expires_at", 0)))


@dataclass
class Task:
    id: int
    title: str
    course: str
    status: str
    deadline: datetime | None
    url: str
    element_type: str

    @property
    def completed(self) -> bool:
        return self.status.replace(" ", "").lower() in COMPLETED_STATUSES

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "course": self.course,
            "status": self.status,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "url": self.url,
            "type": self.element_type,
        }


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    s = str(value).strip()
    m = re.match(r"/Date\((-?\d+)", s)  # Old MS JSON format
    if m:
        return datetime.fromtimestamp(int(m.group(1)) / 1000, timezone.utc)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)  # trim >6 fraction digits
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # API "…Utc" fields are UTC
    return dt


def _task_from_json(j: dict[str, Any]) -> Task:
    return Task(
        id=int(j.get("TaskId") or j.get("ElementId") or 0),
        title=str(j.get("Title") or ""),
        course=str(j.get("LocationTitle") or j.get("CourseTitle") or ""),
        status=str(j.get("Status") or ""),
        deadline=parse_datetime(j.get("Deadline") or j.get("DeadlineUtc")),
        url=str(j.get("Url") or ""),
        element_type=str(j.get("ElementType") or ""),
    )


class _CodeReceived(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class ItslearningClient:
    """Async client. Pass your own aiohttp session or let it create one."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        tokens: Tokens | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.tokens = tokens
        self._session = session
        self._own_session = session is None

    # ---- session handling ------------------------------------------------- #
    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(),
                headers={"User-Agent": USER_AGENT, "Accept-Language": "sv-SE,sv;q=0.9"},
                timeout=aiohttp.ClientTimeout(total=30),
            )
            self._own_session = True
        return self._session

    async def close(self) -> None:
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    # ---- low level -------------------------------------------------------- #
    @staticmethod
    def _url(u: str) -> URL:
        """Keep the server's exact percent-encoding (like a browser does)."""
        try:
            if u.isascii() and " " not in u:
                return URL(u, encoded=True)
        except ValueError:
            pass
        return URL(u)

    async def _request(self, method: str, url: str, data: dict[str, str] | None = None) -> tuple[str, str]:
        """Do a request and follow redirects by hand.

        Returns (final_url, html). Raises _CodeReceived when itslearning
        redirects to the app's custom scheme.
        """
        for _ in range(MAX_STEPS):
            try:
                async with self.session.request(method, self._url(url), data=data, allow_redirects=False) as resp:
                    _LOGGER.debug("  %s %s -> %s", method, _short(url), resp.status)
                    if resp.status in (301, 302, 303, 307, 308):
                        location = resp.headers.get("Location", "")
                        nxt = urljoin(url, location)
                        self._check_for_code(nxt)
                        if resp.status in (301, 302, 303):
                            method, data = "GET", None
                        url = nxt
                        continue
                    text = await resp.text(errors="replace")
                    if resp.status >= 500:
                        raise ItslearningConnectionError(f"HTTP {resp.status} from {urlparse(url).netloc}")
                    return url, text
            except aiohttp.ClientError as err:
                raise ItslearningConnectionError(str(err)) from err
        raise ItslearningConnectionError("Too many redirects")

    @staticmethod
    def _check_for_code(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            qs = parse_qs(parsed.query)
            if "code" in qs:
                raise _CodeReceived(qs["code"][0])
            err = qs.get("error_description") or qs.get("error") or ["unknown"]
            raise ItslearningAuthError(f"itslearning refused the login: {err[0]}")

    # ---- login ------------------------------------------------------------ #
    async def login(self) -> Tokens:
        """Full browser-like login. Use sparingly; refresh tokens are preferred."""
        self.session.cookie_jar.clear()
        params = {
            "client_id": CLIENT_ID,
            "state": secrets.token_hex(8),
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": "SCOPE",
        }
        try:
            code = await self._run_login_flow(f"{self.base_url}/oauth2/authorize.aspx?{urlencode(params)}")
        except _CodeReceived as rec:
            code = rec.code
        self.tokens = await self._token_request({"grant_type": "authorization_code", "code": code})
        return self.tokens

    async def _run_login_flow(self, start_url: str) -> str:
        url, html = await self._request("GET", start_url)
        password_sent = False
        federation_clicked = False
        reauthorized = False
        seen: dict[str, int] = {}
        trail: list[str] = []

        for _ in range(MAX_STEPS):
            page = _parse(html)
            host = urlparse(url).netloc
            key = _short(url)
            seen[key] = seen.get(key, 0) + 1
            trail.append(key)
            _LOGGER.debug(
                "Sida: %s | titel=%r | formulär=%d | länkar=%d",
                key, page.title.strip(), len(page.forms), len(page.links),
            )
            if seen[key] > 3:
                raise ItslearningConnectionError(
                    "Inloggningen fastnade i en loop på " + key + ". Steg: " + " → ".join(trail[-8:])
                )

            # 0) Logged in to itslearning but the OAuth context was lost (the
            #    federated login runs "in a new window" for the app). Ask the
            #    authorize endpoint again with the fresh session cookie.
            if password_sent and "itslearning" in host and not page.forms_with_saml() and not reauthorized:
                reauthorized = True
                _LOGGER.debug("→ Inloggad i itslearning, begär OAuth-koden igen")
                url, html = await self._request("GET", start_url)
                continue

            # 1) Login form with a password field -> credentials.
            pw_form = next((f for f in page.forms if f.has_password()), None)
            if pw_form is not None:
                if password_sent:
                    raise ItslearningAuthError("Fel användarnamn eller lösenord")
                data = _form_fields(pw_form)
                for i in pw_form.inputs:
                    if i.get("type") == "password" and i.get("name"):
                        data[i["name"]] = self.password
                    elif i.get("type") in ("text", "email") and i.get("name"):
                        data[i["name"]] = self.username
                submit = next((i for i in pw_form.inputs if i.get("type") == "submit" and i.get("name")), None)
                if submit:
                    data[submit["name"]] = submit.get("value", "")
                password_sent = True
                _LOGGER.debug("→ Skickar användarnamn/lösenord (fält: %s)", ", ".join(data))
                url, html = await self._submit(url, pw_form, data)
                continue

            # 2) SAML / auto-post forms -> post them on.
            saml_form = next((f for f in page.forms if f.is_saml()), None)
            if saml_form is not None:
                _LOGGER.debug("→ Skickar vidare SAML-formulär till %s", _short(urljoin(url, saml_form.action or "")))
                url, html = await self._submit(url, saml_form, _form_fields(saml_form))
                continue

            # 3) itslearning login page -> "Logga in med Skolfederation".
            if "itslearning" in host and not federation_clicked:
                target = self._federation_postback_target(html, page.links)
                if target and page.forms:
                    form = page.forms[0]
                    data = _form_fields(form)
                    data["__EVENTTARGET"] = target
                    data["__EVENTARGUMENT"] = ""
                    federation_clicked = True
                    _LOGGER.debug("→ Klickar 'Logga in med Skolfederation' (%s)", target)
                    url, html = await self._submit(url, form, data)
                    continue

            # 4) IdP choice page -> "Användarnamn och lösenord".
            link = next(
                (h for h, t in page.links if "authmech" in h.lower() and any(k in (h + t).lower() for k in PASSWORD_AUTHMECH_HINTS)),
                None,
            )
            if link:
                _LOGGER.debug("→ Väljer inloggningsmetod: %s", link)
                url, html = await self._request("GET", urljoin(url, link))
                continue

            # 5) Meta refresh.
            if page.meta_refresh:
                url, html = await self._request("GET", urljoin(url, page.meta_refresh))
                continue

            # 6) Single plain form without visible fields (JS auto-submit).
            if "itslearning" not in host and len(page.forms) == 1 and all(i.get("type") in ("hidden", "submit") for i in page.forms[0].inputs):
                f = page.forms[0]
                if f.action or f.inputs:
                    url, html = await self._submit(url, f, _form_fields(f))
                    continue

            _LOGGER.debug("Sidans text: %s", page.visible_text[:400])
            if password_sent:
                raise ItslearningAuthError(
                    f"Inloggningen fastnade på {_short(url)} ({page.title.strip()}): {page.visible_text[:200]}"
                )
            raise ItslearningConnectionError(f"Okänd sida i inloggningsflödet: {host} ({page.title.strip()})")

        raise ItslearningConnectionError("Inloggningsflödet tog för många steg")

    async def _submit(self, page_url: str, form: _Form, data: dict[str, str]) -> tuple[str, str]:
        action = urljoin(page_url, form.action) if form.action else page_url
        self._check_for_code(action)
        if form.method == "post":
            return await self._request("POST", action, data)
        sep = "&" if "?" in action else "?"
        return await self._request("GET", f"{action}{sep}{urlencode(data)}")

    @staticmethod
    def _federation_postback_target(html: str, links: list[tuple[str, str]]) -> str | None:
        # <a href="javascript:__doPostBack(&#39;ctl00$...$federatedLoginButtons$ctl00$ctl00&#39;,&#39;&#39;)">
        #   Logga in med Skolfederation</a>   (quotes are HTML-encoded in the real page)
        pat = re.compile(r"__doPostBack\(\s*['\"]([^'\"]+)['\"]")
        for href, text in links:
            m = pat.search(href)
            if m and FEDERATION_HINT.lower() in text.lower():
                return m.group(1)
        for href, _ in links:
            m = pat.search(href)
            if m and "federatedLoginButtons" in m.group(1):
                return m.group(1)
        m = re.search(r"([\w$]*federatedLoginButtons[\w$]*)", unescape(html))
        return m.group(1) if m else None

    # ---- tokens ----------------------------------------------------------- #
    async def _token_request(self, extra: dict[str, str]) -> Tokens:
        data = {"client_id": CLIENT_ID, **extra}
        try:
            async with self.session.post(f"{self.base_url}/restapi/oauth2/token", data=data) as resp:
                body = await resp.json(content_type=None)
                if resp.status != 200 or "access_token" not in body:
                    raise ItslearningAuthError(f"Token request failed ({resp.status}): {body}")
        except aiohttp.ClientError as err:
            raise ItslearningConnectionError(str(err)) from err
        expires_in = float(body.get("expires_in") or 3600)
        if expires_in > 86400 * 7:  # some versions answer in milliseconds
            expires_in /= 1000
        return Tokens(body["access_token"], body.get("refresh_token") or extra.get("refresh_token", ""), time.time() + expires_in)

    async def ensure_token(self) -> Tokens:
        if self.tokens and self.tokens.valid:
            return self.tokens
        if self.tokens and self.tokens.refresh_token:
            try:
                self.tokens = await self._token_request(
                    {"grant_type": "refresh_token", "refresh_token": self.tokens.refresh_token}
                )
                return self.tokens
            except ItslearningAuthError:
                _LOGGER.info("Refresh token rejected, logging in again")
        return await self.login()

    # ---- API -------------------------------------------------------------- #
    async def _get(self, path: str, params: dict[str, Any] | None = None, _retry: bool = True) -> Any:
        tokens = await self.ensure_token()
        query = {"access_token": tokens.access_token, **(params or {})}
        try:
            async with self.session.get(
                f"{self.base_url}{path}",
                params=query,
                headers={"Authorization": f"Bearer {tokens.access_token}", "Accept": "application/json"},
            ) as resp:
                if resp.status == 401 and _retry:
                    self.tokens.expires_at = 0
                    return await self._get(path, params, _retry=False)
                if resp.status != 200:
                    raise ItslearningConnectionError(f"{path}: HTTP {resp.status}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise ItslearningConnectionError(str(err)) from err

    async def fetch_tasks(self) -> list[Task]:
        data = await self._get("/restapi/personal/tasks/v1/", {"PageIndex": 0, "PageSize": 100})
        return [_task_from_json(t) for t in (data or {}).get("EntityArray", [])]

    async def fetch_unread_notifications(self) -> int:
        data = await self._get("/restapi/personal/notifications/v1/", {"PageIndex": 0, "PageSize": 50})
        return sum(1 for n in (data or {}).get("EntityArray", []) if not n.get("IsRead", True))

    async def fetch_user_name(self) -> str | None:
        try:
            data = await self._get("/restapi/personal/person/v1/")
        except ItslearningError:
            return None
        if isinstance(data, dict):
            name = " ".join(x for x in (data.get("FirstName"), data.get("LastName")) if x)
            return name or None
        return None
