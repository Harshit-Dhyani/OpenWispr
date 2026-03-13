from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_dictionary_service
from app.api.route_utils import log_route
from app.api.services.dictionary_service import DictionaryService

router = APIRouter()


@router.get("/api/dictionary")
@log_route("GET", "/api/dictionary")
def list_dictionary_entries(
    scope: str | None = Query(None),
    search: str | None = Query(None),
    svc: DictionaryService = Depends(get_dictionary_service),
) -> dict:
    return {"entries": svc.list_entries(scope=scope, search=search)}


@router.post("/api/dictionary")
@log_route("POST", "/api/dictionary")
def create_dictionary_entry(
    request: dict,
    svc: DictionaryService = Depends(get_dictionary_service),
) -> dict:
    try:
        entry = svc.create_entry(
            phrase=str(request.get("phrase", "")),
            replacement=str(request.get("replacement", "")),
            scope=request.get("scope"),
            enabled=bool(request.get("enabled", True)),
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
    request: dict,
    svc: DictionaryService = Depends(get_dictionary_service),
) -> dict:
    try:
        entry = svc.update_entry(entry_id, request)
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
    deleted = svc.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"success": True}


@router.post("/api/dictionary/preview-apply")
@log_route("POST", "/api/dictionary/preview-apply")
def preview_dictionary_apply(
    request: dict,
    svc: DictionaryService = Depends(get_dictionary_service),
) -> dict:
    return svc.preview_apply(str(request.get("text", "")))
