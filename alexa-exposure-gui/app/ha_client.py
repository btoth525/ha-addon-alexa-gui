from __future__ import annotations
import os
import logging
import httpx
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

SUPPORTED_DOMAINS = {"light", "switch", "fan", "climate", "lock", "cover", "script", "binary_sensor", "media_player"}

_supervisor_token: Optional[str] = None
_ha_token: Optional[str] = None


def _get_headers() -> Dict[str, str]:
    token = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _is_dev_mode() -> bool:
    return bool(os.environ.get("HA_TOKEN")) and not os.environ.get("SUPERVISOR_TOKEN")


def _supervisor_base() -> str:
    return "http://supervisor"


def _direct_base() -> str:
    return os.environ.get("HA_URL", "https://ha.plexserver525.com")


async def get_supported_states() -> List[Dict]:
    """Fetch entity states for all supported domains."""
    headers = _get_headers()

    if _is_dev_mode():
        url = f"{_direct_base()}/api/states"
    else:
        url = f"{_supervisor_base()}/core/api/states"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        all_states = resp.json()

    result = []
    for state in all_states:
        entity_id = state.get("entity_id", "")
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        if domain in SUPPORTED_DOMAINS:
            result.append({
                "entity_id": entity_id,
                "domain": domain,
                "friendly_name": state.get("attributes", {}).get("friendly_name", entity_id),
            })

    return sorted(result, key=lambda x: x["entity_id"])


async def check_config() -> tuple[bool, str]:
    """Run HA config check via supervisor. Returns (success, message)."""
    headers = _get_headers()

    if _is_dev_mode():
        logger.warning("Dev mode: skipping supervisor /core/check (no SUPERVISOR_TOKEN). Config not fully validated.")
        return True, "Dev mode: config check skipped"

    url = f"{_supervisor_base()}/core/check"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers)
            if resp.status_code == 404:
                return False, "Supervisor /core/check not found (404). Run 'ha core check' manually."
            if resp.status_code >= 400:
                body = resp.text
                return False, f"Config check failed (HTTP {resp.status_code}): {body}"
            return True, "Config check passed"
    except httpx.RequestError as e:
        return False, f"Config check request error: {e}"


async def restart_ha() -> tuple[bool, str]:
    """Restart HA core via supervisor. Returns (success, message)."""
    headers = _get_headers()

    if _is_dev_mode():
        url = f"{_direct_base()}/api/services/homeassistant/restart"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json={})
            if resp.status_code >= 400:
                return False, f"Restart failed (HTTP {resp.status_code}): {resp.text}"
            return True, "Restart triggered"

    url = f"{_supervisor_base()}/core/restart"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers)
            if resp.status_code == 404:
                return False, "Supervisor /core/restart not found (404). Run 'ha core restart' manually."
            if resp.status_code >= 400:
                return False, f"Restart failed (HTTP {resp.status_code}): {resp.text}"
            return True, "Restart triggered"
    except httpx.RequestError as e:
        return False, f"Restart request error: {e}"
