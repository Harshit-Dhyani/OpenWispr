from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.deps import get_snippet_service
from app.api.route_utils import log_route
from app.api.services.snippet_service import SnippetService

router = APIRouter()


@router.get("/api/snippets")
@log_route("GET", "/api/snippets")
def list_snippets(
    scope: str | None = Query(None),
    search: str | None = Query(None),
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    return {"entries": svc.list_entries(scope=scope, search=search)}


@router.post("/api/snippets")
@log_route("POST", "/api/snippets")
def create_snippet(
    request: dict,
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    try:
        entry = svc.create_entry(
            trigger=str(request.get("trigger", "")),
            expansion=str(request.get("expansion", "")),
            scope=request.get("scope"),
            enabled=bool(request.get("enabled", True)),
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
    request: dict,
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    try:
        entry = svc.update_entry(snippet_id, request)
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
    deleted = svc.delete_entry(snippet_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Snippet not found")
    return {"success": True}


@router.post("/api/snippets/preview-expand")
@log_route("POST", "/api/snippets/preview-expand")
def preview_snippet_expand(
    request: dict,
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    return svc.preview_expand(str(request.get("text", "")))


@router.post("/api/snippets/import")
@log_route("POST", "/api/snippets/import")
def import_snippets(
    request: dict,
    svc: SnippetService = Depends(get_snippet_service),
) -> dict:
    payload = request.get("entries") or []
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="entries must be a list")
    return svc.import_entries(payload, replace_existing=bool(request.get("replace_existing", False)))


@router.get("/api/snippets/export")
@log_route("GET", "/api/snippets/export")
def export_snippets(
    svc: SnippetService = Depends(get_snippet_service),
):
    content = svc.export_entries()
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="snippets.json"'},
    )
