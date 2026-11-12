#!/usr/bin/env python3
"""Test the itslearning login outside Home Assistant.

    pip install aiohttp
    python3 test_login.py                 # automatic login (asks for username/password)
    python3 test_login.py --debug         # shows every step and saves the consent page
    python3 test_login.py --manual        # log in yourself in a browser, paste the address

Nothing is saved except the HTML files written with --debug (without session data).
"""
import argparse
import asyncio
import getpass
import importlib.util
import logging
import os
import pathlib
import sys

# Load api.py directly so Home Assistant does not need to be installed.
_api_path = pathlib.Path(__file__).parent / "custom_components" / "itslearning" / "api.py"
_spec = importlib.util.spec_from_file_location("itslearning_api", _api_path)
api = importlib.util.module_from_spec(_spec)
sys.modules["itslearning_api"] = api
_spec.loader.exec_module(api)

MANUAL_HELP = """
Manuell inloggning
------------------
1. Öppna Chrome eller Edge och tryck F12 → fliken "Network" (Nätverk).
   Kryssa i "Preserve log".
2. Klistra in den här adressen i adressfältet och logga in med Skolfederation:

{url}

3. Tryck på knappen på sidan "Den här appen vill få åtkomst till itslearning".
4. Webbläsaren försöker öppna en adress som börjar med itsl-itslearning://login?code=…
   (kanske med en fråga om att öppna en app – tryck Avbryt).
   Hittar du den inte: leta i Network-fliken efter raden "authorize.aspx" med
   status 302 och kopiera "Location" under Response Headers.
5. Klistra in hela adressen (eller bara koden) här nedan. Koden gäller bara
   några minuter, så gör det direkt.
"""


async def show(client) -> None:
    name = await client.fetch_user_name()
    if name:
        print(f"  Användare: {name}")
    tasks = await client.fetch_tasks()
    print(f"✓ {len(tasks)} uppgifter:")
    for t in sorted(tasks, key=lambda t: (t.deadline is None, t.deadline)):
        dl = t.deadline.astimezone().strftime("%a %d %b %H:%M") if t.deadline else "ingen deadline"
        print(f"  - {dl:20}  {t.title}  [{t.course}]  status={t.status!r}")
    try:
        events = await client.fetch_calendar(days_back=0, days_ahead=7)
        print(f"✓ {len(events)} kalenderhändelser kommande 7 dagar:")
        for e in events[:25]:
            when = e.start.astimezone().strftime("%a %d %b %H:%M") + "–" + e.end.astimezone().strftime("%H:%M")
            print(f"  - {when:24}  {e.title}  [{e.course}]  {e.location}  typ={e.kind!r}")
        if not events:
            print("  (inga – kör med --debug och skicka raden 'Kalenderfält' om schemat borde synas)")
    except api.ItslearningError as err:
        print(f"  (kalendern gick inte att hämta: {err})")
    try:
        print(f"✓ Olästa notiser: {await client.fetch_unread_notifications()}")
    except api.ItslearningError as err:
        print(f"  (notiser gick inte att hämta: {err})")
    print("✓ Förnyar token …")
    client.tokens.expires_at = 0
    await client.ensure_token()
    print("✓ Klart, allt fungerar")


def _compact(v, depth=0):
    """Short preview of an API value (long texts cut, nested objects summarised)."""
    if isinstance(v, str):
        v = " ".join(v.split())
        return v if len(v) <= 50 else v[:47] + "…"
    if isinstance(v, dict):
        if depth >= 1:
            return "{" + ",".join(list(v)[:6]) + ("…" if len(v) > 6 else "") + "}"
        return {k: _compact(x, depth + 1) for k, x in v.items()}
    if isinstance(v, list):
        return f"[{len(v)} st]" if depth else [_compact(x, depth + 1) for x in v[:3]]
    return v


def _rows(body):
    if isinstance(body, dict):
        for k in ("EntityArray", "Items", "Data", "Plans", "Result"):
            if isinstance(body.get(k), list):
                return body[k], body.get("Total")
        return [body], None
    if isinstance(body, list):
        return body, len(body)
    return [], None


