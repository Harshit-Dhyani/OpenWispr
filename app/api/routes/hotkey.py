from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_hotkey_service, get_history_service
from app.api.route_utils import log_endpoint
from app.api.services.coach_service import CoachRequestContext
from app.api.services.refiner_service import RefinerService, is_llama_cpp_available
from app.core.settings.config import AppSettings
from app.core.settings.manager import get_settings_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class HotkeyStartRequest(BaseModel):
    capture_source: Literal["microphone", "system"] | None = None
    device_id: str | None = None
    model_name: str | None = None
    language_mode: str = "auto"
    execution_mode: str = "auto"
    transcription_mode: Literal["dictation", "literal", "session_paragraph"] = "dictation"


class HotkeyStartResponse(BaseModel):
    session_id: str
    status: str
    message: str = ""


class HotkeyStopRequest(BaseModel):
    mode: Literal["finish", "finish_and_paste", "cancel"] = "finish_and_paste"


class HotkeyStatusResponse(BaseModel):
    state: str = "idle"
    is_recording: bool
    partial_text: str
    raw_partial_text: str = ""
    display_partial_text: str = ""
    audio_level: float
    session_id: str | None = None
    correlation_id: str | None = None
    duration_ms: int = 0
    levels: list[float] | None = None


class HotkeyInjectRequest(BaseModel):
    text: str


class HotkeyInjectResponse(BaseModel):
    success: bool
    message: str = ""


class CoachPromptPreviewRequest(BaseModel):
    capture_source: Literal["microphone", "system"] = "microphone"
    original_text: str = ""
    language_mode: str = "auto"
    detail_level: Literal["compact", "standard", "deep"] = "compact"
    template_id: str = "default_english_coach"
    custom_user_template: str = ""
    overrides: dict[str, Any] = Field(default_factory=dict)
    privacy_mode: Literal["local_only", "allow_llm"] = "local_only"
    templates: list[dict[str, Any]] = Field(default_factory=list)


class HotkeyConfig(BaseModel):
    chunk_seconds: float = 2.4
    overlap_seconds: float = 0.32
    vad_threshold_db: float = -40.0
    vad_min_silence_ms: int = 250
    vad_speech_pad_ms: int = 240
    confidence_threshold: float = 0.35
    enable_filler_filter: bool = False


class HotkeyConfigRequest(BaseModel):
    chunk_seconds: float | None = None
    overlap_seconds: float | None = None
    vad_threshold_db: float | None = None
    vad_min_silence_ms: int | None = None
    vad_speech_pad_ms: int | None = None
    confidence_threshold: float | None = None
    enable_filler_filter: bool | None = None


class HotkeyConfigResponse(BaseModel):
    success: bool
    config: HotkeyConfig
    message: str = ""


@router.post("/api/transcription/hotkey/start")
@log_endpoint
async def hotkey_start(
    request: HotkeyStartRequest,
    svc: Any = Depends(get_hotkey_service),
) -> HotkeyStartResponse:
    """Start hotkey push-to-talk transcription."""
    hotkey_start.__endpoint_path__ = "/api/transcription/hotkey/start"
    hotkey_start.__http_method__ = "POST"

    logger.debug(
        "Hotkey start: source=%s, model=%s, lang=%s, mode=%s, device=%s, exec=%s",
        request.capture_source or "default",
        request.model_name,
        request.language_mode,
        request.transcription_mode,
        request.device_id or "default",
        request.execution_mode,
    )

    return await svc.start_session(
        capture_source=request.capture_source,
        device_id=request.device_id,
        model_name=request.model_name,
        language_mode=request.language_mode,
        execution_mode=request.execution_mode,
        transcription_mode=request.transcription_mode,
    )


@router.post("/api/transcription/hotkey/stop")
@log_endpoint
async def hotkey_stop(
    request: HotkeyStopRequest | None = None,
    svc: Any = Depends(get_hotkey_service),
    history_svc: Any = Depends(get_history_service),
) -> dict[str, Any]:
    """Stop hotkey transcription and return final transcription."""
    hotkey_stop.__endpoint_path__ = "/api/transcription/hotkey/stop"
    hotkey_stop.__http_method__ = "POST"

    logger.debug("Hotkey stop: requesting session stop")

    result = await svc.stop_session(mode=(request.mode if request else "finish_and_paste"))

    logger.debug(
        "Hotkey stop complete: duration=%dms, segments=%d, text_length=%d, backend=%s",
        result.duration_ms,
        result.segment_count,
        len(result.composed_text or result.final_transcription),
        result.source_backend,
    )

    try:
        history_svc.ingest_hotkey_result(
            result, settings_snapshot=get_settings_manager().get_settings_dict()
        )
    except Exception as exc:
        logger.warning("History ingest failed for hotkey stop: %s", exc)

    # Convert to dict for FastAPI response
    return {
        "session_id": result.session_id,
        "status": result.status,
        "transcription_mode": result.transcription_mode,
        "composed_text": result.composed_text,
        "final_transcription": result.final_transcription,
        "aggregated_raw_text": result.aggregated_raw_text,
        "aggregated_clean_text": result.aggregated_clean_text,
        "postprocessed_text": result.postprocessed_text,
        "paste_text": result.paste_text,
        "live_paste_text": result.live_paste_text,
        "final_cleanup_applied": result.final_cleanup_applied,
        "raw_transcription": result.raw_transcription,
        "refined_transcription": result.refined_transcription,
        "coach_result": result.coach_result,
        "coach_status": result.coach_status,
        "coach_display_source": result.coach_display_source,
        "coach_error": result.coach_error,
        "coach_cache_hit": result.coach_cache_hit,
        "debug_wav_path": result.debug_wav_path,
        "duration_ms": result.duration_ms,
        "segment_count": result.segment_count,
        "source_backend": result.source_backend,
        "language_used": result.language_used,
        "refinement_mode": result.refinement_mode,
        "refiner_model_id": result.refiner_model_id,
        "warnings": result.warnings,
    }


