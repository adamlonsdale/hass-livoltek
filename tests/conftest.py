"""Pytest fixtures for the Livoltek integration tests."""
from __future__ import annotations

from collections.abc import AsyncIterator
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
