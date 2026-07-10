"""Config flow for the xAI Grok Usage integration."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_ACCOUNT_NAME,
    CONF_REFRESH_TOKEN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    GROK_BILLING_API_URL,
    GROK_CLIENT_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class GrokUsageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for xAI Grok Usage."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle setup with manual credential input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            access_token = _normalize_credential_value(user_input.get(CONF_ACCESS_TOKEN, ""))
            account_id = _normalize_credential_value(user_input.get(CONF_ACCOUNT_ID, ""))
            refresh_token = _normalize_credential_value(user_input.get(CONF_REFRESH_TOKEN, ""))

            if not access_token:
                errors[CONF_ACCESS_TOKEN] = "missing_access_token"
            elif await self._validate_credentials(access_token):
                account_name = user_input.get(CONF_ACCOUNT_NAME, "").strip()
                unique_id = account_id if account_id else DOMAIN
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = "xAI Grok Usage"
                if account_name:
                    title = f"xAI Grok Usage ({account_name})"

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_ACCESS_TOKEN: access_token,
                        CONF_ACCOUNT_ID: account_id,
                        CONF_ACCOUNT_NAME: account_name,
                        CONF_REFRESH_TOKEN: refresh_token,
                    },
                    options={
                        CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                        CONF_ACCESS_TOKEN: access_token,
                        CONF_ACCOUNT_ID: account_id,
                        CONF_REFRESH_TOKEN: refresh_token,
                    },
                )
            else:
                errors[CONF_ACCESS_TOKEN] = "invalid_access_token"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Optional(CONF_ACCOUNT_ID, default=""): str,
                    vol.Optional(CONF_ACCOUNT_NAME, default=""): str,
                    vol.Optional(CONF_REFRESH_TOKEN, default=""): str,
                }
            ),
            errors=errors,
        )

    async def _validate_credentials(self, access_token: str) -> bool:
        """Validate credentials by performing a Grok billing request."""
        try:
            session = aiohttp_client.async_get_clientsession(self.hass)
            resp = await session.get(
                GROK_BILLING_API_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "x-grok-client-version": GROK_CLIENT_VERSION,
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            )
            return resp.ok
        except aiohttp.ClientError:
            _LOGGER.exception("Grok auth validation request failed")
            return False

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth when credentials are invalid or expired."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth with replacement credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            access_token = _normalize_credential_value(user_input.get(CONF_ACCESS_TOKEN, ""))
            account_id = _normalize_credential_value(user_input.get(CONF_ACCOUNT_ID, ""))
            refresh_token = _normalize_credential_value(user_input.get(CONF_REFRESH_TOKEN, ""))
            if not access_token:
                errors[CONF_ACCESS_TOKEN] = "missing_access_token"
            elif await self._validate_credentials(access_token):
                reauth_entry = self._get_reauth_entry()
                stored_id = reauth_entry.data.get(CONF_ACCOUNT_ID)

                # Allow replacing the migration sentinel (entry_id placeholder)
                # but block reauth with a genuinely different account.
                if (
                    account_id
                    and stored_id
                    and stored_id != reauth_entry.entry_id
                    and account_id != stored_id
                ):
                    return self.async_abort(reason="account_mismatch")

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    unique_id=account_id if account_id else reauth_entry.unique_id,
                    data_updates={
                        CONF_ACCESS_TOKEN: access_token,
                        CONF_ACCOUNT_ID: account_id,
                        CONF_REFRESH_TOKEN: refresh_token,
                    },
                )
            else:
                errors[CONF_ACCESS_TOKEN] = "invalid_access_token"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Optional(CONF_ACCOUNT_ID, default=""): str,
                    vol.Optional(CONF_REFRESH_TOKEN, default=""): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow."""
        return GrokUsageOptionsFlow()


class GrokUsageOptionsFlow(OptionsFlow):
    """Handle options for xAI Grok Usage."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        current_access_token = self.config_entry.options.get(
            CONF_ACCESS_TOKEN,
            self.config_entry.data.get(CONF_ACCESS_TOKEN, ""),
        )
        current_account_id = self.config_entry.options.get(
            CONF_ACCOUNT_ID,
            self.config_entry.data.get(CONF_ACCOUNT_ID, ""),
        )
        current_refresh_token = self.config_entry.options.get(
            CONF_REFRESH_TOKEN,
            self.config_entry.data.get(CONF_REFRESH_TOKEN, ""),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UPDATE_INTERVAL, default=current_interval): vol.All(
                        int, vol.Range(min=60, max=3600)
                    ),
                    vol.Required(CONF_ACCESS_TOKEN, default=current_access_token): str,
                    vol.Optional(CONF_ACCOUNT_ID, default=current_account_id): str,
                    vol.Optional(CONF_REFRESH_TOKEN, default=current_refresh_token): str,
                }
            ),
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
