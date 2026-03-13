from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.route_utils import apply_runtime_log_levels, log_route, resolve_runtime_log_level
from app.api.strings.en import API_STRINGS
from app.core.settings.manager import get_settings_manager

router = APIRouter()


@router.get("/api/settings")
@log_route("GET", "/api/settings")
def get_settings() -> dict[str, Any]:
    return get_settings_manager().get_settings_dict()


@router.post("/api/settings")
@log_route("POST", "/api/settings")
def save_settings(request: dict[str, Any]) -> dict[str, Any]:
    manager = get_settings_manager()
    success = manager.import_settings(request)
    if not success:
        raise HTTPException(status_code=400, detail=API_STRINGS.errors.save_settings_failed)

    log_level = resolve_runtime_log_level(request)
    apply_runtime_log_levels(log_level)
    return {"success": True, "message": API_STRINGS.messages.settings_saved}


@router.post("/api/settings/reset")
@log_route("POST", "/api/settings/reset")
def reset_settings() -> dict[str, Any]:
    manager = get_settings_manager()
    manager.reset_to_defaults()
    return {"success": True, "message": API_STRINGS.messages.settings_reset}
