"""Config flow to configure the Livoltek integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pylivoltek.exceptions import *
from pylivoltek.apis.paths.hess_api_login import HessApiLogin
from pylivoltek.paths.hess_api_login.post.request_body.content.application_json.schema import (
    Schema,
)

import voluptuous as vol
import ast

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
)


async def validate_input(
    hass: HomeAssistant, *, secuid: str, api_key: str, emea: bool, user_token: str
) -> None:
    """Try using the give system id & api key against the Livoltek API."""
    session = async_get_clientsession(hass)

    livoltek = HessApiLogin()

    if emea:
        livoltek.api_client.configuration.host = LIVOLTEK_EMEA_SERVER
    else:
        livoltek.api_client.configuration.host = LIVOLTEK_GLOBAL_SERVER

    loginBody = Schema(key=api_key, secuid=secuid)
    loginResultStr = await hass.async_add_executor_job(livoltek.post(loginBody))
    loginResultObj = ast.literal_eval(loginResultStr[0].data)

    if not loginResultStr[0].message == "SUCCESS":
        raise ConfigEntryAuthFailed(loginResultObj["message"])

    token = loginResultObj["data"]

    userSites = await hass.async_create_task(
        livoltek.hess_api_user_sites_list_get(token, user_token)
    )
    print(userSites.count)


class LivoltekFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Livoltek."""

    VERSION = 1

    imported_name: str | None = None
    reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                await validate_input(
                    self.hass,
                    api_key=user_input[CONF_API_KEY],
                    secuid=user_input[CONF_SECUID_ID],
                    emea=user_input[CONF_EMEA_ID],
                    user_token=user_input[CONF_USERTOKEN_ID],
                )
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except ApiException:
                LOGGER.exception("Cannot connect to Livoltek")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(user_input[CONF_SITE_ID]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self.imported_name or str(user_input[CONF_SITE_ID]),
                    data={
                        CONF_SITE_ID: user_input[CONF_SITE_ID],
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "account_url": "https://Livoltek.org/account.jsp"
            },
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
                    vol.Required(
                        CONF_EMEA_ID, default=user_input.get(CONF_EMEA_ID, "")
                    ): bool,
                }
            ),
            errors=errors,
        )

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
                    self.hass,
                    api_key=user_input[CONF_API_KEY],
                    secuid=user_input[CONF_SECUID_ID],
                    emea=user_input[CONF_EMEA_ID],
                    user_token=user_input[CONF_USERTOKEN_ID],
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
