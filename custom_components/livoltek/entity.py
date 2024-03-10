"""Base class for any Livoltek entities."""
from __future__ import annotations



from . import LivoltekDataUpdateCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class LivoltekEntity(CoordinatorEntity[LivoltekDataUpdateCoordinator]):
    """Defines a base Livoltek entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LivoltekDataUpdateCoordinator) -> None:
        """Initialize a Livoltek entity."""
        super().__init__(coordinator=coordinator)
