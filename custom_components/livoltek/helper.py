"""Livoltek API Helpers."""

from __future__ import annotations
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import device_registry as dr
from homeassistant.auth.jwt_wrapper import PyJWT

from .const import (
    DOMAIN,
    CONF_EMEA_ID,
    LIVOLTEK_EMEA_SERVER,
    LIVOLTEK_GLOBAL_SERVER,
    CONF_SECUID_ID,
    CONF_USERTOKEN_ID,
    CONF_SITE_ID,
    LOGGER,
)

from pylivoltek import ApiClient, ApiLoginBody, Configuration
from pylivoltek.api import DefaultApi
from pylivoltek.rest import ApiException
from pylivoltek.models import (
    Site,
    CurrentPowerFlow,
    DeviceList,
    DeviceDetails,
    GridImportExportList,
    SolarGenerationtList,
)
from homeassistant.helpers.device_registry import DeviceInfo

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
)


def validate_jwt(jwt: str) -> bool:
    """Validate a JWT token."""
    try:
        PyJWT(jwt)
        return True
    except Exception as e:
        LOGGER.info("Invalid JWT token: %s", e)
        return False


async def async_get_login_token(host: str, api_key: str, secuid: str) -> str:
    """Get the login token for the Livoltek API."""
    config = Configuration()
    config.host = host

    api_key = api_key.replace("\\r", "\r")
    api_key = api_key.replace("\\n", "\n")

    api_client = ApiClient(config)
    model = ApiLoginBody(secuid, api_key)
    api = DefaultApi(api_client)

    thread = api.hess_api_login_post_with_http_info(
        model, async_req=True, _preload_content=True
    )
    threadResult = thread.get()
    loginResultObj = threadResult[0].data

    if not threadResult[0].message == "SUCCESS":
        raise ConfigEntryAuthFailed(threadResult[0].message)

    return loginResultObj["data"]


async def async_get_api_client(
    entry: ConfigEntry, access_token: str = None
) -> tuple[DefaultApi, str]:
    """Get the Livoltek API client."""
    config = Configuration()

    emea = bool(entry.data[CONF_EMEA_ID])
    secuid = str(entry.data[CONF_SECUID_ID])
    api_key = str(entry.data[CONF_API_KEY])

    if emea:
        host = LIVOLTEK_EMEA_SERVER
    else:
        host = LIVOLTEK_GLOBAL_SERVER
    config.host = host

    if access_token is None:
        access_token = ""

    if validate_jwt(access_token):
        token = access_token
    else:
        LOGGER.info("Invalid JWT token, refreshing")
        token = await async_get_login_token(host, api_key, secuid)

    api_client = ApiClient(config)
    api_client.set_default_header("Authorization", token)
    return DefaultApi(api_client), token


async def async_get_site(api: DefaultApi, user_token: str, site_id: str) -> Site:
    """Get the Livoltek API client."""

    thread = api.hess_api_site_site_id_overview_get_with_http_info(
        user_token, site_id, async_req=True
    )
    site = thread.get()
    return site


async def async_get_cur_power_flow(
    api: DefaultApi, user_token: str, site_id: str
) -> CurrentPowerFlow:
    """Get the Livoltek API client."""
    try:
        thread = api.hess_api_site_site_id_cur_powerflow_get_with_http_info(
            user_token, site_id, async_req=True
        )
        current_power_flow = thread.get()
        return current_power_flow
    except ApiException as e:
        LOGGER.error("Error getting current power flow: %s", e)


async def async_get_device_list(
    api: DefaultApi, user_token: str, site_id: str
) -> DeviceList:
    """Get the Livoltek API client."""

    thread = api.hess_api_device_site_id_list_get_with_http_info(
        user_token, site_id, 1, 10, async_req=True
    )
    device_list = thread.get()
    return device_list[0].data["list"]


async def async_get_device_generation(
    api: DefaultApi, user_token: str, device_id: str
) -> DeviceList:
    """Get the Livoltek API client."""

    thread = api.hess_api_device_device_id_real_electricity_get_with_http_info(
        user_token, device_id, async_req=True
    )
    device_generation = thread.get()
    return device_generation[0]


async def async_get_recent_grid(
    api: DefaultApi, user_token: str, site_id: str
) -> GridImportExportList:
    """Get the Recent Grid Import/Export."""

    thread = api.get_recent_energy_import_export_with_http_info(
        user_token, site_id, async_req=True
    )
    recent_grid = thread.get()
    return recent_grid[0]["data"]


async def async_get_recent_solar(
    api: DefaultApi, user_token: str, site_id: str
) -> SolarGenerationtList:
    """Get the Recent Solar Generation."""

    thread = api.get_recent_solar_generated_energy_with_http_info(
        user_token, site_id, async_req=True
    )
    recent_solar = thread.get()
    return recent_solar[0]["data"]


async def async_update_devices(entry: ConfigEntry, hass: HomeAssistant) -> None:
    """Update Livoltek devices."""

    api = await async_get_api_client(entry)
    user_token = str(entry.data[CONF_USERTOKEN_ID])
    site_id = str(entry.data[CONF_SITE_ID])

    async with asyncio.timeout(10):
        device_list = await async_get_device_list(api, user_token, site_id)

    await async_register_devices(api, entry, user_token, site_id, device_list, hass)


async def async_register_devices(
    api: DefaultApi,
    entry: ConfigEntry,
    user_token: str,
    site_id: str,
    device_list: DeviceList,
    hass: HomeAssistant,
) -> None:
    """Register Livoltek devices."""
    device_registry = dr.async_get(hass)

    for device in device_list:
        async with asyncio.timeout(10):
            thread = api.get_device_details(
                user_token,
                site_id,
                device["inverterSn"],
                async_req=True,
                _preload_content=True,
            )
            dev = thread.get().data

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, dev.id)},
            manufacturer=dev.device_manufacturer,
            name=dev.inverter_sn,
            model=dev.product_type,
            serial_number=dev.inverter_sn,
            sw_version=dev.firmware_version,
        )


async def async_get_hass_device_info(
    entry: ConfigEntry, device: DeviceDetails
) -> DeviceInfo:
    """Get device info for Home Assistant."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.id)},
        manufacturer=device.device_manufacturer,
        name=device.inverter_sn,
        model=device.product_type,
        sw_version=device.firmware_version,
        serial_number=device.inverter_sn,
    )
