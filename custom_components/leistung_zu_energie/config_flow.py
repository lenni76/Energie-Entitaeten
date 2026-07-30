"""Config flow for Leistung zu Energie."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import UnitOfPower
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DAILY_RESET_HOUR,
    CONF_INTEGRATION_METHOD,
    CONF_MAX_INTERVAL,
    CONF_SOURCE_ENTITIES,
    CONF_VALUE_MODE,
    CONF_WEEK_START,
    DEFAULT_DAILY_RESET_HOUR,
    DEFAULT_MAX_INTERVAL,
    DEFAULT_METHOD,
    DEFAULT_MODE,
    DEFAULT_WEEK_START,
    DOMAIN,
    INTEGRATION_METHODS,
    VALUE_MODES,
)

SUPPORTED_UNITS = {
    UnitOfPower.MILLIWATT,
    UnitOfPower.WATT,
    UnitOfPower.KILO_WATT,
    UnitOfPower.MEGA_WATT,
}


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the user/options schema."""
    defaults = defaults or {}

    # SelectSelector values must always be strings. Older entries and the
    # original 2.0.0 defaults may contain the week start as an integer.
    normalized_defaults = dict(defaults)
    normalized_defaults[CONF_WEEK_START] = str(
        normalized_defaults.get(CONF_WEEK_START, str(DEFAULT_WEEK_START))
    )
    normalized_defaults[CONF_DAILY_RESET_HOUR] = int(
        defaults.get(CONF_DAILY_RESET_HOUR, DEFAULT_DAILY_RESET_HOUR)
    )
    normalized_defaults[CONF_MAX_INTERVAL] = int(
        normalized_defaults.get(CONF_MAX_INTERVAL, DEFAULT_MAX_INTERVAL)
    )

    return vol.Schema(
        {
            vol.Required(
                CONF_SOURCE_ENTITIES,
                default=normalized_defaults.get(CONF_SOURCE_ENTITIES, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="power",
                    multiple=True,
                )
            ),
            vol.Required(
                CONF_VALUE_MODE,
                default=normalized_defaults.get(CONF_VALUE_MODE, DEFAULT_MODE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=VALUE_MODES,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="value_mode",
                )
            ),
            vol.Required(
                CONF_INTEGRATION_METHOD,
                default=normalized_defaults.get(CONF_INTEGRATION_METHOD, DEFAULT_METHOD),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=INTEGRATION_METHODS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="integration_method",
                )
            ),
            vol.Required(
                CONF_MAX_INTERVAL,
                default=normalized_defaults.get(CONF_MAX_INTERVAL, DEFAULT_MAX_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=1440,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
            vol.Required(
                CONF_DAILY_RESET_HOUR,
                default=normalized_defaults.get(
                    CONF_DAILY_RESET_HOUR, DEFAULT_DAILY_RESET_HOUR
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=23,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                )
            ),
            vol.Required(
                CONF_WEEK_START,
                default=normalized_defaults.get(CONF_WEEK_START, str(DEFAULT_WEEK_START)),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[str(day) for day in range(7)],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="week_start",
                )
            ),
        }
    )


def _validate_sources(hass, sources: list[str]) -> dict[str, str]:
    """Validate selected power sensors."""
    if not sources:
        return {CONF_SOURCE_ENTITIES: "no_entities"}
    for entity_id in sources:
        state = hass.states.get(entity_id)
        if state is None:
            return {CONF_SOURCE_ENTITIES: "entity_not_found"}
        if state.attributes.get("unit_of_measurement") not in SUPPORTED_UNITS:
            return {CONF_SOURCE_ENTITIES: "unsupported_unit"}
    return {}


class LeistungZuEnergieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2
    MINOR_VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_sources(self.hass, user_input[CONF_SOURCE_ENTITIES])
            if not errors:
                return self.async_create_entry(
                    title="Leistung zu Energie", data=user_input
                )
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow."""
        return LeistungZuEnergieOptionsFlow(config_entry)


class LeistungZuEnergieOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_sources(self.hass, user_input[CONF_SOURCE_ENTITIES])
            if not errors:
                return self.async_create_entry(title="", data=user_input)
        current = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or current),
            errors=errors,
        )
