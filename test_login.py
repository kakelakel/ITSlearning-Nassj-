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


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site", default="https://nassjo.itslearning.com")
    p.add_argument("--username")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--manual", action="store_true", help="logga in själv i webbläsaren och klistra in adressen")
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