async def explore(client) -> None:
    import json
    from datetime import date, timedelta

    d0 = date.today() - timedelta(days=7)
    d1 = date.today() + timedelta(days=14)
    ds = lambda d: d.isoformat()

    async def probe(label, method, path, params=None, show=2):
        try:
            status, body = await client.raw(method, path, params)
        except Exception as err:  # noqa: BLE001
            print(f"\n## {label}\n  FEL: {err}")
            return []
        rows, total = _rows(body) if status == 200 else ([], None)
        print(f"\n## {label}\n  {method} {path} → HTTP {status}, {len(rows)} rader" + (f" (totalt {total})" if total is not None else ""))
        if status != 200:
            print("  " + str(_compact(body))[:300])
        elif rows:
            print("  fält: " + ", ".join(sorted(rows[0].keys())) if isinstance(rows[0], dict) else "")
            for r in rows[:show]:
                print("  " + json.dumps(_compact(r), ensure_ascii=False)[:700])
        return rows

    print("\n================ UTFORSKAR API:ET ================")
    await probe("Uppgifter (personal/tasks)", "GET", "/restapi/personal/tasks/v1/", {"PageIndex": 0, "PageSize": 100}, show=2)
    await probe("Kalender", "GET", "/restapi/personal/calendar/events/v1",
                {"fromDate": ds(d0), "toDate": ds(d1), "PageIndex": 0, "PageSize": 100}, show=3)
    await probe("Kalender (bara fromDate)", "GET", "/restapi/personal/calendar/events/v1",
                {"fromDate": ds(d0), "PageIndex": 0, "PageSize": 100}, show=1)
    courses = await probe("Kurser", "GET", "/restapi/personal/courses/v1/", {"PageIndex": 0, "PageSize": 100}, show=1)
    await probe("Aktiva planer", "POST", "/restapi/personal/courses/activeplans/v1",
                {"startDate": ds(d0), "endDate": ds(d1)}, show=2)
    await probe("Nyheter/flöde", "GET", "/restapi/personal/notifications/stream/v1/", {"PageIndex": 0, "PageSize": 5}, show=2)

    print("\n## Per kurs (planer / uppgifter / kalender)")
    samples = {}
    for c in courses[:25]:
        cid = c.get("CourseId")
        if cid is None:
            continue
        counts = []
        for key, path, params in (
            ("planer", "/restapi/personal/planner/v1", {"courseId": cid, "startDate": ds(d0), "stopDate": ds(d1)}),
            ("uppgifter", f"/restapi/personal/courses/{cid}/tasks/v1", {"PageIndex": 0, "PageSize": 50}),
            ("kalender", f"/restapi/personal/courses/{cid}/calendarevents/v1",
             {"fromDate": ds(d0), "toDate": ds(d1), "PageIndex": 0, "PageSize": 50}),
        ):
            try:
                status, body = await client.raw("GET", path, params)
            except Exception:  # noqa: BLE001
                counts.append(f"{key}=fel")
                continue
            rows, _ = _rows(body) if status == 200 else ([], None)
            counts.append(f"{key}={len(rows)}" if status == 200 else f"{key}=HTTP{status}")
            if rows and key not in samples:
                samples[key] = (c.get("Title"), rows)
        print(f"  {str(c.get('Title'))[:30]:30}  " + "  ".join(counts))
    for key, (title, rows) in samples.items():
        print(f"\n## Exempel {key} ({title})\n  fält: " + ", ".join(sorted(rows[0].keys())))
        for r in rows[:2]:
            print("  " + json.dumps(_compact(r), ensure_ascii=False)[:700])
    print("\n================ SLUT ================")


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site", default="https://nassjo.itslearning.com")
    p.add_argument("--username")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--manual", action="store_true", help="logga in själv i webbläsaren och klistra in adressen")
    p.add_argument("--explore", action="store_true", help="visa vad itslearnings API innehåller (kalender, planer …)")
    a = p.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.debug else logging.INFO, format="%(message)s")

    if a.manual:
        client = api.ItslearningClient(a.site, "", "")
        print(MANUAL_HELP.format(url=client.manual_authorize_url()))
        pasted = input("Adress eller kod: ")
        try:
            await client.exchange_code(pasted)
            print("✓ Token hämtad")
            await show(client)
            return 0
        except api.ItslearningError as err:
            print(f"✗ {type(err).__name__}: {err}")
            return 1
        finally:
            await client.close()

    username = a.username or input("Användarnamn: ")
    password = getpass.getpass("Lösenord: ")
    client = api.ItslearningClient(a.site, username, password)
    if a.debug:
        client.dump_dir = os.getcwd()
    try:
        await client.login()
        print("✓ Inloggad, token hämtad")
        if a.explore:
            await explore(client)
            return 0
        await show(client)
        return 0
    except api.ItslearningError as err:
        print(f"✗ {type(err).__name__}: {err}")
        if a.debug:
            print("\nSkicka gärna filerna itslearning_consent.html och itslearning_consent_after_click.html")
            print("(de ligger i den här mappen och innehåller inga lösenord eller sessionsdata).")
        return 1
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
