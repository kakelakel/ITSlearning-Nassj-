"""Copy itslearning deadlines/schedule into another HA calendar (e.g. Google Calendar).

Only adds missing events. Each created event carries a marker
"[itsl:<uid>]" in its description so it is never added twice.
Events removed or moved in itslearning are not deleted from the target,
because Home Assistant's calendar actions cannot delete events.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .calendar import deadline_event, schedule_event
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SYNC = "sync_calendar"
ATTR_TARGET = "target_calendar"
ATTR_INCLUDE = "include"
ATTR_DAYS = "days_ahead"
INCLUDE_OPTIONS = ["deadlines", "schedule"]
MARKER = "[itsl:{uid}]"

SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TARGET): cv.entity_id,
        vol.Optional(ATTR_INCLUDE, default=["deadlines"]): vol.All(cv.ensure_list, [vol.In(INCLUDE_OPTIONS)]),
        vol.Optional(ATTR_DAYS, default=14): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
    }
)


def _bounds(e: CalendarEvent) -> tuple[datetime, datetime]:
    return e.start_datetime_local, e.end_datetime_local


async def _existing(hass: HomeAssistant, target: str, start: datetime, end: datetime) -> tuple[set[str], set[tuple[str, str]]]:
    resp = await hass.services.async_call(
        "calendar", "get_events",
        {ATTR_ENTITY_ID: target, "start_date_time": start.isoformat(), "end_date_time": end.isoformat()},
        blocking=True, return_response=True,
    )
    markers: set[str] = set()
    keys: set[tuple[str, str]] = set()
    for ev in (resp or {}).get(target, {}).get("events", []):
        desc = ev.get("description") or ""
        for part in desc.split("[itsl:")[1:]:
            markers.add(part.split("]", 1)[0])
        keys.add(((ev.get("summary") or "").strip(), str(ev.get("start"))[:16]))
    return markers, keys


def _event_payload(target: str, ev: CalendarEvent) -> dict[str, Any]:
    marker = MARKER.format(uid=ev.uid)
    payload: dict[str, Any] = {
        ATTR_ENTITY_ID: target,
        "summary": ev.summary,
        "description": f"{ev.description}\n\n{marker}".strip() if ev.description else marker,
    }
    if ev.location:
        payload["location"] = ev.location
    if isinstance(ev.start, datetime):
        payload["start_date_time"] = dt_util.as_local(ev.start).isoformat()
        payload["end_date_time"] = dt_util.as_local(ev.end).isoformat()
    else:
        payload["start_date"] = ev.start.isoformat()
        payload["end_date"] = ev.end.isoformat()
    return payload


def _start_key(ev: CalendarEvent) -> str:
    s = ev.start
    return (dt_util.as_local(s).isoformat() if isinstance(s, datetime) else s.isoformat())[:16]


def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SYNC):
        return

    async def handle(call: ServiceCall) -> ServiceResponse:
        target: str = call.data[ATTR_TARGET]
        include: list[str] = call.data[ATTR_INCLUDE]
        days: int = call.data[ATTR_DAYS]
        if hass.states.get(target) is None:
            raise HomeAssistantError(f"Kalendern {target} finns inte")
        if target.startswith("calendar.itslearning_"):
            raise HomeAssistantError("Välj en annan kalender än itslearnings egna")

        now = dt_util.now()
        start = now - timedelta(hours=1)
        end = now + timedelta(days=days)

        wanted: list[CalendarEvent] = []
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            data = entry.runtime_data.data
            if "deadlines" in include:
                wanted += [deadline_event(t) for t in data.tasks if t.deadline and not t.completed]
            if "schedule" in include:
                wanted += [schedule_event(i) for i in data.events]
        wanted = [e for e in wanted if _bounds(e)[1] > start and _bounds(e)[0] < end]

        markers, keys = await _existing(hass, target, start - timedelta(days=1), end + timedelta(days=1))
        created, skipped, failed = 0, 0, 0
        for ev in wanted:
            if ev.uid in markers or (ev.summary.strip(), _start_key(ev)) in keys:
                skipped += 1
                continue
            try:
                await hass.services.async_call("calendar", "create_event", _event_payload(target, ev), blocking=True)
                created += 1
            except HomeAssistantError as err:
                failed += 1
                _LOGGER.warning("Kunde inte skapa '%s' i %s: %s", ev.summary, target, err)
        _LOGGER.info("itslearning → %s: %d nya, %d fanns redan, %d fel", target, created, skipped, failed)
        return {"created": created, "already_there": skipped, "failed": failed}

    hass.services.async_register(DOMAIN, SERVICE_SYNC, handle, schema=SCHEMA, supports_response=SupportsResponse.OPTIONAL)
