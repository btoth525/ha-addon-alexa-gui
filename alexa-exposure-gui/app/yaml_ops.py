from __future__ import annotations
import os
import re
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import TaggedScalar

logger = logging.getLogger(__name__)

ALEXA_CONFIG_FILENAME = "alexa_config.yaml"
MANAGED_COMMENT = (
    "MANAGED BY Alexa Exposure GUI — do not edit filter/entity_config by hand;\n"
    "the add-on rewrites them. The connection header below is preserved across rewrites."
)
MAX_BACKUPS = 20


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096

    def secret_representer(dumper, data):
        return dumper.represent_scalar("!secret", data.value)

    y.representer.add_representer(TaggedScalar, secret_representer)
    return y


def _config_path() -> Path:
    return Path(os.environ.get("HA_CONFIG_PATH", "/homeassistant"))


def _backup_dir() -> Path:
    return Path(os.environ.get("BACKUP_DIR", "/homeassistant/alexa_gui_backups"))


def _alexa_config_path() -> Path:
    return _config_path() / ALEXA_CONFIG_FILENAME


def _configuration_yaml_path() -> Path:
    return _config_path() / "configuration.yaml"


def _secrets_yaml_path() -> Path:
    return _config_path() / "secrets.yaml"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")


def _ensure_backup_dir():
    bdir = _backup_dir()
    bdir.mkdir(parents=True, exist_ok=True)
    return bdir


def _backup_file(src: Path, label: Optional[str] = None) -> Optional[Path]:
    if not src.exists():
        return None
    bdir = _ensure_backup_dir()
    stem = label or src.name
    dest = bdir / f"{stem}.{_utc_stamp()}.bak"
    shutil.copy2(src, dest)
    logger.info("Backed up %s → %s", src, dest)
    _prune_backups(bdir, stem)
    return dest


def _prune_backups(bdir: Path, stem: str):
    pattern = f"{stem}.*.bak"
    backups = sorted(bdir.glob(pattern), key=lambda p: p.stat().st_mtime)
    excess = len(backups) - MAX_BACKUPS
    for old in backups[:excess]:
        old.unlink()
        logger.info("Pruned old backup: %s", old)


def backup_alexa_config() -> Optional[Path]:
    return _backup_file(_alexa_config_path(), ALEXA_CONFIG_FILENAME)


# ---------------------------------------------------------------------------
# Phase 0: text-based extraction of inline `alexa:` block
# ---------------------------------------------------------------------------

