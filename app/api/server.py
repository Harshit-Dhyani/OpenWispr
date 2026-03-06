from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import wave
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np

logger = logging.getLogger(__name__)

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.json_utils import make_json_safe
from app.api.coach_service import CoachRequestContext, CoachResult, CoachService
import app.api.deps as api_deps
from app.api.deps import get_history_service, get_hotkey_service, get_service
from app.api.route_utils import (
    apply_runtime_log_levels,
    log_endpoint,
    resolve_log_level_from_settings_payload,
    resolve_runtime_log_level,
)
from app.api.routes import (
    dictionary_router,
    history_router,
    models_router,
    session_router,
    settings_router,
    snippets_router,
    style_router,
    system_router,
)
from app.api.schemas import (
    AttachPdfRequest,
    ModelSelectionRequest,
    PreloadModelRequest,
    RefinementModeRequest,
    StartSessionRequest,
)
from app.api.strings.en import API_STRINGS
from app.api.service import BackendService
from app.api.refiner_service import RefinerService, is_llama_cpp_available
from app.api.services import DictionaryService, SnippetService, StyleService, TranscriptHistoryService
from app.storage.history_db import HistoryDatabase
from app.audio.capture import LoopbackAudioSource
from app.audio.devices import list_audio_devices
from app.core.config import AppSettings
from app.core.model_catalog import runtime_name_for_model
from app.core.system_profiler import SystemProfiler
from app.core.auto_optimizer import AutoOptimizer, get_recommended_settings
from app.stt.dictation_cleanup import (
    TranscriptComposer,
    clean_final_text,
    compose_transcript_text,
    merge_segment_texts,
    normalize_dictation_text,
    stabilize_partial_text,
)
from app.stt.deterministic_postprocess import (
    postprocess_final_text,
    postprocess_live_text,
)
from app.stt.utterance_aggregator import UtteranceAggregator
from app.core.settings_manager import (
    SettingsManager,
    SettingsState,
    DEFAULT_SETTINGS_STATE,
    get_settings_manager,
)
from app.api.websocket_server import (
    WebSocketManager,
    WebSocketConnection,
    MessageType,
    ConnectionConfig,
    get_websocket_manager,
)
from app.api.settings_sync import (
    SettingsSynchronizer,
    SyncConfig,
    SyncDirection,
    get_settings_synchronizer,
)
from app.stt.stability import PartialStabilizer, build_stream_payload
from app.api.session_resolution import (
    resolve_capture_source_setting,
    resolve_input_device_for_source,
)

_sse_client_count = 0
_sse_lock = asyncio.Lock()
_sse_metrics: dict[str, int] = {
    "connections_opened": 0,
    "connections_closed": 0,
    "keepalives_sent": 0,
    "events_sent": 0,
}

# WebSocket manager and settings synchronizer
_ws_manager: WebSocketManager | None = None
_settings_sync: SettingsSynchronizer | None = None
_health_broadcast_task: asyncio.Task | None = None
_HOTKEY_REFINER_TIMEOUT_SECONDS = float(
    os.getenv("TRANSCRIPTA_HOTKEY_REFINER_TIMEOUT_SECONDS", "0.75")
)
_HOTKEY_COACH_TIMEOUT_SECONDS = float(
    os.getenv("TRANSCRIPTA_HOTKEY_COACH_TIMEOUT_SECONDS", "0.5")
)
_HOTKEY_STOP_PROCESSING_WAIT_SECONDS = float(
    os.getenv("TRANSCRIPTA_HOTKEY_STOP_PROCESSING_WAIT_SECONDS", "0.9")
)
_HOTKEY_STOP_DRAIN_WAIT_SECONDS = float(
    os.getenv("TRANSCRIPTA_HOTKEY_STOP_DRAIN_WAIT_SECONDS", "0.45")
)
_HOTKEY_STOP_PROCESSING_WAIT_EMPTY_SECONDS = float(
    os.getenv("TRANSCRIPTA_HOTKEY_STOP_PROCESSING_WAIT_EMPTY_SECONDS", "0.2")
)
_HOTKEY_STOP_DRAIN_WAIT_EMPTY_SECONDS = float(
    os.getenv("TRANSCRIPTA_HOTKEY_STOP_DRAIN_WAIT_EMPTY_SECONDS", "0.1")
)

# Compatibility aliases for refactored helpers.
# Keep these while server.py still contains internal call sites that predate the extraction.
_resolve_log_level_from_settings_payload = resolve_log_level_from_settings_payload
_resolve_runtime_log_level = resolve_runtime_log_level
_apply_runtime_log_levels = apply_runtime_log_levels
_resolve_capture_source_setting = resolve_capture_source_setting
_resolve_input_device_for_source = resolve_input_device_for_source


def _make_json_safe(value: Any) -> Any:
    return make_json_safe(value)


# Hotkey-specific request/response models


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


class HotkeyStopResponse(BaseModel):
    session_id: str | None = None
    status: str = "idle"
    transcription_mode: Literal["dictation", "literal", "session_paragraph"] = "dictation"
    composed_text: str = ""
    final_transcription: str
    aggregated_raw_text: str = ""
    aggregated_clean_text: str = ""
    postprocessed_text: str = ""
    paste_text: str = ""
    live_paste_text: str = ""
    final_cleanup_applied: bool = False
    raw_transcription: str = ""
    refined_transcription: str | None = None
    coach_result: CoachResult | None = None
    coach_status: Literal["disabled", "queued", "running", "failed", "fallback", "cache_hit", "generated", "success"] = "disabled"
    coach_error: str | None = None
    coach_cache_hit: bool = False
    debug_wav_path: str | None = None
    duration_ms: int
    segment_count: int
    source_backend: str = "unknown"
    language_used: str = "auto"
    refinement_mode: str = "off"
    refiner_model_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


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
    levels: list[float] | None = None  # Frequency-based levels for visualization


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


class HotkeyStopRequest(BaseModel):
    mode: Literal["finish", "finish_and_paste", "cancel"] = "finish_and_paste"


