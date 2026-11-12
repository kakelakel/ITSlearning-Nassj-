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
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse

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
APP_REDIRECT_RE = re.compile(re.escape(REDIRECT_URI.split("://")[0]) + r":(?://|\\/\\/)[^'\"\s<>]*")
# Scopes are space separated. First the ones we need, then broader/narrower fallbacks.
SCOPE_CANDIDATES = (
    "Tasks Notifications Person Courses Calendar Planner LightBulletin Assignment",
    "Tasks Notifications Person Courses Calendar",
    "All",
    "Tasks Notifications",
    "Tasks",
    "SCOPE",
)
ALLOW_WORDS = ("tillåt", "godkänn", "acceptera", "allow", "accept", "approve", "authorize", "ja", "yes", "fortsätt", "continue", "ok")
DENY_WORDS = ("neka", "avbryt", "avvisa", "deny", "cancel", "reject", "decline", "nej")
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
        self._button: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "form":
            self._form = _Form(a.get("action"), (a.get("method") or "get").lower())
            self.forms.append(self._form)
        elif tag == "button" and self._form is not None:
            self._button = {"name": a.get("name", ""), "type": (a.get("type") or "submit").lower(),
                            "value": a.get("value", ""), "label": "", "onclick": a.get("onclick", ""), "tag": "button"}
            self._form.inputs.append(self._button)
        elif tag in ("input", "select", "textarea") and self._form is not None:
            if tag == "input" or a.get("name"):
                self._form.inputs.append(
                    {"name": a.get("name", ""), "type": a.get("type", "text").lower(), "value": a.get("value", ""),
                     "label": a.get("value", ""), "onclick": a.get("onclick", ""),
                     "checked": "1" if ("checked" in a or "selected" in a) else "", "tag": tag}
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
        elif tag == "button":
            self._button = None
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
        if self._button is not None:
            self._button["label"] = (self._button["label"] + " " + data.strip()).strip()
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
            if i.get("checked"):
                data[name] = i.get("value") or "on"
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


# Swedish subject names for itslearning course codes ("BR7E/SV" -> "Svenska").
SUBJECTS = {
    "BI": "Biologi", "BL": "Bild", "FY": "Fysik", "GE": "Geografi", "HI": "Historia",
    "HKK": "Hem- och konsumentkunskap", "IDH": "Idrott och hälsa", "KE": "Kemi",
    "MA": "Matematik", "MU": "Musik", "RE": "Religion", "SH": "Samhällskunskap",
    "SL": "Slöjd", "SLTX": "Textilslöjd", "SLTR": "Trä- och metallslöjd", "SO": "SO", "NO": "NO",
    "SV": "Svenska", "SVA": "Svenska som andraspråk", "TEMA": "Tema", "TK": "Teknik",
    "EN": "Engelska", "DEU": "Tyska", "FRA": "Franska", "SPA": "Spanska", "M2DEU": "Tyska",
    "M2FRA": "Franska", "M2SPA": "Spanska", "M-TID": "Mentorstid", "MENTOR": "Mentorstid",
    "ML": "Modersmål", "SPRÅK": "Språkval", "ELEVENS VAL": "Elevens val",
}


def subject_name(title: str | None, code: str | None = None) -> str:
    """Readable subject for a course title like 'BR7E/SV', 'M2DEU/BR7' or 'BR7E/HKK-1'."""
    title = (title or "").strip()
    candidates = []
    if code:
        candidates.append(code)
    for part in title.replace("\\", "/").split("/"):
        candidates.append(part)
        candidates.append(re.sub(r"[-_ ]?\d+$", "", part))
    for c in candidates:
        key = c.strip().upper()
        if key in SUBJECTS:
            return SUBJECTS[key]
    return title


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", html)
    t = re.sub(r"(?i)<li[^>]*>", "• ", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = unescape(t).replace("\xa0", " ")
    lines = [" ".join(line.split()) for line in t.splitlines()]
    return "\n".join(line for line in lines if line).strip()


@dataclass
class Task:
    id: int
    title: str
    course: str
    status: str
    deadline: datetime | None
    url: str
    element_type: str
    homework: bool = False
    description: str = ""
    color: str = ""

    @property
    def completed(self) -> bool:
        return self.status.replace(" ", "").lower() in COMPLETED_STATUSES

    @property
    def subject(self) -> str:
        return subject_name(self.course)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "course": self.course,
            "subject": self.subject,
            "status": self.status,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "url": self.url,
            "type": self.element_type,
            "homework": self.homework,
            "color": self.color,
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


@dataclass
class CalendarItem:
    """An itslearning calendar event: homework check, test, school event …"""

    id: str
    title: str
    start: datetime
    end: datetime
    course: str
    location: str
    description: str
    url: str
    kind: str
    all_day: bool = False
    color: str = ""

    @property
    def subject(self) -> str:
        return subject_name(self.course) if self.course else ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "all_day": self.all_day,
            "course": self.course,
            "subject": self.subject,
            "location": self.location,
            "description": self.description[:300],
            "kind": self.kind,
            "url": self.url,
            "color": self.color,
        }


@dataclass
class Plan:
    """A lesson plan / weekly plan from a course (where teachers put homework)."""

    id: int
    name: str
    description: str
    start: datetime
    stop: datetime
    course: str
    course_id: int
    url: str = ""
    color: str = ""

    @property
    def subject(self) -> str:
        return subject_name(self.course)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description[:500],
            "start": self.start.isoformat(),
            "stop": self.stop.isoformat(),
            "course": self.course,
            "subject": self.subject,
            "url": self.url,
            "color": self.color,
        }


