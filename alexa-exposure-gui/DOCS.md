# Alexa Exposure GUI — Documentation

## Overview

This add-on provides a web interface to choose exactly which Home Assistant entities are exposed to your custom Alexa Smart Home skill (the one backed by an AWS Lambda that proxies requests to HA's `/api/alexa/smart_home` endpoint). It owns `/config/alexa_config.yaml` and rewrites it whenever you save changes.

## First Start — Phase 0 Migration

On the very first start, the add-on performs a one-time migration:

1. **Backs up** `configuration.yaml` and `secrets.yaml` (timestamped copies in the backup directory).
2. **Extracts** the inline `alexa:` block from `configuration.yaml` and replaces it with `alexa: !include alexa_config.yaml`. Everything else in that file is untouched byte-for-byte.
3. **Relocates** the `client_secret` literal into `secrets.yaml` as `alexa_client_secret` (unless `relocate_secret: false`). The add-on never logs or re-emits the raw value afterward.
4. **Expands** the current domain-based filter to an explicit list of all 130 supported entities — day-one exposure is unchanged, you trim from there.
5. **Validates** via `POST /supervisor/core/check`. If that fails, backups are restored automatically.
6. Sets a **"Restart required"** banner — restart is user-initiated, not automatic.

Migration is idempotent: if `alexa: !include alexa_config.yaml` is already present and `alexa_config.yaml` exists, the add-on skips straight to serving the UI.

## Using the GUI

- **Domain tabs** filter the 130 entities by domain (light, switch, fan, etc.). The count shows exposed/total.
- **Search** filters by entity ID or friendly name within the active tab.
- **Checkboxes** toggle exposure. "Select all" / "Deselect all" act on the current tab's visible entities.
- **Name override** sets the name Alexa will use (leave blank to use the HA friendly name).
- **Category** sets the Alexa display category (e.g. `LIGHT`, `SWITCH`, `SMARTPLUG`). Leave blank to use Alexa's default.
- **Save** validates the new config against HA before committing. If validation fails, the previous config is restored automatically and an error is shown.
- **Restart HA** button triggers a core restart after confirmation. After restart, run Alexa device discovery.

## Alexa Device Discovery

After every restart that changes your exposure list, you must re-run discovery in the Alexa app:

> **Alexa app → Devices → ⊕ → Add Device → Other → Discover**

Or say: *"Alexa, discover devices."*

The add-on cannot do this for you — it is an Alexa cloud action.

## emulated_hue Note

This add-on controls only the `alexa:` Smart Home skill integration. Your HA instance also runs `emulated_hue`, which independently exposes a separate set of entities (~15) to Alexa via local Hue-bridge emulation. Removing an entity in this GUI does **not** remove it from `emulated_hue`. If you want to consolidate, consider disabling `emulated_hue` separately once you've confirmed the skill covers its entity set — that is outside this add-on's scope.

## Options

| Option | Default | Description |
|---|---|---|
| `ha_config_path` | `/homeassistant` | Mount path of HA's `/config` inside the container |
| `relocate_secret` | `true` | Move `client_secret` to `secrets.yaml` on migration |
| `auto_restart_after_apply` | `false` | Restart HA automatically after a successful Save |
| `backup_dir` | `/homeassistant/alexa_gui_backups` | Where timestamped backups are stored |

## Backups

Before every write, the current `alexa_config.yaml` is backed up with a UTC timestamp to `backup_dir`. The last 20 backups are kept; older ones are pruned automatically. Use the `/api/backups` and `/api/restore` endpoints to list and restore backups programmatically.

## Security

- Served via HA ingress only — no direct LAN port. Access is gated by HA authentication.
- Uses the auto-injected `SUPERVISOR_TOKEN`; no user-supplied token required.
- `client_secret` and `SUPERVISOR_TOKEN` are never logged or displayed.
- All user input that lands in YAML is emitter-quoted; unknown `display_categories` are rejected with HTTP 400.
