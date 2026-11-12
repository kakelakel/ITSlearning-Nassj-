"""Shared selections over itslearning data (used by sensors, calendars and sync)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.util import dt as dt_util

from .api import CalendarItem, Task
from .coordinator import ItslearningData


def open_tasks(data: ItslearningData) -> list[Task]:
    return [t for t in data.tasks if not t.completed]


def upcoming(data: ItslearningData) -> list[Task]:
    """Open tasks with a deadline from now on, soonest first."""
    now = dt_util.utcnow()
    return sorted((t for t in open_tasks(data) if t.deadline and t.deadline >= now), key=lambda t: t.deadline)


def without_deadline(data: ItslearningData) -> list[Task]:
    return sorted((t for t in open_tasks(data) if t.deadline is None), key=lambda t: (t.course, t.title))


def due_by_end_of_tomorrow(data: ItslearningData) -> list[Task]:
    end = dt_util.start_of_local_day() + timedelta(days=2)
    return [t for t in upcoming(data) if t.deadline < end]


def overdue(data: ItslearningData) -> list[Task]:
    now = dt_util.utcnow()
    return sorted((t for t in open_tasks(data) if t.deadline and t.deadline < now), key=lambda t: t.deadline)


def events_on(data: ItslearningData, day: date) -> list[CalendarItem]:
    return [e for e in data.events if dt_util.as_local(e.start).date() == day]


def today(data: ItslearningData) -> list[CalendarItem]:
    return events_on(data, dt_util.now().date())


def tomorrow(data: ItslearningData) -> list[CalendarItem]:
    return events_on(data, dt_util.now().date() + timedelta(days=1))


def next_school_day(data: ItslearningData) -> list[CalendarItem]:
    """Events of the next day (after today) that has any."""
    now_day = dt_util.now().date()
    later = [e for e in data.events if dt_util.as_local(e.start).date() > now_day]
    if not later:
        return []
    return events_on(data, dt_util.as_local(later[0].start).date())


def next_event(data: ItslearningData) -> CalendarItem | None:
    now = dt_util.utcnow()
    return next((e for e in data.events if e.end > now and not e.all_day), None)


def fmt_event(e: CalendarItem) -> dict:
    d = e.as_dict()
    d["time"] = "Heldag" if e.all_day else (
        f"{dt_util.as_local(e.start):%H:%M}–{dt_util.as_local(e.end):%H:%M}"
    )
    return d


def fmt_task(t: Task) -> dict:
    d = t.as_dict()
    if t.deadline:
        local = dt_util.as_local(t.deadline)
        d["deadline_local"] = f"{local:%Y-%m-%d %H:%M}"
        d["days_left"] = (local.date() - dt_util.now().date()).days
    return d


def as_local(dt: datetime) -> datetime:
    return dt_util.as_local(dt)
