from __future__ import annotations

import asyncio
import inspect
import json
import logging
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

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.json_utils import make_json_safe
from app.api.service import BackendService
from app.api.refiner_service import RefinerService, is_llama_cpp_available
from app.audio.capture import LoopbackAudioSource
from app.audio.devices import list_audio_devices
from app.core.config import AppSettings
from app.core.model_catalog import runtime_name_for_model
from app.core.system_profiler import SystemProfiler
from app.core.auto_optimizer import AutoOptimizer, get_recommended_settings
from app.stt.dictation_cleanup import (
    clean_final_text_from_segments,
    merge_segment_texts,
    normalize_dictation_text,
    stabilize_partial_text,
)
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

service: BackendService | None = None
hotkey_service: "HotkeyTranscriptionService | None" = None
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


def _resolve_log_level_from_settings_payload(settings_payload: dict[str, Any]) -> str:
    advanced = settings_payload.get("advanced", {})
    configured = str(advanced.get("logLevel", "INFO") or "INFO").upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    return configured if configured in valid_levels else "INFO"


def _make_json_safe(value: Any) -> Any:
    return make_json_safe(value)


class StartSessionRequest(BaseModel):
    title: str
    output_root: str
    model_name: str
    language_mode: str
    capture_source: Literal["microphone", "system"] | None = None
    device_id: str | None = None
    live_mode: str = "balanced"
    execution_mode: str = "auto"
    vad_threshold: float | None = None
    vad_min_silence_ms: int | None = None
    vad_speech_pad_ms: int | None = None


class AttachPdfRequest(BaseModel):
    path: str


class PreloadModelRequest(BaseModel):
    model_name: str
    execution_mode: str = "auto"


class ModelSelectionRequest(BaseModel):
    category: str
    model_id: str


class RefinementModeRequest(BaseModel):
    mode: str


# Hotkey-specific request/response models


class HotkeyStartRequest(BaseModel):
    capture_source: Literal["microphone", "system"] | None = None
    device_id: str | None = None
    model_name: str | None = None
    language_mode: str = "auto"
    execution_mode: str = "auto"


class HotkeyStartResponse(BaseModel):
    session_id: str
    status: str
    message: str = ""


class HotkeyStopResponse(BaseModel):
    final_transcription: str
    raw_transcription: str = ""
    refined_transcription: str | None = None
    debug_wav_path: str | None = None
    duration_ms: int
    segment_count: int
    source_backend: str = "unknown"
    language_used: str = "auto"
    refinement_mode: str = "off"
    refiner_model_id: str | None = None


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


def _resolve_capture_source_setting(
    capture_source: Literal["microphone", "system"] | None,
) -> Literal["microphone", "system"]:
    if capture_source in {"microphone", "system"}:
        return capture_source
    settings = get_settings_manager().get_settings()
    return "system" if settings.audio.default_capture_source == "system" else "microphone"


def _resolve_input_device_for_source(
    capture_source: Literal["microphone", "system"] | None,
    device_id: str | None,
) -> str | None:
    source = _resolve_capture_source_setting(capture_source)
    normalized_device_id = device_id if device_id not in {None, "", "default"} else None
    devices = list_audio_devices()

    if source == "system":
        loopback_devices = [
            device for device in devices if device.is_loopback or device.supports_loopback
        ]
        if not loopback_devices:
            return normalized_device_id
        if normalized_device_id:
            selected = next(
                (device for device in loopback_devices if device.id == normalized_device_id),
                None,
            )
            if selected is not None:
                return selected.id
        settings = get_settings_manager().get_settings()
        preferred_id = settings.audio.defaultDeviceId
        selected = next((device for device in loopback_devices if device.id == preferred_id), None)
        return selected.id if selected is not None else loopback_devices[0].id

    microphones = [
        device
        for device in devices
        if device.is_input and not (device.is_loopback or device.supports_loopback)
    ]
    if not microphones:
        return normalized_device_id
    if normalized_device_id:
        selected = next((device for device in microphones if device.id == normalized_device_id), None)
        if selected is not None:
            return selected.id
    return microphones[0].id


