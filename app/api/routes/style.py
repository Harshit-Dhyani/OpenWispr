"""Style profile management API endpoints.

Provides APIs for creating, updating, and managing writing style profiles
that are applied to transcripts for tone and formatting consistency.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_style_service
from app.api.route_utils import log_route
from app.api.schemas import (
    StyleAssignmentRequest,
    StylePreviewRequest,
    StyleProfileCreateRequest,
    StyleProfileUpdateRequest,
)
from app.api.services.style_service import StyleService

router = APIRouter()


@router.get("/api/style/profiles")
@log_route("GET", "/api/style/profiles")
def list_style_profiles(
    svc: StyleService = Depends(get_style_service),
) -> dict:
    """
    List all style profiles and their assignments.

    Returns:
        dict: Contains 'profiles' list and 'assignments' list
    """
    return {
        "profiles": svc.list_profiles(),
        "assignments": svc.list_assignments(),
    }


@router.post("/api/style/profiles")
@log_route("POST", "/api/style/profiles")
def create_style_profile(
    request: StyleProfileCreateRequest,
    svc: StyleService = Depends(get_style_service),
) -> dict:
    """
    Create a new style profile.

    Args:
        request: StyleProfileCreateRequest containing name, style_key, description, rules, enabled

    Returns:
        dict: Contains 'profile' object with created profile data

    Raises:
        HTTPException: 400 if profile creation fails
    """
    try:
        profile = svc.create_profile(
            name=str(request.name),
            style_key=str(request.style_key),
            description=str(request.description),
            rules=request.rules,
            enabled=request.enabled,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"profile": profile}


@router.put("/api/style/profiles/{profile_id}")
@log_route("PUT", "/api/style/profiles/{profile_id}")
def update_style_profile(
    profile_id: str,
    request: StyleProfileUpdateRequest,
    svc: StyleService = Depends(get_style_service),
) -> dict:
    """
    Update an existing style profile.

    Args:
        profile_id: ID of the profile to update
        request: StyleProfileUpdateRequest containing fields to update

    Returns:
        dict: Contains 'profile' object with updated profile data

    Raises:
        HTTPException: 404 if profile not found, 400 if update fails
    """
    try:
        profile = svc.update_profile(profile_id, request.model_dump(exclude_unset=True))
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
    """
    Delete a style profile.

    Args:
        profile_id: ID of the profile to delete

    Returns:
        dict: Contains 'success': True

    Raises:
        HTTPException: 400 if deletion fails, 404 if profile not found
    """
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
    request: StyleAssignmentRequest,
    svc: StyleService = Depends(get_style_service),
) -> dict:
    """
    Set style profile assignment for a context.

    Args:
        request: StyleAssignmentRequest containing context and profile_id

    Returns:
        dict: Contains 'assignments' list with current assignments

    Raises:
        HTTPException: 404 if profile not found, 400 if assignment fails
    """
    try:
        assignments = svc.set_assignment(
            context=str(request.context),
            profile_id=str(request.profile_id),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Profile not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"assignments": assignments}


@router.post("/api/style/preview")
@log_route("POST", "/api/style/preview")
def preview_style(
    request: StylePreviewRequest,
    svc: StyleService = Depends(get_style_service),
) -> dict:
    """
    Preview how a style profile transforms text.

    Args:
        request: StylePreviewRequest containing text, context, and profile_id

    Returns:
        dict: Contains transformed text preview
    """
    return svc.preview(
        text=str(request.text),
        context=str(request.context),
        profile_id=request.profile_id,
    )
