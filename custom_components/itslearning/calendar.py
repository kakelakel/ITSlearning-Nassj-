"""Calendars: deadlines, itslearning events (tests, homework checks …) and course plans."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ItslearningConfigEntry
from .api import CalendarItem, Plan, Task
from .const import DOMAIN
from .coordinator import ItslearningData
from .entity import ItslearningEntity

DEADLINE_LENGTH = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ItslearningConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    reg = er.async_get(hass)
    if eid := reg.async_get_entity_id("calendar", DOMAIN, f"{entry.entry_id}_schedule"):
        reg.async_remove(eid)  # renamed to "events" (itslearning has no lesson schedule)
    c = entry.runtime_data
    async_add_entities([DeadlineCalendar(c), EventCalendar(c), PlanCalendar(c)])


CATEGORY_EMOJI = {
    "test": "📝", "quiz": "🗣️", "homework": "📚", "assignment": "📤", "event": "📅",
    "lesson": "📖", "area": "🗺️",
}


def _label(subject: str, title: str) -> str:
    if subject and subject.lower() not in title.lower():
        return f"{subject}: {title}"
    return title


def _summary(category: str, subject: str, title: str) -> str:
    from .api import CATEGORY_LABELS

    return f"{CATEGORY_EMOJI.get(category, '•')} {CATEGORY_LABELS.get(category, '')}: {_label(subject, title)}"


def deadline_event(task: Task) -> CalendarEvent:
    description = f"Status: {task.status or 'okänd'}"
    if task.url:
        description += f"\n{task.url}"
    return CalendarEvent(
        start=task.deadline - DEADLINE_LENGTH, end=task.deadline,
        summary=_summary(task.category, task.subject, task.title), description=description, uid=f"itsl-task-{task.id}",
    )


def item_event(item: CalendarItem) -> CalendarEvent:
    if item.all_day:
        start = dt_util.as_local(item.start).date()
        end = dt_util.as_local(item.end - timedelta(seconds=1)).date() + timedelta(days=1)
        if end <= start:
            end = start + timedelta(days=1)
    else:
        start, end = item.start, item.end
    description = item.description
    if item.url:
        description = f"{description}\n{item.url}".strip()
    return CalendarEvent(
        start=start, end=end, summary=_summary(item.category, item.subject, item.title), description=description or None,
        location=item.location or None, uid=f"itsl-event-{item.id}",
    )


def plan_event(plan: Plan) -> CalendarEvent:
    start = dt_util.as_local(plan.start).date()
    end = dt_util.as_local(plan.stop).date() + timedelta(days=1)
    if end <= start:
        end = start + timedelta(days=1)
    description = plan.description
    if plan.url:
        description = f"{description}\n{plan.url}".strip()
    return CalendarEvent(
        start=start, end=end, summary=_summary(plan.category, plan.subject, plan.name),
        description=description or None, uid=f"itsl-plan-{plan.id}",
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


class EventCalendar(_BaseCalendar):
    """Events from the itslearning calendar (homework checks, tests, school events)."""

    _attr_translation_key = "events"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "events", "calendar")

    def _events(self, data: ItslearningData) -> list[CalendarEvent]:
        return sorted((item_event(i) for i in data.events), key=lambda e: e.start_datetime_local)


class PlanCalendar(_BaseCalendar):
    """Course plans (lesson plans / weekly plans) as all-day events."""

    _attr_translation_key = "plans"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "plans", "calendar")

    def _events(self, data: ItslearningData) -> list[CalendarEvent]:
        return sorted((plan_event(p) for p in data.plans), key=lambda e: e.start_datetime_local)
