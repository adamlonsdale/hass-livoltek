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


SENSORS = [
    LivoltekSensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        enabled=lambda x: x.current_power_flow is not None,
        value_fn=lambda x: x.current_power_flow.energy_soc
        if x.current_power_flow
        else None,
    ),
    LivoltekSensorEntityDescription(
        key="power_grid_power",
        translation_key="power_grid_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        enabled=lambda x: x.current_power_flow is not None,
        value_fn=lambda x: x.current_power_flow.power_grid_power
        if x.current_power_flow
        else None,
    ),
    LivoltekSensorEntityDescription(
        key="pv_power",
        translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        enabled=lambda x: x.current_power_flow is not None,
        value_fn=lambda x: x.current_power_flow.pv_power
        if x.current_power_flow
        else None,
    ),
    LivoltekSensorEntityDescription(
        key="load_power",
        translation_key="load_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        enabled=lambda x: x.current_power_flow is not None,
        value_fn=lambda x: x.current_power_flow.load_power
        if x.current_power_flow
        else None,
    ),
    LivoltekSensorEntityDescription(
        key="energy_power",
        translation_key="energy_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        enabled=lambda x: x.current_power_flow is not None,
        value_fn=lambda x: x.current_power_flow.energy_power
        if x.current_power_flow
        else None,
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

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)