def _find_alexa_block_in_text(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Return (start_line_index, end_line_index) — exclusive end — of the `alexa:` block.
    The block starts at a line beginning with `alexa:` at column 0 and ends just
    before the next line that starts at column 0 with a non-space, non-`#` character,
    or at EOF.
    """
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if re.match(r'^alexa\s*:', line):
            start = i
            break
    if start is None:
        return None, None

    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].rstrip("\n\r")
        if stripped and not stripped[0].isspace() and not stripped[0] == "#":
            end = i
            break

    return start, end


def _extract_alexa_block(text: str) -> Tuple[Optional[str], str]:
    """
    Extract the inline `alexa:` block from configuration.yaml text.
    Returns (extracted_block_text, new_configuration_text) where the block
    is replaced with `alexa: !include alexa_config.yaml`.
    """
    start, end = _find_alexa_block_in_text(text)
    if start is None:
        return None, text

    lines = text.splitlines(keepends=True)
    block_lines = lines[start:end]
    block_text = "".join(block_lines)

    replacement = "alexa: !include alexa_config.yaml\n"
    new_lines = lines[:start] + [replacement] + lines[end:]
    new_text = "".join(new_lines)
    return block_text, new_text


def _detect_migration_state() -> str:
    """
    Returns one of:
      'already_migrated'  — configuration.yaml has the !include and alexa_config.yaml exists
      'needs_migration'   — inline alexa: block present
      'not_configured'    — no alexa: block at all
    """
    cfg = _configuration_yaml_path()
    if not cfg.exists():
        return "not_configured"

    text = cfg.read_text(encoding="utf-8")
    if re.search(r'^alexa\s*:\s*!include\s+alexa_config\.yaml', text, re.MULTILINE):
        if _alexa_config_path().exists():
            return "already_migrated"

    start, _ = _find_alexa_block_in_text(text)
    if start is not None:
        return "needs_migration"

    return "not_configured"


# ---------------------------------------------------------------------------
# Secret relocation
# ---------------------------------------------------------------------------

def _secret_tag_value() -> TaggedScalar:
    ts = TaggedScalar(value="alexa_client_secret", tag="!secret")
    return ts


def _relocate_secret_to_secrets_yaml(value: str):
    secrets_path = _secrets_yaml_path()
    if secrets_path.exists():
        content = secrets_path.read_text(encoding="utf-8")
        if "alexa_client_secret:" in content:
            logger.info("alexa_client_secret already in secrets.yaml, skipping")
            return
        secrets_path.write_text(content + f"\nalexa_client_secret: {value}\n", encoding="utf-8")
    else:
        secrets_path.write_text(f"alexa_client_secret: {value}\n", encoding="utf-8")
    logger.info("Relocated client_secret to secrets.yaml")


def _is_secret_tag(value) -> bool:
    return isinstance(value, TaggedScalar) and value.tag == "!secret"


# ---------------------------------------------------------------------------
# Parse extracted alexa block into a managed dict
# ---------------------------------------------------------------------------

def _parse_alexa_block(block_text: str) -> Dict:
    """Parse the raw `alexa:` block text into a dict. The top-level key is `alexa`."""
    y = _yaml()
    from io import StringIO
    data = y.load(StringIO(block_text))
    if data is None:
        return {}
    return dict(data)


def _get_smart_home(parsed_block: Dict) -> Dict:
    alexa = parsed_block.get("alexa", {}) or {}
    smart_home = alexa.get("smart_home", {}) or {}
    return smart_home


# ---------------------------------------------------------------------------
# Build managed alexa_config.yaml from scratch (migration)
# ---------------------------------------------------------------------------

def _build_managed_doc(smart_home: Dict, entity_ids: List[str], relocate_secret: bool) -> Any:
    """Build a ruamel CommentedMap for the managed alexa_config.yaml."""
    from ruamel.yaml.comments import CommentedMap

    doc = CommentedMap()
    doc.yaml_set_start_comment(MANAGED_COMMENT)

    sh = CommentedMap()
    doc["smart_home"] = sh

    for key in ("locale", "endpoint", "client_id"):
        if key in smart_home:
            sh[key] = smart_home[key]

    client_secret = smart_home.get("client_secret")
    if _is_secret_tag(client_secret):
        sh["client_secret"] = client_secret
    elif relocate_secret and isinstance(client_secret, str):
        _relocate_secret_to_secrets_yaml(client_secret)
        sh["client_secret"] = _secret_tag_value()
    else:
        if client_secret is not None:
            sh["client_secret"] = client_secret

    flt = CommentedMap()
    sh["filter"] = flt
    flt["include_entities"] = sorted(entity_ids)

    entity_config_src = smart_home.get("entity_config", {}) or {}
    if entity_config_src:
        ec = CommentedMap()
        for eid, cfg in entity_config_src.items():
            if eid in set(entity_ids):
                ec[eid] = CommentedMap(cfg) if isinstance(cfg, dict) else cfg
            else:
                logger.info("Dropping stale entity_config entry: %s (not in live states)", eid)
        if ec:
            sh["entity_config"] = ec

    return doc


# ---------------------------------------------------------------------------
# Write alexa_config.yaml (round-trip update)
# ---------------------------------------------------------------------------

def write_alexa_config(
    include_entities: List[str],
    entity_config: Dict[str, Dict],
) -> None:
    """
    Update alexa_config.yaml in-place via ruamel round-trip.
    Replaces only filter.include_entities and entity_config; preserves everything else.
    """
    from io import StringIO
    from ruamel.yaml.comments import CommentedMap

    backup_alexa_config()

    alexa_path = _alexa_config_path()
    y = _yaml()

    if alexa_path.exists():
        with open(alexa_path, encoding="utf-8") as f:
            doc = y.load(f)
        if doc is None:
            doc = CommentedMap()
    else:
        doc = CommentedMap()
        doc.yaml_set_start_comment(MANAGED_COMMENT)

    sh = doc.get("smart_home")
    if sh is None:
        sh = CommentedMap()
        doc["smart_home"] = sh

    flt = sh.get("filter")
    if flt is None:
        flt = CommentedMap()
        sh["filter"] = flt

    flt["include_entities"] = sorted(include_entities)
    if "include_domains" in flt:
        del flt["include_domains"]

    if entity_config:
        ec = CommentedMap()
        for eid, cfg in sorted(entity_config.items()):
            entry = CommentedMap()
            if cfg.get("name"):
                entry["name"] = cfg["name"]
            if cfg.get("display_categories"):
                entry["display_categories"] = cfg["display_categories"]
            if entry:
                ec[eid] = entry
        sh["entity_config"] = ec
    elif "entity_config" in sh:
        del sh["entity_config"]

    buf = StringIO()
    y.dump(doc, buf)
    alexa_path.write_text(buf.getvalue(), encoding="utf-8")
    logger.info("Wrote %s with %d entities", alexa_path, len(include_entities))


# ---------------------------------------------------------------------------
# Read current alexa_config.yaml
# ---------------------------------------------------------------------------

def read_alexa_config() -> Tuple[List[str], Dict[str, Dict]]:
    """
    Returns (include_entities, entity_config_map).
    entity_config_map: {entity_id: {name, display_categories}}
    """
    alexa_path = _alexa_config_path()
    if not alexa_path.exists():
        return [], {}

    y = _yaml()
    with open(alexa_path, encoding="utf-8") as f:
        doc = y.load(f)

    if not doc:
        return [], {}

    sh = doc.get("smart_home", {}) or {}
    flt = sh.get("filter", {}) or {}
    include_entities = list(flt.get("include_entities", []) or [])

    ec_raw = sh.get("entity_config", {}) or {}
    entity_config = {}
    for eid, cfg in ec_raw.items():
        if isinstance(cfg, dict):
            entity_config[eid] = {
                "name": cfg.get("name"),
                "display_categories": cfg.get("display_categories"),
            }

    return include_entities, entity_config


# ---------------------------------------------------------------------------
# Full Phase 0 migration
# ---------------------------------------------------------------------------

async def run_phase0_migration(live_entity_ids: List[str]) -> Tuple[str, str]:
    """
    Execute the Phase 0 migration.
    Returns (status, message) where status is 'migrated' or 'migration_failed'.

    Caller is responsible for detecting state first (not_configured / already_migrated)
    — this function assumes we are in 'needs_migration' state.
    """
    cfg_path = _configuration_yaml_path()
    secrets_path = _secrets_yaml_path()
    relocate = os.environ.get("RELOCATE_SECRET", "true").lower() in ("true", "1", "yes")

    # Step 3: backup
    cfg_backup = _backup_file(cfg_path, "configuration.yaml")
    secrets_backup = _backup_file(secrets_path, "secrets.yaml")

    cfg_text = cfg_path.read_text(encoding="utf-8")

    # Step 4: text-based extraction
    block_text, new_cfg_text = _extract_alexa_block(cfg_text)
    if block_text is None:
        return "migration_failed", "Could not locate inline alexa: block in configuration.yaml"

    # Parse the extracted block
    parsed = _parse_alexa_block(block_text)
    smart_home = _get_smart_home(parsed)

    # Step 6: expand exposure — union of existing include_entities with all live entity_ids
    existing_include = set(smart_home.get("filter", {}).get("include_entities", []) or [])
    all_entity_ids = sorted(existing_include | set(live_entity_ids))

    # Step 7: build managed alexa_config.yaml
    _ensure_backup_dir()
    backup_alexa_config()  # backup any pre-existing alexa_config.yaml

    doc = _build_managed_doc(smart_home, all_entity_ids, relocate)

    from io import StringIO
    y = _yaml()
    buf = StringIO()
    y.dump(doc, buf)
    _alexa_config_path().write_text(buf.getvalue(), encoding="utf-8")
    logger.info("Wrote new alexa_config.yaml with %d entities", len(all_entity_ids))

    # Write the updated configuration.yaml (text-based)
    cfg_path.write_text(new_cfg_text, encoding="utf-8")
    logger.info("Updated configuration.yaml to use !include alexa_config.yaml")

    # Step 8: validate
    from app.ha_client import check_config
    ok, msg = await check_config()
    if not ok:
        logger.error("Config check failed after migration: %s", msg)
        # Restore backups
        if cfg_backup and cfg_backup.exists():
            shutil.copy2(cfg_backup, cfg_path)
            logger.info("Restored configuration.yaml from backup")
        if secrets_backup and secrets_backup.exists():
            shutil.copy2(secrets_backup, secrets_path)
            logger.info("Restored secrets.yaml from backup")
        elif not secrets_backup and secrets_path.exists():
            # secrets.yaml was created by us — remove it if it didn't exist before
            pass
        return "migration_failed", msg

    logger.info("Phase 0 migration complete")
    return "migrated", "Migration successful. Restart required to apply."


# ---------------------------------------------------------------------------
# Backup listing and restore
# ---------------------------------------------------------------------------

def list_backups() -> List[Dict]:
    bdir = _backup_dir()
    if not bdir.exists():
        return []
    backups = []
    for f in sorted(bdir.glob("*.bak"), key=lambda p: p.stat().st_mtime, reverse=True):
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        backups.append({
            "filename": f.name,
            "timestamp": mtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return backups


def restore_backup(filename: str) -> bool:
    bdir = _backup_dir()
    src = bdir / filename
    if not src.exists():
        return False
    # Only allow restoring alexa_config.yaml backups
    if not filename.startswith(ALEXA_CONFIG_FILENAME):
        return False
    backup_alexa_config()
    shutil.copy2(src, _alexa_config_path())
    logger.info("Restored %s from backup %s", _alexa_config_path(), filename)
    return True
