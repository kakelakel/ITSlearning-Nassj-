"""Detect new itslearning items and fire `itslearning_new` events.

Remembers what it has already seen (persisted with HA's Store), so a restart
does not produce duplicates. The very first run only records what exists.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import selectors as sel
from .api import CATEGORY_LABELS
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

EVENT_NEW = f"{DOMAIN}_new"
STORE_VERSION = 1
MAX_SEEN = 3000
MAX_EVENTS_PER_UPDATE = 25


class NewItemTracker:
    def __init__(self, hass: HomeAssistant, entry_id: str, child: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.child = child
        self._store: Store = Store(hass, STORE_VERSION, f"{DOMAIN}.seen.{entry_id}")
        self._seen: list[str] = []
        self._seen_set: set[str] = set()
        self._loaded = False
        self._initialized = False

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if data:
            self._seen = list(data.get("seen", []))
            self._seen_set = set(self._seen)
            self._initialized = bool(data.get("initialized"))
        self._loaded = True

    async def async_remove(self) -> None:
        await self._store.async_remove()

    def _mark(self, key: str) -> bool:
        """Remember key; True if it was new."""
        if key in self._seen_set:
            return False
        self._seen.append(key)
        self._seen_set.add(key)
        return True

    def _base(self, kind: str, d: dict[str, Any]) -> dict[str, Any]:
        cat = d.get("category") or kind
        return {
            "entry_id": self.entry_id,
            "child": self.child,
            "kind": kind,
            "category": cat,
            "category_label": d.get("category_label") or CATEGORY_LABELS.get(cat, cat),
            "subject": d.get("subject") or "",
            "course": d.get("course") or "",
            "title": d.get("title") or d.get("name") or d.get("text") or "",
            "description": (d.get("description") or "")[:250],
            "url": d.get("url") or "",
            "date": d.get("start") or d.get("deadline") or d.get("published"),
            "day": d.get("day") or "",
            "days_left": d.get("days_left"),
            "time": (d.get("deadline_local") or "")[11:] if d.get("deadline") else d.get("time") or "",
        }

    def process(self, data) -> list[dict[str, Any]]:
        """Return payloads for new items and remember everything seen."""
        if not self._loaded:
            return []
        today = dt_util.now().date()
        old_cutoff = dt_util.utcnow() - timedelta(days=1)
        found: list[tuple[str, dict[str, Any], bool]] = []  # key, payload, relevant

        for n in data.news:
            found.append((f"news:{n.id}", self._news_payload(n), True))
        for n in getattr(data, "notifications", []):
            found.append((f"notif:{n.id}", self._base("notification", n.as_dict()), not n.is_read))
        for e in data.events:
            d = sel.fmt_event(e)
            found.append((f"event:{e.id}", self._base("event", d), sel.local_date(e.end) >= today))
        for t in data.tasks:
            if t.completed:
                continue
            d = sel.fmt_task(t)
            found.append((f"task:{t.id}", self._base("task", d), t.deadline is None or t.deadline >= old_cutoff))
            if t.deadline:
                # A deadline that is added or moved later on is news too.
                p = self._base("deadline", d)
                p["category_label"] = "Ny deadline"
                found.append((f"deadline:{t.id}:{t.deadline.isoformat()}", p, t.deadline >= old_cutoff))
        for p in data.plans:
            d = sel.fmt_plan(p)
            found.append((f"plan:{p.id}", self._base("plan", d), sel.local_date(p.stop) >= today))

        new = []
        for key, payload, relevant in found:
            if self._mark(key) and relevant and self._initialized:
                new.append(payload)
        # A task's first deadline arrives together with the task itself: one notice is enough.
        task_ids = {p["title"] for p in new if p["kind"] == "task"}
        new = [p for p in new if not (p["kind"] == "deadline" and p["title"] in task_ids)]

        if not self._initialized:
            _LOGGER.debug("itslearning: first run, remembered %d items without notifying", len(found))
            self._initialized = True
        if len(self._seen) > MAX_SEEN:
            self._seen = self._seen[-MAX_SEEN:]
            self._seen_set = set(self._seen)
        self._store.async_delay_save(lambda: {"seen": self._seen, "initialized": True}, 5)
        return new[:MAX_EVENTS_PER_UPDATE]

    def _news_payload(self, n) -> dict[str, Any]:
        d = n.as_dict()
        if n.published:
            d["day"] = sel._day_label(sel.local_date(n.published))
        d["description"] = n.author
        return self._base("news", d)

    def fire(self, payloads: list[dict[str, Any]]) -> None:
        for p in payloads:
            _LOGGER.debug("itslearning_new: %s %s", p["category_label"], p["title"])
            self.hass.bus.async_fire(EVENT_NEW, p)