@router.post("/api/coach/prompt-preview")
@log_endpoint
async def coach_prompt_preview(
    request: CoachPromptPreviewRequest,
    svc: Any = Depends(get_hotkey_service),
) -> dict[str, Any]:
    """Compile the effective coach prompt for preview in settings."""
    coach_prompt_preview.__endpoint_path__ = "/api/coach/prompt-preview"
    coach_prompt_preview.__http_method__ = "POST"

    context = CoachRequestContext(
        text=request.original_text,
        language_mode=request.language_mode,
        detail_level=request.detail_level,
        capture_source=request.capture_source,
        template_id=request.template_id,
        overrides=request.overrides,
        privacy_mode=request.privacy_mode,
        runtime_enabled=False,
        model_id=None,
        custom_user_template=request.custom_user_template,
        templates=request.templates,
    )
    return svc._get_coach_service().prompt_preview(context)


@router.get("/api/transcription/hotkey/status")
@log_endpoint
def hotkey_status(
    svc: Any = Depends(get_hotkey_service),
) -> HotkeyStatusResponse:
    """Get current hotkey session status."""
    hotkey_status.__endpoint_path__ = "/api/transcription/hotkey/status"
    hotkey_status.__http_method__ = "GET"

    status = svc.get_status()
    return status


@router.get("/api/refiner/status")
@log_endpoint
def get_refiner_status() -> dict[str, Any]:
    """Get refiner runtime status."""
    settings = get_settings_manager().get_settings()
    selected_model_id = settings.refiner.selected_model_id
    runtime_enabled = settings.refiner.runtime_enabled

    import_available = is_llama_cpp_available()

    refiner = RefinerService(AppSettings().download_root)
    model_installed = bool(selected_model_id and refiner.is_available(selected_model_id))

    reason = None
    if not runtime_enabled:
        reason = "runtime_disabled"
    elif not import_available:
        reason = "llama_cpp_missing"
    elif not selected_model_id:
        reason = "no_model_selected"
    elif not model_installed:
        reason = "model_not_installed"

    return {
        "runtime_enabled": runtime_enabled,
        "import_available": import_available,
        "selected_model_id": selected_model_id,
        "model_installed": model_installed,
        "available": runtime_enabled and import_available and model_installed,
        "reason": reason,
    }


@router.post("/api/transcription/hotkey/inject")
@log_endpoint
def hotkey_inject(
    request: HotkeyInjectRequest,
    svc: Any = Depends(get_hotkey_service),
) -> HotkeyInjectResponse:
    """Inject text into active window."""
    hotkey_inject.__endpoint_path__ = "/api/transcription/hotkey/inject"
    hotkey_inject.__http_method__ = "POST"

    logger.debug("Hotkey inject: text_length=%d", len(request.text))

    from app.api.strings.en import API_STRINGS

    return HotkeyInjectResponse(
        success=True,
        message=API_STRINGS.messages.hotkey_inject_ready,
    )


@router.post("/api/hotkey/config")
@log_endpoint
def update_hotkey_config(
    request: HotkeyConfigRequest,
    svc: Any = Depends(get_hotkey_service),
) -> HotkeyConfigResponse:
    """Update hotkey transcription configuration."""
    update_hotkey_config.__endpoint_path__ = "/api/hotkey/config"
    update_hotkey_config.__http_method__ = "POST"

    logger.debug("Hotkey config update: %s", request.model_dump(exclude_none=True))

    if request.chunk_seconds is not None:
        svc._config.chunk_seconds = request.chunk_seconds
    if request.overlap_seconds is not None:
        svc._config.overlap_seconds = request.overlap_seconds
    if request.vad_threshold_db is not None:
        svc._config.vad_threshold_db = request.vad_threshold_db
    if request.vad_min_silence_ms is not None:
        svc._config.vad_min_silence_ms = request.vad_min_silence_ms
    if request.vad_speech_pad_ms is not None:
        svc._config.vad_speech_pad_ms = request.vad_speech_pad_ms
    if request.confidence_threshold is not None:
        svc._config.confidence_threshold = request.confidence_threshold
    if request.enable_filler_filter is not None:
        svc._config.enable_filler_filter = request.enable_filler_filter

    from app.api.strings.en import API_STRINGS

    return HotkeyConfigResponse(
        success=True,
        config=svc._config,
        message=API_STRINGS.messages.hotkey_config_updated,
    )
