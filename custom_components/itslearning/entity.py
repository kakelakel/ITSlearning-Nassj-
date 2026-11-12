"""Base entity for itslearning."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SITE_URL, DOMAIN
from .coordinator import ItslearningCoordinator


class ItslearningEntity(CoordinatorEntity[ItslearningCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ItslearningCoordinator, key: str, platform: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        # Predictable ids (sensor.itslearning_upcoming_tasks …) so the
        # dashboard works regardless of HA's language. A second child gets _2.
        self.entity_id = f"{platform}.itslearning_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"itslearning {entry.title}",
            manufacturer="itslearning",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=entry.data[CONF_SITE_URL],
        )
