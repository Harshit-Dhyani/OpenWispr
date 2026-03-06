from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_history_service, get_service
from app.api.route_utils import log_route
from app.api.schemas import AttachPdfRequest, StartSessionRequest
from app.api.service import BackendService
from app.api.services.transcript_history_service import TranscriptHistoryService
from app.api.session_resolution import (
    resolve_capture_source_setting,
    resolve_input_device_for_source,
)
from app.core.model_catalog import runtime_name_for_model
from app.core.settings_manager import get_settings_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/session")
@log_route("GET", "/api/session")
def session_snapshot(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    return svc.get_snapshot_payload()


@router.get("/api/metrics/streaming")
@log_route("GET", "/api/metrics/streaming")
def streaming_metrics(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    return svc.get_streaming_metrics()


@router.post("/api/session/start")
@log_route("POST", "/api/session/start")
def start_session(
    request: StartSessionRequest,
    svc: BackendService = Depends(get_service),
) -> dict[str, Any]:
    resolved_capture_source = resolve_capture_source_setting(request.capture_source)
    resolved_device_id = resolve_input_device_for_source(
        resolved_capture_source,
        request.device_id,
    )
    logger.debug(
        "Start session: title=%s, resolved_asr_model_id=%s, runtime_model_name=%s, lang=%s, source=%s, device=%s, mode=%s, exec=%s",
        request.title,
        request.model_name,
        runtime_name_for_model(request.model_name) or request.model_name,
        request.language_mode,
        resolved_capture_source,
        resolved_device_id or "default",
        request.live_mode,
        request.execution_mode,
    )
    try:
        start_time = time.perf_counter()
        vad_params = {
            "vad_threshold": request.vad_threshold,
            "vad_min_silence_ms": request.vad_min_silence_ms,
            "vad_speech_pad_ms": request.vad_speech_pad_ms,
        }
        session = svc.start_session(
            title=request.title,
            output_root=request.output_root,
            model_name=request.model_name,
            language_mode=request.language_mode,
            device_id=resolved_device_id,
            live_mode=request.live_mode,
            execution_mode=request.execution_mode,
            vad_params=vad_params,
        )
        logger.debug(
            "Start session complete: session_id=%s, time=%.2fms",
            session.get("id", "unknown") if isinstance(session, dict) else "unknown",
            (time.perf_counter() - start_time) * 1000,
        )
        return {"session": session}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/session/stop")
@log_route("POST", "/api/session/stop")
def stop_session(
    svc: BackendService = Depends(get_service),
    history: TranscriptHistoryService = Depends(get_history_service),
) -> dict[str, Any]:
    session = svc.stop_session()
    if session:
        segments = session.get("segments") or []
        display_chunks = [
            str(segment.get("display_text") or segment.get("text") or "").strip()
            for segment in segments
        ]
        raw_chunks = [str(segment.get("text") or "").strip() for segment in segments]
        active_text = " ".join([chunk for chunk in display_chunks if chunk])
        raw_text = " ".join([chunk for chunk in raw_chunks if chunk])
        settings_snapshot = get_settings_manager().get_settings_dict()
        history.ingest_session(
            {
                "session_id": str(session.get("session_id") or session.get("id") or ""),
                "source_workflow": "session",
                "capture_source": settings_snapshot.get("audio", {}).get("default_capture_source", "microphone"),
                "title": session.get("title"),
                "transcription_mode": settings_snapshot.get("transcription", {}).get("transcription_mode", "dictation"),
                "started_at": session.get("started_at") or session.get("created_at"),
                "ended_at": session.get("updated_at") or session.get("ended_at"),
                "duration_ms": int(float(session.get("duration_s") or 0) * 1000),
                "model_name": session.get("model_name"),
                "model_id": settings_snapshot.get("transcription", {}).get("default_asr_model_id"),
                "language_mode": session.get("language_mode"),
                "execution_mode": session.get("execution_mode"),
                "device_id": session.get("device_id"),
                "status": "completed",
                "raw_text": raw_text,
                "aggregated_clean_text": active_text,
                "postprocessed_text": active_text,
                "coach_polished_text": None,
                "active_text": active_text,
                "active_text_source": "session_stop",
                "audio_path": None,
                "session_artifacts_path": session.get("output_dir"),
                "settings_snapshot": settings_snapshot,
            }
        )
    return {"session": session}


@router.post("/api/session/attach-pdf")
@log_route("POST", "/api/session/attach-pdf")
def attach_pdf(
    request: AttachPdfRequest,
    svc: BackendService = Depends(get_service),
) -> dict[str, Any]:
    logger.debug("Attach PDF: path=%s", request.path)
    return {"session": svc.attach_pdf(request.path)}
