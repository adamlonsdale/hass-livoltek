"""Pytest fixtures for the Livoltek integration tests."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from types import MappingProxyType

import pytest

from homeassistant import config_entries, loader
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant


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
    user_token: str


def _env_truthy(name: str) -> bool:
    """Return whether an environment variable should be treated as true."""
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


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
    user_token = os.getenv("LIVOLTEK_TEST_USER_TOKEN")

    missing = [
        name
        for name, value in (
            ("LIVOLTEK_TEST_API_KEY", api_key),
            ("LIVOLTEK_TEST_SECUID", secuid),
            ("LIVOLTEK_TEST_USER_TOKEN", user_token),
        )
        if not value
    ]
    if missing:
        pytest.skip(
            "Live Livoltek API test requires local environment variables: "
            + ", ".join(missing)
        )

    return LiveCredentials(
        api_key=api_key,
        emea=_env_truthy("LIVOLTEK_TEST_EMEA"),
        secuid=secuid,
        user_token=user_token,
    )
