# Changelog

## 0.1.0 — 2026-06-28

- Initial release
- Phase 0 migration: extracts inline `alexa:` block to `!include alexa_config.yaml`, relocates `client_secret` to `secrets.yaml`, expands domain filter to explicit entity list
- Web GUI: domain tabs, search, bulk select, name overrides, display categories
- Validate via `/core/check` before every write; auto-restore on failure
- Timestamped backups before every write, max 20 kept
- Ingress-only (no host port)
