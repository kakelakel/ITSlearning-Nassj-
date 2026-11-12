"""Calendar with itslearning deadlines."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ItslearningConfigEntry
from .api import Task
from .entity import ItslearningEntity

EVENT_LENGTH = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ItslearningConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ItslearningCalendar(entry.runtime_data)])


def _event(task: Task) -> CalendarEvent:
    end = task.deadline
    summary = f"{task.title} ({task.course})" if task.course else task.title
    description = f"Status: {task.status or 'okänd'}"
    if task.url:
        description += f"\n{task.url}"
    return CalendarEvent(start=end - EVENT_LENGTH, end=end, summary=summary, description=description, uid=str(task.id))


class ItslearningCalendar(ItslearningEntity, CalendarEntity):
    """Each task deadline is a 30 minute event ending at the deadline."""

    _attr_translation_key = "deadlines"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "deadlines")

    def _events(self) -> list[CalendarEvent]:
        return sorted(
            (_event(t) for t in self.coordinator.data.tasks if t.deadline and not t.completed),
            key=lambda e: e.start,
        )

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.utcnow()
        return next((e for e in self._events() if e.end >= now), None)

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return [e for e in self._events() if e.end > start_date and e.start < end_date]
