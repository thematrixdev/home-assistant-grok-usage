"""xAI Grok Usage integration for Home Assistant."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_REFRESH_TOKEN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    GROK_BILLING_API_URL,
    GROK_CLIENT_VERSION,
    OAUTH_CLIENT_ID,
    OAUTH_TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type GrokUsageConfigEntry = ConfigEntry[GrokUsageCoordinator]


async def async_migrate_entry(hass: HomeAssistant, entry: GrokUsageConfigEntry) -> bool:
    """Migrate config entry to a new version."""
    if entry.version == 1 and entry.unique_id is None:
        account_id = _normalize_credential_value(entry.data.get(CONF_ACCOUNT_ID, ""))
        # ponytail: fall back to entry_id if no account_id stored — reauth replaces it
        if not account_id:
            account_id = entry.entry_id
        hass.config_entries.async_update_entry(entry, unique_id=account_id)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GrokUsageConfigEntry) -> bool:
    """Set up xAI Grok Usage from a config entry."""
    coordinator = GrokUsageCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GrokUsageConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: GrokUsageConfigEntry) -> None:
    """Handle options update."""
    coordinator: GrokUsageCoordinator = entry.runtime_data
    interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    coordinator.update_interval = timedelta(seconds=interval)


class GrokUsageCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch xAI Grok usage data."""

    config_entry: GrokUsageConfigEntry

    def __init__(self, hass: HomeAssistant, entry: GrokUsageConfigEntry) -> None:
        """Initialize the coordinator."""
        interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch usage data from the API."""
        access_token = _normalize_credential_value(
            self.config_entry.options.get(
                CONF_ACCESS_TOKEN,
                self.config_entry.data.get(CONF_ACCESS_TOKEN, ""),
            )
        )
        refresh_token = _normalize_credential_value(
            self.config_entry.options.get(
                CONF_REFRESH_TOKEN,
                self.config_entry.data.get(CONF_REFRESH_TOKEN, ""),
            )
        )

        if not access_token:
            raise ConfigEntryAuthFailed("Missing access token")

        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            raw = await _fetch_grok_usage(session=session, access_token=access_token)
        except aiohttp.ClientResponseError as err:
            if err.status not in (401, 403):
                raise UpdateFailed(f"Error fetching usage data: {err}") from err
            if not refresh_token:
                raise ConfigEntryAuthFailed(
                    "Authentication failed - run `grok login` on the Grok machine "
                    "and update credentials"
                ) from err
            try:
                new_access_token, new_refresh_token = await _refresh_access_token(
                    session=session,
                    refresh_token=refresh_token,
                )
            except aiohttp.ClientError as refresh_err:
                raise ConfigEntryAuthFailed(
                    "Token refresh failed - run `grok login` on the Grok machine "
                    "and update credentials"
                ) from refresh_err
            access_token = new_access_token
            if new_refresh_token:
                refresh_token = new_refresh_token
            self._update_stored_credentials(
                access_token=access_token,
                refresh_token=refresh_token,
            )
            raw = await _fetch_grok_usage(session=session, access_token=access_token)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching usage data: {err}") from err

        return _parse_usage(raw)

    def _update_stored_credentials(self, access_token: str, refresh_token: str) -> None:
        """Persist newly refreshed credentials."""
        new_data = {
            **self.config_entry.data,
            CONF_ACCESS_TOKEN: access_token,
            CONF_REFRESH_TOKEN: refresh_token,
        }
        new_options = {
            **self.config_entry.options,
            CONF_ACCESS_TOKEN: access_token,
            CONF_REFRESH_TOKEN: refresh_token,
        }
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data,
            options=new_options,
        )


def _normalize_credential_value(value: Any) -> str:
    """Accept plain tokens, quoted tokens, or a JSON object with `data`/`key`."""
    if not isinstance(value, str):
        return ""
    raw = value.strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(parsed, str):
        return parsed.strip()
    if isinstance(parsed, dict):
        for field in ("data", "key", "access_token"):
            candidate = parsed.get(field)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return raw


async def _refresh_access_token(
    session: aiohttp.ClientSession,
    refresh_token: str,
) -> tuple[str, str | None]:
    """Refresh xAI auth tokens using the OIDC token endpoint."""
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": OAUTH_CLIENT_ID,
    }
    resp = await session.post(
        OAUTH_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=aiohttp.ClientTimeout(total=15),
    )
    resp.raise_for_status()
    token_data = await resp.json()
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise ConfigEntryAuthFailed("Token refresh response missing access_token")
    new_refresh_token = token_data.get("refresh_token")
    if isinstance(new_refresh_token, str) and new_refresh_token:
        return access_token, new_refresh_token
    return access_token, None


async def _fetch_grok_usage(
    session: aiohttp.ClientSession,
    access_token: str,
) -> dict[str, Any]:
    """Fetch Grok billing/usage limits from the Grok CLI chat proxy."""
    resp = await session.get(
        GROK_BILLING_API_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "x-grok-client-version": GROK_CLIENT_VERSION,
            "Accept": "application/json",
        },
        timeout=aiohttp.ClientTimeout(total=15),
    )
    resp.raise_for_status()
    payload = await resp.json()
    if not isinstance(payload, dict):
        raise UpdateFailed("Unexpected Grok usage response format")
    return payload


def _parse_usage(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract the weekly usage window from the Grok billing payload."""
    config = raw.get("config")
    if not isinstance(config, dict):
        config = raw

    data: dict[str, Any] = {}

    percent = _as_percent(config.get("creditUsagePercent"))
    if percent is not None:
        data["weekly_limit_percent"] = percent

    period = config.get("currentPeriod")
    reset_raw = period.get("end") if isinstance(period, dict) else None
    if reset_raw is None:
        reset_raw = config.get("billingPeriodEnd")
    reset = _parse_iso(reset_raw)
    if reset is not None:
        data["weekly_reset_time"] = reset

    return data


def _parse_iso(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp into a timezone-aware datetime."""
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _as_percent(value: Any) -> float | None:
    """Parse an explicit 0..100 percentage from the Grok payload.

    Grok reports usage as a real percentage (e.g. 8.0 == 8%), so unlike the
    Codex integration there is no fraction-vs-percent ambiguity to resolve.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        try:
            numeric = float(value.strip().rstrip("%"))
        except ValueError:
            return None
    else:
        return None

    if numeric < 0 or numeric > 1000:
        return None
    return round(numeric, 2)
