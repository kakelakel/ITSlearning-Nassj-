"""Config flow for itslearning."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .api import ItslearningAuthError, ItslearningClient, ItslearningConnectionError, Tokens
from .const import CONF_SITE_URL, CONF_TOKENS, DEFAULT_SITE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _validate(site_url: str, username: str, password: str) -> tuple[Tokens, str | None]:
    client = ItslearningClient(site_url, username, password)
    try:
        tokens = await client.login()
        name = await client.fetch_user_name()
        return tokens, name
    finally:
        await client.close()


class ItslearningConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            site = user_input[CONF_SITE_URL].strip().rstrip("/")
            if not site.startswith("http"):
                site = f"https://{site}"
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(f"{site}|{username.lower()}")
            self._abort_if_unique_id_configured()
            try:
                tokens, name = await _validate(site, username, user_input[CONF_PASSWORD])
            except ItslearningAuthError as err:
                _LOGGER.warning("itslearning login failed: %s", err)
                errors["base"] = "invalid_auth"
            except ItslearningConnectionError as err:
                _LOGGER.warning("itslearning connection failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during itslearning login")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=name or username,
                    data={
                        CONF_SITE_URL: site,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_TOKENS: tokens.as_dict(),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_SITE_URL, default=(user_input or {}).get(CONF_SITE_URL, DEFAULT_SITE_URL)): str,
                vol.Required(CONF_USERNAME, default=(user_input or {}).get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                tokens, _ = await _validate(entry.data[CONF_SITE_URL], entry.data[CONF_USERNAME], user_input[CONF_PASSWORD])
            except ItslearningAuthError:
                errors["base"] = "invalid_auth"
            except ItslearningConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during itslearning reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD], CONF_TOKENS: tokens.as_dict()},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )
