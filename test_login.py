#!/usr/bin/env python3
"""Test the itslearning login outside Home Assistant.

    pip install aiohttp
    python3 test_login.py                 # asks for username/password
    python3 test_login.py --debug         # shows every step of the login flow

Nothing is saved; the password is only sent to itslearning and the
municipality's login service.
"""
import argparse
import asyncio
import getpass
import importlib.util
import logging
import pathlib
import sys

# Load api.py directly so Home Assistant does not need to be installed.
_api_path = pathlib.Path(__file__).parent / "custom_components" / "itslearning" / "api.py"
_spec = importlib.util.spec_from_file_location("itslearning_api", _api_path)
api = importlib.util.module_from_spec(_spec)
sys.modules["itslearning_api"] = api
_spec.loader.exec_module(api)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site", default="https://nassjo.itslearning.com")
    p.add_argument("--username")
    p.add_argument("--debug", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.debug else logging.INFO, format="%(message)s")

    username = a.username or input("Användarnamn: ")
    password = getpass.getpass("Lösenord: ")
    client = api.ItslearningClient(a.site, username, password)
    try:
        await client.login()
        print("✓ Inloggad, token hämtad")
        name = await client.fetch_user_name()
        if name:
            print(f"  Användare: {name}")
        tasks = await client.fetch_tasks()
        print(f"✓ {len(tasks)} uppgifter:")
        for t in sorted(tasks, key=lambda t: (t.deadline is None, t.deadline)):
            dl = t.deadline.astimezone().strftime("%a %d %b %H:%M") if t.deadline else "ingen deadline"
            print(f"  - {dl:20}  {t.title}  [{t.course}]  status={t.status!r}")
        print(f"✓ Olästa notiser: {await client.fetch_unread_notifications()}")
        print("✓ Förnyar token …")
        client.tokens.expires_at = 0
        await client.ensure_token()
        print("✓ Klart, allt fungerar")
        return 0
    except api.ItslearningError as err:
        print(f"✗ {type(err).__name__}: {err}")
        return 1
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
