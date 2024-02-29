"""Config flow to configure the Livoltek integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Optional

from pylivoltek import ApiClient, ApiLoginBody, Configuration
from pylivoltek.api import DefaultApi
from pylivoltek.models import Site
from pylivoltek.rest import ApiException

import voluptuous as vol
import ast
import json

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .helper import async_get_login_token

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .const import (
    CONF_SECUID_ID,
    CONF_EMEA_ID,
    CONF_SITE_ID,
    CONF_USERTOKEN_ID,
    DOMAIN,
    LOGGER,
    LIVOLTEK_EMEA_SERVER,
    LIVOLTEK_GLOBAL_SERVER,
    DEFAULT_NAME,
)


async def validate_input(secuid: str, api_key: str, emea: bool) -> str:
    """Try using the give system id & api key against the Livoltek API."""

    if emea:
        host = LIVOLTEK_EMEA_SERVER
    else:
        host = LIVOLTEK_GLOBAL_SERVER

    api_key = api_key.replace("\\r", "\r")
    api_key = api_key.replace("\\n", "\n")

    token = await async_get_login_token(host, api_key, secuid)

    # Check token is not empty
    if not token:
        raise ConfigEntryAuthFailed("empty_token")

    return token

class LivoltekFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Livoltek."""

    VERSION = 1

    imported_name: str | None = None
    reauth_entry: ConfigEntry | None = None

    data: Optional[Dict[str, Any]]
    access_token: str

    async def get_sites(
        self, host: str, access_token: str, user_token: str
    ) -> list[Site]:
        """Get the login token for the Livoltek API."""
        config = Configuration()
        config.host = host

        api_client = ApiClient(config)
        api_client.set_default_header("Authorization", access_token)
        api = DefaultApi(api_client)

        thread = api.hess_api_user_sites_list_get_with_http_info(
            user_token, size=10, page=1, async_req=True, _preload_content=True
        )
        user_sites = thread.get()
        return user_sites[0].data.list

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                self.access_token = await validate_input(
                    api_key=user_input[CONF_API_KEY],
                    secuid=user_input[CONF_SECUID_ID],
                    emea=user_input[CONF_EMEA_ID],
                )
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except ApiException:
                LOGGER.exception("Cannot connect to Livoltek")
                errors["base"] = "cannot_connect"
            else:
                if not errors:
                    self.data = user_input
                    self.data[CONF_SITE_ID] = None
                    return await self.async_step_select_site()
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            description_placeholders={"account_url": "https://livoltek-portal.com/#/"},
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
                    ): str,
                    vol.Required(
                        CONF_SECUID_ID, default=user_input.get(CONF_SECUID_ID, "")
                    ): str,
                    vol.Required(
                        CONF_USERTOKEN_ID, default=user_input.get(CONF_USERTOKEN_ID, "")
                    ): str,
                    vol.Optional(
                        CONF_EMEA_ID, default=user_input.get(CONF_EMEA_ID, "")
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_select_site(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to select a site."""
        errors = {}

        if user_input is not None:
            try:
                if user_input[CONF_SITE_ID] == "":
                    raise ConfigEntryAuthFailed("empty_site")
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except ApiException:
                LOGGER.exception("Cannot connect to Livoltek")
                errors["base"] = "cannot_connect"
            else:
                if not errors:
                    self.data[CONF_SITE_ID] = user_input[CONF_SITE_ID]

                    await self.async_set_unique_id(str(self.data[CONF_SITE_ID]))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=self.imported_name or DEFAULT_NAME, data=self.data
                    )
        else:
            emea = bool(self.data[CONF_EMEA_ID])
            if emea:
                host = LIVOLTEK_EMEA_SERVER
            else:
                host = LIVOLTEK_GLOBAL_SERVER

            sites = await self.get_sites(
                host, self.access_token, self.data[CONF_USERTOKEN_ID]
            )
            user_input = {}

        return self.async_show_form(
            step_id="select_site",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SITE_ID, default=user_input.get(CONF_SITE_ID, "")
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=(self.get_site_list(sites)),
                            mode=SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    def get_site_list(
        self,
        site_results: list[Site],
    ) -> list[SelectOptionDict]:
        """Return a set of nearby sensors as SelectOptionDict objects."""

        return [
            SelectOptionDict(
                value=str(result["powerStationId"]),
                label=str(result["powerStationName"]),
            )
            for result in site_results
        ]

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle initiation of re-authentication with Livoltek."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication with Livoltek."""
        errors = {}

        if user_input is not None and self.reauth_entry:
            try:
                await validate_input(
                    secuid=user_input[CONF_SECUID_ID],
                    api_key=user_input[CONF_API_KEY],
                    emea=user_input[CONF_EMEA_ID],
                )
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except ApiException:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry,
                    data={
                        **self.reauth_entry.data,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                "account_url": "https://Livoltek.org/account.jsp"
            },
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )
