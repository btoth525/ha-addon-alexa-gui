#!/usr/bin/with-contenv bashio
export HA_CONFIG_PATH="$(bashio::config 'ha_config_path')"
export RELOCATE_SECRET="$(bashio::config 'relocate_secret')"
export AUTO_RESTART="$(bashio::config 'auto_restart_after_apply')"
export BACKUP_DIR="$(bashio::config 'backup_dir')"
# SUPERVISOR_TOKEN is injected automatically; do NOT log it.
bashio::log.info "Starting Alexa Exposure GUI on :8099"
exec uvicorn app.main:app --host 0.0.0.0 --port 8099
