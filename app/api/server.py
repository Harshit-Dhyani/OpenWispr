"""
OpenWispr Backend API Server.

This module provides the FastAPI application that serves as the backend
for the OpenWispr desktop transcription application.

Key responsibilities:
- HTTP API endpoints for settings, models, sessions, history
- WebSocket for real-time transcription streaming
- SSE for event streaming
- Hotkey transcription service management
- Session and transcription state management

The server is designed to run locally on Windows and communicate
with the Electron renderer process via HTTP, WebSocket, and SSE.

Security notes:
- CORS is restricted to localhost development ports
- No authentication required for local desktop app
- Sensitive operations are validated at the transport boundary
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
import wave
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np

from app.api import schemas
from app.api.schemas import (
    CoachPromptPreviewRequest,
    HotkeyConfig,
    HotkeyConfigRequest,
    HotkeyInjectRequest,
    HotkeyInjectResponse,
    HotkeyStartRequest,
    HotkeyStartResponse,
    HotkeyStatusResponse,
    HotkeyStopRequest,
    HotkeyStopResponse,
)

logger = logging.getLogger(__name__)


def _check_runtime_dependencies() -> None:
    """Check for missing runtime dependencies and log warnings."""
    # Check torch
    try:
        import torch  # type: ignore[no-redef]

        try:
            if torch.cuda.is_available():
                logger.info("torch with CUDA available")
            else:
                logger.info("torch available (CPU mode)")
        except Exception:
            logger.info("torch available")
    except ImportError:
        logger.warning(
            "torch not installed - GPU acceleration unavailable. Install with `pip install torch`"
        )

    # Check faster-whisper
    try:
        import faster_whisper  # type: ignore[no-redef]

        logger.info("faster-whisper available")
    except ImportError:
        logger.error(
            "faster-whisper not installed - transcription will fail. Install with `pip install faster-whisper`"
        )

    # Check llama-cpp-python
    try:
        import llama_cpp  # type: ignore[no-redef]

        logger.info("llama-cpp-python available")
    except ImportError:
        logger.warning(
            "llama-cpp-python not installed - refinement unavailable. Install with `pip install llama-cpp-python`"
        )


class RateLimiter:
    """Simple in-memory rate limiter for FastAPI endpoints.

    Tracks request counts per endpoint using a sliding window approach.
    Returns 429 when limits are exceeded.
    """

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._limits = {
            "/api/session/start": (10, 60),
            "/api/models/preload": (5, 60),
            "/api/transcribe": (30, 60),
            "/api/hotkey/start": (10, 60),
        }

    def _get_client_id(self, request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, path: str) -> tuple[bool, int, int]:
        for pattern, (max_requests, window_seconds) in self._limits.items():
            if path.startswith(pattern) or path == pattern:
                return True, max_requests, window_seconds
        return False, 0, 0

    async def __call__(self, request: Request, call_next):
        path = request.url.path
        is_limited, max_requests, window_seconds = self._is_rate_limited(path)

        if not is_limited:
            return await call_next(request)

        client_id = self._get_client_id(request)
        key = f"{client_id}:{path}"
        now = time.time()
        window_start = now - window_seconds

        async with self._lock:
            timestamps = self._requests[key]
            self._requests[key] = [ts for ts in timestamps if ts > window_start]

            if len(self._requests[key]) >= max_requests:
                count = len(self._requests[key])
                logger.warning(
                    "Rate limit exceeded: client=%s path=%s count=%d limit=%d",
                    client_id,
                    path,
                    count,
                    max_requests,
                )
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Please try again later.",
                        "retry_after": window_seconds,
                    },
                    headers={"Retry-After": str(window_seconds)},
                )

            self._requests[key].append(now)

        return await call_next(request)


_rate_limiter = RateLimiter()

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.json_utils import make_json_safe
from app.api.services.coach_service import CoachRequestContext, CoachResult, CoachService
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
    hotkey_router,
    models_router,
    providers_router,
    session_router,
    settings_router,
    snippets_router,
    style_router,
    system_router,
    text_transform_router,
)
from app.api.schemas import (
    AttachPdfRequest,
    ModelSelectionRequest,
    PreloadModelRequest,
    RefinementModeRequest,
    StartSessionRequest,
)
from app.api.strings.en import API_STRINGS
from app.api.services.backend_service import BackendService
from app.api.services.refiner_service import RefinerService, is_llama_cpp_available
from app.api.services import (
    DictionaryService,
    HotkeyTranscriptionService,
    SnippetService,
    StyleService,
    TranscriptHistoryService,
)
from app.storage.history_db import HistoryDatabase
from app.audio.capture import LoopbackAudioSource
from app.audio.devices import list_audio_devices

# Note: CoreHotkeySession is in app.core.hotkey_session but is not used in this file
# The API layer uses the dataclass below for session state management
from app.core.settings.config import AppSettings
from app.core.model_catalog import runtime_name_for_model
from app.core.profiling.system_profiler import SystemProfiler
from app.core.optimization.auto_optimizer import AutoOptimizer, get_recommended_settings
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
from app.core.settings.manager import (
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
from app.api.transport.settings_sync import (
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
SSE_EVENT_QUEUE_MAXSIZE = 50
SSE_CLIENT_IDLE_TIMEOUT_SECONDS = 300
DEFAULT_AUDIO_THROTTLE_MS = 50.0


class AudioThrottle:
    """Shared audio event throttle to reduce redundant updates."""

    __slots__ = ("_last_update", "_throttle_ms")

    def __init__(self, throttle_ms: float = DEFAULT_AUDIO_THROTTLE_MS):
        self._last_update: float = 0.0
        self._throttle_ms: float = throttle_ms

    def should_update(self) -> bool:
        now = time.time() * 1000
        if now - self._last_update < self._throttle_ms:
            return False
        self._last_update = now
        return True

    def reset(self) -> None:
        self._last_update = 0.0


# WebSocket manager and settings synchronizer
_ws_manager: WebSocketManager | None = None
_settings_sync: SettingsSynchronizer | None = None
_health_broadcast_task: asyncio.Task | None = None
_HOTKEY_REFINER_TIMEOUT_SECONDS = float(
    os.getenv("OPENWISPR_HOTKEY_REFINER_TIMEOUT_SECONDS", "0.75")
)
_HOTKEY_COACH_TIMEOUT_SECONDS = float(os.getenv("OPENWISPR_HOTKEY_COACH_TIMEOUT_SECONDS", "0.5"))
_HOTKEY_STOP_PROCESSING_WAIT_SECONDS = float(
    os.getenv("OPENWISPR_HOTKEY_STOP_PROCESSING_WAIT_SECONDS", "0.9")
)
_HOTKEY_STOP_DRAIN_WAIT_SECONDS = float(
    os.getenv("OPENWISPR_HOTKEY_STOP_DRAIN_WAIT_SECONDS", "0.45")
)
_HOTKEY_STOP_PROCESSING_WAIT_EMPTY_SECONDS = float(
    os.getenv("OPENWISPR_HOTKEY_STOP_PROCESSING_WAIT_EMPTY_SECONDS", "0.2")
)
_HOTKEY_STOP_DRAIN_WAIT_EMPTY_SECONDS = float(
    os.getenv("OPENWISPR_HOTKEY_STOP_DRAIN_WAIT_EMPTY_SECONDS", "0.1")
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


def _create_sse_event_queue() -> asyncio.Queue[tuple[str, dict[str, Any]]]:
    return asyncio.Queue(maxsize=SSE_EVENT_QUEUE_MAXSIZE)


# Hotkey-specific request/response models are imported from schemas
# See imports at top of file: HotkeyStartRequest, HotkeyStartResponse, etc.


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
    segment_counter: int = 0
    aggregator: UtteranceAggregator = field(default_factory=UtteranceAggregator)
    composer: TranscriptComposer = field(default_factory=TranscriptComposer)
    raw_composed_text: str = ""
    composed_text: str = ""
    aggregated_raw_text: str = ""
    aggregated_clean_text: str = ""
    postprocessed_text: str = ""
    paste_text: str = ""
    latest_live_buffer_text: str = ""
    coach_result: "CoachResult" | None = None
    coach_cache_hit: bool = False
    coach_error: str | None = None
    audio_level: float = 0.0
    source_backend: str = "unknown"
    language_used: str = "auto"
    _callbacks: list[Callable[[str, dict[str, Any]], None]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    processing_task: asyncio.Task | None = None
    draft_stabilizer: "PartialStabilizer" | None = None
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
    final_response: "HotkeyStopResponse" | None = None
    finalization_error: str | None = None
    stop_websockets: set[WebSocket] = field(default_factory=set)

    @property
    def duration_ms(self) -> int:
        return int((time.time() - self.started_at) * 1000)


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_time = time.perf_counter()

    # Check for missing dependencies
    _check_runtime_dependencies()

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

        # Skip synchronous model preloading - models load on first hotkey press
        # This was causing startup issues
        # TODO: Make model loading faster without blocking startup

        history_db_path = Path.cwd() / ".openwispr" / "history.db"
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

        # Start health metrics broadcast
        global _health_broadcast_task
        if _health_broadcast_task is None or _health_broadcast_task.done():
            _health_broadcast_task = asyncio.create_task(_broadcast_health_metrics())
            logger.debug("Started health metrics broadcast task")
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

    # Stop health broadcast and disconnect WebSockets
    if _health_broadcast_task and not _health_broadcast_task.done():
        _health_broadcast_task.cancel()
        try:
            await _health_broadcast_task
        except asyncio.CancelledError:
            pass
        logger.debug("Stopped health metrics broadcast task")

    if _ws_manager is not None:
        await _ws_manager.disconnect_all(1001, "Server shutting down")


_app_settings = AppSettings()
app = FastAPI(
    title=f"{_app_settings.app_name} Local API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(_rate_limiter)
app.include_router(system_router)
app.include_router(models_router)
app.include_router(providers_router)
app.include_router(session_router)
app.include_router(settings_router)
app.include_router(history_router)
app.include_router(dictionary_router)
app.include_router(snippets_router)
app.include_router(style_router)
app.include_router(text_transform_router)
app.include_router(hotkey_router)


# Hotkey WebSocket and SSE endpoints (not in router module)
@app.websocket("/api/transcription/hotkey/ws")
async def hotkey_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time hotkey updates."""
    await websocket.accept()
    client_id = id(websocket)
    logger.debug("Hotkey WebSocket connected: client_id=%s", client_id)

    svc = get_hotkey_service()
    svc.register_websocket(websocket)
    audio_throttle = AudioThrottle()

    async def send_event(event_type: str, data: dict[str, Any]) -> None:
        try:
            if event_type == "hotkey_audio_level" and not audio_throttle.should_update():
                return
            await websocket.send_json(
                {
                    "type": event_type,
                    "payload": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as exc:
            logger.debug("WebSocket send error: %s", exc)

    svc.register_callback(send_event)

    try:
        status = svc.get_status()
        await websocket.send_json(
            {
                "type": "hotkey_status",
                "payload": {
                    "state": status.state,
                    "is_recording": status.is_recording,
                    "partial_text": status.partial_text,
                    "audio_level": status.audio_level,
                    "levels": [status.audio_level] * 36 if status.audio_level > 0 else [0.0] * 36,
                    "session_id": status.session_id,
                    "duration_ms": status.duration_ms,
                },
            }
        )

        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                if message.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
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
    """SSE endpoint for hotkey transcription events."""
    client_id = id(request)
    logger.debug("Hotkey SSE connect: client_id=%s", client_id)

    queue = asyncio.Queue(maxsize=50)
    loop = asyncio.get_running_loop()
    audio_throttle = AudioThrottle()
    idle_deadline = time.perf_counter() + SSE_CLIENT_IDLE_TIMEOUT_SECONDS

    def on_event(event_type: str, data: dict[str, Any]) -> None:
        if event_type == "hotkey_audio_level" and not audio_throttle.should_update():
            return
        try:
            queue.put_nowait({"type": event_type, "payload": data})
        except asyncio.QueueFull:
            logger.debug("Hotkey SSE queue full, dropping event: %s", event_type)

    svc.register_callback(on_event)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break

                remaining = idle_deadline - time.perf_counter()
                timeout = min(30.0, max(1.0, remaining))

                if remaining <= 0:
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=timeout)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
        except Exception as exc:
            logger.debug("Hotkey SSE error: %s", exc)
        finally:
            svc.unregister_callback(on_event)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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

    queue = _create_sse_event_queue()
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
        idle_deadline = connection_start + SSE_CLIENT_IDLE_TIMEOUT_SECONDS

        logger.debug("SSE event generator started: %s", client_info)

        try:
            while True:
                if await request.is_disconnected():
                    logger.debug("SSE client disconnected: %s", client_info)
                    break

                if time.perf_counter() > idle_deadline:
                    logger.debug(
                        "SSE client idle timeout: %s | alive_for=%.1fs",
                        client_info,
                        time.perf_counter() - connection_start,
                    )
                    break

                timeout = min(15.0, idle_deadline - time.perf_counter())
                timeout = max(1.0, timeout)

                try:
                    event_type, data = await asyncio.wait_for(queue.get(), timeout=timeout)
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
        allowed_origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]
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
            allowed_origins=allowed_origins,
            auth_required=os.getenv("OPENWISPR_WS_AUTH_REQUIRED", "true").lower() == "true",
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
            await asyncio.sleep(5.0)

            if api_deps.service is None:
                continue

            conn_count = manager.connection_count
            if conn_count == 0:
                continue

            snapshot = api_deps.service.get_snapshot()
            health = snapshot.health if hasattr(snapshot, "health") else {}

            hotkey_data = None
            if api_deps.hotkey_service is not None:
                hs = api_deps.hotkey_service.get_status()
                if hs.is_recording:
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

    audio_throttle = AudioThrottle()

    async def handle_audio_event(event_type: str, data: dict[str, Any]) -> None:
        if event_type not in ("meter", "audio_level", "hotkey_audio_level"):
            return

        if not audio_throttle.should_update():
            return

        level = data.get("level", 0.0)
        peak = data.get("peak", level)
        levels = data.get("levels")

        await connection.send_audio_level(level, peak, levels)

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
