"""Calendars: homework deadlines and the school schedule."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ItslearningConfigEntry
from .api import CalendarItem, Task
from .coordinator import ItslearningData
from .entity import ItslearningEntity

DEADLINE_LENGTH = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ItslearningConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    async_add_entities([DeadlineCalendar(c), ScheduleCalendar(c)])


def deadline_event(task: Task) -> CalendarEvent:
    summary = f"📚 {task.title} ({task.course})" if task.course else f"📚 {task.title}"
    description = f"Status: {task.status or 'okänd'}"
    if task.url:
        description += f"\n{task.url}"
    return CalendarEvent(
        start=task.deadline - DEADLINE_LENGTH, end=task.deadline,
        summary=summary, description=description, uid=f"itsl-task-{task.id}",
    )


def schedule_event(item: CalendarItem) -> CalendarEvent:
    summary = item.title
    if item.course and item.course.lower() not in item.title.lower():
        summary = f"{item.title} ({item.course})"
    if item.all_day:
        start, end = dt_util.as_local(item.start).date(), dt_util.as_local(item.end).date()
        if end <= start:
            end = start + timedelta(days=1)
    else:
        start, end = item.start, item.end
    description = item.description
    if item.url:
        description = f"{description}\n{item.url}".strip()
    return CalendarEvent(
        start=start, end=end, summary=summary, description=description or None,
        location=item.location or None, uid=f"itsl-event-{item.id}",
    )


def _overlaps(e: CalendarEvent, start: datetime, end: datetime) -> bool:
    return e.end_datetime_local > start and e.start_datetime_local < end


class _BaseCalendar(ItslearningEntity, CalendarEntity):
    def _events(self, data: ItslearningData) -> list[CalendarEvent]:
        raise NotImplementedError

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        return next((e for e in self._events(self.coordinator.data) if e.end_datetime_local >= now), None)

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return [e for e in self._events(self.coordinator.data) if _overlaps(e, start_date, end_date)]


class DeadlineCalendar(_BaseCalendar):
    """Each open task deadline as a 30 minute event ending at the deadline."""

    _attr_translation_key = "deadlines"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "deadlines", "calendar")

    def _events(self, data: ItslearningData) -> list[CalendarEvent]:
        return sorted(
            (deadline_event(t) for t in data.tasks if t.deadline and not t.completed),
            key=lambda e: e.start_datetime_local,
        )


class ScheduleCalendar(_BaseCalendar):
    """Lessons and other events from the itslearning calendar."""

    _attr_translation_key = "schedule"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "schedule", "calendar")

    def _events(self, data: ItslearningData) -> list[CalendarEvent]:
        return sorted((schedule_event(i) for i in data.events), key=lambda e: e.start_datetime_local)
