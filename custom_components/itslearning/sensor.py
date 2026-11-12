"""Sensors for itslearning."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ItslearningConfigEntry
from . import selectors as sel
from .coordinator import ItslearningData
from .entity import ItslearningEntity

MAX_ITEMS = 30


def _tasks(tasks) -> dict[str, Any]:
    return {"tasks": [sel.fmt_task(t) for t in tasks[:MAX_ITEMS]]}


def _events(events) -> dict[str, Any]:
    return {"events": [sel.fmt_event(e) for e in events[:MAX_ITEMS]]}


def _first_start(events):
    timed = [e for e in events if not e.all_day]
    return timed[0].start if timed else None


@dataclass(frozen=True, kw_only=True)
class ItslearningSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ItslearningData], Any]
    attrs_fn: Callable[[ItslearningData], dict[str, Any]] | None = None


SENSORS: tuple[ItslearningSensorDescription, ...] = (
    # --- Homework / tasks ---------------------------------------------------
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
    # --- Schedule ------------------------------------------------------------
    ItslearningSensorDescription(
        key="schedule_today",
        translation_key="schedule_today",
        icon="mdi:calendar-today",
        native_unit_of_measurement="st",
        value_fn=lambda d: len(sel.today(d)),
        attrs_fn=lambda d: _events(sel.today(d)),
    ),
    ItslearningSensorDescription(
        key="schedule_tomorrow",
        translation_key="schedule_tomorrow",
        icon="mdi:calendar-arrow-right",
        native_unit_of_measurement="st",
        value_fn=lambda d: len(sel.tomorrow(d)),
        attrs_fn=lambda d: _events(sel.tomorrow(d)),
    ),
    ItslearningSensorDescription(
        key="next_lesson",
        translation_key="next_lesson",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: (e.start if (e := sel.next_event(d)) else None),
        attrs_fn=lambda d: (sel.fmt_event(e) if (e := sel.next_event(d)) else {}),
    ),
    ItslearningSensorDescription(
        key="next_school_day_start",
        translation_key="next_school_day_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:alarm",
        value_fn=lambda d: _first_start(sel.next_school_day(d)),
        attrs_fn=lambda d: _events(sel.next_school_day(d)),
    ),
    # --- Other ---------------------------------------------------------------
    ItslearningSensorDescription(
        key="unread_notifications",
        translation_key="unread_notifications",
        icon="mdi:bell-badge-outline",
        value_fn=lambda d: d.unread_notifications,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ItslearningConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
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
