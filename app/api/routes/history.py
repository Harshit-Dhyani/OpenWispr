"""Transcript history and session management endpoints.

Provides APIs for listing, retrieving, and managing past transcription
sessions including audio, transcripts, and metadata.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from app.api.deps import get_history_service
from app.api.route_utils import log_route
from app.api.services.transcript_history_service import TranscriptHistoryService
from app.core.settings.manager import get_settings_manager

logger = logging.getLogger(__name__)

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
    """
    List transcription history sessions with filtering.

    Args:
        range_days: Time range filter ('7', '30', '90', or 'all')
        capture_source: Optional capture source filter
        workflow: Optional workflow filter
        include_deleted: Include deleted sessions in results
        limit: Maximum number of results (1-1000)
        offset: Number of results to skip

    Returns:
        dict: Contains 'sessions' list and 'count'

    Raises:
        HTTPException: 400 if range_days is invalid
    """
    parsed_range: int | None = None
    if range_days != "all":
        try:
            parsed_range = int(range_days)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="range_days must be one of 7, 30, 90, all"
            ) from exc
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
    """
    Get a specific history session by ID.

    Args:
        session_id: ID of the session to retrieve

    Returns:
        dict: Session data including transcript, metadata

    Raises:
        HTTPException: 404 if session not found
    """
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
    """
    Undo AI edits to a session transcript.

    Args:
        session_id: ID of the session to undo edits for

    Returns:
        dict: Contains 'session' object with restored transcript

    Raises:
        HTTPException: 404 if session not found
    """
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
    """
    Retry transcription for an existing session.

    Args:
        session_id: ID of the session to retry

    Returns:
        dict: Contains 'session' object with new transcription

    Raises:
        HTTPException: 404 if session not found
    """
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
    """
    Delete a history session.

    Args:
        session_id: ID of the session to delete

    Returns:
        dict: Contains 'success': True

    Raises:
        HTTPException: 404 if session not found
    """
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
    """
    Download a session asset (transcript, audio, etc.).

    Args:
        session_id: ID of the session
        asset: Asset type to download ('transcript', 'audio', etc.)

    Returns:
        FileResponse or Response: The requested asset file

    Raises:
        HTTPException: 404 if session or asset not found, 400 if asset type invalid
    """
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
    """
    Get transcription history analytics.

    Args:
        range_days: Time range for analytics ('7', '30', '90', or 'all')
        tz: Timezone for analytics data

    Returns:
        dict: Contains analytics data for the specified period

    Raises:
        HTTPException: 400 if range_days is invalid
    """
    parsed_range: int | None = None
    if range_days != "all":
        try:
            parsed_range = int(range_days)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="range_days must be one of 7, 30, 90, all"
            ) from exc
    return svc.analytics(range_days=parsed_range, tz=tz)


@router.post("/api/history/cleanup")
@log_route("POST", "/api/history/cleanup")
def cleanup_history(
    retention_days: int | None = Query(None, ge=1, le=365, description="Override retention days"),
    svc: TranscriptHistoryService = Depends(get_history_service),
) -> dict:
    """
    Trigger retention cleanup for deleted transcript sessions.

    Args:
        retention_days: Optional override for retention days (defaults to setting value)

    Returns:
        dict: Contains 'status' and 'count' of cleaned records

    Raises:
        HTTPException: 400 if retention_days is invalid
    """
    settings = get_settings_manager().get_settings()
    days = retention_days if retention_days is not None else settings.history.retention_days
    logger.info(f"Starting history retention cleanup with {days} days retention")
    count = svc.cleanup_retention(days)
    logger.info(f"History retention cleanup completed, removed {count} records")
    return {"status": "completed", "count": count}
