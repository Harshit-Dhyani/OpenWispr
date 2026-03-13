from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from app.api.deps import get_history_service
from app.api.route_utils import log_route
from app.api.services.transcript_history_service import TranscriptHistoryService

router = APIRouter()


@router.get("/api/history/sessions")
@log_route("GET", "/api/history/sessions")
def list_history_sessions(
    range_days: str = Query("all"),
    capture_source: str | None = Query(None),
    workflow: str | None = Query(None),
    include_deleted: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    svc: TranscriptHistoryService = Depends(get_history_service),
) -> dict:
    parsed_range: int | None = None
    if range_days != "all":
        try:
            parsed_range = int(range_days)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="range_days must be one of 7, 30, 90, all") from exc
    sessions = svc.list_sessions(
        range_days=parsed_range,
        capture_source=capture_source,
        workflow=workflow,
        include_deleted=include_deleted,
        limit=limit,
        offset=offset,
    )
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/api/history/sessions/{session_id}")
@log_route("GET", "/api/history/sessions/{session_id}")
def get_history_session(
    session_id: str,
    svc: TranscriptHistoryService = Depends(get_history_service),
) -> dict:
    session = svc.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/api/history/sessions/{session_id}/undo-ai-edit")
@log_route("POST", "/api/history/sessions/{session_id}/undo-ai-edit")
def undo_ai_edit(
    session_id: str,
    svc: TranscriptHistoryService = Depends(get_history_service),
) -> dict:
    try:
        session = svc.undo_ai_edit(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    return {"session": session}


@router.post("/api/history/sessions/{session_id}/retry")
@log_route("POST", "/api/history/sessions/{session_id}/retry")
def retry_session(
    session_id: str,
    svc: TranscriptHistoryService = Depends(get_history_service),
) -> dict:
    try:
        session = svc.retry_transcript(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    return {"session": session}


@router.delete("/api/history/sessions/{session_id}")
@log_route("DELETE", "/api/history/sessions/{session_id}")
def delete_session(
    session_id: str,
    svc: TranscriptHistoryService = Depends(get_history_service),
) -> dict:
    deleted = svc.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}


@router.get("/api/history/sessions/{session_id}/download")
@log_route("GET", "/api/history/sessions/{session_id}/download")
def download_session_asset(
    session_id: str,
    asset: str = Query("transcript"),
    svc: TranscriptHistoryService = Depends(get_history_service),
):
    try:
        built = svc.build_download_asset(session_id, asset)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if built.path is not None:
        return FileResponse(
            str(built.path),
            media_type=built.content_type,
            filename=built.filename,
        )

    return Response(
        content=built.text or "",
        media_type=built.content_type,
        headers={"Content-Disposition": f'attachment; filename="{built.filename}"'},
    )


@router.get("/api/history/analytics")
@log_route("GET", "/api/history/analytics")
def history_analytics(
    range_days: str = Query("7"),
    tz: str = Query("UTC"),
    svc: TranscriptHistoryService = Depends(get_history_service),
) -> dict:
    parsed_range: int | None = None
    if range_days != "all":
        try:
            parsed_range = int(range_days)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="range_days must be one of 7, 30, 90, all") from exc
    return svc.analytics(range_days=parsed_range, tz=tz)
