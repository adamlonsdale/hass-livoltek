"""Tests for Livoltek sensor entities."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.livoltek.const import DOMAIN
from custom_components.livoltek.sensor import async_setup_entry

from .common import build_energy_storage, build_power_flow


@pytest.mark.asyncio
async def test_async_setup_entry_adds_all_enabled_sensors(hass, livoltek_entry) -> None:
    """Sensor setup should expose power and daily energy entities when data is present."""
    coordinator = SimpleNamespace(
        current_power_flow=build_power_flow(),
        energy_storage=build_energy_storage(),
        todays_grid={"positive": "4.6", "negative": "1.4"},
        todays_solar={"powerGeneration": "8.9"},
    )
    hass.data[DOMAIN] = {livoltek_entry.entry_id: coordinator}
    entities = []

    await async_setup_entry(hass, livoltek_entry, entities.extend)

    assert len(entities) == 8
    entity_map = {entity.entity_description.key: entity for entity in entities}
    assert entity_map["battery_soc"].native_value == 72.0
    assert entity_map["grid_import_energy"].native_value == 4.6
    assert entity_map["solar_generation_energy"].native_value == 8.9
    assert entity_map["battery_soc"].unique_id == "site-123-battery_soc"


@pytest.mark.asyncio
async def test_battery_soc_falls_back_to_power_flow_when_ess_unavailable(
    hass, livoltek_entry
) -> None:
    """battery_soc should fall back to curPowerflow.energy_soc when /ESS data is absent."""
    coordinator = SimpleNamespace(
        current_power_flow=build_power_flow(),
        energy_storage=None,
        todays_grid={"positive": "4.6", "negative": "1.4"},
        todays_solar={"powerGeneration": "8.9"},
    )
    hass.data[DOMAIN] = {livoltek_entry.entry_id: coordinator}
    entities = []

    await async_setup_entry(hass, livoltek_entry, entities.extend)

    entity_map = {entity.entity_description.key: entity for entity in entities}
    assert entity_map["battery_soc"].native_value == 64.5


@pytest.mark.asyncio
async def test_battery_soc_uses_ess_current_soc_over_power_flow(
    hass, livoltek_entry
) -> None:
    """battery_soc should prefer /ESS current_soc over curPowerflow.energy_soc."""
    coordinator = SimpleNamespace(
        current_power_flow=build_power_flow(energy_soc=50.0),
        energy_storage=build_energy_storage(current_soc=88.5),
        todays_grid={"positive": "4.6", "negative": "1.4"},
        todays_solar={"powerGeneration": "8.9"},
    )
    hass.data[DOMAIN] = {livoltek_entry.entry_id: coordinator}
    entities = []

    await async_setup_entry(hass, livoltek_entry, entities.extend)

    entity_map = {entity.entity_description.key: entity for entity in entities}
    assert entity_map["battery_soc"].native_value == 88.5


@pytest.mark.asyncio
async def test_async_setup_entry_skips_daily_energy_sensors_without_values(
    hass,
    livoltek_entry,
) -> None:
    """Sensor setup should only add entities whose enable predicates pass."""
    coordinator = SimpleNamespace(
        current_power_flow=build_power_flow(),
        energy_storage=None,
        todays_grid={"positive": None, "negative": None},
        todays_solar={"powerGeneration": None},
    )
    hass.data[DOMAIN] = {livoltek_entry.entry_id: coordinator}
    entities = []

    await async_setup_entry(hass, livoltek_entry, entities.extend)

    assert {entity.entity_description.key for entity in entities} == {
        "battery_soc",
        "power_grid_power",
        "pv_power",
        "load_power",
        "energy_power",
    }
