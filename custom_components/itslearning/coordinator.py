"""Data update coordinator for itslearning."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ItslearningAuthError, ItslearningClient, ItslearningError, Task
from .const import CONF_TOKENS, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class ItslearningData:
    tasks: list[Task]
    unread_notifications: int | None


class ItslearningCoordinator(DataUpdateCoordinator[ItslearningData]):
    """Polls itslearning and keeps tokens saved in the config entry."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: ItslearningClient) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL, config_entry=entry)
        self.client = client

    async def _async_update_data(self) -> ItslearningData:
        old_refresh = self.client.tokens.refresh_token if self.client.tokens else None
        try:
            tasks = await self.client.fetch_tasks()
            try:
                unread = await self.client.fetch_unread_notifications()
            except ItslearningError as err:
                _LOGGER.debug("Could not fetch notifications: %s", err)
                unread = None
        except ItslearningAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ItslearningError as err:
            raise UpdateFailed(str(err)) from err

        # Persist new tokens so a restart does not need a full login.
        if self.client.tokens and self.client.tokens.refresh_token != old_refresh:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_TOKENS: self.client.tokens.as_dict()},
            )
        return ItslearningData(tasks=tasks, unread_notifications=unread)
