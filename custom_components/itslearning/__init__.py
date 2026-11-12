"""The itslearning integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import ItslearningClient, Tokens
from .const import CONF_SITE_URL, CONF_TOKENS, DOMAIN
from .coordinator import ItslearningCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]

type ItslearningConfigEntry = ConfigEntry[ItslearningCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


CARD_URL = "/itslearning_static/itslearning-card.js"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the Lovelace card from the integration and load it on every dashboard."""
    import json
    from pathlib import Path

    if "frontend" not in hass.config.components or "http" not in hass.config.components:
        return
    try:
        from homeassistant.components.frontend import add_extra_js_url
        from homeassistant.components.http import StaticPathConfig
    except ImportError:  # very old HA
        return
    path = Path(__file__).parent / "www" / "itslearning-card.js"
    version = await hass.async_add_executor_job(
        lambda: json.loads((Path(__file__).parent / "manifest.json").read_text())["version"]
    )
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(path), False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")


def _install_blueprints(config_dir: str) -> list[str]:
    """Copy the bundled blueprints to config/blueprints/automation/itslearning/."""
    from pathlib import Path

    src = Path(__file__).parent / "blueprints"
    dst = Path(config_dir) / "blueprints" / "automation" / "itslearning"
    changed = []
    for f in sorted(src.glob("*.yaml")):
        target = dst / f.name
        content = f.read_text(encoding="utf-8")
        if target.exists():
            current = target.read_text(encoding="utf-8")
            if current == content or not current.startswith("# itslearning-blueprint"):
                continue  # up to date, or edited by the user: leave it alone
        dst.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        changed.append(f.name)
    return changed


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    import logging

    from .sync import async_register_services

    async_register_services(hass)
    await _async_register_card(hass)
    try:
        changed = await hass.async_add_executor_job(_install_blueprints, hass.config.config_dir)
        if changed:
            logging.getLogger(__name__).info("itslearning: installerade blueprints %s", ", ".join(changed))
    except OSError as err:
        logging.getLogger(__name__).warning("itslearning: kunde inte installera blueprints: %s", err)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ItslearningConfigEntry) -> bool:
    client = ItslearningClient(
        entry.data[CONF_SITE_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        tokens=Tokens.from_dict(entry.data.get(CONF_TOKENS)),
    )
    coordinator = ItslearningCoordinator(hass, entry, client)
    await coordinator.tracker.async_load()
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise
    entry.runtime_data = coordinator
    entry.async_on_unload(client.close)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ItslearningConfigEntry) -> None:
    from .tracker import NewItemTracker

    await NewItemTracker(hass, entry.entry_id, entry.title).async_remove()


async def async_unload_entry(hass: HomeAssistant, entry: ItslearningConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
