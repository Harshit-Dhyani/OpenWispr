"""Snippet management API endpoints.

Provides APIs for creating, updating, and managing text snippets that are
expanded during transcript post-processing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.deps import get_snippet_service
from app.api.route_utils import log_route
from app.api.schemas import (
    PreviewExpandRequest,
    SnippetCreateRequest,
    SnippetImportRequest,
    SnippetUpdateRequest,
)
from app.api.services.snippet_service import SnippetService

router = APIRouter()


@router.get("/api/snippets")
@log_route("GET", "/api/snippets")
def list_snippets(
    scope: str | None = Query(None),
    search: str | None = Query(None),
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    """
    List all text snippets with optional filtering.

    Args:
        scope: Optional scope filter (e.g., 'global', 'personal')
        search: Optional search term to filter snippets

    Returns:
        dict: Contains 'entries' list of snippet entries
    """
    return {"entries": svc.list_entries(scope=scope, search=search)}


@router.post("/api/snippets")
@log_route("POST", "/api/snippets")
def create_snippet(
    request: SnippetCreateRequest,
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    """
    Create a new text snippet.

    Args:
        request: SnippetCreateRequest containing trigger, expansion, scope, enabled

    Returns:
        dict: Contains 'entry' object with created snippet data

    Raises:
        HTTPException: 400 if creation fails, 409 if trigger conflicts
    """
    try:
        entry = svc.create_entry(
            trigger=str(request.trigger),
            expansion=str(request.expansion),
            scope=request.scope,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"entry": entry}


@router.put("/api/snippets/{snippet_id}")
@log_route("PUT", "/api/snippets/{snippet_id}")
def update_snippet(
    snippet_id: str,
    request: SnippetUpdateRequest,
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    """
    Update an existing text snippet.

    Args:
        snippet_id: ID of the snippet to update
        request: SnippetUpdateRequest containing fields to update

    Returns:
        dict: Contains 'entry' object with updated snippet data

    Raises:
        HTTPException: 404 if snippet not found, 400 if update fails, 409 if trigger conflicts
    """
    try:
        entry = svc.update_entry(snippet_id, request.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Snippet not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"entry": entry}


@router.delete("/api/snippets/{snippet_id}")
@log_route("DELETE", "/api/snippets/{snippet_id}")
def delete_snippet(
    snippet_id: str,
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    """
    Delete a text snippet.

    Args:
        snippet_id: ID of the snippet to delete

    Returns:
        dict: Contains 'success': True

    Raises:
        HTTPException: 404 if snippet not found
    """
    deleted = svc.delete_entry(snippet_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Snippet not found")
    return {"success": True}


@router.post("/api/snippets/preview-expand")
@log_route("POST", "/api/snippets/preview-expand")
def preview_snippet_expand(
    request: PreviewExpandRequest,
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    """
    Preview how snippets would expand in given text.

    Args:
        request: PreviewExpandRequest containing text to preview

    Returns:
        dict: Contains text with snippets expanded
    """
    return svc.preview_expand(request.text)


@router.post("/api/snippets/import")
@log_route("POST", "/api/snippets/import")
def import_snippets(
    request: SnippetImportRequest,
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    """
    Import snippets from a list of entries.

    Args:
        request: SnippetImportRequest containing entries list and replace_existing flag

    Returns:
        dict: Contains import result details
    """
    return svc.import_entries(request.entries, replace_existing=request.replace_existing)


@router.get("/api/snippets/export")
@log_route("GET", "/api/snippets/export")
def export_snippets(
    svc: SnippetService = Depends(get_snippet_service),
):
    """
    Export all snippets as JSON file.

    Returns:
        Response: JSON file download with all snippets
    """
    content = svc.export_entries()
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="snippets.json"'},
    )
