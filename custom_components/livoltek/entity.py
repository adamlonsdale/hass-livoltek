"""Base class for any Livoltek entities."""
from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import ATTRIBUTION, DOMAIN
from . import LivoltekDataUpdateCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class LivoltekEntity(CoordinatorEntity[LivoltekDataUpdateCoordinator]):
    """Defines a base Livoltek entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LivoltekDataUpdateCoordinator) -> None:
        """Initialize a Livoltek entity."""
        super().__init__(coordinator=coordinator)
