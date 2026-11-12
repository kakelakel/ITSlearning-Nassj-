"""Constants for the itslearning integration."""
from datetime import timedelta

DOMAIN = "itslearning"

CONF_SITE_URL = "site_url"
CONF_TOKENS = "tokens"

DEFAULT_SITE_URL = "https://nassjo.itslearning.com"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)
