"""Tests for the Livoltek data update coordinator."""
from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock

import pytest

from custom_components.livoltek.coordinator import LivoltekDataUpdateCoordinator

from .common import build_energy_storage, build_power_flow, midday_timestamp_ms


@pytest.mark.asyncio
async def test_async_update_data_populates_coordinator_state(
    hass,
    livoltek_entry,
    monkeypatch,
) -> None:
    """Coordinator refreshes should map helper responses onto HA-facing state."""
    coordinator = LivoltekDataUpdateCoordinator(hass, livoltek_entry)
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    power_flow = build_power_flow()
    energy_storage = build_energy_storage()

    get_api_client = AsyncMock(return_value=(object(), "access-token"))
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_api_client",
        get_api_client,
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_site",
        AsyncMock(return_value={"name": "Home Site"}),
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_device_list",
        AsyncMock(return_value={"device-1": {"name": "Inverter"}}),
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_cur_power_flow",
        AsyncMock(return_value=power_flow),
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_energy_storage",
        AsyncMock(return_value=energy_storage),
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_recent_grid",
        AsyncMock(
            return_value=[
                {
                    "ts": str(midday_timestamp_ms(yesterday)),
                    "positive": "1.1",
                    "negative": "0.2",
                },
                {
                    "ts": str(midday_timestamp_ms(today)),
                    "positive": "4.6",
                    "negative": "1.4",
                },
            ]
        ),
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_recent_solar",
        AsyncMock(
            return_value=[
                {
                    "ts": str(midday_timestamp_ms(yesterday)),
                    "powerGeneration": "3.2",
                },
                {
                    "ts": str(midday_timestamp_ms(today)),
                    "powerGeneration": "8.9",
                },
            ]
        ),
    )

    await coordinator._async_update_data()

    assert coordinator.access_token == "access-token"
    assert coordinator.site == {"name": "Home Site"}
    assert coordinator.devices == {"device-1": {"name": "Inverter"}}
    assert coordinator.current_power_flow is power_flow
    assert coordinator.energy_storage is energy_storage
    assert coordinator.todays_grid == {
        "ts": str(midday_timestamp_ms(today)),
        "positive": "4.6",
        "negative": "1.4",
    }
    assert coordinator.todays_solar == {
        "ts": str(midday_timestamp_ms(today)),
        "powerGeneration": "8.9",
    }
    get_api_client.assert_awaited_once_with(livoltek_entry, None)


@pytest.mark.asyncio
async def test_async_update_data_reuses_cached_access_token(
    hass,
    livoltek_entry,
    monkeypatch,
) -> None:
    """Coordinator refreshes should pass the cached token back into the helper."""
    coordinator = LivoltekDataUpdateCoordinator(hass, livoltek_entry)
    power_flow = build_power_flow()

    get_api_client = AsyncMock(
        side_effect=[
            (object(), "first-token"),
            (object(), "second-token"),
        ]
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_api_client",
        get_api_client,
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_site",
        AsyncMock(return_value={"name": "Home Site"}),
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_device_list",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_cur_power_flow",
        AsyncMock(return_value=power_flow),
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_energy_storage",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_recent_grid",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_recent_solar",
        AsyncMock(return_value=[]),
    )

    await coordinator._async_update_data()
    await coordinator._async_update_data()

    assert get_api_client.await_args_list[0].args == (livoltek_entry, None)
    assert get_api_client.await_args_list[1].args == (livoltek_entry, "first-token")
    assert coordinator.access_token == "second-token"


def _patch_fetch(monkeypatch, get_api_client, get_site) -> None:
    """Patch every API call made by one coordinator update."""
    base = "custom_components.livoltek.coordinator."
    monkeypatch.setattr(base + "async_get_api_client", get_api_client)
    monkeypatch.setattr(base + "async_get_site", get_site)
    monkeypatch.setattr(base + "async_get_device_list", AsyncMock(return_value={}))
    monkeypatch.setattr(base + "async_get_cur_power_flow", AsyncMock(return_value=build_power_flow()))
    monkeypatch.setattr(base + "async_get_energy_storage", AsyncMock(return_value=build_energy_storage()))
    monkeypatch.setattr(base + "async_get_recent_grid", AsyncMock(return_value=[]))
    monkeypatch.setattr(base + "async_get_recent_solar", AsyncMock(return_value=[]))


