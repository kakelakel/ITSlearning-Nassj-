"""Sensors for itslearning."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ItslearningConfigEntry
from .api import Task
from .coordinator import ItslearningData
from .entity import ItslearningEntity


def _open(data: ItslearningData) -> list[Task]:
    return [t for t in data.tasks if not t.completed]


def _upcoming(data: ItslearningData) -> list[Task]:
    now = dt_util.utcnow()
    tasks = [t for t in _open(data) if t.deadline is None or t.deadline >= now]
    return sorted(tasks, key=lambda t: t.deadline or datetime.max.replace(tzinfo=now.tzinfo))


def _due_by_end_of_tomorrow(data: ItslearningData) -> list[Task]:
    end = dt_util.start_of_local_day() + timedelta(days=2)
    return [t for t in _upcoming(data) if t.deadline and t.deadline < end]


def _overdue(data: ItslearningData) -> list[Task]:
    now = dt_util.utcnow()
    return [t for t in _open(data) if t.deadline and t.deadline < now]


def _next_deadline(data: ItslearningData) -> datetime | None:
    return next((t.deadline for t in _upcoming(data) if t.deadline), None)


def _task_list(tasks: list[Task]) -> dict[str, Any]:
    return {"tasks": [t.as_dict() for t in tasks[:25]]}


@dataclass(frozen=True, kw_only=True)
class ItslearningSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ItslearningData], Any]
    attrs_fn: Callable[[ItslearningData], dict[str, Any]] | None = None


SENSORS: tuple[ItslearningSensorDescription, ...] = (
    ItslearningSensorDescription(
        key="upcoming_tasks",
        translation_key="upcoming_tasks",
        icon="mdi:book-open-variant",
        native_unit_of_measurement="uppgifter",
        value_fn=lambda d: len(_upcoming(d)),
        attrs_fn=lambda d: _task_list(_upcoming(d)),
    ),
    ItslearningSensorDescription(
        key="due_tomorrow",
        translation_key="due_tomorrow",
        icon="mdi:calendar-alert",
        native_unit_of_measurement="uppgifter",
        value_fn=lambda d: len(_due_by_end_of_tomorrow(d)),
        attrs_fn=lambda d: _task_list(_due_by_end_of_tomorrow(d)),
    ),
    ItslearningSensorDescription(
        key="overdue_tasks",
        translation_key="overdue_tasks",
        icon="mdi:alert-circle-outline",
        native_unit_of_measurement="uppgifter",
        value_fn=lambda d: len(_overdue(d)),
        attrs_fn=lambda d: _task_list(_overdue(d)),
    ),
    ItslearningSensorDescription(
        key="next_deadline",
        translation_key="next_deadline",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_deadline,
        attrs_fn=lambda d: (
            {"title": t[0].title, "course": t[0].course, "url": t[0].url}
            if (t := [x for x in _upcoming(d) if x.deadline])
            else {}
        ),
    ),
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
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
