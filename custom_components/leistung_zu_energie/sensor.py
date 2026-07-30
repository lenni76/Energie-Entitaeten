"""Energy sensors for Leistung zu Energie."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_FRIENDLY_NAME, UnitOfEnergy, UnitOfPower
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

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
    METHOD_LEFT,
    METHOD_RIGHT,
    MODE_ABSOLUTE,
    MODE_POSITIVE,
    MODE_SIGNED,
    PERIODS,
    STORE_VERSION,
)

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=1)


@dataclass
class SourceEnergyData:
    """Persistent values for one source."""

    values: dict[str, float] = field(
        default_factory=lambda: {period: 0.0 for period in PERIODS}
    )
    period_keys: dict[str, str] = field(default_factory=dict)
    last_update: datetime | None = None
    last_power_w: float | None = None
    skipped_intervals: int = 0


class EnergyCoordinator(DataUpdateCoordinator[dict[str, SourceEnergyData]]):
    """Integrate multiple power sensors and maintain period counters."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{entry.entry_id}")
        self.entry = entry
        config = {**entry.data, **entry.options}
        self.sources: list[str] = list(config[CONF_SOURCE_ENTITIES])
        self.value_mode: str = config.get(CONF_VALUE_MODE, DEFAULT_MODE)
        self.method: str = config.get(CONF_INTEGRATION_METHOD, DEFAULT_METHOD)
        self.max_interval = timedelta(
            minutes=float(config.get(CONF_MAX_INTERVAL, DEFAULT_MAX_INTERVAL))
        )
        self.daily_reset_hour = int(
            config.get(CONF_DAILY_RESET_HOUR, DEFAULT_DAILY_RESET_HOUR)
        )
        self.week_start = int(config.get(CONF_WEEK_START, DEFAULT_WEEK_START))
        self.store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.data = {source: SourceEnergyData() for source in self.sources}
        self._unsubs: list[Any] = []

    async def async_start(self) -> None:
        """Restore data and start listeners."""
        stored = await self.store.async_load() or {}
        stored_sources = stored.get("sources", {})
        # Migrate the v1 single-source store layout.
        if not stored_sources and stored.get("values") and len(self.sources) == 1:
            stored_sources = {self.sources[0]: stored}

        now = dt_util.now()
        for source, source_data in self.data.items():
            raw = stored_sources.get(source, {})
            source_data.values.update(raw.get("values", {}))
            source_data.period_keys.update(raw.get("period_keys", {}))
            if last_update := raw.get("last_update"):
                source_data.last_update = dt_util.parse_datetime(last_update)
            source_data.last_power_w = raw.get("last_power_w")
            source_data.skipped_intervals = int(raw.get("skipped_intervals", 0))
            self._reset_changed_periods(source_data, now)
            source_data.last_update = now
            source_data.last_power_w = self._state_to_watts(
                self.hass.states.get(source)
            )

        await self._async_save()
        self._unsubs.append(
            async_track_state_change_event(
                self.hass, self.sources, self._async_source_changed
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_interval, UPDATE_INTERVAL
            )
        )
        self.async_set_updated_data(self.data)

    async def async_stop(self) -> None:
        """Stop listeners and save."""
        await self._async_process_all(dt_util.now())
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def _state_to_watts(self, state: State | None) -> float | None:
        """Convert a state to watts."""
        if state is None or state.state in {"unknown", "unavailable"}:
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        factors = {
            UnitOfPower.MILLIWATT: 0.001,
            UnitOfPower.WATT: 1.0,
            UnitOfPower.KILO_WATT: 1000.0,
            UnitOfPower.MEGA_WATT: 1_000_000.0,
        }
        factor = factors.get(state.attributes.get("unit_of_measurement"))
        return value * factor if factor is not None else None

    @callback
    def _effective_power(self, watts: float) -> float:
        """Apply negative-value handling."""
        if self.value_mode == MODE_ABSOLUTE:
            return abs(watts)
        if self.value_mode == MODE_SIGNED:
            return watts
        return max(0.0, watts)

    @callback
    def _period_reference(self, now: datetime) -> datetime:
        """Shift time so reset-hour boundaries become midnight."""
        return now - timedelta(hours=self.daily_reset_hour)

    @callback
    def _keys(self, now: datetime) -> dict[str, str]:
        """Return current period keys."""
        ref = self._period_reference(now)
        week_anchor = ref.date() - timedelta(
            days=(ref.weekday() - self.week_start) % 7
        )
        return {
            "day": ref.strftime("%Y-%m-%d"),
            "week": week_anchor.isoformat(),
            "month": ref.strftime("%Y-%m"),
            "year": ref.strftime("%Y"),
        }

    @callback
    def _reset_changed_periods(
        self, source_data: SourceEnergyData, now: datetime
    ) -> None:
        """Reset counters whose period changed."""
        for period, key in self._keys(now).items():
            if source_data.period_keys.get(period) != key:
                source_data.values[period] = 0.0
                source_data.period_keys[period] = key

    @callback
    def _interval_energy(
        self,
        previous_power: float,
        current_power: float | None,
        seconds: float,
    ) -> float:
        """Calculate kWh for an interval."""
        old = self._effective_power(previous_power)
        if self.method == METHOD_RIGHT and current_power is not None:
            power = self._effective_power(current_power)
        elif self.method not in {METHOD_LEFT, METHOD_RIGHT} and current_power is not None:
            power = (old + self._effective_power(current_power)) / 2
        else:
            power = old
        return power * seconds / 3_600_000

    async def _async_process_source(
        self, source: str, now: datetime, new_power_w: float | None = None
    ) -> None:
        """Process one source up to now."""
        source_data = self.data[source]
        previous_time = source_data.last_update
        previous_power = source_data.last_power_w

        if previous_time and previous_power is not None and now > previous_time:
            elapsed = now - previous_time
            if elapsed <= self.max_interval:
                energy = self._interval_energy(
                    previous_power, new_power_w, elapsed.total_seconds()
                )
                source_data.values["total"] += energy
                old_keys = self._keys(previous_time)
                new_keys = self._keys(now)
                for period in ("day", "week", "month", "year"):
                    if old_keys[period] == new_keys[period]:
                        source_data.values[period] += energy
                    else:
                        source_data.values[period] = 0.0
                        source_data.period_keys[period] = new_keys[period]
            else:
                source_data.skipped_intervals += 1

        self._reset_changed_periods(source_data, now)
        source_data.last_update = now
        # None intentionally marks the source unavailable and prevents
        # retroactive integration when it returns.
        source_data.last_power_w = new_power_w

    async def _async_process_all(self, now: datetime) -> None:
        for source in self.sources:
            await self._async_process_source(
                source, now, self._state_to_watts(self.hass.states.get(source))
            )
        await self._async_save()
        self.async_set_updated_data(self.data)

    async def _async_save(self) -> None:
        """Persist all counters."""
        payload: dict[str, Any] = {"sources": {}}
        for source, source_data in self.data.items():
            raw = asdict(source_data)
            raw["last_update"] = (
                source_data.last_update.isoformat()
                if source_data.last_update
                else None
            )
            payload["sources"][source] = raw
        await self.store.async_save(payload)

    async def _async_source_changed(self, event: Event) -> None:
        source = event.data["entity_id"]
        await self._async_process_source(
            source,
            dt_util.now(),
            self._state_to_watts(event.data.get("new_state")),
        )
        await self._async_save()
        self.async_set_updated_data(self.data)

    async def _async_interval(self, now: datetime) -> None:
        await self._async_process_all(now)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up energy sensors."""
    coordinator = EnergyCoordinator(hass, entry)
    await coordinator.async_start()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    entities: list[SensorEntity] = []
    for source in coordinator.sources:
        entities.extend(
            EnergySensor(hass, coordinator, entry, source, period)
            for period in PERIODS
        )
        entities.append(SourceStatusSensor(hass, coordinator, entry, source))
    async_add_entities(entities)


class EnergySensor(CoordinatorEntity[EnergyCoordinator], SensorEntity):
    """Energy counter sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: EnergyCoordinator,
        entry: ConfigEntry,
        source: str,
        period: str,
    ) -> None:
        super().__init__(coordinator)
        self.source = source
        self.period = period
        self._attr_unique_id = f"{entry.entry_id}_{source}_{period}"
        self._attr_translation_key = period
        self._attr_suggested_object_id = f"{slugify(source.split('.', 1)[-1])}_energie_{period}"
        self.device_entry = async_entity_id_to_device(hass, source)

    @property
    def state_class(self) -> SensorStateClass:
        return (
            SensorStateClass.TOTAL
            if self.coordinator.value_mode == MODE_SIGNED
            else SensorStateClass.TOTAL_INCREASING
        )

    @property
    def native_value(self) -> Decimal:
        return Decimal(str(round(self.coordinator.data[self.source].values[self.period], 6)))

    @property
    def available(self) -> bool:
        state = self.hass.states.get(self.source)
        return state is not None and state.state not in {"unknown", "unavailable"}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "value_mode": self.coordinator.value_mode,
            "integration_method": self.coordinator.method,
            "period_key": self.coordinator.data[self.source].period_keys.get(
                self.period
            ),
        }


