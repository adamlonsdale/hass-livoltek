"""Diagnostics support for Livoltek."""
from __future__ import annotations

import json
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LivoltekDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: LivoltekDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.data is None:
        return {}

    try:
        data: dict[str, Any] = json.loads(coordinator.data.json())
    except (AttributeError, json.JSONDecodeError):
        return {}

    return data
