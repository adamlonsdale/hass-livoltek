"""Tests for the Livoltek config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.const import CONF_API_KEY
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.livoltek.config_flow import LivoltekFlowHandler
from custom_components.livoltek.const import (
    CONF_EMEA_ID,
    CONF_SECUID_ID,
    CONF_SITE_ID,
    CONF_USERTOKEN_ID,
    DOMAIN,
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
