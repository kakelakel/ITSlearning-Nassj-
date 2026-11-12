"""Data update coordinator for itslearning."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CalendarItem, Course, ItslearningAuthError, ItslearningClient, ItslearningError, News, Plan, Task
from .const import CONF_TOKENS, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
COURSES_TTL = 6 * 3600


@dataclass
class ItslearningData:
    tasks: list[Task]
    unread_notifications: int | None
    events: list[CalendarItem] = field(default_factory=list)
    plans: list[Plan] = field(default_factory=list)
    news: list[News] = field(default_factory=list)
    courses: list[Course] = field(default_factory=list)


class ItslearningCoordinator(DataUpdateCoordinator[ItslearningData]):
    """Polls itslearning and keeps tokens saved in the config entry."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: ItslearningClient) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL, config_entry=entry)
        self.client = client
        self._courses: list[Course] = []
        self._courses_at = 0.0

    async def _optional(self, label: str, coro, fallback):
        try:
            return await coro
        except ItslearningAuthError:
            raise
        except ItslearningError as err:
            _LOGGER.warning("itslearning: %s gick inte att hämta: %s", label, err)
            return fallback

    async def _async_update_data(self) -> ItslearningData:
        old_refresh = self.client.tokens.refresh_token if self.client.tokens else None
        prev = self.data
        try:
            tasks = await self.client.fetch_tasks()
            if not self._courses or time.monotonic() - self._courses_at > COURSES_TTL:
                self._courses = await self._optional("kurser", self.client.fetch_courses(), self._courses)
                self._courses_at = time.monotonic()
            unread = await self._optional("notiser", self.client.fetch_unread_notifications(), None)
            events = await self._optional("kalendern", self.client.fetch_calendar(), prev.events if prev else [])
            plans = await self._optional("planer", self.client.fetch_plans(self._courses), prev.plans if prev else [])
            news = await self._optional("nyheter", self.client.fetch_news(), prev.news if prev else [])
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
        return ItslearningData(
            tasks=tasks, unread_notifications=unread, events=events, plans=plans, news=news, courses=self._courses
        )