class SourceStatusSensor(CoordinatorEntity[EnergyCoordinator], SensorEntity):
    """Diagnostic source status sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_icon = "mdi:information-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: EnergyCoordinator,
        entry: ConfigEntry,
        source: str,
    ) -> None:
        super().__init__(coordinator)
        self.source = source
        self._attr_unique_id = f"{entry.entry_id}_{source}_status"
        self._attr_suggested_object_id = f"{slugify(source.split('.', 1)[-1])}_energie_status"
        self.device_entry = async_entity_id_to_device(hass, source)

    @property
    def native_value(self) -> str:
        state = self.hass.states.get(self.source)
        return "available" if state and state.state not in {"unknown", "unavailable"} else "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.hass.states.get(self.source)
        return {
            "source": self.source,
            "source_name": state.attributes.get(ATTR_FRIENDLY_NAME) if state else None,
            "source_unit": state.attributes.get("unit_of_measurement") if state else None,
            "last_update": self.coordinator.data[self.source].last_update,
            "last_power_w": self.coordinator.data[self.source].last_power_w,
            "skipped_intervals": self.coordinator.data[self.source].skipped_intervals,
            "max_interval_minutes": self.coordinator.max_interval.total_seconds() / 60,
            "daily_reset_hour": self.coordinator.daily_reset_hour,
            "week_start": self.coordinator.week_start,
        }
