from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, field_validator

ALLOWED_DISPLAY_CATEGORIES = {
    "LIGHT", "SWITCH", "SMARTPLUG", "FAN", "THERMOSTAT", "SMARTLOCK",
    "GARAGE_DOOR", "DOOR", "INTERIOR_BLIND", "EXTERIOR_BLIND",
    "SCENE_TRIGGER", "ACTIVITY_TRIGGER", "CONTACT_SENSOR", "MOTION_SENSOR",
    "SECURITY_PANEL", "OTHER",
}

SUPPORTED_DOMAINS = ["light", "switch", "fan", "climate", "lock", "cover", "script", "binary_sensor"]


class EntityUpdate(BaseModel):
    entity_id: str
    exposed: bool
    name_override: Optional[str] = None
    display_category: Optional[str] = None

    @field_validator("display_category")
    @classmethod
    def validate_category(cls, v):
        if v and v not in ALLOWED_DISPLAY_CATEGORIES:
            raise ValueError(f"Unknown display_category '{v}'. Allowed: {sorted(ALLOWED_DISPLAY_CATEGORIES)}")
        return v or None

    @field_validator("name_override")
    @classmethod
    def validate_name(cls, v):
        if v is not None and len(v) > 256:
            raise ValueError("name_override too long (max 256 chars)")
        return v or None


class SaveRequest(BaseModel):
    entities: List[EntityUpdate]


class EntityState(BaseModel):
    entity_id: str
    domain: str
    friendly_name: str
    exposed: bool
    name_override: Optional[str] = None
    display_category: Optional[str] = None


class StateResponse(BaseModel):
    migration_status: str
    migration_message: Optional[str] = None
    restart_required: bool
    supported_domains: List[str]
    entities: List[EntityState]


class SaveResponse(BaseModel):
    ok: bool
    restart_required: Optional[bool] = None
    restarting: Optional[bool] = None
    error: Optional[str] = None
    restored: Optional[bool] = None


class RestartResponse(BaseModel):
    ok: bool
    error: Optional[str] = None


class BackupEntry(BaseModel):
    filename: str
    timestamp: str


class RestoreRequest(BaseModel):
    filename: str
