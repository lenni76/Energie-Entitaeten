"""Leistung zu Energie integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_SOURCE_ENTITIES,
    CONF_SOURCE_ENTITY,
    DOMAIN,
    PLATFORMS,
)


type LeistungZuEnergieConfigEntry = ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: LeistungZuEnergieConfigEntry
) -> bool:
    """Set up Leistung zu Energie from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LeistungZuEnergieConfigEntry
) -> bool:
    """Unload a config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is not None:
        await coordinator.async_stop()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


async def async_migrate_entry(
    hass: HomeAssistant, entry: LeistungZuEnergieConfigEntry
) -> bool:
    """Migrate old config entries."""
    if entry.version == 1:
        data = dict(entry.data)
        options = dict(entry.options)
        source = options.pop(CONF_SOURCE_ENTITY, None) or data.pop(
            CONF_SOURCE_ENTITY, None
        )
        sources = options.get(CONF_SOURCE_ENTITIES) or data.get(CONF_SOURCE_ENTITIES)
        if not sources and source:
            data[CONF_SOURCE_ENTITIES] = [source]
        if source:
            entity_registry = er.async_get(hass)
            for period in ("total", "day", "week", "month", "year"):
                old_unique_id = f"{entry.entry_id}_{period}"
                entity_id = entity_registry.async_get_entity_id(
                    "sensor", DOMAIN, old_unique_id
                )
                if entity_id:
                    entity_registry.async_update_entity(
                        entity_id,
                        new_unique_id=f"{entry.entry_id}_{source}_{period}",
                    )
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            version=2,
            minor_version=1,
            unique_id=None,
            title="Leistung zu Energie",
        )
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: LeistungZuEnergieConfigEntry
) -> None:
    """Reload after options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)