@dataclass
class HotkeySession:
    session_id: str
    capture_source: Literal["microphone", "system"]
    device_id: str | None
    model_name: str
    language_mode: str
    execution_mode: str
    started_at: float
    transcription_mode: Literal["dictation", "literal", "session_paragraph"] = "dictation"
    refinement_profile: str = "raw"
    audio_source: LoopbackAudioSource | None = None
    transcriber: Any = None
    state: Literal["starting", "recording", "stopping", "error"] = "starting"
    is_recording: bool = False
    partial_text: str = ""
    raw_partial_text: str = ""
    display_partial_text: str = ""
    final_segments: list[dict[str, Any]] = field(default_factory=list)
    aggregator: UtteranceAggregator = field(default_factory=UtteranceAggregator)
    composer: TranscriptComposer = field(default_factory=TranscriptComposer)
    raw_composed_text: str = ""
    composed_text: str = ""
    aggregated_raw_text: str = ""
    aggregated_clean_text: str = ""
    postprocessed_text: str = ""
    paste_text: str = ""
    latest_live_buffer_text: str = ""
    coach_result: CoachResult | None = None
    coach_cache_hit: bool = False
    coach_error: str | None = None
    audio_level: float = 0.0
    source_backend: str = "unknown"
    language_used: str = "auto"
    _callbacks: list[Callable[[str, dict[str, Any]], None]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    processing_task: asyncio.Task | None = None
    draft_stabilizer: PartialStabilizer | None = None
    cancel_requested: bool = False
    stop_requested_at: float | None = None
    stop_ack_at: float | None = None
    first_partial_at: float | None = None
    suppress_stream_events: bool = False
    resolved_device_id: str | None = None
    debug_audio_chunks: list[np.ndarray] = field(default_factory=list)
    debug_wav_path: str | None = None
    debug_last_audio_log_at: float = 0.0
    backlog_warning_at: float = 0.0
    skipped_silent_chunks: int = 0
    silence_skip_streak: int = 0
    adaptive_silence_gate_relaxed: bool = False
    submitted_audio_seconds: float = 0.0
    finalize_task: asyncio.Task | None = None
    final_response: HotkeyStopResponse | None = None
    finalization_error: str | None = None
    stop_websockets: set[WebSocket] = field(default_factory=set)

    @property
    def duration_ms(self) -> int:
        return int((time.time() - self.started_at) * 1000)


class HotkeyTranscriptionService:
    """Service for managing hotkey push-to-talk transcription sessions.

    Unlike regular sessions, hotkey sessions:
    - Don't persist to disk
    - Use shorter chunks for lower latency
    - Don't emit to main SSE channel (use dedicated hotkey channel)
    - Are temporary and transient
    """

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._session: HotkeySession | None = None
        self._lock = asyncio.Lock()
        self._callbacks: list[Callable[[str, dict[str, Any]], None]] = []
        self._config = HotkeyConfig()
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._refiner_service: RefinerService | None = None
        self._coach_service: CoachService | None = None
        self._websockets: set[WebSocket] = set()

    async def start_session(
        self,
        capture_source: Literal["microphone", "system"] | None,
        device_id: str | None,
        model_name: str | None,
        language_mode: str,
        execution_mode: str,
        transcription_mode: Literal["dictation", "literal", "session_paragraph"] = "dictation",
    ) -> HotkeyStartResponse:
        """Start a new hotkey transcription session."""
        async with self._lock:
            self._event_loop = asyncio.get_running_loop()
            if self._session is not None and self._session.is_recording:
                logger.debug("Hotkey session already active, stopping previous")
                await self._stop_internal()

            user_settings = get_settings_manager().get_settings()
            capture_source = self._resolve_capture_source(capture_source)
            requested_model_name = model_name
            model_name = self._resolve_hotkey_model_name(capture_source, model_name)
            session_id = f"hotkey-{uuid.uuid4().hex[:12]}"
            logger.debug(
                "Starting hotkey session: id=%s, source=%s, resolved_asr_model_id=%s, runtime_model_name=%s, lang=%s, mode=%s, device=%s",
                session_id,
                capture_source,
                requested_model_name or ("system" if capture_source == "system" else "microphone"),
                model_name,
                language_mode,
                transcription_mode,
                device_id or "default",
            )
            logger.info(
                "Hotkey language resolved: session=%s requested=%s effective=%s capture_source=%s",
                session_id,
                language_mode,
                language_mode,
                capture_source,
            )

            session = HotkeySession(
                session_id=session_id,
                capture_source=capture_source,
                device_id=device_id,
                model_name=model_name,
                language_mode=language_mode,
                execution_mode=execution_mode,
                transcription_mode=transcription_mode,
                refinement_profile=getattr(user_settings.transcription, "refinement_profile", "raw"),
                started_at=time.time(),
                is_recording=True,
                state="starting",
                draft_stabilizer=PartialStabilizer(session_id=session_id, stability_threshold=2),
            )

            try:
                # Initialize audio capture with hotkey-optimized settings
                session.audio_source = self._create_audio_source(
                    capture_source=capture_source,
                    device_id=device_id,
                )
                session.resolved_device_id = getattr(session.audio_source, "device_id", device_id)
                resolved_device = next(
                    (device for device in list_audio_devices() if device.id == session.resolved_device_id),
                    None,
                )
                logger.info(
                    "Hotkey audio source resolved: session=%s capture_source=%s requested_device=%s resolved_device=%s resolved_name=%s kind=%s loopback=%s source_class=%s backend_pref=%s",
                    session.session_id,
                    capture_source,
                    device_id or "default",
                    session.resolved_device_id or "default",
                    getattr(resolved_device, "name", "unknown"),
                    getattr(resolved_device, "kind", "unknown"),
                    bool(
                        getattr(resolved_device, "is_loopback", False)
                        or getattr(resolved_device, "supports_loopback", False)
                    ),
                    type(session.audio_source).__name__,
                    getattr(session.audio_source, "audio_backend_preference", "unknown"),
                )

                # Initialize transcriber with hotkey settings
                session.transcriber = await self._create_transcriber(
                    model_name=model_name,
                    language_mode=language_mode,
                    execution_mode=execution_mode,
                )

                # Register callbacks to receive transcription results
                session.transcriber.add_segment_callback(
                    lambda segment: self._on_transcription_segment(session, segment)
                )
                if hasattr(session.transcriber, "add_partial_callback"):
                    session.transcriber.add_partial_callback(
                        lambda text, start, end: self._on_partial_transcription(
                            session, text, start, end
                        )
                    )

                # Start the transcriber
                session.transcriber.start()

                self._session = session

                # Start audio processing in background
                session.processing_task = asyncio.create_task(self._process_audio_loop(session))
                session.state = "recording"

                self._publish_event(
                    "hotkey_started",
                    {
                        "session_id": session_id,
                        "started_at": session.started_at,
                        "state": session.state,
                        "is_recording": True,
                    },
                )
                self._publish_status(session)

                return HotkeyStartResponse(
                    session_id=session_id,
                    status=session.state,
                    message=API_STRINGS.messages.hotkey_started,
                )

            except Exception as exc:
                logger.exception("Failed to start hotkey session")
                session.state = "error"
                session.is_recording = False
                self._publish_event(
                    "hotkey_error",
                    {
                        "session_id": session.session_id,
                        "error": str(exc),
                        "state": session.state,
                    },
                )
                await self._cleanup_session(session)
                raise HTTPException(
                    status_code=500, detail=f"Failed to start hotkey session: {exc}"
                ) from exc

    async def stop_session(
        self, *, mode: Literal["finish", "finish_and_paste", "cancel"] = "finish_and_paste"
    ) -> HotkeyStopResponse:
        """Stop the current hotkey session and return transcription."""
        session: HotkeySession | None = None
        finalize_task: asyncio.Task | None = None
        async with self._lock:
            if self._session is None:
                return self._build_empty_stop_response()
            session = self._session
            if self._session.state == "stopping":
                finalize_task = self._session.finalize_task
            elif not self._session.is_recording:
                return self._build_stop_response_from_session(self._session)
            else:
                finalize_task = self._stop_internal(mode=mode)

        if finalize_task is not None:
            try:
                await finalize_task
            except Exception as exc:
                logger.debug("Hotkey finalize task failed while stopping: %s", exc)

        return self._build_stop_response_from_session(session)

    def _stop_internal(
        self, *, mode: Literal["finish", "finish_and_paste", "cancel"] = "finish_and_paste"
    ) -> asyncio.Task | None:
        """Internal stop method - assumes lock is held."""
        session = self._session
        if session is None:
            return None

        session.is_recording = False
        session.state = "stopping"
        session.cancel_requested = mode == "cancel"
        session.stop_requested_at = time.time()
        session.stop_ack_at = time.time()
        session.suppress_stream_events = True
        session.stop_websockets = set(self._websockets)
        session.audio_level = 0.0
        session.partial_text = ""
        session.raw_partial_text = ""
        session.display_partial_text = ""
        duration_ms = session.duration_ms
        self._publish_event(
            "hotkey_stop_ack",
            {
                "session_id": session.session_id,
                "duration_ms": duration_ms,
                "state": session.state,
                "is_recording": False,
                "reason": mode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._publish_event(
            "hotkey_stopping",
            {
                "session_id": session.session_id,
                "duration_ms": duration_ms,
                "state": session.state,
                "is_recording": False,
            },
        )
        self._publish_status(session)
        if session.finalize_task is None or session.finalize_task.done():
            session.finalize_task = asyncio.create_task(self._finalize_stopped_session(session))

        return session.finalize_task

    def _build_empty_stop_response(
        self,
        *,
        session: HotkeySession | None = None,
        status: str = "idle",
    ) -> HotkeyStopResponse:
        return HotkeyStopResponse(
            session_id=session.session_id if session is not None else None,
            status=status,
            composed_text="",
            final_transcription="",
            transcription_mode=getattr(session, "transcription_mode", "dictation"),
            aggregated_raw_text="",
            aggregated_clean_text="",
            postprocessed_text="",
            paste_text="",
            live_paste_text="",
            final_cleanup_applied=False,
            raw_transcription="",
            refined_transcription=None,
            coach_result=None,
            coach_status="disabled",
            coach_error=None,
            coach_cache_hit=False,
            debug_wav_path=getattr(session, "debug_wav_path", None),
            duration_ms=session.duration_ms if session is not None else 0,
            segment_count=len(session.final_segments) if session is not None else 0,
            source_backend=session.source_backend if session is not None else "unknown",
            language_used=session.language_used if session is not None else "auto",
            refinement_mode="off",
            refiner_model_id=None,
            warnings=[],
        )

    def _build_stop_response_from_session(
        self,
        session: HotkeySession | None,
        *,
        status: str | None = None,
    ) -> HotkeyStopResponse:
        if session is None:
            return self._build_empty_stop_response(status=status or "idle")

        if session.final_response is not None and status is None:
            return session.final_response

        warnings = [session.finalization_error] if session.finalization_error else []
        return HotkeyStopResponse(
            session_id=session.session_id,
            status=status or ("stopping" if session.finalize_task and not session.finalize_task.done() else "idle"),
            transcription_mode=getattr(session, "transcription_mode", "dictation"),
            composed_text=session.composed_text or "",
            final_transcription=session.composed_text or "",
            aggregated_raw_text=session.aggregated_raw_text or session.raw_composed_text or "",
            aggregated_clean_text=session.aggregated_clean_text or session.composed_text or "",
            postprocessed_text=session.postprocessed_text or session.composed_text or "",
            paste_text=session.paste_text or session.postprocessed_text or session.composed_text or "",
            live_paste_text=(
                ""
                if session.cancel_requested
                else (
                    session.latest_live_buffer_text
                    or session.paste_text
                    or session.postprocessed_text
                    or session.composed_text
                    or ""
                )
            ),
            final_cleanup_applied=bool(session.postprocessed_text or session.composed_text),
            raw_transcription=session.raw_composed_text or "",
            refined_transcription=None,
            coach_result=session.coach_result,
            coach_status="cache_hit" if session.coach_cache_hit else ("success" if session.coach_result else "disabled"),
            coach_error=session.coach_error,
            coach_cache_hit=session.coach_cache_hit,
            debug_wav_path=session.debug_wav_path,
            duration_ms=session.duration_ms,
            segment_count=len(session.final_segments),
            source_backend=session.source_backend,
            language_used=session.language_used,
            refinement_mode="off",
            refiner_model_id=None,
            warnings=warnings,
        )

    async def _wait_for_hotkey_transcriber_drain(
        self,
        session: HotkeySession,
        *,
        timeout_seconds: float = 1.5,
        settle_iterations: int = 2,
    ) -> None:
        transcriber = session.transcriber
        if transcriber is None:
            return

        stable_iterations = 0
        previous_segments = len(session.final_segments)
        deadline = time.perf_counter() + timeout_seconds
        while time.perf_counter() < deadline:
            queue_depth = None
            try:
                stats = getattr(transcriber, "stats", None)
                if isinstance(stats, dict):
                    queue_depth = stats.get("queue_depth")
            except Exception:
                queue_depth = None

            if queue_depth is None:
                return

            current_segments = len(session.final_segments)
            if queue_depth == 0 and current_segments == previous_segments:
                stable_iterations += 1
                if stable_iterations >= settle_iterations:
                    return
            else:
                stable_iterations = 0

            previous_segments = current_segments
            await asyncio.sleep(0.05)

    async def _finalize_stopped_session(self, session: HotkeySession) -> None:
        duration_ms = session.duration_ms
        try:
            has_live_text = bool(
                session.final_segments
                or session.raw_composed_text
                or session.partial_text
                or session.raw_partial_text
                or session.display_partial_text
            )
            processing_timeout = (
                _HOTKEY_STOP_PROCESSING_WAIT_SECONDS
                if has_live_text
                else _HOTKEY_STOP_PROCESSING_WAIT_EMPTY_SECONDS
            )
            drain_timeout = (
                _HOTKEY_STOP_DRAIN_WAIT_SECONDS
                if has_live_text
                else _HOTKEY_STOP_DRAIN_WAIT_EMPTY_SECONDS
            )

            if session.processing_task is not None:
                try:
                    await asyncio.wait_for(session.processing_task, timeout=processing_timeout)
                except asyncio.TimeoutError:
                    logger.debug(
                        "Timed out waiting for hotkey processing loop to stop after %.2fs",
                        processing_timeout,
                    )
                except Exception as exc:
                    logger.debug("Error waiting for hotkey processing task: %s", exc)

            await self._wait_for_hotkey_transcriber_drain(
                session,
                timeout_seconds=drain_timeout,
            )

            logger.debug(
                "Finalizing hotkey session: id=%s, duration=%dms, segments=%d, composed_chars=%d",
                session.session_id,
                duration_ms,
                len(session.final_segments),
                len(session.raw_composed_text or ""),
            )

            if session.cancel_requested:
                final_text = ""
                raw_text = ""
                aggregated_raw_text = ""
                aggregated_clean_text = ""
                session.latest_live_buffer_text = ""
            else:
                aggregated = session.aggregator.finalize()
                aggregated_raw_text = aggregated.aggregated_raw_text
                aggregated_clean_text = aggregated.aggregated_clean_text
                session.aggregated_raw_text = aggregated_raw_text
                session.aggregated_clean_text = aggregated_clean_text
                if not session.raw_composed_text and session.final_segments:
                    rebuilt = ""
                    for segment in session.final_segments:
                        rebuilt = compose_transcript_text(
                            rebuilt,
                            segment.get("raw_text") or segment.get("text", ""),
                        )
                    session.raw_composed_text = rebuilt

                raw_text = normalize_dictation_text(session.raw_composed_text)
                transcription_mode = getattr(session, "transcription_mode", "dictation")
                base_text = (
                    aggregated_raw_text or raw_text
                    if transcription_mode == "literal"
                    else aggregated_clean_text or aggregated_raw_text or raw_text
                )
                final_text = postprocess_final_text(base_text, mode=transcription_mode)
                session.raw_composed_text = raw_text
                session.composed_text = final_text
                self._log_hotkey_debug_text(
                    "Hotkey ASR aggregate",
                    session=session,
                    text=raw_text or final_text,
                )

            refined_text: str | None = None
            refinement_mode = "off"
            refiner_model_id: str | None = None
            coach_result: CoachResult | None = None
            coach_status: Literal["disabled", "queued", "running", "failed", "fallback", "cache_hit", "generated", "success"] = "disabled"
            coach_error: str | None = None
            coach_cache_hit = False
            user_settings = get_settings_manager().get_settings()
            hotkey_settings = getattr(user_settings, "hotkey", None)
            coach_settings = getattr(user_settings, "coach", None)
            transcription_mode = getattr(session, "transcription_mode", "dictation")
            should_refine_on_stop = bool(
                getattr(hotkey_settings, "enable_refiner_on_stop", False)
            )
            should_write_debug_wav = bool(getattr(hotkey_settings, "save_debug_wav", False))
            response_warnings = list(getattr(aggregated, "warnings", [])) if not session.cancel_requested else []
            final_text_present = bool((final_text or "").strip())

            try:
                if (
                    should_refine_on_stop
                    and not session.cancel_requested
                    and getattr(session, "refinement_profile", "raw") != "raw"
                    and final_text_present
                ):
                    refinement_mode = user_settings.transcription.refinement_mode
                    refiner_model_id = user_settings.refiner.selected_model_id
                    try:
                        refiner_result = await asyncio.wait_for(
                            self._refine_final_text(
                                text=final_text,
                                language_hint=session.language_used,
                                refinement_mode=refinement_mode,
                                refinement_profile=getattr(session, "refinement_profile", "raw"),
                                refiner_model_id=refiner_model_id,
                                runtime_enabled=user_settings.refiner.runtime_enabled,
                                cleanup_instructions=user_settings.refiner.cleanup_instructions,
                            ),
                            timeout=_HOTKEY_REFINER_TIMEOUT_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        logger.debug(
                            "Hotkey refiner timed out after %.2fs",
                            _HOTKEY_REFINER_TIMEOUT_SECONDS,
                        )
                        response_warnings.append("refiner_timeout")
                        refiner_result = None
                    if refiner_result and refiner_result.used_runtime and refiner_result.text:
                        refined_text = refiner_result.text
                        final_text = refiner_result.text
            except Exception as exc:
                logger.debug("Hotkey refiner fallback engaged: %s", exc)

            session.composed_text = final_text
            session.postprocessed_text = final_text
            session.latest_live_buffer_text = (
                session.latest_live_buffer_text
                or postprocess_live_text(
                    aggregated_raw_text or raw_text or final_text,
                    mode=transcription_mode,
                )
                or final_text
            )

            if not session.cancel_requested and final_text_present:
                try:
                    coach_enabled = bool(getattr(coach_settings, "coach_enabled", True))
                    if not coach_enabled:
                        coach_status = "disabled"
                        coach_error = None
                    else:
                        privacy_mode = getattr(coach_settings, "privacy_mode", "local_only")
                        detail_level = getattr(coach_settings, "coach_detail_level", "compact")
                        template_id = getattr(
                            coach_settings,
                            (
                                "coach_template_id_system"
                                if session.capture_source == "system"
                                else "coach_template_id_mic"
                            ),
                            "default_english_coach",
                        )
                        prompt_overrides = getattr(coach_settings, "coach_overrides", None)
                        prompt_templates = getattr(coach_settings, "coach_prompt_templates", None)
                        custom_prompt_enabled = bool(
                            getattr(coach_settings, "coach_prompt_custom_enabled", False)
                        )
                        custom_prompt_text = (
                            getattr(coach_settings, "coach_prompt_custom_text", "")
                            if custom_prompt_enabled
                            else ""
                        )

                        context = CoachRequestContext(
                            text=aggregated_clean_text or final_text,
                            language_mode=session.language_used or session.language_mode,
                            detail_level=detail_level,
                            capture_source=(
                                "system" if session.capture_source == "system" else "microphone"
                            ),
                            template_id=template_id,
                            overrides=(
                                prompt_overrides.__dict__
                                if hasattr(prompt_overrides, "__dict__")
                                else dict(prompt_overrides or {})
                            ),
                            privacy_mode=privacy_mode,
                            runtime_enabled=bool(getattr(user_settings.refiner, "runtime_enabled", False)),
                            model_id=getattr(user_settings.refiner, "selected_model_id", None),
                            custom_user_template=custom_prompt_text,
                            templates=[
                                template.__dict__ if hasattr(template, "__dict__") else dict(template)
                                for template in (prompt_templates or [])
                            ],
                        )
                        coach_status = "queued"
                        logger.info(
                            "Coach queued: session=%s source=%s template=%s detail=%s privacy=%s",
                            session.session_id,
                            session.capture_source,
                            template_id,
                            detail_level,
                            privacy_mode,
                        )
                        try:
                            coach_status = "running"
                            logger.info(
                                "Coach running: session=%s model=%s runtime_enabled=%s",
                                session.session_id,
                                getattr(user_settings.refiner, "selected_model_id", None),
                                bool(getattr(user_settings.refiner, "runtime_enabled", False)),
                            )
                            raw_coach_result = await asyncio.wait_for(
                                asyncio.to_thread(
                                    self._get_coach_service().generate,
                                    context,
                                    fallback_text=final_text,
                                ),
                                timeout=_HOTKEY_COACH_TIMEOUT_SECONDS,
                            )
                        except asyncio.TimeoutError:
                            logger.debug(
                                "Coach generation timed out after %.2fs",
                                _HOTKEY_COACH_TIMEOUT_SECONDS,
                            )
                            coach_status = "failed"
                            coach_error = "coach_timeout"
                            raw_coach_result = None

                        if raw_coach_result is not None:
                            coach_cache_hit = bool(raw_coach_result.meta.cache_hit)
                            coach_status = (
                                "cache_hit"
                                if raw_coach_result.meta.cache_hit
                                else (
                                    "success"
                                    if raw_coach_result.meta.provider in {"local_llm", "cache"}
                                    else "fallback"
                                )
                            )
                            if raw_coach_result.meta.provider.startswith("fallback") or raw_coach_result.meta.provider.startswith("disabled"):
                                coach_error = raw_coach_result.meta.provider
                                coach_result = None
                                logger.warning(
                                    "Coach fallback provider: session=%s provider=%s",
                                    session.session_id,
                                    raw_coach_result.meta.provider,
                                )
                            else:
                                coach_result = raw_coach_result
                                logger.info(
                                    "Coach success: session=%s provider=%s cache_hit=%s",
                                    session.session_id,
                                    raw_coach_result.meta.provider,
                                    coach_cache_hit,
                                )
                        session.coach_result = coach_result
                        session.coach_cache_hit = coach_cache_hit
                        session.coach_error = coach_error
                except Exception as exc:
                    coach_status = "failed"
                    coach_error = str(exc)
                    session.coach_error = coach_error
                    logger.warning("Coach failed: session=%s error=%s", session.session_id, exc)

            paste_text = final_text
            if coach_result is not None and bool(getattr(coach_settings, "copy_polished_by_default", True)):
                paste_text = coach_result.polished or final_text
            logger.info(
                "Hotkey finalize paste source: session=%s coach_status=%s selected=%s",
                session.session_id,
                coach_status,
                "coach_polished" if coach_result is not None and bool(getattr(coach_settings, "copy_polished_by_default", True)) else "postprocessed",
            )

            session.paste_text = paste_text

            if should_write_debug_wav:
                session.debug_wav_path = await asyncio.to_thread(
                    self._write_hotkey_debug_wav, session
                )

            if coach_error:
                response_warnings.append(coach_error)

            session.final_response = HotkeyStopResponse(
                session_id=session.session_id,
                status="idle",
                transcription_mode=transcription_mode,
                composed_text=final_text,
                final_transcription=final_text,
                aggregated_raw_text=aggregated_raw_text,
                aggregated_clean_text=aggregated_clean_text,
                postprocessed_text=final_text,
                paste_text=paste_text,
                live_paste_text="" if session.cancel_requested else (session.latest_live_buffer_text or paste_text),
                final_cleanup_applied=not session.cancel_requested,
                raw_transcription=raw_text,
                refined_transcription=refined_text,
                coach_result=coach_result,
                coach_status=coach_status,
                coach_error=coach_error,
                coach_cache_hit=coach_cache_hit,
                debug_wav_path=session.debug_wav_path,
                duration_ms=duration_ms,
                segment_count=len(session.final_segments),
                source_backend=session.source_backend,
                language_used=session.language_used,
                refinement_mode=refinement_mode,
                refiner_model_id=refiner_model_id,
                warnings=response_warnings,
            )

            self._publish_event(
                "hotkey_stopped",
                {
                    "session_id": session.session_id,
                    "transcription_mode": transcription_mode,
                    "duration_ms": duration_ms,
                    "composed_text": final_text,
                    "final_transcription": final_text,
                    "aggregated_raw_text": aggregated_raw_text,
                    "aggregated_clean_text": aggregated_clean_text,
                    "postprocessed_text": final_text,
                    "paste_text": paste_text,
                    "live_paste_text": "" if session.cancel_requested else (session.latest_live_buffer_text or paste_text),
                    "final_cleanup_applied": not session.cancel_requested,
                    "raw_transcription": raw_text,
                    "refined_transcription": refined_text,
                    "coach_result": coach_result.model_dump(by_alias=True) if coach_result else None,
                    "coach_status": coach_status,
                    "coach_error": coach_error,
                    "coach_cache_hit": coach_cache_hit,
                    "segment_count": len(session.final_segments),
                    "source_backend": session.source_backend,
                    "language_used": session.language_used,
                    "refinement_mode": refinement_mode,
                    "refiner_model_id": refiner_model_id,
                    "debug_wav_path": session.debug_wav_path,
                    "cancelled": session.cancel_requested,
                    "state": "idle",
                    "is_recording": False,
                },
            )
            self._publish_event(
                "final_text",
                {
                    "session_id": session.session_id,
                    "mode": transcription_mode,
                    "text": final_text,
                    "final_text": final_text,
                    "paste_text": paste_text,
                    "segment_count": len(session.final_segments),
                    "cancelled": session.cancel_requested,
                },
            )
            self._log_hotkey_metrics(session, duration_ms)
        except Exception as exc:
            session.finalization_error = str(exc)
            logger.exception("Failed to finalize hotkey session")
            self._publish_event(
                "hotkey_error",
                {
                    "session_id": session.session_id,
                    "error": str(exc),
                    "state": "error",
                },
            )
        finally:
            await self._cleanup_session(session)
            async with self._lock:
                if self._session is session:
                    self._session = None
            self._publish_status(None)
            await self._close_websockets(
                code=1000,
                reason="hotkey-session-stopped",
                targets=session.stop_websockets,
            )

    async def _refine_final_text(
        self,
        *,
        text: str,
        language_hint: str,
        refinement_mode: str,
        refinement_profile: str,
        refiner_model_id: str | None,
        runtime_enabled: bool,
        cleanup_instructions: str = "",
    ):
        if not text or refinement_mode == "off":
            return None

        if self._refiner_service is None:
            self._refiner_service = RefinerService(self.settings.download_root)

        if self._is_debug_mode_enabled():
            logger.debug(
                "Hotkey refiner input: mode=%s profile=%s model_id=%s language=%s chars=%d text=%s",
                refinement_mode,
                refinement_profile,
                refiner_model_id or "none",
                language_hint,
                len(text),
                self._preview_debug_text(text),
            )

        result = await asyncio.to_thread(
            self._refiner_service.refine_text,
            text,
            mode=refinement_mode,
            profile=refinement_profile,
            model_id=refiner_model_id,
            runtime_enabled=runtime_enabled,
            language_hint=language_hint,
            cleanup_instructions=cleanup_instructions,
        )
        if self._is_debug_mode_enabled():
            logger.debug(
                "Hotkey refiner output: mode=%s model_id=%s used_runtime=%s error=%s chars=%d text=%s",
                result.mode,
                result.model_id or "none",
                result.used_runtime,
                result.error or "",
                len(result.text),
                self._preview_debug_text(result.text),
            )
        return result

    def _get_coach_service(self) -> CoachService:
        if self._coach_service is None:
            settings_manager = get_settings_manager()
            self._coach_service = CoachService(
                self.settings.download_root,
                settings_manager.settings_path.parent / "coach_cache.json",
            )
        return self._coach_service

    async def _cleanup_session(self, session: HotkeySession) -> None:
        """Clean up session resources."""
        session.processing_task = None
        if session.audio_source is not None:
            try:
                session.audio_source.stop()
            except Exception as exc:
                logger.debug("Error stopping audio source: %s", exc)

        if session.transcriber is not None:
            try:
                if hasattr(session.transcriber, "stop"):
                    session.transcriber.stop()
            except Exception as exc:
                logger.debug("Error stopping transcriber: %s", exc)

    def get_status(self) -> HotkeyStatusResponse:
        """Get current hotkey session status."""
        if self._session is None:
            return HotkeyStatusResponse(
                state="idle",
                is_recording=False,
                partial_text="",
                raw_partial_text="",
                display_partial_text="",
                audio_level=0.0,
                session_id=None,
                correlation_id=None,
                duration_ms=0,
                levels=[0.0] * 36,
            )

        # Generate frequency levels from current audio level
        base_level = self._session.audio_level
        levels = [base_level * (0.5 + 0.5 * np.sin(i * 0.3)) for i in range(36)]

        return HotkeyStatusResponse(
            state=self._session.state,
            is_recording=self._session.is_recording,
            partial_text=self._session.display_partial_text,
            raw_partial_text=self._session.raw_partial_text,
            display_partial_text=self._session.display_partial_text,
            audio_level=self._session.audio_level,
            session_id=self._session.session_id,
            correlation_id=self._session.session_id,
            duration_ms=self._session.duration_ms,
            levels=levels,
        )

    def register_websocket(self, websocket: WebSocket) -> None:
        self._websockets.add(websocket)

    def unregister_websocket(self, websocket: WebSocket) -> None:
        self._websockets.discard(websocket)

    async def _close_websockets(
        self,
        *,
        code: int,
        reason: str,
        targets: set[WebSocket] | None = None,
    ) -> None:
        if not self._websockets:
            return

        await asyncio.sleep(0.05)
        if targets is None:
            active_websockets = list(self._websockets)
        else:
            active_websockets = [websocket for websocket in list(targets) if websocket in self._websockets]
        for websocket in active_websockets:
            try:
                await websocket.close(code=code, reason=reason)
            except Exception:
                pass
            finally:
                self._websockets.discard(websocket)

    def _publish_status(self, session: HotkeySession | None) -> None:
        if session is None:
            payload = {
                "state": "idle",
                "is_recording": False,
                "partial_text": "",
                "raw_partial_text": "",
                "display_partial_text": "",
                "audio_level": 0.0,
                "levels": [0.0] * 36,
                "session_id": None,
                "duration_ms": 0,
            }
        else:
            payload = {
                "state": session.state,
                "is_recording": session.is_recording,
                "partial_text": session.display_partial_text,
                "raw_partial_text": session.raw_partial_text,
                "display_partial_text": session.display_partial_text,
                "audio_level": session.audio_level,
                "levels": [session.audio_level] * 36 if session.audio_level > 0 else [0.0] * 36,
                "session_id": session.session_id,
                "duration_ms": session.duration_ms,
            }
        self._publish_event("hotkey_status", payload)

    def _resolve_capture_source(
        self, capture_source: Literal["microphone", "system"] | None
    ) -> Literal["microphone", "system"]:
        return _resolve_capture_source_setting(capture_source)

    def _resolve_hotkey_model_name(
        self,
        capture_source: Literal["microphone", "system"],
        requested_model_name: str | None,
    ) -> str:
        resolved = runtime_name_for_model(requested_model_name) if requested_model_name else None
        if resolved:
            return resolved
        if requested_model_name:
            return requested_model_name

        settings = get_settings_manager().get_settings()
        model_id = (
            settings.transcription.system_asr_model_id
            if capture_source == "system"
            else settings.transcription.microphone_asr_model_id
        )
        return (
            runtime_name_for_model(model_id)
            or runtime_name_for_model(settings.transcription.default_asr_model_id)
            or settings.transcription.model_name
        )

    def _create_audio_source(
        self,
        *,
        capture_source: Literal["microphone", "system"],
        device_id: str | None,
    ) -> LoopbackAudioSource:
        """Create audio source with hotkey-optimized settings."""
        resolved_device_id = self._resolve_hotkey_input_device(capture_source, device_id)

        # Convert block_seconds to block_size (samples per block)
        block_size = int(self.settings.sample_rate * self.settings.capture_block_seconds)
        max_queue_items = 10  # Allow ~5 seconds of audio buffering

        return LoopbackAudioSource(
            device_id=resolved_device_id,
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
            block_size=block_size,
            max_queue_items=max_queue_items,
            audio_backend=self.settings.audio_backend,
        )

    def _resolve_hotkey_input_device(
        self,
        capture_source: Literal["microphone", "system"],
        device_id: str | None,
    ) -> str | None:
        return _resolve_input_device_for_source(capture_source, device_id)

    async def _create_transcriber(
        self,
        model_name: str,
        language_mode: str,
        execution_mode: str,
    ) -> Any:
        """Create transcriber with hotkey-optimized settings."""
        # Import here to avoid circular dependencies
        from app.stt.fast_engine import FastTranscriber
        from app.core.config import resolve_live_profile

        # Resolve the profile so low-latency defaults stay aligned with settings.
        resolve_live_profile("low_latency", self.settings)

        # Determine device
        device = self.settings.device
        if execution_mode == "cpu_only":
            device = "cpu"
        elif execution_mode == "gpu_only":
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        return FastTranscriber(
            model_name=model_name,
            download_root=str(self.settings.download_root),
            device=device,
            compute_type=self.settings.compute_type,
            language_mode=language_mode,
            execution_mode=execution_mode,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            # Hotkey capture is already press-to-talk scoped. Disabling backend VAD
            # here avoids dropping short first-utterance chunks.
            vad_filter=False,
            max_queue_items=self.settings.max_queue_items,
        )

    async def _process_audio_loop(self, session: HotkeySession) -> None:
        """Main audio processing loop for hotkey session."""
        if session.audio_source is None or session.transcriber is None:
            logger.error("Cannot start audio loop: missing audio source or transcriber")
            return

        try:
            session.audio_source.start()
            session.source_backend = session.audio_source.backend_name or "unknown"

            chunk_samples = int(self._config.chunk_seconds * self.settings.sample_rate)
            overlap_samples = max(
                0, int(self._config.overlap_seconds * self.settings.sample_rate)
            )
            step_samples = max(1, chunk_samples - overlap_samples)
            audio_buffer = np.array([], dtype=np.float32)

            while session.is_recording:
                try:
                    # Read audio chunk with timeout
                    chunk = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, session.audio_source.read),
                        timeout=0.1,
                    )

                    if chunk is None or len(chunk) == 0:
                        await asyncio.sleep(0.01)
                        continue

                    if session.audio_source.backend_name:
                        session.source_backend = session.audio_source.backend_name

                    # Update audio level for visualizer
                    session.audio_level = self._calculate_audio_level(chunk)

                    if session.is_recording and not session.suppress_stream_events:
                        # Publish audio level update for real-time visualization.
                        self._publish_event(
                            "hotkey_audio_level",
                            {
                                "session_id": session.session_id,
                                "audio_level": session.audio_level,
                                "levels": self._calculate_frequency_levels(chunk, num_bars=36),
                                "peak": float(
                                    np.max(
                                        np.abs(
                                            np.nan_to_num(
                                                np.clip(
                                                    chunk.astype(np.float32, copy=False),
                                                    -1.0,
                                                    1.0,
                                                ),
                                                nan=0.0,
                                                posinf=1.0,
                                                neginf=-1.0,
                                            )
                                        )
                                    )
                                )
                                if len(chunk) > 0
                                else 0.0,
                            },
                        )

                    # Accumulate audio
                    audio_buffer = np.concatenate([audio_buffer, chunk])

                    # Process when we have enough samples
                    while len(audio_buffer) >= chunk_samples:
                        process_chunk = audio_buffer[:chunk_samples]
                        audio_buffer = audio_buffer[step_samples:]

                        # Transcribe chunk
                        await self._transcribe_chunk(session, process_chunk)

                except asyncio.TimeoutError:
                    continue
                except Exception as exc:
                    logger.debug("Error in audio loop: %s", exc)
                    await asyncio.sleep(0.01)

            # Process any remaining audio
            if not session.cancel_requested and len(audio_buffer) > self.settings.sample_rate * 0.18:
                await self._transcribe_chunk(session, audio_buffer)

        except Exception as exc:
            logger.exception("Fatal error in hotkey audio loop")
            self._publish_event("hotkey_error", {"error": str(exc)})
        finally:
            try:
                session.audio_source.stop()
            except Exception:
                pass

    def _calculate_audio_level(self, audio: np.ndarray) -> float:
        """Calculate audio level for visualizer (0.0 to 1.0)."""
        if len(audio) == 0:
            return 0.0

        safe_audio = np.nan_to_num(
            np.clip(audio.astype(np.float32, copy=False), -1.0, 1.0),
            nan=0.0,
            posinf=1.0,
            neginf=-1.0,
        )

        # Calculate RMS
        rms = np.sqrt(np.mean(safe_audio**2))

        # Convert to dB and normalize
        db = 20 * np.log10(rms + 1e-10)

        # Normalize to 0-1 range (assuming -60dB to 0dB range)
        normalized = (db + 60) / 60
        return max(0.0, min(1.0, normalized))

    def _calculate_frequency_levels(self, audio: np.ndarray, num_bars: int = 36) -> list[float]:
        """Calculate frequency-based levels for waveform visualization.

        Returns an array of levels (0.0 to 1.0) representing different
        frequency bands for a more realistic waveform display.
        """
        if len(audio) == 0:
            return [0.0] * num_bars

        safe_audio = np.nan_to_num(
            np.clip(audio.astype(np.float32, copy=False), -1.0, 1.0),
            nan=0.0,
            posinf=1.0,
            neginf=-1.0,
        )

        # Calculate overall RMS for base level
        rms = np.sqrt(np.mean(safe_audio**2))
        base_level = max(0.0, min(1.0, (20 * np.log10(rms + 1e-10) + 60) / 60))

        # Generate frequency-like distribution using FFT-like approach
        # We'll simulate different frequency bands
        levels = []

        # Use audio samples to create varied frequency response
        # Split audio into segments for "frequency" bands
        segment_size = max(1, len(safe_audio) // num_bars)

        for i in range(num_bars):
            start = i * segment_size
            end = min(start + segment_size, len(safe_audio))

            if start < len(safe_audio):
                segment = safe_audio[start:end]
                # Calculate local energy
                local_rms = np.sqrt(np.mean(segment**2)) if len(segment) > 0 else 0

                # Create frequency response curve (boost middle frequencies)
                freq_response = np.exp(-0.5 * ((i - num_bars / 2) / (num_bars / 4)) ** 2)
                freq_response = 0.3 + 0.7 * freq_response  # Ensure minimum response

                # Combine base level with local variation
                local_level = max(0.0, min(1.0, (20 * np.log10(local_rms + 1e-10) + 60) / 60))

                # Blend base and local levels
                blended = 0.4 * base_level + 0.6 * local_level * freq_response

                # Add some noise for visual interest when there's audio
                if base_level > 0.05:
                    noise = np.random.random() * 0.15 * base_level
                    blended = min(1.0, blended + noise)

                levels.append(blended)
            else:
                levels.append(0.0)

        return levels

    async def _transcribe_chunk(self, session: HotkeySession, audio: np.ndarray) -> None:
        """Transcribe an audio chunk and update session state."""
        if session.transcriber is None or session.cancel_requested:
            logger.debug("No transcriber available")
            return

        try:
            from app.stt.chunker import AudioChunk

            chunk_duration = len(audio) / float(self.settings.sample_rate)
            started_at = float(getattr(session, "submitted_audio_seconds", 0.0) or 0.0)
            setattr(session, "submitted_audio_seconds", started_at + chunk_duration)
            ended_at = started_at + chunk_duration

            if self._should_collect_hotkey_audio_debug():
                session.debug_audio_chunks.append(
                    np.asarray(audio, dtype=np.float32, order="C").copy()
                )
            should_skip, chunk_stats = self._should_skip_silent_hotkey_chunk(
                audio,
                relaxed=session.adaptive_silence_gate_relaxed,
            )
            if should_skip:
                session.skipped_silent_chunks += 1
                session.silence_skip_streak = int(
                    getattr(session, "silence_skip_streak", 0) or 0
                ) + 1
                if (
                    getattr(session, "capture_source", "microphone") == "microphone"
                    and not getattr(session, "final_segments", [])
                    and not getattr(session, "adaptive_silence_gate_relaxed", False)
                    and session.silence_skip_streak >= 3
                ):
                    session.adaptive_silence_gate_relaxed = True
                    logger.info(
                        "Hotkey silence gate relaxed after repeated empty skips: session=%s skipped=%d",
                        session.session_id,
                        session.skipped_silent_chunks,
                    )
                if self._should_collect_hotkey_audio_debug():
                    logger.info(
                        "Hotkey chunk skipped by silence gate: session=%s start=%.2f end=%.2f rms=%.6f peak=%.6f duration_ms=%.1f skipped=%d",
                        session.session_id,
                        started_at,
                        ended_at,
                        chunk_stats["rms"],
                        chunk_stats["peak"],
                        chunk_stats["duration_ms"],
                        session.skipped_silent_chunks,
                    )
                return
            session.silence_skip_streak = 0
            chunk = AudioChunk(
                started_at=started_at,
                samples=audio,
                duration=chunk_duration,
            )
            self._log_hotkey_audio_chunk(session, audio, phase="submit")

            status = session.transcriber.submit(chunk)

            accepted = status.accepted if hasattr(status, "accepted") else bool(status)
            if not accepted:
                queue_depth = getattr(status, "queue_depth", None)
                backpressure_state = getattr(status, "backpressure_state", "unknown")
                logger.debug(
                    "Chunk rejected: queue_depth=%s, state=%s",
                    queue_depth,
                    backpressure_state,
                )
                return

            queue_depth = getattr(status, "queue_depth", None)
            estimated_backlog = float(
                getattr(status, "estimated_backlog_seconds", 0.0) or 0.0
            )
            logger.debug(
                "Chunk submitted: queue_depth=%s backlog=%.2fs",
                queue_depth,
                estimated_backlog,
            )
            if (
                queue_depth is not None
                and queue_depth >= 3
                and (time.time() - session.backlog_warning_at) >= 5.0
            ):
                session.backlog_warning_at = time.time()
                logger.warning(
                    "Hotkey backlog warning: session=%s queue_depth=%s backlog=%.2fs",
                    session.session_id,
                    queue_depth,
                    estimated_backlog,
                )

        except Exception as exc:
            logger.exception("Transcription error: %s", exc)

    def _on_transcription_segment(self, session: HotkeySession, segment: Any) -> None:
        """Capture completed hotkey segments for the floating window and stop payload."""
        if (
            session.cancel_requested
            or self._session is not session
        ):
            return

        raw_text = normalize_dictation_text(getattr(segment, "text", "") or "")
        if getattr(segment, "suppressed", False) and not self._should_keep_hotkey_segment(
            session,
            segment,
            raw_text,
        ):
            if self._should_collect_hotkey_audio_debug():
                logger.info(
                    "Hotkey ASR segment suppressed before aggregation: session=%s confidence=%.3f reasons=%s text=%r",
                    session.session_id,
                    float(getattr(segment, "confidence", 0.0) or 0.0),
                    getattr(segment, "suppression_reasons", [])
                    or getattr(segment, "review_reasons", []),
                    getattr(segment, "text", "") or "",
                )
            return

        display_source = getattr(segment, "display_text", None) or raw_text
        display_text = stabilize_partial_text(session.display_partial_text, display_source)
        if not raw_text and not display_text:
            return

        if session.first_partial_at is None:
            session.first_partial_at = time.time()

        payload = {
            "id": getattr(segment, "id", f"hotkey-seg-{len(session.final_segments)}"),
            "text": display_text,
            "raw_text": raw_text or display_text,
            "start": float(getattr(segment, "start", 0.0)),
            "end": float(getattr(segment, "end", 0.0)),
            "language": getattr(segment, "language", session.language_mode),
            "confidence": float(getattr(segment, "confidence", 0.0) or 0.0),
        }

        session.language_used = payload["language"] or session.language_mode
        session.raw_partial_text = raw_text or display_text
        session.display_partial_text = display_text
        session.partial_text = display_text
        session.silence_skip_streak = 0
        prior_last_text = (
            normalize_dictation_text(
                session.final_segments[-1].get("raw_text")
                or session.final_segments[-1].get("text")
                or ""
            )
            if session.final_segments
            else ""
        )
        merged_existing = merge_segment_texts(session.final_segments, raw_text or display_text)
        if merged_existing:
            payload = {**session.final_segments[-1]}
            current_last_text = normalize_dictation_text(
                payload.get("raw_text") or payload.get("text") or ""
            )
            if current_last_text == prior_last_text:
                return
        else:
            session.final_segments.append(payload)
        try:
            session.aggregator.add_segment(
                segment_id=payload["id"],
                text=raw_text or display_text,
                display_text=display_text,
                start=payload["start"],
                end=payload["end"],
                confidence=payload["confidence"],
                suppressed=False,
                suppression_reasons=[],
            )
        except Exception as exc:
            logger.exception(
                "Hotkey aggregation failed: session=%s segment=%s error=%s",
                session.session_id,
                payload["id"],
                exc,
            )
            session.finalization_error = f"aggregation_error:{exc}"
        try:
            session.raw_composed_text = session.composer.add_final_segment(
                raw_text or display_text,
                start=payload["start"],
                end=payload["end"],
                confidence=payload["confidence"],
            )
            session.latest_live_buffer_text = postprocess_final_text(
                session.raw_composed_text or payload["raw_text"] or payload["text"],
                mode=getattr(session, "transcription_mode", "dictation"),
            )
        except Exception as exc:
            logger.exception(
                "Hotkey composer failed: session=%s segment=%s error=%s",
                session.session_id,
                payload["id"],
                exc,
            )
        self._log_hotkey_debug_text(
            "Hotkey ASR final",
            session=session,
            text=raw_text or display_text,
            start=payload["start"],
            end=payload["end"],
        )
        if self._is_debug_mode_enabled():
            logger.debug(
                "Hotkey ASR composed: session=%s chars=%d text=%s",
                session.session_id,
                len(session.raw_composed_text),
                self._preview_debug_text(session.raw_composed_text),
            )
        if not session.suppress_stream_events:
            draft_state = session.draft_stabilizer.consume_final_text(
                payload["text"],
                start=payload["start"],
                end=payload["end"],
            ) if session.draft_stabilizer else None
            if draft_state is not None and getattr(session, "transcription_mode", "dictation") != "session_paragraph":
                self._publish_event(
                    "hotkey_commit_final",
                    {
                        **build_stream_payload(
                            session_id=session.session_id,
                            segment_id=payload["id"],
                            revision=draft_state.revision,
                            stream_id=draft_state.stream_id,
                            text=payload["text"],
                            start=payload["start"],
                            end=payload["end"],
                        committed_text=draft_state.committed_text,
                    ),
                    "live_buffer_text": session.latest_live_buffer_text,
                    "transcription_mode": getattr(session, "transcription_mode", "dictation"),
                        "segment": payload,
                    },
                )

    def _on_partial_transcription(
        self,
        session: HotkeySession,
        text: str,
        start: float,
        end: float,
    ) -> None:
        if (
            session.cancel_requested
            or session.suppress_stream_events
            or self._session is not session
            or not text
            or session.draft_stabilizer is None
        ):
            return

        draft_state = session.draft_stabilizer.push(text, start=start, end=end)
        if session.first_partial_at is None:
            session.first_partial_at = time.time()
        session.raw_partial_text = draft_state.text
        session.display_partial_text = draft_state.text
        session.partial_text = draft_state.text
        self._log_hotkey_debug_text(
            "Hotkey ASR partial",
            session=session,
            text=draft_state.text,
            start=start,
            end=end,
        )
        payload = build_stream_payload(
            session_id=session.session_id,
            segment_id=f"hotkey-draft-{draft_state.revision}",
            revision=draft_state.revision,
            stream_id=draft_state.stream_id,
            text=draft_state.text,
            start=start,
            end=end,
            committed_text=draft_state.committed_text,
            draft_suffix=draft_state.draft_suffix,
        )
        payload.update(
            {
                "raw_partial_text": draft_state.text,
                "display_partial_text": draft_state.text,
                "partial_text": draft_state.text,
            }
        )
        # Keep a single draft-stream event for in-progress text. Emitting the same
        # payload on both hotkey_draft_partial and hotkey_partial causes the
        # floating window to receive duplicate equivalent updates for one utterance.
        self._publish_event("hotkey_draft_partial", payload)

    def _is_debug_mode_enabled(self) -> bool:
        try:
            return bool(get_settings_manager().get_settings().advanced.debugMode)
        except Exception:
            return False

    @staticmethod
    def _preview_debug_text(text: str, limit: int = 240) -> str:
        normalized = " ".join((text or "").split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[: limit - 1]}…"

    def _log_hotkey_debug_text(
        self,
        label: str,
        *,
        session: HotkeySession,
        text: str,
        start: float | None = None,
        end: float | None = None,
    ) -> None:
        if not self._is_debug_mode_enabled() or not text:
            return
        logger.debug(
            "%s: session=%s start=%s end=%s chars=%d text=%s",
            label,
            session.session_id,
            f"{start:.2f}" if start is not None else "n/a",
            f"{end:.2f}" if end is not None else "n/a",
            len(text),
            self._preview_debug_text(text),
        )

    def _log_hotkey_metrics(self, session: HotkeySession, duration_ms: int) -> None:
        first_partial_ms = (
            int((session.first_partial_at - session.started_at) * 1000)
            if session.first_partial_at is not None
            else None
        )
        stop_ack_ms = (
            int((session.stop_ack_at - session.stop_requested_at) * 1000)
            if session.stop_ack_at is not None and session.stop_requested_at is not None
            else None
        )
        stop_total_ms = (
            int((time.time() - session.stop_requested_at) * 1000)
            if session.stop_requested_at is not None
            else None
        )
        logger.info(
            "Hotkey metrics: session=%s source=%s resolved_device=%s first_partial_ms=%s stop_ack_ms=%s stop_total_ms=%s segments=%d silent_chunks=%d cancelled=%s duration_ms=%d wav=%s",
            session.session_id,
            session.capture_source,
            session.resolved_device_id or "default",
            first_partial_ms if first_partial_ms is not None else "n/a",
            stop_ack_ms if stop_ack_ms is not None else "n/a",
            stop_total_ms if stop_total_ms is not None else "n/a",
            len(session.final_segments),
            session.skipped_silent_chunks,
            session.cancel_requested,
            duration_ms,
            session.debug_wav_path or "n/a",
        )

    def _should_collect_hotkey_audio_debug(self) -> bool:
        try:
            hotkey_settings = getattr(get_settings_manager().get_settings(), "hotkey", None)
        except Exception:
            hotkey_settings = None
        return self._is_debug_mode_enabled() or bool(
            getattr(hotkey_settings, "save_debug_wav", False)
        )

    @staticmethod
    def _audio_chunk_diagnostics(audio: np.ndarray, sample_rate: int) -> dict[str, float]:
        safe_audio = np.nan_to_num(
            np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0),
            nan=0.0,
            posinf=1.0,
            neginf=-1.0,
        )
        if safe_audio.size == 0:
            return {
                "duration_ms": 0.0,
                "rms": 0.0,
                "peak": 0.0,
                "clipping_ratio": 0.0,
            }
        rms = float(np.sqrt(np.mean(np.square(safe_audio)) + 1e-12))
        peak = float(np.max(np.abs(safe_audio)))
        clipping_ratio = float(np.mean(np.abs(safe_audio) >= 0.995))
        duration_ms = float((safe_audio.size / max(sample_rate, 1)) * 1000.0)
        return {
            "duration_ms": duration_ms,
            "rms": rms,
            "peak": peak,
            "clipping_ratio": clipping_ratio,
        }

    def _should_keep_hotkey_segment(
        self,
        session: HotkeySession,
        segment: Any,
        raw_text: str,
    ) -> bool:
        if session.capture_source != "microphone":
            return False
        if not raw_text:
            return False

        reasons = {
            str(reason)
            for reason in (
                getattr(segment, "suppression_reasons", None)
                or getattr(segment, "review_reasons", None)
                or []
            )
            if reason
        }
        if not reasons:
            return False
        if not reasons.issubset({"empty", "low-value-filler"}):
            return False

        confidence = float(getattr(segment, "confidence", 0.0) or 0.0)
        keep_segment = confidence >= 0.55 and len(raw_text) >= 4
        if keep_segment and self._should_collect_hotkey_audio_debug():
            logger.info(
                "Hotkey ASR segment kept despite soft suppression: session=%s confidence=%.3f reasons=%s text=%r",
                session.session_id,
                confidence,
                sorted(reasons),
                raw_text,
            )
        return keep_segment

    def _should_skip_silent_hotkey_chunk(
        self,
        audio: np.ndarray,
        *,
        relaxed: bool = False,
    ) -> tuple[bool, dict[str, float]]:
        stats = self._audio_chunk_diagnostics(audio, self.settings.sample_rate)
        rms_threshold = 0.00012 if relaxed else 0.00025
        peak_threshold = 0.003 if relaxed else 0.006
        should_skip = stats["rms"] < rms_threshold and stats["peak"] < peak_threshold
        return should_skip, stats

    def _log_hotkey_audio_chunk(
        self,
        session: HotkeySession,
        audio: np.ndarray,
        *,
        phase: str,
    ) -> None:
        if not self._should_collect_hotkey_audio_debug():
            return
        now = time.time()
        if phase == "submit" and session.debug_last_audio_log_at and now - session.debug_last_audio_log_at < 0.75:
            return
        session.debug_last_audio_log_at = now
        stats = self._audio_chunk_diagnostics(audio, self.settings.sample_rate)
        logger.debug(
            "Hotkey audio chunk: session=%s phase=%s source=%s device=%s backend=%s duration_ms=%.1f rms=%.6f peak=%.6f clipping_ratio=%.4f queue=%s",
            session.session_id,
            phase,
            session.capture_source,
            session.resolved_device_id or "default",
            session.source_backend,
            stats["duration_ms"],
            stats["rms"],
            stats["peak"],
            stats["clipping_ratio"],
            (
                session.audio_source.queue.qsize()
                if session.audio_source is not None and hasattr(session.audio_source, "queue")
                else "n/a"
            ),
        )

    def _write_hotkey_debug_wav(self, session: HotkeySession) -> str | None:
        if not session.debug_audio_chunks:
            return None
        debug_dir = Path("logs") / "hotkey-debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        wav_path = debug_dir / f"{session.session_id}.wav"
        combined = np.concatenate(session.debug_audio_chunks) if len(session.debug_audio_chunks) > 1 else session.debug_audio_chunks[0]
        safe_audio = np.nan_to_num(
            np.clip(np.asarray(combined, dtype=np.float32), -1.0, 1.0),
            nan=0.0,
            posinf=1.0,
            neginf=-1.0,
        )
        pcm16 = (safe_audio * 32767.0).astype(np.int16)
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.settings.sample_rate)
            wav_file.writeframes(pcm16.tobytes())
        logger.info(
            "Hotkey debug WAV saved: session=%s path=%s samples=%d duration_ms=%.1f",
            session.session_id,
            wav_path,
            len(safe_audio),
            (len(safe_audio) / max(self.settings.sample_rate, 1)) * 1000.0,
        )
        return str(wav_path)

    def register_callback(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Register an event callback for hotkey events."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Unregister an event callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish event to all registered callbacks."""
        safe_data = _make_json_safe(data)
        if (
            isinstance(safe_data, dict)
            and safe_data.get("session_id")
            and "correlation_id" not in safe_data
        ):
            safe_data = {**safe_data, "correlation_id": safe_data["session_id"]}
        for callback in self._callbacks:
            try:
                result = callback(event_type, safe_data)
                if inspect.isawaitable(result):
                    loop = self._event_loop
                    if loop is not None and loop.is_running():
                        asyncio.run_coroutine_threadsafe(result, loop)
                    else:
                        try:
                            running_loop = asyncio.get_running_loop()
                        except RuntimeError:
                            running_loop = None
                        if running_loop is not None and running_loop.is_running():
                            running_loop.create_task(result)
                        else:
                            logger.debug(
                                "Dropping async hotkey event without active loop: %s", event_type
                            )
            except Exception:
                continue

@asynccontextmanager
async def lifespan(_: FastAPI):
    start_time = time.perf_counter()

    try:
        settings = AppSettings()

        # Configure logging based on user settings
        manager = get_settings_manager()
        user_settings = manager.get_settings_dict()
        log_level = resolve_runtime_log_level(user_settings)
        apply_runtime_log_levels(log_level)

        logger.debug("Lifespan startup: initializing service")
        api_deps.service = BackendService(settings)
        api_deps.hotkey_service = HotkeyTranscriptionService(settings)
        history_db_path = Path.cwd() / ".transcripta" / "history.db"
        api_deps.history_db = HistoryDatabase(history_db_path)
        api_deps.dictionary_service = DictionaryService(api_deps.history_db)
        api_deps.snippet_service = SnippetService(api_deps.history_db)
        api_deps.style_service = StyleService(api_deps.history_db)
        api_deps.history_service = TranscriptHistoryService(
            api_deps.history_db,
            dictionary_service=api_deps.dictionary_service,
            snippet_service=api_deps.snippet_service,
            style_service=api_deps.style_service,
        )
        if not is_llama_cpp_available():
            logger.warning(
                "Refiner runtime unavailable at startup: llama-cpp-python is not installed. "
                "Install with `pip install llama-cpp-python` to enable local refinement."
            )
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug("Lifespan startup complete: service initialized in %.2fms", elapsed_ms)
    except Exception as exc:
        logger.error("Lifespan startup failed: %s", str(exc))
        raise

    yield

    logger.debug("Lifespan shutdown: stopping service")
    shutdown_start = time.perf_counter()
    if api_deps.service is not None:
        try:
            api_deps.service.stop_session()
            elapsed_ms = (time.perf_counter() - shutdown_start) * 1000
            logger.debug("Lifespan shutdown complete: session stopped in %.2fms", elapsed_ms)
        except Exception as exc:
            logger.debug("Lifespan shutdown error: %s", str(exc))
    else:
        logger.debug("Lifespan shutdown: no service to stop")

    # Cleanup hotkey service
    if api_deps.hotkey_service is not None:
        try:
            await api_deps.hotkey_service.stop_session()
        except Exception as exc:
            logger.debug("Hotkey service shutdown error: %s", str(exc))

    if api_deps.history_service is not None:
        try:
            api_deps.history_service.close()
        except Exception as exc:
            logger.debug("History service shutdown error: %s", str(exc))

    if api_deps.history_db is not None:
        try:
            api_deps.history_db.close()
        except Exception as exc:
            logger.debug("History db shutdown error: %s", str(exc))


_app_settings = AppSettings()
app = FastAPI(
    title=f"{_app_settings.app_name} Local API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(system_router)
app.include_router(models_router)
app.include_router(session_router)
app.include_router(settings_router)
app.include_router(history_router)
app.include_router(dictionary_router)
app.include_router(snippets_router)
app.include_router(style_router)


# ============================================================================
# Hotkey Endpoints
# ============================================================================


@app.post("/api/transcription/hotkey/start")
@log_endpoint
async def hotkey_start(
    request: HotkeyStartRequest,
    svc: HotkeyTranscriptionService = Depends(get_hotkey_service),
) -> HotkeyStartResponse:
    """Start hotkey push-to-talk transcription.

    Creates a temporary session that doesn't save to disk.
    Uses shorter chunks for lower latency.
    """
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


@app.post("/api/transcription/hotkey/stop")
@log_endpoint
async def hotkey_stop(
    request: HotkeyStopRequest | None = None,
    svc: HotkeyTranscriptionService = Depends(get_hotkey_service),
    history_svc: TranscriptHistoryService = Depends(get_history_service),
) -> HotkeyStopResponse:
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
        history_svc.ingest_hotkey_result(result, settings_snapshot=get_settings_manager().get_settings_dict())
    except Exception as exc:
        logger.warning("History ingest failed for hotkey stop: %s", exc)

    return result


@app.post("/api/coach/prompt-preview")
@log_endpoint
async def coach_prompt_preview(
    request: CoachPromptPreviewRequest,
    svc: HotkeyTranscriptionService = Depends(get_hotkey_service),
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


@app.get("/api/transcription/hotkey/status")
@log_endpoint
def hotkey_status(
    svc: HotkeyTranscriptionService = Depends(get_hotkey_service),
) -> HotkeyStatusResponse:
    """Get current hotkey session status.

    Returns recording state, partial text, and audio level for visualizer.
    """
    hotkey_status.__endpoint_path__ = "/api/transcription/hotkey/status"
    hotkey_status.__http_method__ = "GET"

    status = svc.get_status()
    return status


@app.get("/api/refiner/status")
@log_endpoint
def get_refiner_status() -> dict[str, Any]:
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


@app.post("/api/transcription/hotkey/inject")
@log_endpoint
def hotkey_inject(
    request: HotkeyInjectRequest,
    svc: HotkeyTranscriptionService = Depends(get_hotkey_service),
) -> HotkeyInjectResponse:
    """Inject text into active window.

    Called by Electron after receiving transcription.
    This is a placeholder - actual injection is handled by Electron.
    """
    hotkey_inject.__endpoint_path__ = "/api/transcription/hotkey/inject"
    hotkey_inject.__http_method__ = "POST"

    logger.debug("Hotkey inject: text_length=%d", len(request.text))

    # In a real implementation, this would communicate with the OS
    # to inject text. For now, we just acknowledge the request.
    # The actual injection is typically handled by the Electron frontend
    # using OS-level APIs.

    return HotkeyInjectResponse(
        success=True,
        message=API_STRINGS.messages.hotkey_inject_ready,
    )


@app.post("/api/hotkey/config")
@log_endpoint
def update_hotkey_config(
    request: HotkeyConfigRequest,
    svc: HotkeyTranscriptionService = Depends(get_hotkey_service),
) -> HotkeyConfigResponse:
    """Update hotkey transcription configuration.

    Allows runtime adjustment of hotkey-specific settings like
    chunk duration, VAD thresholds, and filtering options.
    """
    update_hotkey_config.__endpoint_path__ = "/api/hotkey/config"
    update_hotkey_config.__http_method__ = "POST"

    logger.debug("Hotkey config update: %s", request.model_dump(exclude_none=True))

    # Update config with provided values
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

    return HotkeyConfigResponse(
        success=True,
        config=svc._config,
        message=API_STRINGS.messages.hotkey_config_updated,
    )


@app.websocket("/api/transcription/hotkey/ws")
async def hotkey_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time hotkey updates.

    Streams partial transcriptions and audio levels to the hotkey window.
    """
    await websocket.accept()

    client_id = id(websocket)
    logger.debug("Hotkey WebSocket connected: client_id=%s", client_id)

    svc = get_hotkey_service()
    svc.register_websocket(websocket)

    # Track last audio level for throttling
    last_audio_update = 0.0
    audio_throttle_ms = 50.0  # Send audio updates at 20fps max

    async def send_event(event_type: str, data: dict[str, Any]) -> None:
        nonlocal last_audio_update
        try:
            # Throttle audio level updates to avoid flooding
            if event_type == "hotkey_audio_level":
                now = time.time() * 1000
                if now - last_audio_update < audio_throttle_ms:
                    return
                last_audio_update = now

            await websocket.send_json(
                {
                    "type": event_type,
                    "payload": _make_json_safe(data),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as exc:
            logger.debug("WebSocket send error: %s", exc)

    # Register callback
    svc.register_callback(send_event)

    try:
        # Send initial status
        status = svc.get_status()
        await websocket.send_json(
            {
                "type": "hotkey_status",
                "payload": _make_json_safe(
                    {
                        "state": status.state,
                        "is_recording": status.is_recording,
                        "partial_text": status.partial_text,
                        "raw_partial_text": status.raw_partial_text,
                        "display_partial_text": status.display_partial_text,
                        "audio_level": status.audio_level,
                        "levels": [status.audio_level] * 36 if status.audio_level > 0 else [0.0] * 36,
                        "session_id": status.session_id,
                        "duration_ms": status.duration_ms,
                    }
                ),
            }
        )

        # Keep connection alive and handle client messages
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)

                # Handle client commands
                if message.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})

            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "keepalive"})

    except WebSocketDisconnect:
        logger.debug("Hotkey WebSocket disconnected: client_id=%s", client_id)
    except Exception as exc:
        logger.debug("Hotkey WebSocket error: %s", exc)
    finally:
        svc.unregister_callback(send_event)
        svc.unregister_websocket(websocket)
        try:
            await websocket.close(code=1000, reason="hotkey-websocket-closed")
        except Exception:
            pass


@app.get("/api/transcription/hotkey/events")
async def hotkey_events(
    request: Request,
    svc: HotkeyTranscriptionService = Depends(get_hotkey_service),
) -> StreamingResponse:
    """SSE endpoint for hotkey transcription events.

    Alternative to WebSocket for real-time updates.
    """
    client_id = id(request)
    logger.debug("Hotkey SSE connect: client_id=%s", client_id)

    queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=100)
    loop = asyncio.get_running_loop()

    # Track last audio update for throttling
    last_audio_update = 0.0
    audio_throttle_ms = 50.0  # 20fps max for audio updates

    def on_event(event_type: str, data: dict[str, Any]) -> None:
        nonlocal last_audio_update

        # Throttle audio level updates
        if event_type == "hotkey_audio_level":
            now = time.time() * 1000
            if now - last_audio_update < audio_throttle_ms:
                return
            last_audio_update = now

        def _enqueue() -> None:
            try:
                queue.put_nowait((event_type, data))
            except asyncio.QueueFull:
                pass  # Drop events if queue is full

        loop.call_soon_threadsafe(_enqueue)

    svc.register_callback(on_event)

    async def event_generator():
        try:
            # Send initial status with full audio level data
            status = svc.get_status()
            initial_payload = _make_json_safe(
                {
                    "type": "hotkey_status",
                    "payload": {
                        "is_recording": status.is_recording,
                        "partial_text": status.partial_text,
                        "raw_partial_text": status.raw_partial_text,
                        "display_partial_text": status.display_partial_text,
                        "audio_level": status.audio_level,
                        "levels": [status.audio_level] * 36 if status.audio_level > 0 else [0.0] * 36,
                    },
                }
            )
            yield f"data: {json.dumps(initial_payload)}\n\n"

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event_type, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    payload = json.dumps(
                        _make_json_safe(
                        {
                            "type": event_type,
                            "payload": data,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        )
                    )
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ":\n\n"  # SSE comment as keepalive

        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            svc.unregister_callback(on_event)
            logger.debug("Hotkey SSE disconnect: client_id=%s", client_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/events")
async def events(
    request: Request,
    svc: BackendService = Depends(get_service),
) -> StreamingResponse:
    global _sse_client_count, _sse_metrics

    endpoint_start = time.perf_counter()
    client_id = id(request)
    client_info = f"client_{client_id}"

    logger.debug(
        "SSE connect: %s | path=%s | method=GET | client=%s",
        client_info,
        "/api/events",
        client_info,
    )

    queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    events_sent = 0
    keepalives_sent = 0
    last_event_time = time.perf_counter()

    async with _sse_lock:
        _sse_client_count += 1
        _sse_metrics["connections_opened"] += 1
        current_count = _sse_client_count

    logger.debug("SSE register callback: %s | active_connections=%d", client_info, current_count)

    def on_event(event_type: str, data: dict[str, Any]) -> None:
        def _enqueue() -> None:
            try:
                queue.put_nowait((event_type, data))
            except asyncio.QueueFull:
                logger.debug("SSE queue full: %s", client_info)

        loop.call_soon_threadsafe(_enqueue)

    svc.register_event_callback(on_event)

    async def event_generator():
        nonlocal events_sent, keepalives_sent, last_event_time
        connection_start = time.perf_counter()

        logger.debug("SSE event generator started: %s", client_info)

        try:
            while True:
                if await request.is_disconnected():
                    logger.debug("SSE client disconnected: %s", client_info)
                    break

                try:
                    event_type, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    events_sent += 1
                    last_event_time = time.perf_counter()

                    payload = json.dumps(
                        _make_json_safe(
                            {
                                "type": event_type,
                                "payload": data,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                    )
                    _sse_metrics["events_sent"] += 1

                    # Log first event and periodic stats (every 100 events)
                    if events_sent == 1 or events_sent % 100 == 0:
                        logger.debug(
                            "SSE event sent: %s | type=%s | events_sent=%d | alive_for=%.1fs",
                            client_info,
                            event_type,
                            events_sent,
                            time.perf_counter() - connection_start,
                        )

                    yield f"data: {payload}\n\n"

                except asyncio.TimeoutError:
                    keepalives_sent += 1
                    _sse_metrics["keepalives_sent"] += 1
                    # Log periodic keepalive stats (every 20 keepalives = ~5 min)
                    if keepalives_sent % 20 == 0:
                        logger.debug(
                            "SSE keepalive: %s | keepalives=%d | events=%d | alive_for=%.1fs",
                            client_info,
                            keepalives_sent,
                            events_sent,
                            time.perf_counter() - connection_start,
                        )
                    yield ":\n\n"

        except asyncio.CancelledError:
            logger.debug("SSE client cancelled: %s | events_sent=%d", client_info, events_sent)
        except (ConnectionResetError, BrokenPipeError) as exc:
            logger.debug(
                "SSE connection error: %s | error=%s | events_sent=%d",
                client_info,
                type(exc).__name__,
                events_sent,
            )
        finally:
            svc.unregister_event_callback(on_event)
            connection_duration = time.perf_counter() - connection_start

            async with _sse_lock:
                global _sse_client_count
                _sse_client_count -= 1
                _sse_metrics["connections_closed"] += 1
                remaining = _sse_client_count

            logger.debug(
                "SSE disconnect: %s | events_sent=%d | keepalives=%d | duration=%.2fs | remaining_clients=%d | totals=%s",
                client_info,
                events_sent,
                keepalives_sent,
                connection_duration,
                remaining,
                _sse_metrics,
            )

    # Set endpoint attributes for the decorator
    events.__endpoint_path__ = "/api/events"
    events.__http_method__ = "GET"

    elapsed_ms = (time.perf_counter() - endpoint_start) * 1000
    logger.debug(
        "SSE endpoint setup complete: %s | setup_time=%.2fms | active_connections=%d",
        client_info,
        elapsed_ms,
        current_count,
    )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# WebSocket Endpoints (Production-Grade)
# ============================================================================


def get_ws_manager() -> WebSocketManager:
    """Get or initialize the WebSocket manager."""
    global _ws_manager
    if _ws_manager is None:
        config = ConnectionConfig(
            heartbeat_interval=30.0,
            heartbeat_timeout=60.0,
            max_message_size=1024 * 1024,
            compression_threshold=1024,
            compression_level=6,
            rate_limit_messages=1000,
            rate_limit_window=60.0,
            message_queue_size=1000,
            max_connections_per_ip=10,
            allowed_origins=["*"],  # Configure for production
            auth_required=False,
        )
        _ws_manager = WebSocketManager(config)
    return _ws_manager


def get_settings_sync() -> SettingsSynchronizer:
    """Get or initialize the settings synchronizer."""
    global _settings_sync
    if _settings_sync is None:
        config = SyncConfig(
            direction=SyncDirection.BIDIRECTIONAL,
            debounce_ms=100.0,
            validate_on_receive=True,
            notify_on_change=True,
            batch_updates=True,
            batch_interval_ms=50.0,
        )
        _settings_sync = SettingsSynchronizer(
            settings_manager=get_settings_manager(),
            config=config,
        )
    return _settings_sync


async def _broadcast_health_metrics() -> None:
    """Background task to broadcast health metrics to all WebSocket clients."""
    manager = get_ws_manager()
    while True:
        try:
            await asyncio.sleep(5.0)  # Broadcast every 5 seconds

            if api_deps.service is None or manager.connection_count == 0:
                continue

            snapshot = api_deps.service.get_snapshot()
            health = snapshot.health if hasattr(snapshot, "health") else {}

            # Get hotkey status
            hotkey_data = None
            if api_deps.hotkey_service is not None:
                hs = api_deps.hotkey_service.get_status()
                hotkey_data = {
                    "is_recording": hs.is_recording,
                    "session_id": hs.session_id,
                    "duration_ms": hs.duration_ms,
                }

            metrics = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "health": health,
                "meter_value": getattr(snapshot, "meter_value", 0.0),
                "model_cache": getattr(snapshot, "model_cache", {}),
                "hotkey": hotkey_data,
                "websocket_stats": manager.get_stats(),
            }

            await manager.broadcast_health_metrics(metrics)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("Health metrics broadcast error: %s", exc)
            await asyncio.sleep(1.0)


async def _handle_transcription_event(event_type: str, data: dict[str, Any]) -> None:
    """Forward transcription events to WebSocket clients."""
    manager = get_ws_manager()

    try:
        if event_type == "segment":
            text = data.get("text", "")
            is_final = data.get("is_final", False)
            await manager.broadcast_transcription_partial(text, is_final)

        elif event_type == "transcription":
            text = data.get("text", "")
            confidence = data.get("confidence", 0.0)
            segments = data.get("segments")
            await manager.broadcast_transcription_final(text, confidence, segments)

        elif event_type == "meter":
            level = data.get("level", 0.0)
            peak = data.get("peak", level)
            levels = data.get("levels")
            await manager.broadcast_audio_level(level, peak, levels)

    except Exception as exc:
        logger.debug("Transcription event broadcast error: %s", exc)


@app.websocket("/api/ws")
async def websocket_main(websocket: WebSocket):
    """Main WebSocket endpoint for real-time transcription and events.

    Protocol:
    - Client connects and receives initial state
    - Server streams: transcription_partial, transcription_final, audio_level, health_metrics
    - Client sends: ping, settings_update requests
    - Heartbeat every 30s with ping/pong
    """
    client_ip = websocket.client.host if websocket.client else "unknown"
    manager = get_ws_manager()

    connection = await manager.connect(websocket, client_ip)
    if connection is None:
        return

    # Register transcription event callback
    if api_deps.service is not None:
        api_deps.service.register_event_callback(_handle_transcription_event)

    try:
        # Send initial connection success
        await connection.send(MessageType.AUTH_SUCCESS, {"connected": True})

        # Send current session state if available
        if api_deps.service is not None:
            snapshot = api_deps.service.get_snapshot_payload()
            await connection.send(MessageType.SESSION_STARTED, snapshot)

        # Send current settings
        settings_sync = get_settings_sync()
        settings_sync.subscribe_connection(connection.connection_id)
        await settings_sync.send_current_settings(connection)

        # Drain any queued messages
        await connection.drain_queue()

        # Main message loop
        while connection.is_connected:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=connection.config.heartbeat_interval,
                )
                await connection.handle_message(message)

            except asyncio.TimeoutError:
                # Heartbeat check
                if time.time() - connection._last_pong > connection.config.heartbeat_timeout:
                    logger.debug("WebSocket heartbeat timeout: %s", connection.connection_id)
                    break
                continue

            except WebSocketDisconnect:
                logger.debug("WebSocket disconnected: %s", connection.connection_id)
                break

            except Exception as exc:
                logger.debug("WebSocket message error: %s", exc)
                await connection.send_error("Invalid message format", "INVALID_MESSAGE")

    except Exception as exc:
        logger.exception("WebSocket error: %s", exc)
    finally:
        settings_sync = get_settings_sync()
        settings_sync.unsubscribe_connection(connection.connection_id)

        if api_deps.service is not None:
            api_deps.service.unregister_event_callback(_handle_transcription_event)

        await connection.close()


@app.websocket("/api/ws/settings")
async def websocket_settings(websocket: WebSocket):
    """Dedicated WebSocket endpoint for bidirectional settings synchronization.

    Allows clients to:
    - Receive settings updates immediately when they change
    - Send settings changes that apply immediately
    - Request current settings state
    """
    client_ip = websocket.client.host if websocket.client else "unknown"
    manager = get_ws_manager()
    settings_sync = get_settings_sync()

    connection = await manager.connect(websocket, client_ip)
    if connection is None:
        return

    # Subscribe to settings updates
    settings_sync.subscribe_connection(connection.connection_id)

    # Register message handlers
    async def handle_settings_request(payload: dict, conn: WebSocketConnection) -> None:
        """Handle settings request from client."""
        await settings_sync.send_current_settings(conn)

    async def handle_settings_update(payload: dict, conn: WebSocketConnection) -> None:
        """Handle settings update from client."""
        response = await settings_sync.handle_client_update(
            {"settings": payload, "category": payload.get("category", "general")},
            conn,
        )
        await conn.send(MessageType.SETTINGS_RESPONSE, response)

    connection.register_message_handler(MessageType.SETTINGS_REQUEST, handle_settings_request)
    connection.register_message_handler(MessageType.SETTINGS_UPDATE, handle_settings_update)

    try:
        # Send current settings immediately
        await settings_sync.send_current_settings(connection)

        # Main message loop
        while connection.is_connected:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=connection.config.heartbeat_interval,
                )
                await connection.handle_message(message)

            except asyncio.TimeoutError:
                if time.time() - connection._last_pong > connection.config.heartbeat_timeout:
                    break
                continue

            except WebSocketDisconnect:
                break

            except Exception as exc:
                logger.debug("Settings WebSocket error: %s", exc)

    finally:
        settings_sync.unsubscribe_connection(connection.connection_id)
        await connection.close()


@app.websocket("/api/ws/audio")
async def websocket_audio(websocket: WebSocket):
    """WebSocket endpoint for real-time audio visualization data.

    Streams:
    - audio_level: Current audio level (0.0 to 1.0)
    - audio_spectrum: Frequency spectrum data for visualization
    """
    client_ip = websocket.client.host if websocket.client else "unknown"
    manager = get_ws_manager()

    connection = await manager.connect(websocket, client_ip)
    if connection is None:
        return

    # Audio update throttling
    last_audio_update = 0.0
    audio_throttle_ms = 50.0  # 20fps

    async def handle_audio_event(event_type: str, data: dict[str, Any]) -> None:
        nonlocal last_audio_update

        if event_type not in ("meter", "audio_level", "hotkey_audio_level"):
            return

        now = time.time() * 1000
        if now - last_audio_update < audio_throttle_ms:
            return
        last_audio_update = now

        level = data.get("level", 0.0)
        peak = data.get("peak", level)
        levels = data.get("levels")

        await connection.send_audio_level(level, peak, levels)

    # Register audio event callback
    if api_deps.service is not None:
        api_deps.service.register_event_callback(handle_audio_event)

    try:
        await connection.send(MessageType.AUTH_SUCCESS, {"stream": "audio"})

        while connection.is_connected:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=connection.config.heartbeat_interval,
                )
                await connection.handle_message(message)

            except asyncio.TimeoutError:
                if time.time() - connection._last_pong > connection.config.heartbeat_timeout:
                    break
                continue

            except WebSocketDisconnect:
                break

    finally:
        if api_deps.service is not None:
            api_deps.service.unregister_event_callback(handle_audio_event)
        await connection.close()


@app.get("/api/ws/stats")
@log_endpoint
def websocket_stats() -> dict[str, Any]:
    """Get WebSocket connection statistics."""
    manager = get_ws_manager()
    settings_sync = get_settings_sync()

    return {
        "websocket": manager.get_stats(),
        "settings_sync": settings_sync.get_sync_status(),
    }


@app.post("/api/ws/broadcast")
@log_endpoint
async def websocket_broadcast(message: dict[str, Any]) -> dict[str, Any]:
    """Broadcast a message to all connected WebSocket clients.

    For admin/internal use to send messages to all clients.
    """
    manager = get_ws_manager()
    msg_type = message.get("type", "custom")
    payload = message.get("payload", {})

    try:
        msg_enum = MessageType(msg_type)
    except ValueError:
        msg_enum = MessageType.ERROR

    count = await manager.broadcast(msg_enum, payload)

    return {"success": True, "clients_notified": count}


# Start health metrics broadcast on startup
@app.on_event("startup")
async def start_health_broadcast():
    """Start the health metrics background broadcast task."""
    global _health_broadcast_task
    if _health_broadcast_task is None or _health_broadcast_task.done():
        _health_broadcast_task = asyncio.create_task(_broadcast_health_metrics())
        logger.debug("Started health metrics broadcast task")


@app.on_event("shutdown")
async def stop_health_broadcast():
    """Stop the health metrics background broadcast task."""
    global _health_broadcast_task, _ws_manager, _settings_sync

    if _health_broadcast_task and not _health_broadcast_task.done():
        _health_broadcast_task.cancel()
        try:
            await _health_broadcast_task
        except asyncio.CancelledError:
            pass
        logger.debug("Stopped health metrics broadcast task")

    # Disconnect all WebSocket clients
    if _ws_manager is not None:
        await _ws_manager.disconnect_all(1001, "Server shutting down")
        _ws_manager = None

    _settings_sync = None