@dataclass
class News:
    id: int
    text: str
    course: str
    published: datetime | None
    author: str
    url: str
    color: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text[:200],
            "course": self.course,
            "subject": subject_name(self.course) if self.course else "",
            "published": self.published.isoformat() if self.published else None,
            "author": self.author,
            "url": self.url,
            "color": self.color,
        }


@dataclass
class Course:
    id: int
    title: str
    code: str
    url: str
    new_notifications: int = 0
    color: str = ""

    @property
    def subject(self) -> str:
        return subject_name(self.title, self.code)


def _first(j: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = j.get(k)
        if v not in (None, ""):
            return v
    return None


def _event_from_json(j: dict[str, Any]) -> CalendarItem | None:
    start = parse_datetime(_first(j, "FromDate", "StartDate", "Start", "FromDateUtc", "StartDateUtc", "EventDate"))
    if start is None:
        return None
    end = parse_datetime(_first(j, "ToDate", "EndDate", "End", "ToDateUtc", "EndDateUtc")) or start
    all_day = bool(_first(j, "IsAllDay", "AllDay", "IsFullDay") or False)
    # Teachers often enter "the whole school day" (e.g. 08:00–16:00) for homework.
    if not all_day and end - start >= timedelta(hours=6):
        all_day = True
    if end <= start:
        end = start + (timedelta(days=1) if all_day else timedelta(minutes=30))
    course = _first(j, "LocationTitle", "CourseTitle", "CourseName", "Course", "ContextTitle") or ""
    if isinstance(course, dict):
        course = course.get("Title") or ""
    return CalendarItem(
        id=str(_first(j, "EventId", "CalendarEventId", "Id", "ElementId") or f"{start.isoformat()}-{j.get('Title')}"),
        title=str(_first(j, "EventTitle", "Title", "Name", "Subject") or "Händelse"),
        start=start,
        end=end,
        course=str(course),
        location=str(_first(j, "Location", "Room", "Place") or ""),
        description=html_to_text(str(_first(j, "Description", "Text") or "")),
        url=str(_first(j, "Url", "ContentUrl") or ""),
        kind=str(_first(j, "EventType", "Type", "ElementType") or ""),
        all_day=all_day,
        color=str(_first(j, "LocationColor", "CourseColor", "Color") or ""),
    )


def _task_from_json(j: dict[str, Any]) -> Task:
    return Task(
        id=int(j.get("TaskId") or j.get("ElementId") or 0),
        title=str(j.get("Title") or ""),
        course=str(j.get("LocationTitle") or j.get("CourseTitle") or ""),
        status=str(j.get("Status") or ""),
        deadline=parse_datetime(j.get("Deadline") or j.get("DeadlineUtc")),
        url=str(j.get("Url") or ""),
        element_type=str(j.get("ElementType") or ""),
        homework=bool(j.get("Homework")),
        description=html_to_text(j.get("Description")),
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
        self._state = secrets.token_hex(8)
        self.dump_dir: str | None = None  # test_login.py sets this to save the consent page

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

    async def _request(
        self, method: str, url: str, data: dict[str, str] | None = None, referer: str | None = None
    ) -> tuple[str, str]:
        """Do a request and follow redirects by hand.

        Returns (final_url, html). Raises _CodeReceived when itslearning
        redirects to the app's custom scheme.
        """
        for _ in range(MAX_STEPS):
            try:
                headers = {}
                if referer:
                    rp = urlparse(referer)
                    headers["Referer"] = referer
                    if method == "POST":
                        headers["Origin"] = f"{rp.scheme}://{rp.netloc}"
                async with self.session.request(
                    method, self._url(url), data=data, allow_redirects=False, headers=headers
                ) as resp:
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
                    # itslearning hands the code over with JavaScript:
                    #   top.location.replace('itsl-itslearning://login/?state=…&code=…')
                    for m in APP_REDIRECT_RE.finditer(text):
                        target = unescape(m.group(0)).replace("\\/", "/")
                        if re.search(r"[?&](code|error)=", target):
                            _LOGGER.debug("→ Hittade app-koden i sidans JavaScript")
                            self._check_for_code(target)
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
    def manual_authorize_url(self, scope: str | None = None) -> str:
        """URL for logging in by hand in a normal browser (manual fallback)."""
        return self._authorize_url(scope or SCOPE_CANDIDATES[0])

    async def exchange_code(self, code_or_url: str) -> Tokens:
        """Exchange a code (or the whole itsl-itslearning://login?code=… address)."""
        text = code_or_url.strip().strip('"').strip("'")
        m = re.search(r"[?&]code=([^&\s#]+)", text)
        code = unquote(m.group(1)) if m else text
        if not code:
            raise ItslearningAuthError("Ingen kod hittades")
        self.tokens = await self._token_request({"grant_type": "authorization_code", "code": code})
        return self.tokens

    async def login(self) -> Tokens:
        """Full browser-like login. Use sparingly; refresh tokens are preferred."""
        self.session.cookie_jar.clear()
        self._state = secrets.token_hex(8)
        try:
            code = await self._run_login_flow(self._authorize_url(SCOPE_CANDIDATES[0]))
        except _CodeReceived as rec:
            code = rec.code
        self.tokens = await self._token_request({"grant_type": "authorization_code", "code": code})
        return self.tokens

    def _authorize_url(self, scope: str) -> str:
        params = {
            "client_id": CLIENT_ID,
            "state": self._state,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": scope,
        }
        return f"{self.base_url}/oauth2/authorize.aspx?{urlencode(params, quote_via=quote)}"

    async def _run_login_flow(self, start_url: str) -> str:
        url, html = await self._request("GET", start_url)
        scope_idx = 0
        consent_posted_for: int | None = None
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
                url, html = await self._request("GET", self._authorize_url(SCOPE_CANDIDATES[scope_idx]))
                continue

            # 0b) OAuth consent page ("Den här appen vill få åtkomst …") -> allow.
            if "itslearning" in host and "/oauth2/authorize" in url.lower() and page.forms:
                _LOGGER.debug("Sidans text: %s", page.visible_text[:300])
                if consent_posted_for == scope_idx:
                    # Same page again: itslearning did not accept this scope set.
                    if scope_idx == 0:
                        self._dump("consent_after_click", html)
                    scope_idx += 1
                    if scope_idx >= len(SCOPE_CANDIDATES):
                        raise ItslearningAuthError(
                            "itslearning godkände inte app-åtkomsten. Sidans text: " + page.visible_text[:200]
                        )
                    _LOGGER.debug("→ Provar scope %r", SCOPE_CANDIDATES[scope_idx])
                    seen.pop(key, None)
                    url, html = await self._request("GET", self._authorize_url(SCOPE_CANDIDATES[scope_idx]))
                    continue
                consent_posted_for = scope_idx
                self._dump("consent", html)
                _LOGGER.debug("Scope: %r", SCOPE_CANDIDATES[scope_idx])
                url, html = await self._approve_consent(url, html, page)
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

    def _dump(self, name: str, html: str) -> None:
        if not self.dump_dir:
            return
        import os
        clean = re.sub(r'(name="(?:__VIEWSTATE|__EVENTVALIDATION|SAMLResponse|SAMLRequest)"[^>]*value=")[^"]*', r"\1(borttaget)", html)
        clean = re.sub(r'(value=")[^"]*("[^>]*name="(?:__VIEWSTATE|__EVENTVALIDATION)")', r"\1(borttaget)\2", clean)
        clean = re.sub(r"(code=)[^&'\"\s]+", r"\1(borttaget)", clean)
        path = os.path.join(self.dump_dir, f"itslearning_{name}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(clean)
        _LOGGER.info("Sparade sidan till %s", path)

    async def _approve_consent(self, url: str, html: str, page: _PageParser) -> tuple[str, str]:
        form = page.forms[0]
        controls = [i for i in form.inputs if i.get("type") in ("submit", "button", "image")]
        labels = [f"{c.get('name')}={c.get('label') or c.get('value')}" for c in controls]
        _LOGGER.debug("Godkännandesida, knappar: %s | länkar: %s", labels, [t for _, t in page.links])
        _LOGGER.debug(
            "Formulär: action=%s method=%s fält=%s",
            form.action, form.method,
            [
                f"{i.get('tag', 'input')}:{i.get('type')}:{i.get('name')}"
                + (":checked" if i.get("checked") else "")
                + (f":onclick={i.get('onclick')[:120]}" if i.get("onclick") else "")
                + ("" if i.get("name", "").startswith("__") or i.get("type") == "password" else f"={i.get('value', '')[:40]}")
                for i in form.inputs
            ],
        )
        for m in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.S | re.I):
            if "SaveOrCancel" in m.group(1) or "oauth" in m.group(1).lower():
                _LOGGER.debug("Skript: %s", " ".join(m.group(1).split())[:400])

        def has(words: tuple[str, ...], text: str) -> bool:
            words_in = re.findall(r"[a-zåäö]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower())
            return any(w in words_in or (len(w) > 4 and any(x.startswith(w) for x in words_in)) for w in words)

        def is_allow(text: str) -> bool:
            return has(ALLOW_WORDS, text) and not has(DENY_WORDS, text)

        data = _form_fields(form)

        def text_of(c: dict[str, str]) -> str:
            return f"{c.get('label', '')} {c.get('value', '')}"

        # 1) A button whose visible text says allow.
        choice = next((c for c in controls if is_allow(text_of(c))), None)
        # 2) itslearning's SaveOrCancel control: "$SB" is the save button.
        if choice is None:
            choice = next(
                (c for c in controls if re.search(r"(\$SB|SaveButton|AllowButton|AcceptButton)$", c.get("name", ""))),
                None,
            )
        # 3) The only button whose text does not say deny.
        if choice is None:
            non_deny = [c for c in controls if not has(DENY_WORDS, text_of(c))]
            if len(non_deny) == 1:
                choice = non_deny[0]
        if choice is not None:
            onclick = choice.get("onclick", "")
            pb = re.search(r"(?:__doPostBack|WebForm_PostBackOptions)\(\s*['\"]([^'\"]+)['\"]", onclick)
            if pb and "WebForm_PostBackOptions" not in onclick:
                data["__EVENTTARGET"], data["__EVENTARGUMENT"] = pb.group(1), ""
            if choice.get("name"):
                data[choice["name"]] = choice.get("value", "")
            _LOGGER.debug("→ Godkänner app-åtkomst (%s)", choice.get("label") or choice.get("value") or choice.get("name"))
            return await self._submit(url, form, data)
        for href, text in page.links:
            pb = re.search(r"__doPostBack\(\s*['\"]([^'\"]+)['\"]", href)
            if pb and is_allow(text):
                data["__EVENTTARGET"], data["__EVENTARGUMENT"] = pb.group(1), ""
                _LOGGER.debug("→ Godkänner app-åtkomst (länk %s)", text)
                return await self._submit(url, form, data)
        raise ItslearningAuthError(f"Hittade ingen Tillåt-knapp på godkännandesidan. Knappar: {labels}")

    async def _submit(self, page_url: str, form: _Form, data: dict[str, str]) -> tuple[str, str]:
        action = urljoin(page_url, form.action) if form.action else page_url
        self._check_for_code(action)
        if form.method == "post":
            return await self._request("POST", action, data, referer=page_url)
        sep = "&" if "?" in action else "?"
        return await self._request("GET", f"{action}{sep}{urlencode(data)}", referer=page_url)

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

    async def raw(self, method: str, path: str, params: dict[str, Any] | None = None) -> tuple[int, Any]:
        """Unparsed API call, used by test_login.py --explore."""
        tokens = await self.ensure_token()
        query = {"access_token": tokens.access_token, **(params or {})}
        async with self.session.request(
            method, f"{self.base_url}{path}", params=query,
            headers={"Authorization": f"Bearer {tokens.access_token}", "Accept": "application/json"},
        ) as resp:
            try:
                body = await resp.json(content_type=None)
            except Exception:  # noqa: BLE001
                body = (await resp.text())[:200]
            return resp.status, body

    async def fetch_tasks(self) -> list[Task]:
        data = await self._get("/restapi/personal/tasks/v1/", {"PageIndex": 0, "PageSize": 100})
        return [_task_from_json(t) for t in (data or {}).get("EntityArray", [])]

    async def fetch_unread_notifications(self) -> int:
        data = await self._get("/restapi/personal/notifications/v1/", {"PageIndex": 0, "PageSize": 50})
        return sum(1 for n in (data or {}).get("EntityArray", []) if not n.get("IsRead", True))

    async def fetch_courses(self) -> list[Course]:
        data = await self._get("/restapi/personal/courses/v1/", {"PageIndex": 0, "PageSize": 100})
        return [
            Course(
                id=int(c["CourseId"]), title=str(c.get("Title") or ""), code=str(c.get("CourseCode") or ""),
                url=str(c.get("Url") or ""), new_notifications=int(c.get("NewNotificationsCount") or 0),
                color=str(c.get("CourseColor") or ""),
            )
            for c in (data or {}).get("EntityArray", [])
            if c.get("CourseId") is not None
        ]

    async def fetch_plans(self, courses: list[Course], days_back: int = 7, days_ahead: int = 21) -> list[Plan]:
        """Lesson/weekly plans for all courses in a date window."""
        import asyncio

        today = datetime.now(timezone.utc).date()
        params = {
            "startDate": (today - timedelta(days=days_back)).isoformat(),
            "stopDate": (today + timedelta(days=days_ahead)).isoformat(),
        }
        sem = asyncio.Semaphore(4)

        async def one(course: Course) -> list[Plan]:
            async with sem:
                try:
                    data = await self._get("/restapi/personal/planner/v1", {"courseId": course.id, **params})
                except ItslearningError as err:
                    _LOGGER.debug("Planer för %s gick inte att hämta: %s", course.title, err)
                    return []
            rows = data.get("EntityArray", []) if isinstance(data, dict) else (data or [])
            out = []
            for r in rows:
                start = parse_datetime(r.get("Start"))
                stop = parse_datetime(r.get("Stop")) or start
                if start is None:
                    continue
                out.append(Plan(
                    id=int(r.get("PlanId") or 0), name=str(r.get("PlanName") or "Planering"),
                    description=html_to_text(r.get("PlanDescription")), start=start, stop=max(stop, start),
                    course=course.title, course_id=course.id, url=course.url, color=course.color,
                ))
            return out

        results = await asyncio.gather(*(one(c) for c in courses))
        return sorted((p for r in results for p in r), key=lambda p: (p.start, p.course))

    async def fetch_news(self, count: int = 15) -> list[News]:
        data = await self._get("/restapi/personal/notifications/stream/v1/", {"PageIndex": 0, "PageSize": count})
        out = []
        for n in (data or {}).get("EntityArray", []):
            by = n.get("PublishedBy") or {}
            lb = n.get("LightBulletin") or {}
            text = html_to_text(lb.get("Text")) if isinstance(lb, dict) and lb.get("Text") else html_to_text(n.get("Text"))
            out.append(News(
                id=int(n.get("NotificationId") or 0), text=text, course=str(n.get("LocationTitle") or ""),
                published=parse_datetime(n.get("PublishedDate")),
                author=str(by.get("FullName") or " ".join(x for x in (by.get("FirstName"), by.get("LastName")) if x)),
                url=str(n.get("Url") or ""),
            ))
        return out

    async def fetch_calendar(self, days_back: int = 7, days_ahead: int = 28) -> list[CalendarItem]:
        """Calendar events (lessons, tests, school events) around today."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days_back)
        stop = now + timedelta(days=days_ahead)
        items: list[CalendarItem] = []
        for page in range(10):
            data = await self._get(
                "/restapi/personal/calendar/events/v1",
                {
                    "fromDate": start.strftime("%Y-%m-%dT00:00:00"),
                    "toDate": stop.strftime("%Y-%m-%dT23:59:59"),
                    "PageIndex": page,
                    "PageSize": 100,
                },
            )
            rows = (data or {}).get("EntityArray", []) if isinstance(data, dict) else (data or [])
            if page == 0 and rows:
                _LOGGER.debug("Kalenderfält: %s", sorted(rows[0].keys()))
            for row in rows:
                item = _event_from_json(row)
                if item is None:
                    _LOGGER.debug("Kalenderhändelse utan känt datumfält: %s", sorted(row.keys()))
                elif item.start < stop:
                    items.append(item)
            total = (data or {}).get("Total") if isinstance(data, dict) else None
            if not rows or len(rows) < 100 or (total is not None and (page + 1) * 100 >= total):
                break
            if rows and (last := _event_from_json(rows[-1])) and last.start >= stop:
                break
        return sorted(items, key=lambda i: i.start)

    async def fetch_user_name(self) -> str | None:
        try:
            data = await self._get("/restapi/personal/person/v1/")
        except ItslearningError:
            return None
        if isinstance(data, dict):
            name = " ".join(x for x in (data.get("FirstName"), data.get("LastName")) if x)
            return name or None
        return None
