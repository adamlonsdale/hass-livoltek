"""DataUpdateCoordinator for the Livoltek integration."""
from __future__ import annotations
import datetime as dt
# from pvo import Livoltek, LivoltekAuthenticationError, LivoltekNoDataError, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
    CONF_USERTOKEN_ID,
    CONF_SITE_ID,
)

from pylivoltek.rest import ApiException
from requests.structures import CaseInsensitiveDict
from urllib3.exceptions import HTTPError
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
        """Fetch system status; a network outage or a server error is a normal failed update.

        Without DNS or with the portal down, urllib3 raises its own errors and the API
        returns 5xx: as UpdateFailed, Home Assistant logs it once and retries, instead of
        reporting "Unexpected error fetching livoltek data".
        """
        try:
            return await self._async_update_with_relogin()
        except ApiException as err:
            raise UpdateFailed(f"Livoltek API error: {err.status}") from err
        except (HTTPError, OSError) as err:
            raise UpdateFailed(f"Cannot reach Livoltek: {err}") from err

    async def _async_update_with_relogin(self):
        """Fetch system status from Livoltek.

        If the server rejects the cached login token (it can invalidate it before
        its expiry, e.g. after a login from the Livoltek app), drop it and retry
        once with a fresh one instead of failing the whole update.
        """
        try:
            return await self._async_fetch()
        except ApiException as err:
            if err.status not in (401, 403):
                raise
            LOGGER.debug("Livoltek rejected the login token (%s); retrying with a new one", err.status)
            self.access_token = None
            try:
                return await self._async_fetch()
            except ApiException as retry_err:
                if retry_err.status in (401, 403):  # a fresh login rejected too: ask the user to sign in again
                    raise ConfigEntryAuthFailed(f"Livoltek rejected a fresh login token: {retry_err.status}") from retry_err
                raise UpdateFailed(f"Livoltek update failed after a new login: {retry_err.status}") from retry_err

    async def _async_fetch(self):
        """One full read of the site, devices, power flow, storage and history."""
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

        # Only today's entry counts: without one (e.g. just after midnight) the
        # daily sensors have no value instead of keeping yesterday's reading.
        def today(entries):
            return next((e for e in entries if dt.date.fromtimestamp(int(e["ts"]) / 1000) == dt.date.today()), None)

        self.todays_grid = today(recent_grid)
        self.todays_solar = today(recent_solar)

        self.site = site
        if devices is not None:  # an empty answer keeps the devices we already know
            self.devices = devices
        self.current_power_flow = current_power_flow
        self.energy_storage = energy_storage
        LOGGER.debug("Current Power Flow: %s", current_power_flow)
        LOGGER.debug("Energy Storage (/ESS): %s", energy_storage)
