"""Shared selections over itslearning data (used by sensors, calendars and sync)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.util import dt as dt_util

from .api import CalendarItem, Plan, Task
from .coordinator import ItslearningData

WEEKDAYS = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]


def _today() -> date:
    return dt_util.now().date()


def local_date(dt: datetime) -> date:
    return dt_util.as_local(dt).date()


# --------------------------------------------------------------------- tasks
def open_tasks(data: ItslearningData) -> list[Task]:
    return [t for t in data.tasks if not t.completed]


def upcoming(data: ItslearningData) -> list[Task]:
    """Open tasks with a deadline from now on, soonest first."""
    now = dt_util.utcnow()
    return sorted((t for t in open_tasks(data) if t.deadline and t.deadline >= now), key=lambda t: t.deadline)


def without_deadline(data: ItslearningData) -> list[Task]:
    return sorted((t for t in open_tasks(data) if t.deadline is None), key=lambda t: (t.subject, t.title))


def due_by_end_of_tomorrow(data: ItslearningData) -> list[Task]:
    end = dt_util.start_of_local_day() + timedelta(days=2)
    return [t for t in upcoming(data) if t.deadline < end]


def overdue(data: ItslearningData) -> list[Task]:
    now = dt_util.utcnow()
    return sorted((t for t in open_tasks(data) if t.deadline and t.deadline < now), key=lambda t: t.deadline)


# -------------------------------------------------------------------- events
def _event_days(e: CalendarItem) -> tuple[date, date]:
    first = local_date(e.start)
    last = local_date(e.end - timedelta(seconds=1)) if e.end > e.start else first
    return first, max(first, last)


def events_on(data: ItslearningData, day: date) -> list[CalendarItem]:
    return [e for e in data.events if _event_days(e)[0] <= day <= _event_days(e)[1]]


def upcoming_events(data: ItslearningData, days: int = 14) -> list[CalendarItem]:
    today = _today()
    last = today + timedelta(days=days)
    return [e for e in data.events if _event_days(e)[1] >= today and _event_days(e)[0] <= last]


# --------------------------------------------------------------------- plans
def _plan_days(p: Plan) -> tuple[date, date]:
    first = local_date(p.start)
    last = local_date(p.stop) if p.stop > p.start else first
    return first, max(first, last)


def plans_on(data: ItslearningData, day: date) -> list[Plan]:
    """Lesson plans for a day (work areas spanning many days are left out)."""
    return [p for p in data.plans if p.category == "lesson" and _plan_days(p)[0] <= day <= _plan_days(p)[1]]


def areas_on(data: ItslearningData, day: date) -> list[Plan]:
    """Ongoing work areas (plans spanning several days) that cover a day."""
    return sorted(
        (p for p in data.plans if p.category == "area" and _plan_days(p)[0] <= day <= _plan_days(p)[1]),
        key=lambda p: (p.subject, p.name),
    )


def current_areas(data: ItslearningData) -> list[Plan]:
    return areas_on(data, _today())


def week_bounds(offset_weeks: int = 0) -> tuple[date, date]:
    today = _today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)
    return monday, monday + timedelta(days=6)


def plans_in_week(data: ItslearningData, offset_weeks: int = 0) -> list[Plan]:
    """Lesson plans in a week (work areas are listed separately)."""
    mon, sun = week_bounds(offset_weeks)
    return [p for p in data.plans if p.category == "lesson" and _plan_days(p)[0] <= sun and _plan_days(p)[1] >= mon]


def areas_in_week(data: ItslearningData, offset_weeks: int = 0) -> list[Plan]:
    mon, sun = week_bounds(offset_weeks)
    return sorted(
        (p for p in data.plans if p.category == "area" and _plan_days(p)[0] <= sun and _plan_days(p)[1] >= mon),
        key=lambda p: (p.subject, p.name),
    )


# --------------------------------------------------------------- formatting
def _day_label(d: date) -> str:
    today = _today()
    if d == today:
        return "idag"
    if d == today + timedelta(days=1):
        return "i morgon"
    if d == today - timedelta(days=1):
        return "i går"
    return f"{WEEKDAYS[d.weekday()]} {d.day}/{d.month}"


def fmt_event(e: CalendarItem) -> dict:
    d = e.as_dict()
    first, last = _event_days(e)
    d["date"] = first.isoformat()
    d["day"] = _day_label(first)
    d["days_left"] = (first - _today()).days
    d["time"] = "" if e.all_day else f"{dt_util.as_local(e.start):%H:%M}–{dt_util.as_local(e.end):%H:%M}"
    return d


def fmt_task(t: Task) -> dict:
    d = t.as_dict()
    if t.deadline:
        local = dt_util.as_local(t.deadline)
        d["deadline_local"] = f"{local:%Y-%m-%d %H:%M}"
        d["time"] = f"lämnas {local:%H:%M}"
        d["day"] = _day_label(local.date())
        d["days_left"] = (local.date() - _today()).days
    return d


def fmt_plan(p: Plan) -> dict:
    d = p.as_dict()
    first, last = _plan_days(p)
    d["date"] = first.isoformat()
    d["end_date"] = last.isoformat()
    d["day"] = _day_label(first) if first == last else f"{_day_label(first)}–{_day_label(last)}"
    d["weekday"] = WEEKDAYS[first.weekday()]
    d["days_left"] = (first - _today()).days
    d["days_until_end"] = (last - _today()).days
    w1, w2 = first.isocalendar()[1], last.isocalendar()[1]
    d["weeks"] = f"v. {w1}" if w1 == w2 else f"v. {w1}–{w2}"
    return d


def homework_today(data: ItslearningData) -> dict:
    """Everything relevant for one day: events, plans and tasks due."""
    day = _today()
    return _day_bundle(data, day)


def _day_bundle(data: ItslearningData, day: date) -> dict:
    tasks = [t for t in open_tasks(data) if t.deadline and local_date(t.deadline) == day]
    return {
        "date": day.isoformat(),
        "events": [fmt_event(e) for e in events_on(data, day)],
        "tasks": [fmt_task(t) for t in tasks],
        "plans": [fmt_plan(p) for p in plans_on(data, day)],
        "areas": [fmt_plan(p) for p in areas_on(data, day)],
    }


def day_count(bundle: dict) -> int:
    """Things to do or attend that day (ongoing work areas are not counted)."""
    return len(bundle["events"]) + len(bundle["plans"]) + len(bundle["tasks"])


def tomorrow_bundle(data: ItslearningData) -> dict:
    return _day_bundle(data, _today() + timedelta(days=1))
