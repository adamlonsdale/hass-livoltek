"""Livoltek API Helpers."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from pylivoltek import ApiClient, ApiLoginBody, Configuration
from pylivoltek.api import DefaultApi
from pylivoltek.models import (
    CurrentPowerFlow,
    DeviceDetails,
    DeviceList,
    EnergyStore,
    GridImportExportList,
    SiteOverview,
)
from pylivoltek.rest import ApiException

from .const import (
    API_REQUEST_TIMEOUT,
    CONF_EMEA_ID,
    CONF_SECUID_ID,
    CONF_SITE_ID,
    CONF_USERTOKEN_ID,
    DOMAIN,
    LIVOLTEK_EMEA_SERVER,
    LIVOLTEK_GLOBAL_SERVER,
    LOGGER,
)

# Refresh the login token this many seconds before it expires.
TOKEN_EXPIRY_MARGIN = 120


def validate_jwt(jwt: str) -> bool:
    """Return True while the cached login token can still be used.

    The previous implementation called ``PyJWT(jwt)``, which builds a decoder
    (with the token as its *options*) instead of decoding the token. That always
    raised, so the integration logged in again on every update. Here only the
    payload is read (we need the expiry, we do not trust or verify the claims)
    and the token is reused until shortly before ``exp``.
    """
    if not jwt or not isinstance(jwt, str):
        return False
    try:
        payload = jwt.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        exp = claims.get("exp")
        return exp is None or float(exp) - TOKEN_EXPIRY_MARGIN > time.time()
    except Exception as e:  # noqa: BLE001 - not a readable JWT (or odd exp): get a fresh one
        LOGGER.debug("Login token is not a readable JWT, refreshing: %s", e)
        return False


def _is_auth_error(err: Exception) -> bool:
    """Return True for 401/403, which the coordinator recovers from with a fresh login."""
    return getattr(err, "status", None) in (401, 403)


async def async_get_login_token(host: str, api_key: str, secuid: str) -> str:
    """Get the login token for the Livoltek API."""
    config = Configuration()

    config.host = host

    api_key = api_key.replace("\\r", "\r")
    api_key = api_key.replace("\\n", "\n")

    api_client = ApiClient(config)
    model = ApiLoginBody(secuid, api_key)
    api = DefaultApi(api_client)

    loop = asyncio.get_running_loop()
    thread_result = await loop.run_in_executor(
        None,
        lambda: api.hess_api_login_post_with_http_info(
            model,
            _preload_content=True,
            _request_timeout=API_REQUEST_TIMEOUT,
        ),
    )
    response = thread_result[0]

    if response.message != "SUCCESS":
        raise ConfigEntryAuthFailed(response.message)

    login_result = response.data

    if isinstance(login_result, dict):
        return login_result.get("data", "")

    return getattr(login_result, "data", "") or ""


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
        LOGGER.debug("Login token missing or about to expire, logging in again")
        token = await async_get_login_token(host, api_key, secuid)

    api_client = ApiClient(config)
    api_client.set_default_header("Authorization", token)
    return DefaultApi(api_client), token


async def async_get_site(
    api: DefaultApi, user_token: str, site_id: str
) -> SiteOverview:
    """Get the Livoltek API client."""

    loop = asyncio.get_running_loop()
    site = await loop.run_in_executor(
        None,
        lambda: api.hess_api_site_site_id_overview_get_with_http_info(
            user_token,
            site_id,
            _request_timeout=API_REQUEST_TIMEOUT,
        ),
    )
    return site[0].data


async def async_get_cur_power_flow(
    api: DefaultApi, user_token: str, site_id: str
) -> CurrentPowerFlow:
    """Get the Livoltek API client."""
    try:
        loop = asyncio.get_running_loop()
        current_power_flow = await loop.run_in_executor(
            None,
            lambda: api.hess_api_site_site_id_cur_powerflow_get_with_http_info(
                user_token,
                site_id,
                _request_timeout=API_REQUEST_TIMEOUT,
            ),
        )
        return current_power_flow[0].data
    except ApiException as e:
        if _is_auth_error(e):
            raise  # the coordinator retries once with a fresh login
        LOGGER.error("Error getting current power flow: %s", e)


async def async_get_device_list(
    api: DefaultApi, user_token: str, site_id: str
) -> DeviceList:
    """Get the Livoltek API client."""

    loop = asyncio.get_running_loop()
    device_list = await loop.run_in_executor(
        None,
        lambda: api.hess_api_device_site_id_list_get_with_http_info(
            user_token,
            site_id,
            1,
            10,
            _request_timeout=API_REQUEST_TIMEOUT,
        ),
    )
    # The API sometimes answers without a body (e.g. after a server-side timeout):
    # None lets the coordinator keep the previous list instead of crashing.
    return (device_list[0].data or {}).get("list")


async def async_get_energy_storage(
    api: DefaultApi, user_token: str, site_id: str
) -> EnergyStore | None:
    """Get energy storage information from the /ESS endpoint."""
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            # pylivoltek's signature is (user_token, site_id), like every other
            # endpoint. Passing them the other way round sent the site id as the
            # user token, so /ESS always answered 401 "token.invalid".
            lambda: api.get_energy_storage_with_http_info(
                user_token,
                site_id,
                _request_timeout=API_REQUEST_TIMEOUT,
            ),
        )

        if not result or not result[0]:
            return None

        return result[0].data
    except ApiException as e:
        if _is_auth_error(e):
            raise  # the coordinator retries once with a fresh login
        LOGGER.warning(
            "Failed to fetch energy storage data for site %s: %s", site_id, e
        )
        return None
    except asyncio.CancelledError:
        raise
    except Exception as e:
        LOGGER.warning(
            "Unexpected error fetching energy storage for site %s: %s", site_id, e
        )
        return None



async def async_get_energy_storage_direct(
    hass, host: str, user_token: str, site_id: str, auth_token: str
) -> dict[str, Any] | None:
    """Fetch /ESS directly, bypassing pylivoltek wrapper issues."""
    session = async_get_clientsession(hass)
    url = f"{host.rstrip('/')}/hess/api/site/{site_id}/ESS"

    try:
        async with session.get(
            url,
            params={"userToken": user_token},
            headers={
                "Authorization": auth_token,
                "Accept": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=API_REQUEST_TIMEOUT),
        ) as resp:
            resp.raise_for_status()
            payload = await resp.json()

        return payload.get("data")
    except asyncio.CancelledError:
        raise
    except aiohttp.ClientResponseError as e:
        if e.status in (401, 403):  # same as the wrapper: let the coordinator log in again
            raise ApiException(status=e.status, reason=e.message) from e
        LOGGER.warning("Direct /ESS fetch failed for site %s: %s", site_id, e)
        return None
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError) as e:
        LOGGER.warning(
            "Direct /ESS fetch failed for site %s: %s", site_id, e
        )
        return None


async def async_get_device_generation(
    api: DefaultApi, user_token: str, device_id: str
) -> Any:
    """Get the Livoltek API client."""

    loop = asyncio.get_running_loop()
    device_generation = await loop.run_in_executor(
        None,
        lambda: api.hess_api_device_device_id_real_electricity_get_with_http_info(
            user_token,
            device_id,
            _request_timeout=API_REQUEST_TIMEOUT,
        ),
    )
    return device_generation[0].data


async def async_get_recent_grid(
    api: DefaultApi, user_token: str, site_id: str
) -> GridImportExportList:
    """Get the Recent Grid Import/Export."""

    loop = asyncio.get_running_loop()
    recent_grid = await loop.run_in_executor(
        None,
        lambda: api.get_recent_energy_import_export_with_http_info(
            user_token,
            site_id,
            _request_timeout=API_REQUEST_TIMEOUT,
        ),
    )
    return recent_grid[0].get("data") or []


async def async_get_recent_solar(
    api: DefaultApi, user_token: str, site_id: str
) -> Any:
    """Get the Recent Solar Generation."""

    loop = asyncio.get_running_loop()
    recent_solar = await loop.run_in_executor(
        None,
        lambda: api.get_recent_solar_generated_energy_with_http_info(
            user_token,
            site_id,
            _request_timeout=API_REQUEST_TIMEOUT,
        ),
    )
    return recent_solar[0].get("data") or []


async def async_update_devices(entry: ConfigEntry, hass: HomeAssistant) -> None:
    """Update Livoltek devices."""

    api, _ = await async_get_api_client(entry)
    user_token = str(entry.data[CONF_USERTOKEN_ID])
    site_id = str(entry.data[CONF_SITE_ID])

    async with asyncio.timeout(API_REQUEST_TIMEOUT):
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
        inverter_sn = device["inverterSn"]
        async with asyncio.timeout(API_REQUEST_TIMEOUT):
            dev = await hass.async_add_executor_job(
                lambda sn=inverter_sn: api.get_device_details(
                    user_token,
                    site_id,
                    sn,
                    _preload_content=True,
                    _request_timeout=API_REQUEST_TIMEOUT,
                ).data
            )

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
