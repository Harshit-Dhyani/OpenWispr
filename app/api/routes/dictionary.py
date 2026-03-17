"""Dictionary management API endpoints.

Provides CRUD operations for user dictionary entries that are applied
during transcript post-processing for correction purposes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_dictionary_service
from app.api.route_utils import log_route
from app.api.schemas import (
    DictionaryEntryCreateRequest,
    DictionaryEntryUpdateRequest,
    PreviewApplyRequest,
)
from app.api.services.dictionary_service import DictionaryService

router = APIRouter()


@router.get("/api/dictionary")
@log_route("GET", "/api/dictionary")
def list_dictionary_entries(
    scope: str | None = Query(None),
    search: str | None = Query(None),
    svc: DictionaryService = Depends(get_dictionary_service),
) -> dict:
    """
    List all dictionary entries with optional filtering.

    Args:
        scope: Optional scope filter (e.g., 'global', 'personal')
        search: Optional search term to filter entries

    Returns:
        dict: Contains 'entries' list of dictionary entries
    """
    return {"entries": svc.list_entries(scope=scope, search=search)}


@router.post("/api/dictionary")
@log_route("POST", "/api/dictionary")
def create_dictionary_entry(
    request: DictionaryEntryCreateRequest,
    svc: DictionaryService = Depends(get_dictionary_service),
) -> dict:
    """
    Create a new dictionary entry.

    Args:
        request: DictionaryEntryCreateRequest containing phrase, replacement, scope, enabled

    Returns:
        dict: Contains 'entry' object with created entry data

    Raises:
        HTTPException: 400 if creation fails, 409 if phrase conflicts
    """
    try:
        entry = svc.create_entry(
            phrase=str(request.phrase),
            replacement=str(request.replacement),
            scope=request.scope,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"entry": entry}


@router.put("/api/dictionary/{entry_id}")
@log_route("PUT", "/api/dictionary/{entry_id}")
def update_dictionary_entry(
    entry_id: str,
    request: DictionaryEntryUpdateRequest,
    svc: DictionaryService = Depends(get_dictionary_service),
) -> dict:
    """
    Update an existing dictionary entry.

    Args:
        entry_id: ID of the entry to update
        request: DictionaryEntryUpdateRequest containing fields to update

    Returns:
        dict: Contains 'entry' object with updated entry data

    Raises:
        HTTPException: 404 if entry not found, 400 if update fails, 409 if phrase conflicts
    """
    try:
        entry = svc.update_entry(entry_id, request.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Entry not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"entry": entry}


@router.delete("/api/dictionary/{entry_id}")
@log_route("DELETE", "/api/dictionary/{entry_id}")
def delete_dictionary_entry(
    entry_id: str,
    svc: DictionaryService = Depends(get_dictionary_service),
) -> dict:
    """
    Delete a dictionary entry.

    Args:
        entry_id: ID of the entry to delete

    Returns:
        dict: Contains 'success': True

    Raises:
        HTTPException: 404 if entry not found
    """
    deleted = svc.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"success": True}


@router.post("/api/dictionary/preview-apply")
@log_route("POST", "/api/dictionary/preview-apply")
def preview_dictionary_apply(
    request: PreviewApplyRequest,
    svc: DictionaryService = Depends(get_dictionary_service),
) -> dict:
    """
    Preview how dictionary corrections would apply to text.

    Args:
        request: PreviewApplyRequest containing text to preview

    Returns:
        dict: Contains text with dictionary corrections applied
    """
    return svc.preview_apply(request.text)
