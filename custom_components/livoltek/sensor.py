"""Support for getting collected information from Livoltek."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SYSTEM_ID, DOMAIN
from .coordinator import LivoltekDataUpdateCoordinator


@dataclass
class LivoltekSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[any], int | float | None]


@dataclass
class LivoltekSensorEntityDescription(
    SensorEntityDescription, LivoltekSensorEntityDescriptionMixin
):
    """Describes a Livoltek sensor entity."""


SENSORS: tuple[LivoltekSensorEntityDescription, ...] = (
    LivoltekSensorEntityDescription(
        key="energy_consumption",
        name="Energy consumed",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_consumption,
    ),
    LivoltekSensorEntityDescription(
        key="energy_generation",
        name="Energy generated",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_generation,
    ),
    LivoltekSensorEntityDescription(
        key="normalized_output",
        name="Efficiency",
        native_unit_of_measurement=(
            f"{UnitOfEnergy.KILO_WATT_HOUR}/{UnitOfPower.KILO_WATT}"
        ),
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.normalized_output,
    ),
    LivoltekSensorEntityDescription(
        key="power_consumption",
        name="Power consumed",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.power_consumption,
    ),
    LivoltekSensorEntityDescription(
        key="power_generation",
        name="Power generated",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.power_generation,
    ),
    LivoltekSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.temperature,
    ),
    LivoltekSensorEntityDescription(
        key="voltage",
        name="Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.voltage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Livoltek sensors based on a config entry."""
    coordinator: LivoltekDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    system = await coordinator.Livoltek.system()

    async_add_entities(
        LivoltekSensorEntity(
            coordinator=coordinator,
            description=description,
            system_id=entry.data[CONF_SYSTEM_ID],
            system=system,
        )
        for description in SENSORS
    )


class LivoltekSensorEntity(
    CoordinatorEntity[LivoltekDataUpdateCoordinator], SensorEntity
):
    """Representation of a Livoltek sensor."""

    entity_description: LivoltekSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: LivoltekDataUpdateCoordinator,
        description: LivoltekSensorEntityDescription,
        system_id: str,
        system: any,
    ) -> None:
        """Initialize a Livoltek sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{system_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=f"https://Livoltek.org/list.jsp?sid={system_id}",
            identifiers={(DOMAIN, str(system_id))},
            manufacturer="Livoltek",
            model=system.inverter_brand,
            name=system.system_name,
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the device."""
        return self.entity_description.value_fn(self.coordinator.data)
