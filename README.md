# xAI Grok Usage - Home Assistant Integration

A custom Home Assistant integration that monitors xAI Grok subscription usage from the Grok CLI billing endpoint.

Grok exposes a single **weekly** usage window (there is no 5-hour window like OpenAI Codex).

## Sensors

- **Weekly Usage Limit** (%)
- **Weekly Reset Time** (timestamp)
- **API Error** (0 = healthy, 1 = failing)

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Restart Home Assistant
3. Install "xAI Grok Usage"
4. Go to Settings -> Devices & Services -> Add Integration -> "xAI Grok Usage"
5. Follow the instructions

### Manual

1. Copy `custom_components/hass_grok_usage/` to your HA `custom_components/` directory
2. Restart Home Assistant
3. Add the integration via the UI

## Setup

This integration accepts credentials generated on another machine where the Grok CLI is logged in.

### Required credentials

- `Access Token` (required)
- `Account ID` (optional but recommended for multi-account setups)
- `Refresh Token` (optional but strongly recommended)

### How to obtain credentials (from another machine)

1. On the Grok machine, run: `grok login`
2. Open `~/.grok/auth.json`
3. Under the `https://auth.x.ai::...` entry, copy:
   - `key` -> Home Assistant `Access Token`
   - `refresh_token` -> Home Assistant `Refresh Token` (recommended)
   - `team_id` or `user_id` -> Home Assistant `Account ID` (optional)
4. After copying into Home Assistant, remove any generated/exported credential file you created for transfer.

## Options

- **Update interval** - How often to poll usage (default: 300 seconds, min: 60, max: 3600)
- **Access Token** - Credential used for `/v1/billing?format=credits`
- **Account ID** - Optional identifier used to keep multiple accounts distinct
- **Refresh Token** - Used to auto-refresh expired access tokens via xAI OAuth

## Notes

- This integration reads from `https://cli-chat-proxy.grok.com/v1/billing?format=credits`.
- This endpoint is not officially documented for third-party integrations and may change.
- If the access token expires and a refresh token is set, the integration refreshes tokens automatically via `https://auth.x.ai/oauth2/token`.

## License

MIT License - see [LICENSE](LICENSE) file for details.
