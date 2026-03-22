"""Live smoke tests for the main read-only pylivoltek endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest


def _response_payload(response: Any) -> dict[str, Any]:
    """Return a plain-dict representation of a live API response."""
    if hasattr(response, "to_dict"):
        return response.to_dict()
    return response


def _assert_success(response: Any) -> dict[str, Any]:
    """Assert a live API call succeeded and return its payload."""
    payload = _response_payload(response)
    assert payload["message"] == "SUCCESS"
    return payload.get("data")


def _history_windows() -> dict[str, str | int]:
    """Build time filters accepted by the historical endpoints."""
    now = datetime.now(timezone.utc)
    return {
        "alarm_end_date": now.date().isoformat(),
        "alarm_start_date": (now - timedelta(days=7)).date().isoformat(),
        "history_end_day": now.strftime("%Y%m%d"),
        "history_end_ms": int(now.timestamp() * 1000),
        "history_end_timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "history_start_day": (now - timedelta(days=6)).strftime("%Y%m%d"),
        "history_start_ms": int((now - timedelta(days=1)).timestamp() * 1000),
        "history_start_timestamp": (
            now - timedelta(hours=24)
        ).strftime("%Y-%m-%d %H:%M:%S"),
    }


@pytest.mark.live
def test_live_access_token_is_reused_across_smokes(livoltek_live_api_context) -> None:
    """The shared live context should authenticate once and expose a token."""
    assert livoltek_live_api_context.access_token
    assert livoltek_live_api_context.host.startswith("https://")


@pytest.mark.live
def test_live_list_sites_for_all_configured_user_tokens(
    livoltek_live_api_context,
    livoltek_live_credentials,
) -> None:
    """Every configured live user token should reach the site list endpoint."""
    for user_token in livoltek_live_credentials.user_tokens:
        data = _assert_success(
            livoltek_live_api_context.api.list_sites(
                user_token,
                page=1,
                size=10,
                async_req=True,
                _preload_content=True,
            ).get()
        )
        assert isinstance(data["list"], list)


@pytest.mark.live
def test_live_list_devices(livoltek_live_api_context) -> None:
    """The device list endpoint should return the discovered device."""
    data = _assert_success(
        livoltek_live_api_context.api.list_devices(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            page=1,
            size=10,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert data["list"]
    assert any(
        str(device["id"]) == livoltek_live_api_context.device_id
        for device in data["list"]
    )


@pytest.mark.live
def test_live_get_current_power_flow(livoltek_live_api_context) -> None:
    """The current power flow endpoint should return a structured payload."""
    data = _assert_success(
        livoltek_live_api_context.api.get_current_power_flow(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert "timestamp" in data


@pytest.mark.live
def test_live_get_device_generation_or_consumption(livoltek_live_api_context) -> None:
    """The device energy summary endpoint should resolve for the live device."""
    data = _assert_success(
        livoltek_live_api_context.api.get_device_generation_or_consumption(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.device_id,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert "pv_produce_electric" in data


@pytest.mark.live
def test_live_get_site_generation_overview(livoltek_live_api_context) -> None:
    """The site overview endpoint should match the discovered site."""
    data = _assert_success(
        livoltek_live_api_context.api.get_site_generation_overview(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert data["name"]


@pytest.mark.live
def test_live_get_site_details(livoltek_live_api_context) -> None:
    """The site details endpoint should return the selected site id."""
    data = _assert_success(
        livoltek_live_api_context.api.get_site_details(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert str(data["powerStationId"]) == livoltek_live_api_context.site_id


@pytest.mark.live
def test_live_get_site_installer(livoltek_live_api_context) -> None:
    """The site installer endpoint should return a response envelope."""
    data = _assert_success(
        livoltek_live_api_context.api.get_site_installer(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert "installer" in data


@pytest.mark.live
def test_live_get_energy_storage(livoltek_live_api_context) -> None:
    """The energy storage endpoint should respond for the selected site."""
    data = _assert_success(
        livoltek_live_api_context.api.get_energy_storage(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert "current_soc" in data


@pytest.mark.live
def test_live_get_device_details(livoltek_live_api_context) -> None:
    """The device details endpoint should return the selected inverter SN."""
    data = _assert_success(
        livoltek_live_api_context.api.get_device_details(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            livoltek_live_api_context.serial_number,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert str(data["inverter_sn"]) == livoltek_live_api_context.serial_number


@pytest.mark.live
def test_live_get_power_station_id_by_device_sn(livoltek_live_api_context) -> None:
    """The device-SN lookup should map back to the selected site."""
    data = _assert_success(
        livoltek_live_api_context.api.get_power_station_id_by_device_sn(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.serial_number,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert str(data["powerStationId"]) == livoltek_live_api_context.site_id


@pytest.mark.live
def test_live_get_site_owner(livoltek_live_api_context) -> None:
    """The site owner endpoint should return a response envelope."""
    data = _assert_success(
        livoltek_live_api_context.api.get_site_owner(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert isinstance(data, dict)


@pytest.mark.live
def test_live_get_site_historical_power_flow(livoltek_live_api_context) -> None:
    """The historical power flow endpoint should return keyed time-series data."""
    filters = _history_windows()
    data = _assert_success(
        livoltek_live_api_context.api.get_site_historical_power_flow(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            pointInterval=1,
            startTime=filters["history_start_ms"],
            endTime=filters["history_end_ms"],
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert data


@pytest.mark.live
def test_live_get_site_historical_active_power(livoltek_live_api_context) -> None:
    """The historical active power endpoint should return keyed time-series data."""
    filters = _history_windows()
    data = _assert_success(
        livoltek_live_api_context.api.get_site_historical_active_power(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            pointInterval=1,
            startTime=filters["history_start_ms"],
            endTime=filters["history_end_ms"],
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert data


@pytest.mark.live
def test_live_get_device_historical_alarm(livoltek_live_api_context) -> None:
    """The historical alarm endpoint should return a response envelope."""
    filters = _history_windows()
    data = _assert_success(
        livoltek_live_api_context.api.get_device_historical_alarm(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            livoltek_live_api_context.serial_number,
            startTime=filters["alarm_start_date"],
            endTime=filters["alarm_end_date"],
            page=1,
            size=10,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert data is None or isinstance(data, dict)


@pytest.mark.live
def test_live_get_device_technical_parameters(livoltek_live_api_context) -> None:
    """The device realtime endpoint should accept a derived time window."""
    filters = _history_windows()
    data = _assert_success(
        livoltek_live_api_context.api.get_device_technical_parameters(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            livoltek_live_api_context.serial_number,
            startTime=filters["history_start_timestamp"],
            endTime=filters["history_end_timestamp"],
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert isinstance(data, dict)


@pytest.mark.live
def test_live_get_site_historical_solar_generation(livoltek_live_api_context) -> None:
    """The historical solar endpoint should return aggregated samples."""
    filters = _history_windows()
    data = _assert_success(
        livoltek_live_api_context.api.get_site_historical_solar_generation(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            timeType=0,
            startTime=filters["history_start_day"],
            endTime=filters["history_end_day"],
            page=1,
            size=10,
            async_req=True,
            _preload_content=True,
        ).get()
    )

    assert isinstance(data, list)


@pytest.mark.live
def test_live_get_site_historical_grid_import_export(
    livoltek_live_api_context,
) -> None:
    """The historical grid endpoint should return aggregated samples."""
    filters = _history_windows()
    data = _assert_success(
        livoltek_live_api_context.api.get_site_historical_grid_import_export(
            livoltek_live_api_context.user_token,
            livoltek_live_api_context.site_id,
            timeType=0,
            startTime=filters["history_start_day"],
            endTime=filters["history_end_day"],
            page=1,
            size=10,
            async_req=True,
            _preload_content=True,
        ).get()
    )
    
    assert data
