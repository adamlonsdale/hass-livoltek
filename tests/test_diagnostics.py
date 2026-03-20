"""Tests for integration diagnostics."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.livoltek.const import DOMAIN
from custom_components.livoltek.diagnostics import async_get_config_entry_diagnostics


@pytest.mark.asyncio
async def test_diagnostics_round_trip_json(hass, livoltek_entry) -> None:
    """Diagnostics should JSON-serialize the stored coordinator payload."""
    hass.data[DOMAIN] = {
        livoltek_entry.entry_id: SimpleNamespace(
            data=SimpleNamespace(json=lambda: '{"site":"home","devices":2}')
        )
    }

    result = await async_get_config_entry_diagnostics(hass, livoltek_entry)

    assert result == {"site": "home", "devices": 2}
