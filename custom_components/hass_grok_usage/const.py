"""Constants for the xAI Grok Usage integration."""

DOMAIN = "hass_grok_usage"

# API
GROK_BILLING_API_URL = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"
GROK_CLIENT_VERSION = "0.2.93"
OAUTH_TOKEN_URL = "https://auth.x.ai/oauth2/token"
OAUTH_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"

# Defaults
DEFAULT_UPDATE_INTERVAL = 300  # seconds

# Config keys
CONF_ACCESS_TOKEN = "access_token"
CONF_ACCOUNT_ID = "account_id"
CONF_ACCOUNT_NAME = "account_name"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_UPDATE_INTERVAL = "update_interval"

# Sensor definitions: (key, name, unit, icon, device_class)
# Grok exposes only a weekly usage window - no 5-hour window like Codex.
SENSOR_DEFINITIONS = [
    ("weekly_limit_percent", "Weekly Usage Limit", "%", "mdi:calendar-week", None),
    ("weekly_reset_time", "Weekly Reset Time", None, "mdi:calendar-clock", "timestamp"),
    ("api_error", "API Error", "errors", "mdi:alert-circle", None),
]
