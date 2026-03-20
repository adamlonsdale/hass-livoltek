"""Tests for integration setup and teardown."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.livoltek import LivoltekInverterDevice, async_setup_entry, async_unload_entry
from custom_components.livoltek.const import DOMAIN, PLATFORMS

from .common import build_device_details


@pytest.mark.asyncio
async def test_async_setup_entry_creates_coordinator_and_forwards_platforms(
    hass,
    livoltek_entry,
) -> None:
    """Entry setup should refresh the coordinator and forward configured platforms."""
    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "custom_components.livoltek.LivoltekDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(),
        ) as forward_entry_setups,
    ):
        result = await async_setup_entry(hass, livoltek_entry)

    assert result is True
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    assert hass.data[DOMAIN][livoltek_entry.entry_id] is coordinator
    forward_entry_setups.assert_awaited_once_with(livoltek_entry, PLATFORMS)


@pytest.mark.asyncio
async def test_async_unload_entry_removes_coordinator_data(hass, livoltek_entry) -> None:
    """Unloading the entry should remove coordinator data after platform cleanup."""
    hass.data[DOMAIN] = {livoltek_entry.entry_id: object()}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    ) as unload_platforms:
        result = await async_unload_entry(hass, livoltek_entry)

    assert result is True
    unload_platforms.assert_awaited_once_with(livoltek_entry, PLATFORMS)
    assert livoltek_entry.entry_id not in hass.data[DOMAIN]


def test_inverter_device_info_maps_pylivoltek_metadata(hass) -> None:
    """The device wrapper should expose the Home Assistant device registry fields."""
    device = build_device_details(
        id="device-7",
        inverter_sn="INV-777",
        product_type="Battery Inverter",
        firmware_version="3.1.4",
    )

    inverter = LivoltekInverterDevice(api=object(), device=device, hass=hass)
    device_info = inverter.device_info

    assert device_info["identifiers"] == {("livoltek", "device-7")}
    assert device_info["model"] == "Battery Inverter"
    assert device_info["sw_version"] == "3.1.4"