@pytest.mark.asyncio
async def test_async_update_data_retries_once_with_fresh_login_on_401(
    hass,
    livoltek_entry,
    monkeypatch,
) -> None:
    """A rejected token is dropped and the update is retried with a new login."""
    from pylivoltek.rest import ApiException

    coordinator = LivoltekDataUpdateCoordinator(hass, livoltek_entry)
    coordinator.access_token = "stale-token"
    get_api_client = AsyncMock(side_effect=[(object(), "stale-token"), (object(), "fresh-token")])
    get_site = AsyncMock(side_effect=[ApiException(status=401), {"name": "Home Site"}])
    _patch_fetch(monkeypatch, get_api_client, get_site)

    await coordinator._async_update_data()

    assert get_api_client.await_args_list[0].args == (livoltek_entry, "stale-token")
    assert get_api_client.await_args_list[1].args == (livoltek_entry, None)  # token dropped
    assert coordinator.access_token == "fresh-token"
    assert coordinator.site == {"name": "Home Site"}


@pytest.mark.asyncio
async def test_async_update_data_fails_cleanly_when_fresh_login_is_rejected(
    hass,
    livoltek_entry,
    monkeypatch,
) -> None:
    """If a fresh login is rejected too, Home Assistant asks the user to sign in again."""
    from homeassistant.exceptions import ConfigEntryAuthFailed
    from pylivoltek.rest import ApiException

    coordinator = LivoltekDataUpdateCoordinator(hass, livoltek_entry)
    get_api_client = AsyncMock(return_value=(object(), "token"))
    _patch_fetch(monkeypatch, get_api_client, AsyncMock(side_effect=ApiException(status=401)))

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_async_update_data_drops_yesterdays_daily_values(
    hass,
    livoltek_entry,
    monkeypatch,
) -> None:
    """Without an entry for today, the daily values are cleared, not kept from yesterday."""
    coordinator = LivoltekDataUpdateCoordinator(hass, livoltek_entry)
    coordinator.todays_grid = {"positive": "4.6", "negative": "1.4"}
    coordinator.todays_solar = {"powerGeneration": "8.9"}
    yesterday = dt.date.today() - dt.timedelta(days=1)
    _patch_fetch(monkeypatch, AsyncMock(return_value=(object(), "token")), AsyncMock(return_value={"name": "Home Site"}))
    monkeypatch.setattr(
        "custom_components.livoltek.coordinator.async_get_recent_grid",
        AsyncMock(return_value=[{"ts": str(midday_timestamp_ms(yesterday)), "positive": "1.1", "negative": "0.2"}]),
    )

    await coordinator._async_update_data()

    assert coordinator.todays_grid is None
    assert coordinator.todays_solar is None


@pytest.mark.asyncio
async def test_async_update_data_keeps_devices_when_list_is_empty(
    hass,
    livoltek_entry,
    monkeypatch,
) -> None:
    """An empty device-list answer keeps the devices from the previous update."""
    coordinator = LivoltekDataUpdateCoordinator(hass, livoltek_entry)
    coordinator.devices = {"device-1": {"name": "Inverter"}}
    _patch_fetch(monkeypatch, AsyncMock(return_value=(object(), "token")), AsyncMock(return_value={"name": "Home Site"}))
    monkeypatch.setattr("custom_components.livoltek.coordinator.async_get_device_list", AsyncMock(return_value=None))

    await coordinator._async_update_data()

    assert coordinator.devices == {"device-1": {"name": "Inverter"}}


@pytest.mark.asyncio
async def test_async_update_data_does_not_retry_other_errors(
    hass,
    livoltek_entry,
    monkeypatch,
) -> None:
    """Errors other than 401/403 are not retried, and fail the update cleanly."""
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pylivoltek.rest import ApiException

    coordinator = LivoltekDataUpdateCoordinator(hass, livoltek_entry)
    get_api_client = AsyncMock(return_value=(object(), "token"))
    _patch_fetch(monkeypatch, get_api_client, AsyncMock(side_effect=ApiException(status=500)))

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    get_api_client.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_update_data_network_outage_is_update_failed(
    hass,
    livoltek_entry,
    monkeypatch,
) -> None:
    """No DNS / portal unreachable: UpdateFailed, not an unexpected error."""
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from urllib3.exceptions import MaxRetryError

    coordinator = LivoltekDataUpdateCoordinator(hass, livoltek_entry)
    get_api_client = AsyncMock(return_value=(object(), "token"))
    _patch_fetch(monkeypatch, get_api_client, AsyncMock(side_effect=MaxRetryError(None, "/site", "no DNS")))

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