class HotkeyConfig(BaseModel):
    chunk_seconds: float = 1.4
    overlap_seconds: float = 0.25
    vad_threshold_db: float = -40.0
    vad_min_silence_ms: int = 200
    vad_speech_pad_ms: int = 200
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
    audio_source: LoopbackAudioSource | None = None
    transcriber: Any = None
    state: Literal["starting", "recording", "stopping", "error"] = "starting"
    is_recording: bool = False
    partial_text: str = ""
    raw_partial_text: str = ""
    display_partial_text: str = ""
    final_segments: list[dict[str, Any]] = field(default_factory=list)
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
    skipped_silent_chunks: int = 0

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
        self._websockets: set[WebSocket] = set()

    async def start_session(
        self,
        capture_source: Literal["microphone", "system"] | None,
        device_id: str | None,
        model_name: str | None,
        language_mode: str,
        execution_mode: str,
    ) -> HotkeyStartResponse:
        """Start a new hotkey transcription session."""
        async with self._lock:
            self._event_loop = asyncio.get_running_loop()
            if self._session is not None and self._session.is_recording:
                logger.debug("Hotkey session already active, stopping previous")
                await self._stop_internal()

            capture_source = self._resolve_capture_source(capture_source)
            requested_model_name = model_name
            model_name = self._resolve_hotkey_model_name(capture_source, model_name)
            session_id = f"hotkey-{uuid.uuid4().hex[:12]}"
            logger.debug(
                "Starting hotkey session: id=%s, source=%s, resolved_asr_model_id=%s, runtime_model_name=%s, lang=%s, device=%s",
                session_id,
                capture_source,
                requested_model_name or ("system" if capture_source == "system" else "microphone"),
                model_name,
                language_mode,
                device_id or "default",
            )

            session = HotkeySession(
                session_id=session_id,
                capture_source=capture_source,
                device_id=device_id,
                model_name=model_name,
                language_mode=language_mode,
                execution_mode=execution_mode,
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
                    message="Hotkey session started",
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
        async with self._lock:
            if self._session is None or not self._session.is_recording:
                return HotkeyStopResponse(
                    final_transcription="",
                    raw_transcription="",
                    refined_transcription=None,
                    duration_ms=0,
                    segment_count=0,
                    source_backend="unknown",
                    language_used="auto",
                    refinement_mode="off",
                    refiner_model_id=None,
                )
            return await self._stop_internal(mode=mode)

    async def _stop_internal(
        self, *, mode: Literal["finish", "finish_and_paste", "cancel"] = "finish_and_paste"
    ) -> HotkeyStopResponse:
        """Internal stop method - assumes lock is held."""
        session = self._session
        if session is None:
            return HotkeyStopResponse(
                final_transcription="",
                raw_transcription="",
                refined_transcription=None,
                duration_ms=0,
                segment_count=0,
                source_backend="unknown",
                language_used="auto",
                refinement_mode="off",
                refiner_model_id=None,
            )

        session.is_recording = False
        session.state = "stopping"
        session.cancel_requested = mode == "cancel"
        session.stop_requested_at = time.time()
        session.stop_ack_at = time.time()
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

        if session.processing_task is not None:
            try:
                await asyncio.wait_for(session.processing_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.debug("Timed out waiting for hotkey processing loop to stop")
            except Exception as exc:
                logger.debug("Error waiting for hotkey processing task: %s", exc)

        logger.debug(
            "Stopping hotkey session: id=%s, duration=%dms, segments=%d",
            session.session_id,
            duration_ms,
            len(session.final_segments),
        )

        if session.cancel_requested:
            final_text = ""
            raw_text = ""
        else:
            cleaned = clean_final_text_from_segments(
                [seg.get("raw_text") or seg.get("text", "") for seg in session.final_segments]
            )
            final_text = cleaned.clean_final_text
            raw_text = cleaned.raw_final_text
            self._log_hotkey_debug_text(
                "Hotkey ASR aggregate",
                session=session,
                text=raw_text or final_text,
            )
        refined_text: str | None = None
        refinement_mode = "off"
        refiner_model_id: str | None = None

        try:
            user_settings = get_settings_manager().get_settings()
            refinement_mode = user_settings.transcription.refinement_mode
            refiner_model_id = user_settings.refiner.selected_model_id
            if not session.cancel_requested:
                refiner_result = await self._refine_final_text(
                    text=final_text,
                    language_hint=session.language_used,
                    refinement_mode=refinement_mode,
                    refiner_model_id=refiner_model_id,
                    runtime_enabled=user_settings.refiner.runtime_enabled,
                    cleanup_instructions=user_settings.refiner.cleanup_instructions,
                )
                if refiner_result and refiner_result.used_runtime and refiner_result.text:
                    refined_text = refiner_result.text
                    final_text = refiner_result.text
        except Exception as exc:
            logger.debug("Hotkey refiner fallback engaged: %s", exc)

        session.suppress_stream_events = True
        if self._should_collect_hotkey_audio_debug():
            session.debug_wav_path = self._write_hotkey_debug_wav(session)
        self._publish_event(
            "hotkey_stopped",
            {
                "session_id": session.session_id,
                "duration_ms": duration_ms,
                "final_transcription": final_text,
                "raw_transcription": raw_text,
                "refined_transcription": refined_text,
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

        self._log_hotkey_metrics(session, duration_ms)
        await self._cleanup_session(session)
        self._session = None
        self._publish_status(None)
        await self._close_websockets(code=1000, reason="hotkey-session-stopped")

        return HotkeyStopResponse(
            final_transcription=final_text,
            raw_transcription=raw_text,
            refined_transcription=refined_text,
            debug_wav_path=session.debug_wav_path,
            duration_ms=duration_ms,
            segment_count=len(session.final_segments),
            source_backend=session.source_backend,
            language_used=session.language_used,
            refinement_mode=refinement_mode,
            refiner_model_id=refiner_model_id,
        )

    async def _refine_final_text(
        self,
        *,
        text: str,
        language_hint: str,
        refinement_mode: str,
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
                "Hotkey refiner input: mode=%s model_id=%s language=%s chars=%d text=%s",
                refinement_mode,
                refiner_model_id or "none",
                language_hint,
                len(text),
                self._preview_debug_text(text),
            )

        result = await asyncio.to_thread(
            self._refiner_service.refine_text,
            text,
            mode=refinement_mode,
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

    async def _close_websockets(self, *, code: int, reason: str) -> None:
        if not self._websockets:
            return

        await asyncio.sleep(0.05)
        active_websockets = list(self._websockets)
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

        # Get hotkey-optimized settings
        profile = resolve_live_profile("low_latency", self.settings)

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
            beam_size=max(3, self.settings.beam_size),
            best_of=max(3, self.settings.best_of),
            temperature=min(self.settings.temperature, 0.2),
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

                    # Publish audio level update for real-time visualization
                    # Send every 50ms for smooth animation
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
                                                chunk.astype(np.float32, copy=False), -1.0, 1.0
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

            if self._should_collect_hotkey_audio_debug():
                session.debug_audio_chunks.append(
                    np.asarray(audio, dtype=np.float32, order="C").copy()
                )
            should_skip, chunk_stats = self._should_skip_silent_hotkey_chunk(audio)
            if should_skip:
                session.skipped_silent_chunks += 1
                if self._should_collect_hotkey_audio_debug():
                    logger.info(
                        "Hotkey chunk skipped by silence gate: session=%s rms=%.6f peak=%.6f duration_ms=%.1f skipped=%d",
                        session.session_id,
                        chunk_stats["rms"],
                        chunk_stats["peak"],
                        chunk_stats["duration_ms"],
                        session.skipped_silent_chunks,
                    )
                return

            chunk_duration = len(audio) / float(self.settings.sample_rate)
            ended_at = session.duration_ms / 1000.0
            started_at = max(0.0, ended_at - chunk_duration)
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
            logger.debug("Chunk submitted: queue_depth=%s", queue_depth)

        except Exception as exc:
            logger.exception("Transcription error: %s", exc)

    def _on_transcription_segment(self, session: HotkeySession, segment: Any) -> None:
        """Capture completed hotkey segments for the floating window and stop payload."""
        if (
            session.cancel_requested
            or session.suppress_stream_events
            or self._session is not session
        ):
            return

        if getattr(segment, "suppressed", False):
            if self._should_collect_hotkey_audio_debug():
                logger.info(
                    "Hotkey ASR segment suppressed before aggregation: session=%s reasons=%s text=%r",
                    session.session_id,
                    getattr(segment, "suppression_reasons", [])
                    or getattr(segment, "review_reasons", []),
                    getattr(segment, "text", "") or "",
                )
            return

        raw_text = normalize_dictation_text(getattr(segment, "text", "") or "")
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
        self._log_hotkey_debug_text(
            "Hotkey ASR final",
            session=session,
            text=raw_text or display_text,
            start=payload["start"],
            end=payload["end"],
        )
        if not merge_segment_texts(session.final_segments, raw_text or display_text):
            session.final_segments.append(payload)
        draft_state = session.draft_stabilizer.consume_final_text(
            payload["text"],
            start=payload["start"],
            end=payload["end"],
        ) if session.draft_stabilizer else None
        if draft_state is not None:
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
        return self._is_debug_mode_enabled()

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

    def _should_skip_silent_hotkey_chunk(
        self,
        audio: np.ndarray,
    ) -> tuple[bool, dict[str, float]]:
        stats = self._audio_chunk_diagnostics(audio, self.settings.sample_rate)
        should_skip = stats["rms"] < 0.001 and stats["peak"] < 0.015
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


def log_endpoint(func):
    """Decorator to log API endpoint invocations with timing."""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        return await _log_endpoint_call_async(func, args, kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        return _log_endpoint_call_sync(func, args, kwargs)

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def _get_request_info(kwargs: dict) -> dict:
    """Extract sanitized request info from kwargs."""
    request_info = {}
    for key, value in kwargs.items():
        if key == "request" and hasattr(value, "dict"):
            try:
                req_dict = value.dict()
                # Sanitize: exclude sensitive fields
                request_info = {
                    k: v
                    for k, v in req_dict.items()
                    if k not in ("password", "token", "secret", "api_key")
                }
            except Exception:
                request_info = {"type": type(value).__name__}
        elif key in ("device_id", "model_name", "duration"):
            request_info[key] = str(value)
    return request_info


def _log_endpoint_call_sync(func, args, kwargs):
    """Internal helper to log sync endpoint calls."""
    start_time = time.perf_counter()
    endpoint_name = func.__name__
    endpoint_path = getattr(func, "__endpoint_path__", "unknown")
    http_method = getattr(func, "__http_method__", "unknown")
    request_info = _get_request_info(kwargs)
    client_info = _get_client_info()

    logger.debug(
        "API endpoint invoked: %s %s (func=%s) | client=%s | params=%s",
        http_method,
        endpoint_path,
        endpoint_name,
        client_info,
        request_info,
    )

    try:
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        status_code = 200
        response_size = 0
        if hasattr(result, "status_code"):
            status_code = result.status_code
        if hasattr(result, "body"):
            response_size = len(result.body) if result.body else 0
        elif isinstance(result, dict):
            response_size = len(str(result))

        logger.debug(
            "API endpoint completed: %s %s | status=%s | size=%s bytes | time=%.2fms",
            http_method,
            endpoint_path,
            status_code,
            response_size,
            elapsed_ms,
        )
        return result
    except HTTPException as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "API endpoint error: %s %s | status=%s | detail=%s | time=%.2fms",
            http_method,
            endpoint_path,
            exc.status_code,
            exc.detail,
            elapsed_ms,
        )
        raise
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "API endpoint exception: %s %s | error=%s | time=%.2fms",
            http_method,
            endpoint_path,
            str(exc),
            elapsed_ms,
        )
        raise


async def _log_endpoint_call_async(func, args, kwargs):
    """Internal helper to log async endpoint calls."""
    start_time = time.perf_counter()
    endpoint_name = func.__name__
    endpoint_path = getattr(func, "__endpoint_path__", "unknown")
    http_method = getattr(func, "__http_method__", "unknown")
    request_info = _get_request_info(kwargs)
    client_info = _get_client_info()

    logger.debug(
        "API endpoint invoked: %s %s (func=%s) | client=%s | params=%s",
        http_method,
        endpoint_path,
        endpoint_name,
        client_info,
        request_info,
    )

    try:
        result = await func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        status_code = 200
        response_size = 0
        if hasattr(result, "status_code"):
            status_code = result.status_code
        if hasattr(result, "body"):
            response_size = len(result.body) if result.body else 0
        elif isinstance(result, dict):
            response_size = len(str(result))

        logger.debug(
            "API endpoint completed: %s %s | status=%s | size=%s bytes | time=%.2fms",
            http_method,
            endpoint_path,
            status_code,
            response_size,
            elapsed_ms,
        )
        return result
    except HTTPException as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "API endpoint error: %s %s | status=%s | detail=%s | time=%.2fms",
            http_method,
            endpoint_path,
            exc.status_code,
            exc.detail,
            elapsed_ms,
        )
        raise
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "API endpoint exception: %s %s | error=%s | time=%.2fms",
            http_method,
            endpoint_path,
            str(exc),
            elapsed_ms,
        )
        raise


def _get_client_info() -> str:
    """Get client identifier (placeholder for client IP/user agent)."""
    return "local"


@asynccontextmanager
async def lifespan(_: FastAPI):
    global service, hotkey_service
    start_time = time.perf_counter()

    try:
        settings = AppSettings()

        # Configure logging based on user settings
        manager = get_settings_manager()
        user_settings = manager.get_settings_dict()
        log_level = _resolve_log_level_from_settings_payload(user_settings)
        logging.getLogger().setLevel(getattr(logging, log_level))
        logger.setLevel(getattr(logging, log_level))

        logger.debug("Lifespan startup: initializing service")
        service = BackendService(settings)
        hotkey_service = HotkeyTranscriptionService(settings)
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
    if service is not None:
        try:
            service.stop_session()
            elapsed_ms = (time.perf_counter() - shutdown_start) * 1000
            logger.debug("Lifespan shutdown complete: session stopped in %.2fms", elapsed_ms)
        except Exception as exc:
            logger.debug("Lifespan shutdown error: %s", str(exc))
    else:
        logger.debug("Lifespan shutdown: no service to stop")

    # Cleanup hotkey service
    if hotkey_service is not None:
        try:
            await hotkey_service.stop_session()
        except Exception as exc:
            logger.debug("Hotkey service shutdown error: %s", str(exc))


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


def get_service() -> BackendService:
    if service is None:
        logger.debug("Service dependency check failed: service not ready")
        raise HTTPException(status_code=503, detail="Service not ready")
    return service


def get_hotkey_service() -> HotkeyTranscriptionService:
    if hotkey_service is None:
        logger.debug("Hotkey service dependency check failed: service not ready")
        raise HTTPException(status_code=503, detail="Hotkey service not ready")
    return hotkey_service


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
        "Hotkey start: source=%s, model=%s, lang=%s, device=%s, exec=%s",
        request.capture_source or "default",
        request.model_name,
        request.language_mode,
        request.device_id or "default",
        request.execution_mode,
    )

    return await svc.start_session(
        capture_source=request.capture_source,
        device_id=request.device_id,
        model_name=request.model_name,
        language_mode=request.language_mode,
        execution_mode=request.execution_mode,
    )


@app.post("/api/transcription/hotkey/stop")
@log_endpoint
async def hotkey_stop(
    request: HotkeyStopRequest | None = None,
    svc: HotkeyTranscriptionService = Depends(get_hotkey_service),
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
        len(result.final_transcription),
        result.source_backend,
    )

    return result


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
        message="Text ready for injection (handled by Electron)",
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
        message="Hotkey configuration updated",
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


# ============================================================================
# Existing Endpoints
# ============================================================================


@app.get("/api/health")
@log_endpoint
def health(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    health.__endpoint_path__ = "/api/health"
    health.__http_method__ = "GET"
    start_time = time.perf_counter()
    logger.debug("Health check: requesting snapshot from service")

    snapshot = svc.get_snapshot()
    model_cache = getattr(snapshot, "model_cache", {})
    cached_count = len(model_cache) if isinstance(model_cache, dict) else 0

    # Include hotkey service status
    hotkey_status_data = None
    if hotkey_service is not None:
        hs = hotkey_service.get_status()
        hotkey_status_data = {
            "is_recording": hs.is_recording,
            "session_id": hs.session_id,
            "duration_ms": hs.duration_ms,
        }

    # Ensure estimated_backlog_seconds is included in health
    health_dict = snapshot.health
    if isinstance(health_dict, dict) and "estimated_backlog_seconds" not in health_dict:
        health_dict["estimated_backlog_seconds"] = 0.0

    response = {
        "ok": True,
        "health": health_dict,
        "meter_value": snapshot.meter_value,
        "model_cache": model_cache,
        "hotkey": hotkey_status_data,
    }

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(
        "Health check complete: health=%s, meter=%.2f, cached_models=%d, time=%.2fms",
        snapshot.health,
        snapshot.meter_value,
        cached_count,
        elapsed_ms,
    )
    return response


@app.get("/api/devices")
@log_endpoint
def devices(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    devices.__endpoint_path__ = "/api/devices"
    devices.__http_method__ = "GET"
    start_time = time.perf_counter()
    logger.debug("List devices: requesting device list from service")

    device_list = svc.list_devices()
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    logger.debug(
        "List devices complete: found %d devices, time=%.2fms", len(device_list), elapsed_ms
    )
    return {"devices": device_list}


@app.get("/api/devices/{device_id}/probe")
@log_endpoint
def probe_device_endpoint(
    device_id: str,
    duration: float = 3.0,
    svc: BackendService = Depends(get_service),
) -> dict[str, Any]:
    """Probe a device to check if it's working and capture audio stats."""
    probe_device_endpoint.__endpoint_path__ = "/api/devices/{device_id}/probe"
    probe_device_endpoint.__http_method__ = "GET"
    actual_device_id = device_id if device_id != "default" else None
    logger.debug(
        "Probe device: device_id=%s (raw=%s), duration=%.1fs",
        actual_device_id or "default",
        device_id,
        duration,
    )

    start_time = time.perf_counter()
    result = svc.probe_device(actual_device_id, duration=duration)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    logger.debug(
        "Probe device complete: device_id=%s, success=%s, time=%.2fms",
        actual_device_id or "default",
        result.get("ok", False),
        elapsed_ms,
    )
    return result


@app.post("/api/models/preload")
@log_endpoint
def preload_model(
    request: PreloadModelRequest,
    svc: BackendService = Depends(get_service),
) -> dict[str, Any]:
    """Preload a model into cache for instant session start.

    Progress events are emitted via SSE on the /api/events endpoint
    with event type "preload_progress".
    """
    preload_model.__endpoint_path__ = "/api/models/preload"
    preload_model.__http_method__ = "POST"
    logger.debug(
        "Preload model: model_name=%s, execution_mode=%s",
        request.model_name,
        request.execution_mode,
    )

    start_time = time.perf_counter()
    result = svc.preload_model(
        model_name=request.model_name,
        execution_mode=request.execution_mode,
    )
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    logger.debug(
        "Preload model complete: model_name=%s, status=%s, time=%.2fms",
        request.model_name,
        result.get("status", "unknown"),
        elapsed_ms,
    )
    return result


@app.get("/api/models/cache")
@log_endpoint
def get_model_cache(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    """Get current model cache status."""
    get_model_cache.__endpoint_path__ = "/api/models/cache"
    get_model_cache.__http_method__ = "GET"
    start_time = time.perf_counter()
    logger.debug("Model cache status: requesting snapshot")

    snapshot = svc.get_snapshot()
    cached_models = getattr(snapshot, "model_cache", {})
    cached_count = len(cached_models) if isinstance(cached_models, dict) else 0
    available_count = len(snapshot.available_models) if hasattr(snapshot, "available_models") else 0

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(
        "Model cache status complete: cached=%d, available=%d, time=%.2fms",
        cached_count,
        available_count,
        elapsed_ms,
    )
    return {
        "cached_models": cached_models,
        "available_models": snapshot.available_models,
    }


@app.delete("/api/models/cache")
@log_endpoint
def clear_model_cache(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    """Clear all cached models to free memory."""
    clear_model_cache.__endpoint_path__ = "/api/models/cache"
    clear_model_cache.__http_method__ = "DELETE"
    logger.debug("Clear model cache: requesting cache clear")

    start_time = time.perf_counter()
    result = svc.clear_model_cache()
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    logger.debug(
        "Clear model cache complete: status=%s, cleared=%d models, time=%.2fms",
        result.get("status", "unknown"),
        result.get("cleared", 0),
        elapsed_ms,
    )
    return result


@app.get("/api/models/catalog")
@log_endpoint
def get_model_catalog(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    get_model_catalog.__endpoint_path__ = "/api/models/catalog"
    get_model_catalog.__http_method__ = "GET"
    return svc.get_model_catalog_payload()


@app.get("/api/models/state")
@log_endpoint
def get_model_state(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    get_model_state.__endpoint_path__ = "/api/models/state"
    get_model_state.__http_method__ = "GET"
    return {"installed": svc.get_model_install_state()}


@app.post("/api/models/select")
@log_endpoint
def select_model(request: ModelSelectionRequest) -> dict[str, Any]:
    select_model.__endpoint_path__ = "/api/models/select"
    select_model.__http_method__ = "POST"
    manager = get_settings_manager()
    settings = manager.get_settings()

    if request.category == "asr":
        settings.transcription.default_asr_model_id = request.model_id
    elif request.category == "refiner":
        settings.refiner.selected_model_id = request.model_id
    else:
        raise HTTPException(status_code=400, detail="Unknown model category")

    manager.update_settings(settings)
    return {
        "ok": True,
        "selected_asr_model_id": settings.transcription.default_asr_model_id,
        "selected_refiner_model_id": settings.refiner.selected_model_id,
    }


@app.post("/api/models/refinement-mode")
@log_endpoint
def set_refinement_mode(request: RefinementModeRequest) -> dict[str, Any]:
    set_refinement_mode.__endpoint_path__ = "/api/models/refinement-mode"
    set_refinement_mode.__http_method__ = "POST"
    if request.mode not in {"off", "strict", "polished"}:
        raise HTTPException(status_code=400, detail="Unsupported refinement mode")
    manager = get_settings_manager()
    settings = manager.get_settings()
    settings.transcription.refinement_mode = request.mode
    manager.update_settings(settings)
    return {"ok": True, "refinement_mode": settings.transcription.refinement_mode}


@app.get("/api/session")
@log_endpoint
def session_snapshot(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    session_snapshot.__endpoint_path__ = "/api/session"
    session_snapshot.__http_method__ = "GET"
    start_time = time.perf_counter()
    logger.debug("Session snapshot: requesting payload")

    result = svc.get_snapshot_payload()
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    has_session = result.get("session") is not None
    logger.debug("Session snapshot complete: has_session=%s, time=%.2fms", has_session, elapsed_ms)
    return result


@app.get("/api/metrics/streaming")
@log_endpoint
def streaming_metrics(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    streaming_metrics.__endpoint_path__ = "/api/metrics/streaming"
    streaming_metrics.__http_method__ = "GET"
    return svc.get_streaming_metrics()


@app.post("/api/session/start")
@log_endpoint
def start_session(
    request: StartSessionRequest,
    svc: BackendService = Depends(get_service),
) -> dict[str, Any]:
    start_session.__endpoint_path__ = "/api/session/start"
    start_session.__http_method__ = "POST"
    resolved_capture_source = _resolve_capture_source_setting(request.capture_source)
    resolved_device_id = _resolve_input_device_for_source(
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
    logger.debug(
        "Start session VAD params: threshold=%s, min_silence=%s, speech_pad=%s",
        request.vad_threshold,
        request.vad_min_silence_ms,
        request.vad_speech_pad_ms,
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
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            "Start session complete: session_id=%s, time=%.2fms",
            session.get("id", "unknown") if isinstance(session, dict) else "unknown",
            elapsed_ms,
        )
        return {"session": session}
    except RuntimeError as exc:
        logger.debug("Start session failed: error=%s", str(exc))
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/session/stop")
@log_endpoint
def stop_session(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    stop_session.__endpoint_path__ = "/api/session/stop"
    stop_session.__http_method__ = "POST"
    logger.debug("Stop session: requesting session stop")

    start_time = time.perf_counter()
    session = svc.stop_session()
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    logger.debug(
        "Stop session complete: was_active=%s, time=%.2fms", session is not None, elapsed_ms
    )
    return {"session": session}


@app.get("/api/system/profile")
def get_system_profile() -> dict:
    """Get current system hardware profile."""
    profiler = SystemProfiler()
    return profiler.get_summary()


@app.get("/api/system/optimize")
def get_optimized_settings(
    mode: str = Query(
        "balanced", description="Optimization mode: maximum, balanced, speed, low_memory"
    ),
    hotkey: bool = Query(False, description="Optimize for hotkey/push-to-talk mode"),
) -> dict:
    """Get auto-optimized settings for current hardware."""
    settings = get_recommended_settings(mode=mode, hotkey=hotkey)

    return {
        "settings": {
            "model_name": settings.model_name,
            "compute_type": settings.compute_type,
            "chunk_duration": settings.chunk_duration,
            "overlap_ratio": settings.overlap_ratio,
            "vad_enabled": settings.vad_enabled,
            "vad_threshold_db": settings.vad_threshold_db,
            "confidence_threshold": settings.confidence_threshold,
            "enable_filler_filter": settings.enable_filler_filter,
            "enable_hallucination_filter": settings.enable_hallucination_filter,
            "min_segment_length": settings.min_segment_length,
            "max_workers": settings.max_workers,
            "use_parallel_processing": settings.use_parallel_processing,
            "preload_model": settings.preload_model,
            "hotkey_optimized": settings.hotkey_optimized,
        },
        "metadata": {
            "quality_level": settings.quality_level,
            "optimization_reason": settings.optimization_reason,
            "estimated_vram_usage_gb": settings.estimated_vram_usage_gb,
            "estimated_latency_ms": settings.estimated_latency_ms,
        },
        "mode": mode,
        "hotkey_mode": hotkey,
    }


@app.get("/api/system/presets")
def get_preset_settings() -> dict:
    """Get all preset configurations."""
    optimizer = AutoOptimizer()

    presets = {}
    for preset_name in [
        "maximum_quality",
        "balanced",
        "maximum_speed",
        "low_memory",
        "hotkey_mode",
    ]:
        settings = optimizer.get_preset_settings(preset_name)
        presets[preset_name] = {
            "model_name": settings.model_name,
            "compute_type": settings.compute_type,
            "chunk_duration": settings.chunk_duration,
            "confidence_threshold": settings.confidence_threshold,
            "estimated_vram_usage_gb": settings.estimated_vram_usage_gb,
            "estimated_latency_ms": settings.estimated_latency_ms,
            "optimization_reason": settings.optimization_reason,
        }

    return {"presets": presets}


# ============================================================================
# Settings Endpoints
# ============================================================================


@app.get("/api/settings")
@log_endpoint
def get_settings() -> dict[str, Any]:
    """Get all user settings."""
    get_settings.__endpoint_path__ = "/api/settings"
    get_settings.__http_method__ = "GET"

    manager = get_settings_manager()
    return manager.get_settings_dict()


@app.post("/api/settings")
@log_endpoint
def save_settings(request: dict[str, Any]) -> dict[str, Any]:
    """Save all user settings."""
    save_settings.__endpoint_path__ = "/api/settings"
    save_settings.__http_method__ = "POST"

    manager = get_settings_manager()
    success = manager.import_settings(request)

    if success:
        # Update logging level when advanced.logLevel changes.
        log_level = _resolve_log_level_from_settings_payload(request)
        logging.getLogger().setLevel(getattr(logging, log_level))
        logger.setLevel(getattr(logging, log_level))

        return {"success": True, "message": "Settings saved successfully"}
    else:
        raise HTTPException(status_code=400, detail="Failed to save settings")


@app.post("/api/settings/reset")
@log_endpoint
def reset_settings() -> dict[str, Any]:
    """Reset all settings to defaults."""
    reset_settings.__endpoint_path__ = "/api/settings/reset"
    reset_settings.__http_method__ = "POST"

    manager = get_settings_manager()
    manager.reset_to_defaults()

    return {"success": True, "message": "Settings reset to defaults"}


@app.post("/api/session/attach-pdf")
@log_endpoint
def attach_pdf(
    request: AttachPdfRequest,
    svc: BackendService = Depends(get_service),
) -> dict[str, Any]:
    attach_pdf.__endpoint_path__ = "/api/session/attach-pdf"
    attach_pdf.__http_method__ = "POST"
    logger.debug("Attach PDF: path=%s", request.path)

    start_time = time.perf_counter()
    session = svc.attach_pdf(request.path)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    pdf_info = session.get("pdf", {}) if isinstance(session, dict) else {}
    logger.debug(
        "Attach PDF complete: path=%s, pdf_pages=%s, pdf_title=%s, time=%.2fms",
        request.path,
        pdf_info.get("pages") if isinstance(pdf_info, dict) else None,
        pdf_info.get("title") if isinstance(pdf_info, dict) else None,
        elapsed_ms,
    )
    return {"session": session}


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

            if service is None or manager.connection_count == 0:
                continue

            snapshot = service.get_snapshot()
            health = snapshot.health if hasattr(snapshot, "health") else {}

            # Get hotkey status
            hotkey_data = None
            if hotkey_service is not None:
                hs = hotkey_service.get_status()
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
    if service is not None:
        service.register_event_callback(_handle_transcription_event)

    try:
        # Send initial connection success
        await connection.send(MessageType.AUTH_SUCCESS, {"connected": True})

        # Send current session state if available
        if service is not None:
            snapshot = service.get_snapshot_payload()
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

        if service is not None:
            service.unregister_event_callback(_handle_transcription_event)

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
    if service is not None:
        service.register_event_callback(handle_audio_event)

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
        if service is not None:
            service.unregister_event_callback(handle_audio_event)
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
