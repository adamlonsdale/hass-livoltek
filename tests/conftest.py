"""Pytest fixtures for the Livoltek integration tests."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Any

import pytest

from homeassistant import config_entries, loader
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from pylivoltek import ApiClient, ApiLoginBody, Configuration
from pylivoltek.api import DefaultApi
from pylivoltek.rest import ApiException

from custom_components.livoltek.const import (
    LIVOLTEK_EMEA_SERVER,
    LIVOLTEK_GLOBAL_SERVER,
)


DOMAIN = "livoltek"
CONF_EMEA_ID = "emea_id"
CONF_SECUID_ID = "secuid_id"
CONF_SITE_ID = "site_id"
CONF_USERTOKEN_ID = "usertoken_id"
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_dotenv() -> None:
    """Load simple KEY=VALUE pairs from a local .env file."""
    dotenv_path = REPO_ROOT / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)

_load_dotenv()


@dataclass(frozen=True)
class LiveCredentials:
    """Local-only credentials for opt-in live API tests."""

    api_key: str
    emea: bool
    secuid: str
    user_tokens: tuple[str, ...]

    @property
    def user_token(self) -> str:
        """Return the primary configured user token."""
        return self.user_tokens[0]


@dataclass(frozen=True)
class LiveApiContext:
    """Shared live API state for the smoke suite."""

    access_token: str
    api: DefaultApi
    device: dict[str, Any]
    device_id: str
    host: str
    serial_number: str
    site: dict[str, Any]
    site_id: str
    user_token: str


def _env_truthy(name: str) -> bool:
    """Return whether an environment variable should be treated as true."""
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _collect_live_user_tokens() -> tuple[str, ...]:
    """Return every configured live user token from the local environment."""
    token_names = [
        name
        for name in os.environ
        if name == "LIVOLTEK_TEST_USER_TOKEN"
        or name.startswith("LIVOLTEK_TEST_USER_TOKEN_")
        or name in {"LIVOLTEK_TEST_OTHER_USER_TOKEN", "LIVOLTEK_TEST_SECOND_USER_TOKEN"}
    ]

    ordered_names = sorted(
        token_names,
        key=lambda name: (name != "LIVOLTEK_TEST_USER_TOKEN", name),
    )

    seen: set[str] = set()
    user_tokens: list[str] = []
    for name in ordered_names:
        value = os.getenv(name, "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        user_tokens.append(value)

    return tuple(user_tokens)


def _to_live_payload(response: Any) -> dict[str, Any]:
    """Normalise live API responses into plain dictionaries."""
    if hasattr(response, "to_dict"):
        return response.to_dict()
    return response


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Print a one-line result for each completed test to stdout."""
    is_terminal_phase = report.when == "call"
    is_setup_skip_or_fail = report.when == "setup" and report.outcome in {
        "failed",
        "skipped",
    }
    if not (is_terminal_phase or is_setup_skip_or_fail):
        return

    print(f"{report.outcome.upper()}: {report.nodeid}")


@pytest.fixture
async def hass(tmp_path: Path) -> AsyncIterator[HomeAssistant]:
    """Create a lightweight Home Assistant test instance."""
    (tmp_path / "custom_components").symlink_to(
        REPO_ROOT / "custom_components",
        target_is_directory=True,
    )

    hass = HomeAssistant(str(tmp_path))
    loader.async_setup(hass)
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    await hass.async_start()

    try:
        yield hass
    finally:
        await hass.async_block_till_done()
        await hass.async_stop(force=True)


@pytest.fixture
def livoltek_entry() -> ConfigEntry:
    """Build a representative Livoltek config entry."""
    return ConfigEntry(
        data={
            CONF_API_KEY: "api-key",
            CONF_EMEA_ID: False,
            CONF_SECUID_ID: "secuid-123",
            CONF_SITE_ID: "site-123",
            CONF_USERTOKEN_ID: "user-token-123",
        },
        discovery_keys=MappingProxyType({}),
        domain=DOMAIN,
        entry_id="entry-123",
        minor_version=1,
        options={},
        source="user",
        title="Livoltek",
        unique_id="site-123",
        version=1,
    )


@pytest.fixture(scope="session")
def livoltek_live_credentials() -> LiveCredentials:
    """Return live credentials from the local environment when configured."""
    api_key = os.getenv("LIVOLTEK_TEST_API_KEY")
    secuid = os.getenv("LIVOLTEK_TEST_SECUID")
    user_tokens = _collect_live_user_tokens()

    missing = [
        name
        for name, value in (
            ("LIVOLTEK_TEST_API_KEY", api_key),
            ("LIVOLTEK_TEST_SECUID", secuid),
        )
        if not value
    ]
    if not user_tokens:
        missing.append("LIVOLTEK_TEST_USER_TOKEN")

    if missing:
        pytest.skip(
            "Live Livoltek API test requires local environment variables: "
            + ", ".join(missing)
        )

    return LiveCredentials(
        api_key=api_key,
        emea=_env_truthy("LIVOLTEK_TEST_EMEA"),
        secuid=secuid,
        user_tokens=user_tokens,
    )


@pytest.fixture(scope="session")
def livoltek_live_api_context(
    livoltek_live_credentials: LiveCredentials,
) -> LiveApiContext:
    """Authenticate once and return a reusable live API context."""
    host = (
        LIVOLTEK_EMEA_SERVER
        if livoltek_live_credentials.emea
        else LIVOLTEK_GLOBAL_SERVER
    )
    config = Configuration()
    config.host = host

    login_api = DefaultApi(ApiClient(config))
    login_model = ApiLoginBody(
        livoltek_live_credentials.secuid,
        livoltek_live_credentials.api_key.replace("\\r", "\r").replace("\\n", "\n"),
    )
    login_response = login_api.login(
        login_model,
        async_req=True,
        _preload_content=True,
    ).get()
    login_payload = _to_live_payload(login_response)

    assert login_payload["message"] == "SUCCESS"
    access_token = login_payload["data"]["data"]
    assert access_token

    api_client = ApiClient(config)
    api_client.set_default_header("Authorization", access_token)
    api = DefaultApi(api_client)

    last_error: Exception | None = None
    for user_token in livoltek_live_credentials.user_tokens:
        try:
            sites_payload = _to_live_payload(
                api.list_sites(
                    user_token,
                    page=1,
                    size=10,
                    async_req=True,
                    _preload_content=True,
                ).get()
            )
            if sites_payload.get("message") != "SUCCESS":
                continue

            sites = sites_payload["data"]["list"]
            if not sites:
                continue

            site = sites[0]
            site_id = str(site["powerStationId"])
            devices_payload = _to_live_payload(
                api.list_devices(
                    user_token,
                    site_id,
                    page=1,
                    size=10,
                    async_req=True,
                    _preload_content=True,
                ).get()
            )
            if devices_payload.get("message") != "SUCCESS":
                continue

            devices = devices_payload["data"]["list"]
            if not devices:
                continue

            device = devices[0]
            context = LiveApiContext(
                access_token=access_token,
                api=api,
                device=device,
                device_id=str(device["id"]),
                host=host,
                serial_number=str(device["inverterSn"]),
                site=site,
                site_id=site_id,
                user_token=user_token,
            )
            yield context
            pool = getattr(api.api_client, "pool", None)
            if pool is not None:
                pool.close()
                pool.join()
            return
        except ApiException as err:
            last_error = err

    if last_error is not None:
        raise last_error

    pytest.skip(
        "Live Livoltek API smoke tests require at least one configured user token "
        "that can list both sites and devices."
    )
