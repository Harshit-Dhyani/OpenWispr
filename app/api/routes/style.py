from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_style_service
from app.api.route_utils import log_route
from app.api.services.style_service import StyleService

router = APIRouter()


@router.get("/api/style/profiles")
@log_route("GET", "/api/style/profiles")
def list_style_profiles(
    svc: StyleService = Depends(get_style_service),
) -> dict:
    return {
        "profiles": svc.list_profiles(),
        "assignments": svc.list_assignments(),
    }


@router.post("/api/style/profiles")
@log_route("POST", "/api/style/profiles")
def create_style_profile(
    request: dict,
    svc: StyleService = Depends(get_style_service),
) -> dict:
    try:
        profile = svc.create_profile(
            name=str(request.get("name", "")),
            style_key=str(request.get("style_key", "custom")),
            description=str(request.get("description", "")),
            rules=request.get("rules") if isinstance(request.get("rules"), dict) else {},
            enabled=bool(request.get("enabled", True)),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"profile": profile}


@router.put("/api/style/profiles/{profile_id}")
@log_route("PUT", "/api/style/profiles/{profile_id}")
def update_style_profile(
    profile_id: str,
    request: dict,
    svc: StyleService = Depends(get_style_service),
) -> dict:
    try:
        profile = svc.update_profile(profile_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Profile not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"profile": profile}


@router.delete("/api/style/profiles/{profile_id}")
@log_route("DELETE", "/api/style/profiles/{profile_id}")
def delete_style_profile(
    profile_id: str,
    svc: StyleService = Depends(get_style_service),
) -> dict:
    try:
        deleted = svc.delete_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"success": True}


@router.post("/api/style/assignments")
@log_route("POST", "/api/style/assignments")
def set_style_assignment(
    request: dict,
    svc: StyleService = Depends(get_style_service),
) -> dict:
    try:
        assignments = svc.set_assignment(
            context=str(request.get("context", "other")),
            profile_id=str(request.get("profile_id", "")),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Profile not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"assignments": assignments}


@router.post("/api/style/preview")
@log_route("POST", "/api/style/preview")
def preview_style(
    request: dict,
    svc: StyleService = Depends(get_style_service),
) -> dict:
    return svc.preview(
        text=str(request.get("text", "")),
        context=str(request.get("context", "other")),
        profile_id=request.get("profile_id"),
    )
