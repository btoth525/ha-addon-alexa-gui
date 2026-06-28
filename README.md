# ha-addon-alexa-gui

A Home Assistant local add-on repository containing the **Alexa Exposure GUI** — a web interface to choose exactly which HA entities are exposed to your custom Alexa Smart Home skill, replacing hand-edited YAML.

## Add-ons

### [Alexa Exposure GUI](alexa-exposure-gui/)

Pick which of your 130 Alexa-compatible entities are exposed to your Smart Home skill. Features:

- **Phase 0 migration** — automatically extracts your inline `alexa:` block into a managed `alexa_config.yaml` and moves `client_secret` to `secrets.yaml` (one-time, idempotent, self-rolling-back on failure)
- **Web GUI** — domain tabs, search, bulk select/deselect, name overrides, Alexa category picker
- **Safe writes** — validates via `ha core check` before every commit; auto-restores backup on failure
- **Ingress-only** — served through HA auth, no direct LAN port

## Installation via HA Add-on Store

1. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. Add: `https://github.com/btoth525/ha-addon-alexa-gui`
3. Find **Alexa Exposure GUI** under the new repository section → **Install**
4. Review options (defaults are correct) → **Start** → **Open Web UI**

See [alexa-exposure-gui/DOCS.md](alexa-exposure-gui/DOCS.md) for full documentation.
