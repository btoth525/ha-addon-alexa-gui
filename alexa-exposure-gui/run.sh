#!/bin/sh
set -e

# Read supervisor options from /data/options.json (written by supervisor)
# Falls back to environment variables or hardcoded defaults when options file
# is absent (e.g. running outside supervisor in dev mode).
OPTIONS=/data/options.json
if [ -f "$OPTIONS" ]; then
    export HA_CONFIG_PATH="$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('ha_config_path', '/homeassistant'))")"
    export RELOCATE_SECRET="$(python3 -c "import json; print(str(json.load(open('$OPTIONS')).get('relocate_secret', True)).lower())")"
    export AUTO_RESTART="$(python3 -c "import json; print(str(json.load(open('$OPTIONS')).get('auto_restart_after_apply', False)).lower())")"
    export BACKUP_DIR="$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('backup_dir', '/homeassistant/alexa_gui_backups'))")"
else
    export HA_CONFIG_PATH="${HA_CONFIG_PATH:-/homeassistant}"
    export RELOCATE_SECRET="${RELOCATE_SECRET:-true}"
    export AUTO_RESTART="${AUTO_RESTART:-false}"
    export BACKUP_DIR="${BACKUP_DIR:-/homeassistant/alexa_gui_backups}"
fi

echo "Starting Alexa Exposure GUI on :8099"
exec uvicorn app.main:app --host 0.0.0.0 --port 8099
