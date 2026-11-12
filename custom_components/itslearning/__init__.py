"""The itslearning integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .api import ItslearningClient, Tokens
from .const import CONF_SITE_URL, CONF_TOKENS
from .coordinator import ItslearningCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]

type ItslearningConfigEntry = ConfigEntry[ItslearningCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ItslearningConfigEntry) -> bool:
    client = ItslearningClient(
        entry.data[CONF_SITE_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        tokens=Tokens.from_dict(entry.data.get(CONF_TOKENS)),
    )
    coordinator = ItslearningCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise
    entry.runtime_data = coordinator
    entry.async_on_unload(client.close)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ItslearningConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
