"""DataUpdateCoordinator for the Livoltek integration."""
from __future__ import annotations

# from pvo import Livoltek, LivoltekAuthenticationError, LivoltekNoDataError, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SYSTEM_ID, DOMAIN, LOGGER, SCAN_INTERVAL, CONF_USERTOKEN_ID, CONF_SITE_ID
from .helper import async_get_api_client, async_get_site

class LivoltekDataUpdateCoordinator(DataUpdateCoordinator[any]):
    """The Livoltek Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Livoltek coordinator."""
        self.config_entry = entry
        self.Livoltek = any
        # Livoltek(
        #     api_key=entry.data[CONF_API_KEY],
        #     system_id=entry.data[CONF_SYSTEM_ID],
        #     session=async_get_clientsession(hass),
        # )

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> any:
        """Fetch system status from Livoltek."""
        # try:
        api = await async_get_api_client(self.config_entry)
        site = await async_get_site(api, self.config_entry.data[CONF_USERTOKEN_ID], self.config_entry.data[CONF_SITE_ID])
        print(site)
        return await self.Livoltek.status()
        # except LivoltekNoDataError as err:
        #     raise UpdateFailed("Livoltek has no data available") from err
        # except LivoltekAuthenticationError as err:
        #     raise ConfigEntryAuthFailed from err
