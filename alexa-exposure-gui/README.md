# Alexa Exposure GUI

A Home Assistant local add-on that provides a web GUI to select exactly which HA entities are exposed to your custom Alexa Smart Home skill. Replaces hand-editing `alexa_config.yaml`.

## Features

- **Phase 0 migration**: automatically extracts your inline `alexa:` block to a managed file and moves `client_secret` to `secrets.yaml`
- **130-entity GUI**: domain tabs, search, bulk select/deselect, name overrides, category picker
- **Safe writes**: validates via `ha core check` before committing; auto-restores on failure
- **Timestamped backups** before every write
- **Ingress-only** — gated by HA authentication, no LAN port exposed

## Installation

Copy the `alexa-exposure-gui/` folder into your HA local add-ons directory (via Samba, SSH, or Studio Code Server), then:

1. Settings → Add-ons → Add-on Store → ⋮ → **Check for updates**
2. **Local add-ons** → **Alexa Exposure GUI** → Install
3. Review options (defaults are correct for most setups)
4. **Start** → open **Web UI**

See [DOCS.md](DOCS.md) for full documentation.
