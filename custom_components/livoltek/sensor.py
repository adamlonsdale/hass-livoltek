"""Support for Livoltek device sensors."""
from __future__ import annotations

from collections.abc import Callable
import dataclasses
from typing import Any

from pylivoltek.models import DeviceDetails, Site
from pylivoltek.api import DefaultApi

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfTemperature,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .helper import async_get_api_client
from .const import DOMAIN, CONF_SITE_ID
from . import LivoltekInverterDevice


@dataclasses.dataclass(frozen=True)
class LivoltekRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Any], float]
    enabled: Callable[[Any], bool]


@dataclasses.dataclass(frozen=True)
class LivoltekSensorEntityDescription(
    SensorEntityDescription, LivoltekRequiredKeysMixin
):
    """Describes Livoltek sensor entity."""


SENSORS = [
    LivoltekSensorEntityDescription(
        key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        enabled=lambda x: x.current_power_flow is not None,
        value_fn=lambda x: x.current_power_flow.energy_soc
        if x.current_power_flow
        else None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Livoltek device sensors based on config_entry."""
    site_id = entry.data[CONF_SITE_ID]
    api = await async_get_api_client(entry)

    entities: list[LivoltekValueSensor] = [
        LivoltekValueSensor(api, site_id, description) for description in SENSORS
    ]

    async_add_entities(entities, True)


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


class LivoltekValueSensor(SensorEntity):
    """Representation of a Livoltek Value Sensor."""

    entity_description: LivoltekSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        api: DefaultApi,
        site_id: str,
        description: LivoltekSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self._api = api
        self.entity_description = description
        self._attr_unique_id = f"{site_id}-{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._api)

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self._api.async_update()
