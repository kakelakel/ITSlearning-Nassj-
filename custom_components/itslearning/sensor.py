"""Sensors for itslearning."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ItslearningConfigEntry
from . import selectors as sel
from .const import DOMAIN
from .coordinator import ItslearningData
from .entity import ItslearningEntity

MAX_ITEMS = 30


def _tasks(tasks) -> dict[str, Any]:
    return {"tasks": [sel.fmt_task(t) for t in tasks[:MAX_ITEMS]]}


def _events(events) -> dict[str, Any]:
    return {"events": [sel.fmt_event(e) for e in events[:MAX_ITEMS]]}


@dataclass(frozen=True, kw_only=True)
class ItslearningSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ItslearningData], Any]
    attrs_fn: Callable[[ItslearningData], dict[str, Any]] | None = None


def _news_attrs(d: ItslearningData) -> dict[str, Any]:
    out = []
    for n in d.news[:MAX_ITEMS]:
        item = n.as_dict()
        if n.published:
            item["day"] = sel._day_label(sel.local_date(n.published))
        out.append(item)
    return {"news": out}


def _recent_news(d: ItslearningData) -> int:
    since = dt_util.utcnow() - timedelta(days=7)
    return sum(1 for n in d.news if n.published and n.published >= since)


SENSORS: tuple[ItslearningSensorDescription, ...] = (
    # --- Day overview -------------------------------------------------------
    ItslearningSensorDescription(
        key="today",
        translation_key="today",
        icon="mdi:calendar-today",
        native_unit_of_measurement="st",
        value_fn=lambda d: sel.day_count(sel.homework_today(d)),
        attrs_fn=sel.homework_today,
    ),
    ItslearningSensorDescription(
        key="tomorrow",
        translation_key="tomorrow",
        icon="mdi:calendar-arrow-right",
        native_unit_of_measurement="st",
        value_fn=lambda d: sel.day_count(sel.tomorrow_bundle(d)),
        attrs_fn=sel.tomorrow_bundle,
    ),
    # --- Events (homework checks, tests …) ------------------------------------
    ItslearningSensorDescription(
        key="upcoming_events",
        translation_key="upcoming_events",
        icon="mdi:calendar-star",
        native_unit_of_measurement="st",
        value_fn=lambda d: len(sel.upcoming_events(d)),
        attrs_fn=lambda d: _events(sel.upcoming_events(d)),
    ),
    # --- Plans ------------------------------------------------------------------
    ItslearningSensorDescription(
        key="plans_this_week",
        translation_key="plans_this_week",
        icon="mdi:notebook-outline",
        native_unit_of_measurement="st",
        value_fn=lambda d: len(sel.plans_in_week(d)),
        attrs_fn=lambda d: {"plans": [sel.fmt_plan(p) for p in sel.plans_in_week(d)[:MAX_ITEMS]],
                            "areas": [sel.fmt_plan(p) for p in sel.areas_in_week(d)[:MAX_ITEMS]],
                            "week": sel.week_bounds()[0].isocalendar()[1]},
    ),
    ItslearningSensorDescription(
        key="plans_next_week",
        translation_key="plans_next_week",
        icon="mdi:notebook-outline",
        native_unit_of_measurement="st",
        value_fn=lambda d: len(sel.plans_in_week(d, 1)),
        attrs_fn=lambda d: {"plans": [sel.fmt_plan(p) for p in sel.plans_in_week(d, 1)[:MAX_ITEMS]],
                            "areas": [sel.fmt_plan(p) for p in sel.areas_in_week(d, 1)[:MAX_ITEMS]],
                            "week": sel.week_bounds(1)[0].isocalendar()[1]},
    ),
    ItslearningSensorDescription(
        key="work_areas",
        translation_key="work_areas",
        icon="mdi:map-outline",
        native_unit_of_measurement="st",
        value_fn=lambda d: len(sel.current_areas(d)),
        attrs_fn=lambda d: {"areas": [sel.fmt_plan(p) for p in sel.current_areas(d)[:MAX_ITEMS]]},
    ),
    # --- Tasks ------------------------------------------------------------------
    ItslearningSensorDescription(
        key="upcoming_tasks",
        translation_key="upcoming_tasks",
        icon="mdi:book-open-variant",
        native_unit_of_measurement="st",
        value_fn=lambda d: len(sel.upcoming(d)),
        attrs_fn=lambda d: _tasks(sel.upcoming(d)),
    ),
    ItslearningSensorDescription(
        key="due_tomorrow",
        translation_key="due_tomorrow",
        icon="mdi:calendar-alert",
        native_unit_of_measurement="st",
        value_fn=lambda d: len(sel.due_by_end_of_tomorrow(d)),
        attrs_fn=lambda d: _tasks(sel.due_by_end_of_tomorrow(d)),
    ),
    ItslearningSensorDescription(
        key="overdue_tasks",
        translation_key="overdue_tasks",
        icon="mdi:alert-circle-outline",
        native_unit_of_measurement="st",
        value_fn=lambda d: len(sel.overdue(d)),
        attrs_fn=lambda d: _tasks(sel.overdue(d)),
    ),
    ItslearningSensorDescription(
        key="tasks_without_deadline",
        translation_key="tasks_without_deadline",
        icon="mdi:clipboard-text-outline",
        native_unit_of_measurement="st",
        value_fn=lambda d: len(sel.without_deadline(d)),
        attrs_fn=lambda d: _tasks(sel.without_deadline(d)),
    ),
    ItslearningSensorDescription(
        key="next_deadline",
        translation_key="next_deadline",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: (u[0].deadline if (u := sel.upcoming(d)) else None),
        attrs_fn=lambda d: (sel.fmt_task(u[0]) if (u := sel.upcoming(d)) else {}),
    ),
    # --- News -------------------------------------------------------------------
    ItslearningSensorDescription(
        key="news",
        translation_key="news",
        icon="mdi:newspaper-variant-outline",
        native_unit_of_measurement="st",
        value_fn=_recent_news,
        attrs_fn=_news_attrs,
    ),
    ItslearningSensorDescription(
        key="unread_notifications",
        translation_key="unread_notifications",
        icon="mdi:bell-badge-outline",
        value_fn=lambda d: d.unread_notifications,
        attrs_fn=lambda d: {"notifications": [n.as_dict() for n in d.notifications[:MAX_ITEMS]]},
    ),
)

OLD_KEYS = ("schedule_today", "schedule_tomorrow", "next_lesson", "next_school_day_start")


async def async_setup_entry(
    hass: HomeAssistant, entry: ItslearningConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    # Remove sensors from earlier versions (there is no lesson schedule in itslearning).
    reg = er.async_get(hass)
    for key in OLD_KEYS:
        if eid := reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}"):
            reg.async_remove(eid)
    async_add_entities(ItslearningSensor(coordinator, desc) for desc in SENSORS)


class ItslearningSensor(ItslearningEntity, SensorEntity):
    entity_description: ItslearningSensorDescription

    def __init__(self, coordinator, description: ItslearningSensorDescription) -> None:
        super().__init__(coordinator, description.key, "sensor")
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
