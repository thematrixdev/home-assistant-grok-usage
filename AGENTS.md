# AGENTS.md - Design Decisions & Implementation Notes

Architectural decisions and API discoveries for the xAI Grok Usage Home Assistant integration.
Structure mirrors the sibling `home-assistant-codex-usage` project.

## Project Preferences

- **Versioning:** Major version numbers only (1, 2, 3...). No semver.
- **Git commits:** Atomic commits. Each commit is one logical change.
- **Code style:** Short, simple, DRY without over-abstraction.
- **No manufacturer attribution:** xAI provides the API; the maintainer maintains the code.

## API Discovery

Reverse-engineered from the Grok CLI binary (`~/.grok/bin/grok`) and confirmed against
the live endpoint.

### Usage endpoint

- **Method:** `GET https://cli-chat-proxy.grok.com/v1/billing?format=credits`
- **Headers:**
  - `Authorization: Bearer <access_token>`
  - `x-grok-client-version: 0.2.93`
  - `Accept: application/json`

### Response structure

```json
{
  "config": {
    "currentPeriod": {
      "type": "USAGE_PERIOD_TYPE_WEEKLY",
      "start": "2026-07-09T01:29:34.782670+00:00",
      "end": "2026-07-16T01:29:34.782670+00:00"
    },
    "creditUsagePercent": 8.0,
    "onDemandCap": { "val": 0 },
    "onDemandUsed": { "val": 0 },
    "productUsage": [ { "product": "GrokBuild", "usagePercent": 8.0 } ],
    "isUnifiedBillingUser": true,
    "prepaidBalance": { "val": 0 },
    "billingPeriodStart": "2026-07-09T01:29:34.782670+00:00",
    "billingPeriodEnd": "2026-07-16T01:29:34.782670+00:00"
  }
}
```

**Key differences from Codex:**

- Grok exposes a single **weekly** window (`USAGE_PERIOD_TYPE_WEEKLY`). There is **no
  5-hour window** and no code-review window.
- `creditUsagePercent` is an **explicit** 0-100 percentage (8.0 == 8%), so there is no
  fraction-vs-percent ambiguity — `_as_percent` does not scale sub-1 values.
- Weekly reset time comes from `config.currentPeriod.end` (falls back to `billingPeriodEnd`).

### Credentials

Stored in `~/.grok/auth.json`, keyed by `https://auth.x.ai::<oidc_client_id>`:

- `key` -> Access Token
- `refresh_token` -> Refresh Token
- `team_id` / `user_id` -> optional Account ID (for multi-account uniqueness)

### Token refresh

- **Endpoint:** `https://auth.x.ai/oauth2/token` (from the xAI OIDC discovery document)
- **Client ID:** `b1a00492-073a-47ea-816f-4c329264a828`
- **Payload:** `grant_type=refresh_token`, `refresh_token`, `client_id`

## Architecture Decisions

Same as the Codex integration: `DataUpdateCoordinator` polling, one service device with
multiple sensors, deferred loading (sensors show "unavailable" when a data key is absent),
ISO timestamps handed to HA with `device_class: timestamp`.

## Release Process

Major version numbering only (1, 2, 3...). Bump `manifest.json` version, commit, tag, and
create a GitHub Release (HACS shows the 5 most recent releases).
