"""Tests for Livoltek helper functions."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.const import CONF_API_KEY

from custom_components.livoltek import helper
from custom_components.livoltek.const import (
    CONF_EMEA_ID,
    CONF_SECUID_ID,
    CONF_SITE_ID,
    CONF_USERTOKEN_ID,
    LIVOLTEK_EMEA_SERVER,
    LIVOLTEK_GLOBAL_SERVER,
)

from .common import build_device_details, make_thread


def test_validate_jwt_returns_true_for_decodable_token(monkeypatch) -> None:
    """A decodable JWT should be considered valid."""
    decode = Mock(return_value={"exp": 1})
    monkeypatch.setattr(helper, "PyJWT", decode)

    assert helper.validate_jwt({"header": "payload"}) is True
    decode.assert_called_once_with({"header": "payload"})


def test_validate_jwt_returns_false_on_decode_error(monkeypatch) -> None:
    """Any JWT decoding error should invalidate the token."""
    monkeypatch.setattr(helper, "PyJWT", Mock(side_effect=ValueError("bad token")))

    assert helper.validate_jwt("bad-token") is False


@pytest.mark.asyncio
async def test_async_get_api_client_reuses_valid_access_token(
    livoltek_entry,
    monkeypatch,
) -> None:
    """Valid tokens should be reused without logging in again."""

    class FakeApiClient:
        def __init__(self, config) -> None:
            self.config = config
            self.headers = {}

        def set_default_header(self, name: str, value: str) -> None:
            self.headers[name] = value

    class FakeDefaultApi:
        def __init__(self, api_client) -> None:
            self.api_client = api_client

    refresh = AsyncMock()
    monkeypatch.setattr(helper, "validate_jwt", Mock(return_value=True))
    monkeypatch.setattr(helper, "async_get_login_token", refresh)
    monkeypatch.setattr(helper, "ApiClient", FakeApiClient)
    monkeypatch.setattr(helper, "DefaultApi", FakeDefaultApi)

    api, token = await helper.async_get_api_client(livoltek_entry, "cached-token")

    assert token == "cached-token"
    assert api.api_client.config.host == LIVOLTEK_GLOBAL_SERVER
    assert api.api_client.headers["Authorization"] == "cached-token"
    refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_get_api_client_refreshes_invalid_token_on_emea(
    monkeypatch,
) -> None:
    """Invalid tokens should trigger a fresh login against the selected region."""
    entry = SimpleNamespace(
        data={
            CONF_API_KEY: "line1\\nline2",
            CONF_EMEA_ID: True,
            CONF_SECUID_ID: "secuid-456",
            CONF_SITE_ID: "site-123",
            CONF_USERTOKEN_ID: "user-token-123",
        }
    )

    class FakeApiClient:
        def __init__(self, config) -> None:
            self.config = config
            self.headers = {}

        def set_default_header(self, name: str, value: str) -> None:
            self.headers[name] = value

    class FakeDefaultApi:
        def __init__(self, api_client) -> None:
            self.api_client = api_client

    refresh = AsyncMock(return_value="fresh-token")
    monkeypatch.setattr(helper, "validate_jwt", Mock(return_value=False))
    monkeypatch.setattr(helper, "async_get_login_token", refresh)
    monkeypatch.setattr(helper, "ApiClient", FakeApiClient)
    monkeypatch.setattr(helper, "DefaultApi", FakeDefaultApi)

    api, token = await helper.async_get_api_client(entry, "stale-token")

    assert token == "fresh-token"
    assert api.api_client.config.host == LIVOLTEK_EMEA_SERVER
    assert api.api_client.headers["Authorization"] == "fresh-token"
    refresh.assert_awaited_once_with(
        LIVOLTEK_EMEA_SERVER,
        "line1\\nline2",
        "secuid-456",
    )


@pytest.mark.asyncio
async def test_async_update_devices_unpacks_api_result_before_fetching_list(
    livoltek_entry,
    monkeypatch,
) -> None:
    """Device updates should pass the API instance, not the helper tuple, downstream."""
    api = object()
    get_api_client = AsyncMock(return_value=(api, "token"))
    get_device_list = AsyncMock(return_value=[{"inverterSn": "INV-001"}])
    register_devices = AsyncMock()
    monkeypatch.setattr(helper, "async_get_api_client", get_api_client)
    monkeypatch.setattr(helper, "async_get_device_list", get_device_list)
    monkeypatch.setattr(helper, "async_register_devices", register_devices)

    await helper.async_update_devices(livoltek_entry, hass=object())

    get_device_list.assert_awaited_once_with(
        api,
        livoltek_entry.data[CONF_USERTOKEN_ID],
        livoltek_entry.data[CONF_SITE_ID],
    )
    register_devices.assert_awaited_once()
    assert register_devices.await_args.args[0] is api


@pytest.mark.asyncio
async def test_async_register_devices_creates_device_registry_entries(
    livoltek_entry,
    monkeypatch,
) -> None:
    """Each device in the API list should be added to Home Assistant's registry."""
    registry = Mock()
    monkeypatch.setattr(helper.dr, "async_get", Mock(return_value=registry))

    api = Mock()
    api.get_device_details.side_effect = [
        make_thread(SimpleNamespace(data=build_device_details(id="device-1"))),
        make_thread(SimpleNamespace(data=build_device_details(id="device-2"))),
    ]

    await helper.async_register_devices(
        api=api,
        entry=livoltek_entry,
        user_token="user-token-123",
        site_id="site-123",
        device_list=[{"inverterSn": "INV-001"}, {"inverterSn": "INV-002"}],
        hass=object(),
    )

    assert registry.async_get_or_create.call_count == 2
    first_call = registry.async_get_or_create.call_args_list[0]
    assert first_call.kwargs["config_entry_id"] == livoltek_entry.entry_id
    assert first_call.kwargs["identifiers"] == {("livoltek", "device-1")}


@pytest.mark.asyncio
async def test_async_get_hass_device_info_returns_expected_shape() -> None:
    """Device info should preserve the device metadata Home Assistant uses."""
    device = build_device_details(
        id="device-9",
        inverter_sn="INV-009",
        firmware_version="2.0.1",
    )

    result = await helper.async_get_hass_device_info(SimpleNamespace(), device)

    assert result["identifiers"] == {("livoltek", "device-9")}
    assert result["name"] == "INV-009"
    assert result["sw_version"] == "2.0.1"
