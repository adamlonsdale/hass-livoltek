"""Tests for the Livoltek data update coordinator."""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.livoltek.coordinator import LivoltekDataUpdateCoordinator

from .common import build_power_flow, midday_timestamp_ms


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
