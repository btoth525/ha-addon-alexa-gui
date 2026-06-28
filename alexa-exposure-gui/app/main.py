from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import List, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.models import (
    SaveRequest, SaveResponse, StateResponse, RestartResponse,
    EntityState, BackupEntry, RestoreRequest,
    SUPPORTED_DOMAINS,
)
from app import ha_client, yaml_ops

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Alexa Exposure GUI")

# Persistent flag file for restart_required
_DATA_DIR = Path("/data")
_RESTART_FLAG = _DATA_DIR / "restart_required"

# In-memory migration state (set at startup)
_migration_status: str = "unknown"
_migration_message: str = ""


def _is_restart_required() -> bool:
    return _RESTART_FLAG.exists()


def _set_restart_required(v: bool):
    if v:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _RESTART_FLAG.touch()
    else:
        _RESTART_FLAG.unlink(missing_ok=True)


@app.on_event("startup")
async def startup_event():
    global _migration_status, _migration_message

    state = yaml_ops._detect_migration_state()
    logger.info("Migration state: %s", state)

    if state == "already_migrated":
        _migration_status = "migrated"
        _migration_message = ""
        logger.info("Already migrated — skipping Phase 0")
        return

    if state == "not_configured":
        _migration_status = "not_configured"
        _migration_message = "No alexa: block found in configuration.yaml"
        logger.warning(_migration_message)
        return

    # needs_migration
    logger.info("Running Phase 0 migration...")
    try:
        live_states = await ha_client.get_supported_states()
        live_ids = [s["entity_id"] for s in live_states]
    except Exception as e:
        _migration_status = "migration_failed"
        _migration_message = f"Could not fetch live states for migration: {e}"
        logger.error(_migration_message)
        return

    status, msg = await yaml_ops.run_phase0_migration(live_ids)
    _migration_status = status
    _migration_message = msg if status != "migrated" else ""
    if status == "migrated":
        _set_restart_required(True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"ok": True}


@app.get("/api/state", response_model=StateResponse)
async def get_state():
    try:
        live_states = await ha_client.get_supported_states()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not reach HA: {e}")

    include_entities, entity_config = yaml_ops.read_alexa_config()
    exposed_set = set(include_entities)

    entities: List[EntityState] = []
    for s in live_states:
        eid = s["entity_id"]
        ec = entity_config.get(eid, {})
        entities.append(EntityState(
            entity_id=eid,
            domain=s["domain"],
            friendly_name=s["friendly_name"],
            exposed=eid in exposed_set,
            name_override=ec.get("name") if ec else None,
            display_category=ec.get("display_categories") if ec else None,
        ))

    return StateResponse(
        migration_status=_migration_status,
        migration_message=_migration_message or None,
        restart_required=_is_restart_required(),
        supported_domains=SUPPORTED_DOMAINS,
        entities=entities,
    )


@app.post("/api/save", response_model=SaveResponse)
async def save(req: SaveRequest):
    # Fetch live states for validation
    try:
        live_states = await ha_client.get_supported_states()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not reach HA: {e}")

    live_ids = {s["entity_id"] for s in live_states}

    # Validate all entity_ids exist in live states
    bad_ids = [e.entity_id for e in req.entities if e.entity_id not in live_ids]
    if bad_ids:
        raise HTTPException(status_code=400, detail=f"Unknown entity_ids: {bad_ids[:5]}")

    include_entities = [e.entity_id for e in req.entities if e.exposed]
    entity_config: Dict[str, Dict] = {}
    for e in req.entities:
        cfg = {}
        if e.name_override:
            cfg["name"] = e.name_override
        if e.display_category:
            cfg["display_categories"] = e.display_category
        if cfg:
            entity_config[e.entity_id] = cfg

    # Backup + write
    try:
        yaml_ops.write_alexa_config(include_entities, entity_config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Write failed: {e}")

    # Validate
    ok, msg = await ha_client.check_config()
    if not ok:
        # Restore from the backup that write_alexa_config just made
        backups = yaml_ops.list_backups()
        alexa_backups = [b for b in backups if b["filename"].startswith(yaml_ops.ALEXA_CONFIG_FILENAME)]
        if alexa_backups:
            yaml_ops.restore_backup(alexa_backups[0]["filename"])
        return SaveResponse(ok=False, error=msg, restored=True)

    auto_restart = os.environ.get("AUTO_RESTART", "false").lower() in ("true", "1", "yes")
    _set_restart_required(True)

    if auto_restart:
        r_ok, r_msg = await ha_client.restart_ha()
        if r_ok:
            _set_restart_required(False)
            return SaveResponse(ok=True, restart_required=False, restarting=True)
        else:
            return SaveResponse(ok=True, restart_required=True, error=r_msg)

    return SaveResponse(ok=True, restart_required=True)


@app.post("/api/restart", response_model=RestartResponse)
async def restart():
    ok, msg = await ha_client.restart_ha()
    if not ok:
        return RestartResponse(ok=False, error=msg)
    _set_restart_required(False)
    return RestartResponse(ok=True)


@app.get("/api/backups")
async def get_backups():
    return {"backups": yaml_ops.list_backups()}


@app.post("/api/restore", response_model=SaveResponse)
async def restore(req: RestoreRequest):
    success = yaml_ops.restore_backup(req.filename)
    if not success:
        raise HTTPException(status_code=400, detail="Backup not found or not an alexa_config backup")

    ok, msg = await ha_client.check_config()
    if not ok:
        return SaveResponse(ok=False, error=msg, restored=False)

    _set_restart_required(True)
    return SaveResponse(ok=True, restart_required=True)


# ---------------------------------------------------------------------------
# Static frontend — served last so API routes take priority
# ---------------------------------------------------------------------------

WWW_DIR = Path(__file__).parent.parent / "www"
app.mount("/", StaticFiles(directory=str(WWW_DIR), html=True), name="static")
