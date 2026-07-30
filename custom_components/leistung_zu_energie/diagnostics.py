"""Diagnostics support for Leistung zu Energie."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry": {
            "version": entry.version,
            "minor_version": entry.minor_version,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "runtime": {
            "sources": coordinator.sources,
            "value_mode": coordinator.value_mode,
            "integration_method": coordinator.method,
            "max_interval_seconds": coordinator.max_interval.total_seconds(),
            "daily_reset_hour": coordinator.daily_reset_hour,
            "week_start": coordinator.week_start,
            "source_data": {
                source: {
                    "period_keys": data.period_keys,
                    "last_update": data.last_update,
                    "last_power_w": data.last_power_w,
                    "skipped_intervals": data.skipped_intervals,
                }
                for source, data in coordinator.data.items()
            },
        },
    }
