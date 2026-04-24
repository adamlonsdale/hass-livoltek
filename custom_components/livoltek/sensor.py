"""Support for Livoltek device sensors."""
from __future__ import annotations

from collections.abc import Callable
import dataclasses
from typing import Any

from pylivoltek.api import DefaultApi

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfEnergy

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_SITE_ID
from . import LivoltekInverterDevice, LivoltekDataUpdateCoordinator
from .entity import LivoltekEntity


@dataclasses.dataclass(frozen=True)
class LivoltekRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Any], float]
    enabled: Callable[[Any], bool]


@dataclasses.dataclass(frozen=True, kw_only=True)
class LivoltekSensorEntityDescription(
    SensorEntityDescription, LivoltekRequiredKeysMixin
):
    """Describes Livoltek sensor entity."""

def _get_pf(coordinator, attr: str, json_key: str):
    """Get a value from current_power_flow (works with dict or object)."""
    pf = coordinator.current_power_flow
    if pf is None:
        return None
    if isinstance(pf, dict):
        return pf.get(json_key)
    return getattr(pf, attr, None)

def _battery_soc(coordinator: Any) -> float | None:
    """Return battery SOC, preferring /ESS and falling back to curPowerflow."""
    ess = coordinator.energy_storage

    def _as_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, str) and value.lower() == "unknown":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    if ess is not None:
        value = None

        if isinstance(ess, dict):
            value = ess.get("current_soc")
            if _as_float(value) is None:
                value = ess.get("currentSoc")

            if _as_float(value) is None:
                history_map = ess.get("historyMap") or {}
                if isinstance(history_map, dict):
                    latest_ts = None
                    latest_soc = None
                    for bucket_key, bucket_values in history_map.items():
                        try:
                            bucket_ts = int(bucket_key)
                        except (TypeError, ValueError):
                            bucket_ts = -1
                        if not isinstance(bucket_values, list):
                            continue
                        for item in bucket_values:
                            if not isinstance(item, dict):
                                continue
                            soc = item.get("energySoc")
                            parsed_soc = _as_float(soc)
                            if parsed_soc is None:
                                continue
                            item_ts = item.get("time", bucket_ts)
                            try:
                                item_ts = int(item_ts)
                            except (TypeError, ValueError):
                                item_ts = bucket_ts
                            if latest_ts is None or item_ts >= latest_ts:
                                latest_ts = item_ts
                                latest_soc = parsed_soc
                    value = latest_soc
        else:
            value = getattr(ess, "current_soc", None)
            if _as_float(value) is None:
                value = getattr(ess, "currentSoc", None)

        parsed_soc = _as_float(value)
        if parsed_soc is not None:
            return parsed_soc

    if coordinator.current_power_flow is not None:
        value = _get_pf(coordinator, "energy_soc", "energySoc")
        return _as_float(value)

    return None

SENSORS = [
    LivoltekSensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        enabled=lambda x: x.energy_storage is not None or x.current_power_flow is not None,
        value_fn=_battery_soc,
    ),
    LivoltekSensorEntityDescription(
        key="power_grid_power",
        translation_key="power_grid_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        enabled=lambda x: x.current_power_flow is not None,
        value_fn=lambda x: _get_pf(x, "power_grid_power", "powerGridPower"),
    ),
    LivoltekSensorEntityDescription(
        key="pv_power",
        translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        enabled=lambda x: x.current_power_flow is not None,
        value_fn=lambda x: _get_pf(x, "pv_power", "pvPower"),
    ),
    LivoltekSensorEntityDescription(
        key="load_power",
        translation_key="load_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        enabled=lambda x: x.current_power_flow is not None,
        value_fn=lambda x: _get_pf(x, "load_power", "loadPower"),
    ),
    LivoltekSensorEntityDescription(
        key="energy_power",
        translation_key="energy_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        enabled=lambda x: x.current_power_flow is not None,
        value_fn=lambda x: _get_pf(x, "energy_power", "energyPower"),
    ),
    LivoltekSensorEntityDescription(
        key="grid_import_energy",
        translation_key="grid_import_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        enabled=lambda x: x.todays_grid["positive"] is not None,
        value_fn=lambda x: float(x.todays_grid["positive"]) if x.todays_grid else None,
    ),
    LivoltekSensorEntityDescription(
        key="grid_export_energy",
        translation_key="grid_export_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        enabled=lambda x: x.todays_grid["negative"] is not None,
        value_fn=lambda x: float(x.todays_grid["negative"]) if x.todays_grid else None,
    ),
    LivoltekSensorEntityDescription(
        key="solar_generation_energy",
        translation_key="solar_generation_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        enabled=lambda x: x.todays_solar["powerGeneration"] is not None,
        value_fn=lambda x: float(x.todays_solar["powerGeneration"])
        if x.todays_solar
        else None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Livoltek device sensors based on config_entry."""

    coordinator: LivoltekDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    site_id = entry.data[CONF_SITE_ID]

    entities: list[LivoltekValueSensor] = [
        LivoltekValueSensor(coordinator, site_id, description)
        for description in SENSORS
        if description.enabled(coordinator)
    ]

    async_add_entities(entities)


class LivoltekInverterSensor(SensorEntity):
    """Representation of a Livoltek Inverter Sensor."""

    entity_description: LivoltekSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        api: DefaultApi,
        device: LivoltekInverterDevice,
        description: LivoltekSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self._api = api
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.inverter_sn}-{device.id}-{description.key}"
        self._attr_device_info = {}

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._api)

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self._api.async_update()


class LivoltekValueSensor(LivoltekEntity, SensorEntity):
    """Representation of a Livoltek Value Sensor."""

    entity_description: LivoltekSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LivoltekDataUpdateCoordinator,
        site_id: str,
        description: LivoltekSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)

        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{site_id}-{description.key}"

        site_name = "Livoltek"
        if coordinator.site and hasattr(coordinator.site, "name") and coordinator.site.name:
            site_name = coordinator.site.name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, site_id)},
            manufacturer="Livoltek",
            name=site_name,
            entry_type=None,
        )

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)
