"""Shared fixtures and builders for Livoltek tests."""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any


def midday_timestamp_ms(day: dt.date) -> int:
    """Build a stable midday timestamp in milliseconds for a given day."""
    value = dt.datetime.combine(day, dt.time(hour=12), tzinfo=dt.timezone.utc)
    return int(value.timestamp() * 1000)


def build_power_flow(**overrides: Any) -> SimpleNamespace:
    """Create a fake current power flow object."""
    payload = {
        "energy_soc": 64.5,
        "power_grid_power": -0.8,
        "pv_power": 3.4,
        "load_power": 2.2,
        "energy_power": 1.2,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def build_device_details(**overrides: Any) -> SimpleNamespace:
    """Create a fake device details object."""
    payload = {
        "id": "device-1",
        "device_manufacturer": "Livoltek",
        "inverter_sn": "INV-001",
        "product_type": "Hybrid Inverter",
        "firmware_version": "1.0.0",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def make_thread(result: Any) -> SimpleNamespace:
    """Wrap a result in an object with the generated client's get() API."""
    return SimpleNamespace(get=lambda: result)
