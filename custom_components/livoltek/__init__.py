"""The Livoltek integration."""
from __future__ import annotations
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_EMEA_ID,
    LIVOLTEK_EMEA_SERVER,
    LIVOLTEK_GLOBAL_SERVER,
    CONF_USERTOKEN_ID,
    CONF_SITE_ID,
)
from .coordinator import LivoltekDataUpdateCoordinator

from pylivoltek import ApiClient, ApiLoginBody, Configuration
from pylivoltek.api import DefaultApi
from pylivoltek.models import Site, DeviceDetails
from pylivoltek.rest import ApiException

from .helper import (
    async_update_devices,
    async_get_api_client,
    async_get_cur_power_flow,
    async_get_signal_device_status,
)
from homeassistant.util import Throttle

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Livoltek from a config entry."""
    coordinator = LivoltekDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Livoltek config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok

class LivoltekInverterDevice:
    """Representation of a Livoltek Inverter Device."""

    def __init__(
        self, api: DefaultApi, device: DeviceDetails, hass: HomeAssistant
    ) -> None:
        """Initialize the inverter device."""
        self._api = api
        self._device = device
        self._hass = hass

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Retrieve latest state."""
        await async_update_devices(self._api, self._hass)

    @property
    def device(self) -> DeviceDetails:
        """Return the device."""
        return self._device

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""

        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            manufacturer=self.device.device_manufacturer,
            name=self.device.inverter_sn,
            model=self.device.product_type,
            sw_version=self.device.firmware_version,
            serial_number=self.device.inverter_sn,
        )