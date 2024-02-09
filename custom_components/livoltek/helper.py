"""Livoltek API Helpers."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_API_KEY

from .const import DOMAIN, PLATFORMS, CONF_EMEA_ID, LIVOLTEK_EMEA_SERVER, LIVOLTEK_GLOBAL_SERVER, CONF_SECUID_ID, CONF_USERTOKEN_ID

from pylivoltek import ApiClient, ApiLoginBody, Configuration
from pylivoltek.api import DefaultApi
from pylivoltek.models import Site
from pylivoltek.rest import ApiException

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

async def async_get_login_token(host: str, api_key: str, secuid: str) -> str:
    """Get the login token for the Livoltek API."""
    config = Configuration()
    config.host = host

    api_key = api_key.replace("\\r", "\r")
    api_key = api_key.replace("\\n", "\n")

    api_client = ApiClient(config)
    model = ApiLoginBody(secuid, api_key)
    api = DefaultApi(api_client)

    thread = api.hess_api_login_post_with_http_info(model, async_req=True, _preload_content=True)
    threadResult = thread.get()
    loginResultObj = threadResult[0].data

    if not threadResult[0].message == "SUCCESS":
        raise ConfigEntryAuthFailed(threadResult[0].message)

    return loginResultObj["data"]

async def async_get_api_client(entry: ConfigEntry) -> DefaultApi:
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

    token = await async_get_login_token(host, api_key, secuid)

    api_client = ApiClient(config)
    api_client.set_default_header("Authorization", token)
    print("token: " + token)
    return DefaultApi(api_client)


async def async_get_site(api: DefaultApi, user_token: str, site_id: str) -> Site:
    """Get the Livoltek API client."""

    print (api.api_client.configuration.host)
    print (api.api_client.default_headers)
    print ("user_token: " + user_token)
    thread = api.hess_api_site_site_id_overview_get_with_http_info(user_token, site_id, async_req=True)
    site = thread.get()
    print(site)
    return site