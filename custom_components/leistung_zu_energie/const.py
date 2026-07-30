"""Constants for Leistung zu Energie."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "leistung_zu_energie"
PLATFORMS: Final = ["sensor"]

CONF_SOURCE_ENTITY: Final = "source_entity"  # Version 1 migration only
CONF_SOURCE_ENTITIES: Final = "source_entities"
CONF_VALUE_MODE: Final = "value_mode"
CONF_INTEGRATION_METHOD: Final = "integration_method"
CONF_MAX_INTERVAL: Final = "max_interval_minutes"
CONF_DAILY_RESET_HOUR: Final = "daily_reset_hour"
CONF_WEEK_START: Final = "week_start"

MODE_POSITIVE: Final = "positive"
MODE_ABSOLUTE: Final = "absolute"
MODE_SIGNED: Final = "signed"
VALUE_MODES: Final = [MODE_POSITIVE, MODE_ABSOLUTE, MODE_SIGNED]

METHOD_LEFT: Final = "left"
METHOD_RIGHT: Final = "right"
METHOD_TRAPEZOIDAL: Final = "trapezoidal"
INTEGRATION_METHODS: Final = [METHOD_LEFT, METHOD_RIGHT, METHOD_TRAPEZOIDAL]

DEFAULT_MODE: Final = MODE_POSITIVE
DEFAULT_METHOD: Final = METHOD_LEFT
DEFAULT_MAX_INTERVAL: Final = 10
DEFAULT_DAILY_RESET_HOUR: Final = 0
DEFAULT_WEEK_START: Final = 0  # Monday

PERIODS: Final = ("total", "day", "week", "month", "year")
STORE_VERSION: Final = 1
