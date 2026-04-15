"""Tests for the Livoltek config flow."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.const import CONF_API_KEY
from homeassistant.exceptions import ConfigEntryAuthFailed

from pylivoltek import ApiClient, ApiLoginBody, Configuration
from pylivoltek.api import DefaultApi

from custom_components.livoltek.config_flow import LivoltekFlowHandler
from custom_components.livoltek.const import (
    API_REQUEST_TIMEOUT,
    CONF_EMEA_ID,
    CONF_SECUID_ID,
    CONF_SITE_ID,
    CONF_USERTOKEN_ID,
    DOMAIN,
    LIVOLTEK_EMEA_SERVER,
    LIVOLTEK_GLOBAL_SERVER,
)


@pytest.mark.asyncio
async def test_user_flow_creates_entry_after_site_selection(hass) -> None:
    """The user flow should validate credentials and create an entry."""
    user_input = {
        CONF_API_KEY: "api-key",
        CONF_EMEA_ID: False,
        CONF_SECUID_ID: "secuid-123",
        CONF_USERTOKEN_ID: "user-token-123",
    }
    sites = [{"powerStationId": "site-123", "powerStationName": "Home"}]

    with (
        patch(
            "custom_components.livoltek.config_flow.validate_input",
            AsyncMock(return_value="access-token"),
        ),
        patch.object(
            LivoltekFlowHandler,
            "get_sites",
            AsyncMock(return_value=sites),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=user_input,
        )

        assert result["type"] == "form"
        assert result["step_id"] == "select_site"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SITE_ID: "site-123"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Livoltek"
    assert result["data"][CONF_SITE_ID] == "site-123"


@pytest.mark.asyncio
async def test_user_flow_reports_invalid_auth(hass) -> None:
    """The user flow should surface invalid credentials as a form error."""
    with patch(
        "custom_components.livoltek.config_flow.validate_input",
        AsyncMock(side_effect=ConfigEntryAuthFailed("invalid_auth")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={
                CONF_API_KEY: "bad",
                CONF_EMEA_ID: False,
                CONF_SECUID_ID: "bad",
                CONF_USERTOKEN_ID: "bad",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


def test_get_site_list_returns_selector_options() -> None:
    """The site helper should convert API results into selector options."""
    flow = LivoltekFlowHandler()

    result = flow.get_site_list(
        [
            {"powerStationId": "site-1", "powerStationName": "House"},
            {"powerStationId": "site-2", "powerStationName": "Garage"},
        ]
    )

    assert result == [
        {"value": "site-1", "label": "House"},
        {"value": "site-2", "label": "Garage"},
    ]


@pytest.mark.asyncio
async def test_get_sites_sets_request_timeout(monkeypatch) -> None:
    """Site listing should use the integration HTTP timeout."""

    class FakeApiClient:
        def __init__(self, config) -> None:
            self.config = config
            self.headers = {}

        def set_default_header(self, name: str, value: str) -> None:
            self.headers[name] = value

    class FakeDefaultApi:
        def __init__(self, api_client) -> None:
            self.api_client = api_client

        def list_sites(self, user_token, **kwargs):
            assert user_token == "user-token"
            assert kwargs["_preload_content"] is True
            assert kwargs["_request_timeout"] == API_REQUEST_TIMEOUT
            return [
                SimpleNamespace(
                    data=SimpleNamespace(
                        list=[
                            {
                                "powerStationId": "site-123",
                                "powerStationName": "Home",
                            }
                        ]
                    )
                )
            ]

    monkeypatch.setattr("custom_components.livoltek.config_flow.ApiClient", FakeApiClient)
    monkeypatch.setattr("custom_components.livoltek.config_flow.DefaultApi", FakeDefaultApi)

    flow = LivoltekFlowHandler()
    sites = await flow.get_sites("https://example.com", "access-token", "user-token")

    assert sites == [{"powerStationId": "site-123", "powerStationName": "Home"}]


@pytest.mark.asyncio
@pytest.mark.live
async def test_live_credentials_can_authenticate(
    livoltek_live_credentials,
) -> None:
    """Opt-in smoke test against the real Livoltek login endpoint."""
    host = (
        LIVOLTEK_EMEA_SERVER
        if livoltek_live_credentials.emea
        else LIVOLTEK_GLOBAL_SERVER
    )

    config = Configuration()
    config.host = host
    api = DefaultApi(ApiClient(config))
    model = ApiLoginBody(
        livoltek_live_credentials.secuid,
        livoltek_live_credentials.api_key,
    )
    response = api.login(model, async_req=True, _preload_content=True).get()

    assert response.message == "SUCCESS"
