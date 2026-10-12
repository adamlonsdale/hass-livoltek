"""Tests for Livoltek helper functions."""
from __future__ import annotations

import base64
import json
import time
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

from .common import build_device_details


def _jwt(payload) -> str:
    """Build a JWT-shaped token (unsigned: validate_jwt only reads the payload)."""
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{enc({'alg': 'HS256', 'typ': 'JWT'})}.{enc(payload)}.c2lnbmF0dXJl"


def test_validate_jwt_reuses_token_until_shortly_before_expiry() -> None:
    """A token is reused while it is valid and refreshed shortly before it expires."""
    assert helper.validate_jwt(_jwt({"exp": time.time() + 3600})) is True
    assert helper.validate_jwt(_jwt({"exp": time.time() + 30})) is False  # inside the margin
    assert helper.validate_jwt(_jwt({"exp": time.time() - 10})) is False  # expired


def test_validate_jwt_without_exp_is_reused() -> None:
    """Without an exp claim the backend decides; a 401 triggers a fresh login."""
    assert helper.validate_jwt(_jwt({"sub": "user"})) is True


@pytest.mark.parametrize(
    "token",
    ["", None, "bad-token", "a.b.c", _jwt({"exp": "soon"}), _jwt(None), {"header": "payload"}],
)
def test_validate_jwt_rejects_unreadable_tokens(token) -> None:
    """Missing, malformed or odd tokens trigger a fresh login instead of raising."""
    assert helper.validate_jwt(token) is False


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
async def test_async_get_login_token_sets_request_timeout(monkeypatch) -> None:
    """Login requests should use the integration HTTP timeout."""

    class FakeApiClient:
        def __init__(self, config) -> None:
            self.config = config

    class FakeDefaultApi:
        def __init__(self, api_client) -> None:
            self.api_client = api_client

        def hess_api_login_post_with_http_info(self, model, **kwargs):
            assert kwargs["_preload_content"] is True
            assert kwargs["_request_timeout"] == helper.API_REQUEST_TIMEOUT
            return (SimpleNamespace(message="SUCCESS", data={"data": "token"}),)

    monkeypatch.setattr(helper, "ApiClient", FakeApiClient)
    monkeypatch.setattr(helper, "DefaultApi", FakeDefaultApi)

    token = await helper.async_get_login_token(
        LIVOLTEK_GLOBAL_SERVER,
        "api-key",
        "secuid-123",
    )

    assert token == "token"


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
        SimpleNamespace(data=build_device_details(id="device-1")),
        SimpleNamespace(data=build_device_details(id="device-2")),
    ]
    hass = Mock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda job: job())

    await helper.async_register_devices(
        api=api,
        entry=livoltek_entry,
        user_token="user-token-123",
        site_id="site-123",
        device_list=[{"inverterSn": "INV-001"}, {"inverterSn": "INV-002"}],
        hass=hass,
    )

    assert registry.async_get_or_create.call_count == 2
    first_call = registry.async_get_or_create.call_args_list[0]
    assert first_call.kwargs["config_entry_id"] == livoltek_entry.entry_id
    assert first_call.kwargs["identifiers"] == {("livoltek", "device-1")}
    assert api.get_device_details.call_args_list[0].kwargs["_request_timeout"] == (
        helper.API_REQUEST_TIMEOUT
    )


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


@pytest.mark.asyncio
async def test_async_get_energy_storage_returns_data_on_success() -> None:
    """async_get_energy_storage should return the EnergyStore data on a successful call."""
    ess_data = SimpleNamespace(current_soc=75.0, battery_sn="BAT-001")

    api = Mock()
    api.get_energy_storage_with_http_info.return_value = (
        SimpleNamespace(data=ess_data),
    )

    result = await helper.async_get_energy_storage(api, "user-token", "site-123")

    assert result is ess_data
    call = api.get_energy_storage_with_http_info.call_args
    # pylivoltek's signature is (user_token, site_id), like every other endpoint
    assert call.args == ("user-token", "site-123")
    assert call.kwargs["_request_timeout"] == helper.API_REQUEST_TIMEOUT


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_async_get_energy_storage_reraises_auth_errors(status) -> None:
    """A rejected token must reach the coordinator so it can log in again."""
    from pylivoltek.rest import ApiException

    api = Mock()
    api.get_energy_storage_with_http_info.side_effect = ApiException(status=status)

    with pytest.raises(ApiException):
        await helper.async_get_energy_storage(api, "user-token", "site-123")


@pytest.mark.asyncio
async def test_empty_api_answers_do_not_crash() -> None:
    """A response without a body (seen after server-side timeouts) must not raise."""
    api = Mock()
    api.hess_api_device_site_id_list_get_with_http_info.return_value = (SimpleNamespace(data=None),)
    api.get_recent_energy_import_export_with_http_info.return_value = ({"data": None},)
    api.get_recent_solar_generated_energy_with_http_info.return_value = ({"code": "500"},)

    assert await helper.async_get_device_list(api, "user-token", "site-123") is None
    assert await helper.async_get_recent_grid(api, "user-token", "site-123") == []
    assert await helper.async_get_recent_solar(api, "user-token", "site-123") == []


@pytest.mark.asyncio
async def test_async_get_energy_storage_returns_none_on_api_exception(
    monkeypatch,
) -> None:
    """async_get_energy_storage should return None and log a warning when the API fails."""
    from pylivoltek.rest import ApiException

    api = Mock()
    api.get_energy_storage_with_http_info.side_effect = ApiException(status=404)

    result = await helper.async_get_energy_storage(api, "user-token", "site-123")

    assert result is None

