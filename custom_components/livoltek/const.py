"""Constants for the Livoltek integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "livoltek"
PLATFORMS = [Platform.SENSOR]

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=5)
CONF_SYSTEM_ID = "system_id"

CONF_USERTOKEN_ID = "usertoken_id"
CONF_SECUID_ID = "secuid_id"
CONF_EMEA_ID = "emea_id"
CONF_SITE_ID = "site_id"

LIVOLTEK_EMEA_SERVER = "https://api-eu.livoltek-portal.com:8081"
LIVOLTEK_GLOBAL_SERVER = "https://api.livoltek-portal.com:8081"
