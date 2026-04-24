"""DataUpdateCoordinator for the Livoltek integration."""
from __future__ import annotations
import datetime as dt
# from pvo import Livoltek, LivoltekAuthenticationError, LivoltekNoDataError, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
    CONF_USERTOKEN_ID,
    CONF_SITE_ID,
)

from requests.structures import CaseInsensitiveDict
from .helper import (
    async_get_api_client,
    async_get_site,
    async_get_cur_power_flow,
    async_get_device_list,
    async_get_energy_storage,
    async_get_energy_storage_direct,
    async_get_recent_grid,
    async_get_recent_solar,
)


class LivoltekDataUpdateCoordinator(DataUpdateCoordinator):
    """The Livoltek Data Update Coordinator."""

    config_entry: ConfigEntry
    hass: HomeAssistant
    access_token: str = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Livoltek coordinator."""
        self.livoltek = any
        self.hass = hass

        self.site = None
        self.devices = CaseInsensitiveDict({})
        self.current_power_flow = None
        self.energy_storage = None
        self.todays_grid = None
        self.todays_solar = None

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.config_entry = entry

    async def _async_update_data(self):
        """Fetch system status from Livoltek."""
        api_result = await async_get_api_client(self.config_entry, self.access_token)
        api = api_result[0]
        self.access_token = api_result[1]

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

        energy_storage = await async_get_energy_storage(
            api,
            self.config_entry.data[CONF_USERTOKEN_ID],
            self.config_entry.data[CONF_SITE_ID],
        )

        if energy_storage is None:
            LOGGER.debug(
                "Wrapper /ESS returned no data; falling back to direct /ESS fetch for site %s",
                self.config_entry.data[CONF_SITE_ID],
            )
            energy_storage = await async_get_energy_storage_direct(
                self.hass,
                api.api_client.configuration.host,
                self.config_entry.data[CONF_USERTOKEN_ID],
                self.config_entry.data[CONF_SITE_ID],
                self.access_token,
            )

        recent_grid = await async_get_recent_grid(
            api,
            self.config_entry.data[CONF_USERTOKEN_ID],
            self.config_entry.data[CONF_SITE_ID],
        )

        recent_solar = await async_get_recent_solar(
            api,
            self.config_entry.data[CONF_USERTOKEN_ID],
            self.config_entry.data[CONF_SITE_ID],
        )

        for grid in recent_grid:
            ts = dt.date.fromtimestamp(int(grid["ts"]) / 1000)
            if ts == dt.date.today():
                self.todays_grid = grid

        for solar in recent_solar:
            ts = dt.date.fromtimestamp(int(solar["ts"]) / 1000)
            if ts == dt.date.today():
                self.todays_solar = solar

        self.site = site
        self.devices = devices
        self.current_power_flow = current_power_flow
        self.energy_storage = energy_storage
        LOGGER.debug("Current Power Flow: %s", current_power_flow)
        LOGGER.debug("Energy Storage (/ESS): %s", energy_storage)
