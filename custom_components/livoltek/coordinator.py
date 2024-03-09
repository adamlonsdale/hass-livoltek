"""DataUpdateCoordinator for the Livoltek integration."""
from __future__ import annotations

# from pvo import Livoltek, LivoltekAuthenticationError, LivoltekNoDataError, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
    CONF_USERTOKEN_ID,
    CONF_SITE_ID,
)

from pylivoltek.models import DeviceList
from requests.structures import CaseInsensitiveDict
from .helper import (
    async_get_api_client,
    async_get_site,
    async_get_cur_power_flow,
    async_get_device_list,
    async_update_devices,
    validate_jwt,
)


class LivoltekDataUpdateCoordinator(DataUpdateCoordinator):
    """The Livoltek Data Update Coordinator."""

    config_entry: ConfigEntry
    hass: HomeAssistant
    access_token: str = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Livoltek coordinator."""
        self.config_entry = entry
        self.livoltek = any
        self.hass = hass

        self.site = None
        self.devices = CaseInsensitiveDict({})
        self.current_power_flow = None

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Fetch system status from Livoltek."""
        api = await async_get_api_client(self.config_entry, self.access_token)

        site = await async_get_site(
            api,
            self.config_entry.data[CONF_USERTOKEN_ID],
            self.config_entry.data[CONF_SITE_ID],
        )

        devices = await async_get_device_list(
            api,
            self.config_entry.data[CONF_USERTOKEN_ID],
            self.config_entry.data[CONF_SITE_ID],
        )

        current_power_flow = await async_get_cur_power_flow(
            api,
            self.config_entry.data[CONF_USERTOKEN_ID],
            self.config_entry.data[CONF_SITE_ID],
        )

        self.current_power_flow = current_power_flow[0].data
