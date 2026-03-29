"""Hotkey-triggered transcription service for real-time dictation.

This module provides the HotkeyTranscriptionService that handles:
- Hotkey press/release detection for start/stop
- Real-time audio capture from microphone or system audio
- WebSocket streaming of transcription results
- Text injection into focused applications
- Coach and refiner integration for enhanced transcripts

The service manages the complete lifecycle of hotkey transcription sessions
including audio source selection, model routing, and transcript delivery.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np

from fastapi import WebSocket
from pydantic import BaseModel

from app.api.json_utils import make_json_safe
from app.api.services.coach_service import CoachRequestContext, CoachResult, CoachService
from app.api.services.refiner_service import RefinerService
from app.api.session_resolution import (
    resolve_capture_source_setting,
    resolve_input_device_for_source,
)
from app.audio.capture import LoopbackAudioSource
from app.core.model_catalog import runtime_name_for_model
from app.core.settings.config import AppSettings
from app.core.settings.manager import get_settings_manager
from app.stt.deterministic_postprocess import (
    postprocess_final_text,
    postprocess_live_text,
)
from app.stt.dictation_cleanup import (
    TranscriptComposer,
    compose_transcript_text,
    merge_segment_texts,
    normalize_dictation_text,
    stabilize_partial_text,
)
from app.stt.stability import PartialStabilizer, build_stream_payload
from app.stt.utterance_aggregator import UtteranceAggregator

logger = logging.getLogger(__name__)


# Pre-computed empty levels array - reused to avoid allocation
_EMPTY_LEVELS = [0.0] * 36


def _compute_level_array(level: float) -> list[float]:
    """Compute level array with caching for repeated values."""
    if level <= 0.0:
        return _EMPTY_LEVELS
    return [level] * 36


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


class HotkeyConfig(BaseModel):
    chunk_seconds: float = 2.4
    overlap_seconds: float = 0.32
    vad_threshold_db: float = -40.0
    vad_min_silence_ms: int = 250
    vad_speech_pad_ms: int = 240
    confidence_threshold: float = 0.35
    enable_filler_filter: bool = False


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
    coach_status: Literal[
        "disabled", "queued", "running", "failed", "fallback", "cache_hit", "generated", "success"
    ] = "disabled"
    coach_display_source: Literal["coach", "fallback", "faithful"] = "faithful"
    coach_error: str | None = None
    coach_cache_hit: bool = False
    debug_wav_path: str | None = None
    duration_ms: int
    segment_count: int
    source_backend: str = "unknown"
    language_used: str = "auto"
    refinement_mode: str = "off"
    refiner_model_id: str | None = None
    warnings: list[str] = []


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

            # Get model info for floating window display
            stt_model = requested_model_name or model_name or "whisper-medium"
            refiner_settings = user_settings.refiner
            llm_provider = refiner_settings.engine_preference or "llamacpp"
            llm_model = ""
            if refiner_settings.runtime_enabled:
                if llm_provider in ("ollama", "lm_studio") and refiner_settings.custom_model_id:
                    llm_model = refiner_settings.custom_model_id
                else:
                    llm_model = refiner_settings.selected_model_id or "qwen2.5-3b-instruct"

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
                refinement_profile=getattr(
                    user_settings.transcription, "refinement_profile", "raw"
                ),
                started_at=time.time(),
                is_recording=True,
                state="starting",
                draft_stabilizer=PartialStabilizer(session_id=session_id, stability_threshold=2),
            )

            try:
                session.audio_source = self._create_audio_source(
                    capture_source=capture_source,
                    device_id=device_id,
                )
                session.resolved_device_id = getattr(session.audio_source, "device_id", device_id)
                from app.audio.devices import list_audio_devices

                resolved_device = next(
                    (
                        device
                        for device in list_audio_devices()
                        if device.id == session.resolved_device_id
                    ),
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

                session.transcriber = await self._create_transcriber(
                    model_name=model_name,
                    language_mode=language_mode,
                    execution_mode=execution_mode,
                )

                session.transcriber.add_segment_callback(
                    lambda segment: self._on_transcription_segment(session, segment)
                )
                if hasattr(session.transcriber, "add_partial_callback"):
                    session.transcriber.add_partial_callback(
                        lambda text, start, end: self._on_partial_transcription(
                            session, text, start, end
                        )
                    )
                if hasattr(session.transcriber, "add_status_callback"):

                    def _publish_hotkey_loading_status(message: str) -> None:
                        lowered = (message or "").lower()
                        if "loaded" in lowered:
                            stage = "ready"
                        elif "error" in lowered or "failed" in lowered:
                            stage = "error"
                        else:
                            stage = "loading"
                        self._publish_event(
                            "hotkey_status",
                            {
                                "session_id": session.session_id,
                                "message": message,
                                "stage": stage,
                                "model_name": model_name,
                                "stt_model": stt_model,
                                "llm_provider": llm_provider,
                                "llm_model": llm_model,
                            },
                        )

                    session.transcriber.add_status_callback(_publish_hotkey_loading_status)

                session.transcriber.start()

                self._session = session

                session.processing_task = asyncio.create_task(self._process_audio_loop(session))
                session.state = "recording"

                logger.info(
                    "Publishing hotkey_started with stt_model=%s, llm_provider=%s, llm_model=%s",
                    stt_model,
                    llm_provider,
                    llm_model,
                )
                self._publish_event(
                    "hotkey_started",
                    {
                        "session_id": session_id,
                        "started_at": session.started_at,
                        "state": session.state,
                        "is_recording": True,
                        "stt_model": stt_model,
                        "llm_provider": llm_provider,
                        "llm_model": llm_model,
                    },
                )
                self._publish_status(session)

                from app.api.strings.en import API_STRINGS

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
                raise

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
            status=status
            or (
                "stopping" if session.finalize_task and not session.finalize_task.done() else "idle"
            ),
            transcription_mode=getattr(session, "transcription_mode", "dictation"),
            composed_text=session.composed_text or "",
            final_transcription=session.composed_text or "",
            aggregated_raw_text=session.aggregated_raw_text or session.raw_composed_text or "",
            aggregated_clean_text=session.aggregated_clean_text or session.composed_text or "",
            postprocessed_text=session.postprocessed_text or session.composed_text or "",
            paste_text=session.paste_text
            or session.postprocessed_text
            or session.composed_text
            or "",
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
            coach_status="cache_hit"
            if session.coach_cache_hit
            else ("success" if session.coach_result else "disabled"),
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
            except Exception as e:
                logger.debug("Failed to get transcriber stats: %s", e)
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
        from datetime import datetime, timezone
        from pathlib import Path
        import wave

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
                user_settings = get_settings_manager().get_settings()
                hotkey_settings = getattr(user_settings, "hotkey", None)
                should_auto_transform = bool(getattr(hotkey_settings, "auto_transform", True))
                base_text = (
                    aggregated_raw_text or raw_text
                    if transcription_mode == "literal"
                    else aggregated_clean_text or aggregated_raw_text or raw_text
                )
                final_text = (
                    postprocess_final_text(
                        base_text,
                        mode=transcription_mode,
                        profile=getattr(session, "refinement_profile", "clean_dictation"),
                    )
                    if should_auto_transform
                    else base_text
                )
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
            coach_status: Literal[
                "disabled",
                "queued",
                "running",
                "failed",
                "fallback",
                "cache_hit",
                "generated",
                "success",
            ] = "disabled"
            coach_display_source: Literal["coach", "fallback", "faithful"] = "faithful"
            coach_error: str | None = None
            coach_cache_hit = False
            user_settings = get_settings_manager().get_settings()
            hotkey_settings = getattr(user_settings, "hotkey", None)
            coach_settings = getattr(user_settings, "coach", None)
            transcription_mode = getattr(session, "transcription_mode", "dictation")
            should_refine_on_stop = bool(getattr(hotkey_settings, "enable_refiner_on_stop", False))
            should_write_debug_wav = bool(getattr(hotkey_settings, "save_debug_wav", False))
            response_warnings = (
                list(getattr(aggregated, "warnings", [])) if not session.cancel_requested else []
            )
            final_text_present = bool((final_text or "").strip())

            refiner_result = None  # Initialize before try block
            try:
                logger.info(
                    "Hotkey refine check: session=%s should_refine=%s profile=%s mode=%s enabled=%s text_present=%s",
                    session.session_id,
                    should_refine_on_stop,
                    getattr(session, "refinement_profile", "raw"),
                    getattr(user_settings.transcription, "refinement_mode", "off"),
                    getattr(user_settings.refiner, "runtime_enabled", False),
                    final_text_present,
                )
                if (
                    should_refine_on_stop
                    and not session.cancel_requested
                    and getattr(session, "refinement_profile", "raw") != "raw"
                    and final_text_present
                ):
                    refinement_mode = user_settings.transcription.refinement_mode

                    # Use model based on engine preference:
                    # - Ollama/LM Studio: use custom_model_id (from their server)
                    # - llama.cpp: use selected_model_id (from catalog)
                    engine = user_settings.refiner.engine_preference or "llamacpp"
                    if engine in ("ollama", "lm_studio") and user_settings.refiner.custom_model_id:
                        refiner_model_id = user_settings.refiner.custom_model_id
                    else:
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
                logger.info(
                    "Hotkey coach check: session=%s text_chars=%d privacy=%s enabled=%s",
                    session.session_id,
                    len(aggregated_clean_text or final_text or ""),
                    getattr(coach_settings, "privacy_mode", "local_only"),
                    bool(getattr(coach_settings, "coach_enabled", True)),
                )
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
                            runtime_enabled=bool(
                                getattr(user_settings.coach, "coach_runtime_enabled", True)
                            ),
                            model_id=getattr(
                                user_settings.coach,
                                "coach_selected_model_id",
                                "qwen2.5-3b-instruct",
                            ),
                            custom_user_template=custom_prompt_text,
                            templates=[
                                template.__dict__
                                if hasattr(template, "__dict__")
                                else dict(template)
                                for template in (prompt_templates or [])
                            ],
                        )
                        coach_status = "queued"
                        logger.info(
                            "Coach queued: session=%s source=%s template=%s detail=%s privacy=%s text_chars=%d",
                            session.session_id,
                            session.capture_source,
                            template_id,
                            detail_level,
                            privacy_mode,
                            len(context.text or ""),
                        )
                        try:
                            coach_status = "running"
                            logger.info(
                                "Coach running: session=%s model=%s runtime_enabled=%s",
                                session.session_id,
                                getattr(
                                    user_settings.coach,
                                    "coach_selected_model_id",
                                    "qwen2.5-3b-instruct",
                                ),
                                bool(getattr(user_settings.coach, "coach_runtime_enabled", True)),
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
                            if raw_coach_result.meta.provider.startswith(
                                "fallback"
                            ) or raw_coach_result.meta.provider.startswith("disabled"):
                                coach_display_source = "fallback"
                                coach_error = raw_coach_result.meta.provider
                                coach_result = raw_coach_result
                                logger.warning(
                                    "Coach fallback provider: session=%s provider=%s",
                                    session.session_id,
                                    raw_coach_result.meta.provider,
                                )
                            else:
                                coach_display_source = "coach"
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
                    coach_display_source = "faithful"
                    coach_error = str(exc)
                    session.coach_error = coach_error
                    logger.warning("Coach failed: session=%s error=%s", session.session_id, exc)

            faithful_text = aggregated_clean_text or final_text
            # Use refiner output if available, otherwise use clean text
            if refiner_result and refiner_result.used_runtime and refiner_result.text:
                paste_text = refiner_result.text
                paste_source = "refiner"
            else:
                paste_text = faithful_text
                paste_source = "faithful_clean"
            # Coach can override if it ran and copy_polished_by_default is True
            if coach_result is not None and bool(
                getattr(coach_settings, "copy_polished_by_default", True)
            ):
                paste_text = coach_result.polished or paste_text
                paste_source = (
                    "coach_polished" if coach_display_source == "coach" else "coach_fallback"
                )
            logger.info(
                "Hotkey finalize paste source: session=%s coach_status=%s display_source=%s selected=%s faithful_chars=%d final_chars=%d paste_chars=%d",
                session.session_id,
                coach_status,
                coach_display_source,
                paste_source,
                len(faithful_text or ""),
                len(final_text or ""),
                len(paste_text or ""),
            )
            logger.info(
                "Hotkey text details: session=%s faithful='%s' final='%s' paste='%s'",
                session.session_id,
                (faithful_text or "")[:100],
                (final_text or "")[:100],
                (paste_text or "")[:100],
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
                live_paste_text=""
                if session.cancel_requested
                else (session.latest_live_buffer_text or paste_text),
                final_cleanup_applied=not session.cancel_requested,
                raw_transcription=raw_text,
                refined_transcription=refined_text,
                coach_result=coach_result,
                coach_status=coach_status,
                coach_display_source=coach_display_source,
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
                    "live_paste_text": ""
                    if session.cancel_requested
                    else (session.latest_live_buffer_text or paste_text),
                    "final_cleanup_applied": not session.cancel_requested,
                    "raw_transcription": raw_text,
                    "refined_transcription": refined_text,
                    "coach_result": coach_result.model_dump(by_alias=True)
                    if coach_result
                    else None,
                    "coach_status": coach_status,
                    "coach_display_source": coach_display_source,
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
            active_websockets = [
                websocket for websocket in list(targets) if websocket in self._websockets
            ]
        for websocket in active_websockets:
            try:
                await websocket.close(code=code, reason=reason)
            except Exception as e:
                logger.warning(f"Failed to close websocket: {e}")
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
            # Use cached level computation - avoid list allocation in hot path
            levels = _compute_level_array(session.audio_level)
            payload = {
                "state": session.state,
                "is_recording": session.is_recording,
                "partial_text": session.display_partial_text,
                "raw_partial_text": session.raw_partial_text,
                "display_partial_text": session.display_partial_text,
                "audio_level": session.audio_level,
                "levels": levels,
                "session_id": session.session_id,
                "duration_ms": session.duration_ms,
            }
        self._publish_event("hotkey_status", payload)

    def _resolve_capture_source(
        self, capture_source: Literal["microphone", "system"] | None
    ) -> Literal["microphone", "system"]:
        return resolve_capture_source_setting(capture_source)

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

        block_size = int(self.settings.sample_rate * self.settings.capture_block_seconds)
        max_queue_items = 10

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
        return resolve_input_device_for_source(capture_source, device_id)

    async def _create_transcriber(
        self,
        model_name: str,
        language_mode: str,
        execution_mode: str,
    ) -> Any:
        """Create transcriber with hotkey-optimized settings."""
        from app.stt.fast_engine import FastTranscriber
        from app.core.settings.config import resolve_live_profile

        resolve_live_profile("low_latency", self.settings)

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
            await asyncio.sleep(0.1)  # Wait for backend to initialize
            session.source_backend = session.audio_source.backend_name or "unknown"
            logger.info(f"Hotkey audio loop started: backend={session.source_backend}")

            chunk_samples = int(self._config.chunk_seconds * self.settings.sample_rate)
            overlap_samples = max(0, int(self._config.overlap_seconds * self.settings.sample_rate))
            step_samples = max(1, chunk_samples - overlap_samples)
            audio_buffer = np.array([], dtype=np.float32)

            while session.is_recording:
                try:
                    chunk = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, session.audio_source.read),
                        timeout=0.5,
                    )

                    if chunk is None or len(chunk) == 0:
                        await asyncio.sleep(0.01)
                        continue

                    if session.audio_source.backend_name:
                        session.source_backend = session.audio_source.backend_name

                    session.audio_level = self._calculate_audio_level(chunk)

                    # Log audio level periodically
                    now = time.time()
                    if (
                        not hasattr(session, "_last_audio_log")
                        or now - session._last_audio_log > 2.0
                    ):
                        rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                        peak = float(np.max(np.abs(chunk)))
                        logger.info(
                            f"Audio level: %.4f rms=%.6f peak=%.6f backend=%s",
                            session.audio_level,
                            rms,
                            peak,
                            session.source_backend,
                        )
                        session._last_audio_log = now

                    if session.is_recording and not session.suppress_stream_events:
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

                    audio_buffer = np.concatenate([audio_buffer, chunk])

                    while len(audio_buffer) >= chunk_samples:
                        process_chunk = audio_buffer[:chunk_samples]
                        audio_buffer = audio_buffer[step_samples:]

                        await self._transcribe_chunk(session, process_chunk)

                except asyncio.TimeoutError:
                    continue
                except Exception as exc:
                    logger.debug("Error in audio loop: %s", exc)
                    await asyncio.sleep(0.01)

            if (
                not session.cancel_requested
                and len(audio_buffer) > self.settings.sample_rate * 0.18
            ):
                await self._transcribe_chunk(session, audio_buffer)

        except Exception as exc:
            logger.exception("Fatal error in hotkey audio loop")
            self._publish_event("hotkey_error", {"error": str(exc)})
        finally:
            try:
                session.audio_source.stop()
            except Exception as e:
                logger.debug("Failed to stop audio source in finally block: %s", e)

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

        rms = np.sqrt(np.mean(safe_audio**2))

        db = 20 * np.log10(rms + 1e-10)

        normalized = (db + 60) / 60
        return max(0.0, min(1.0, normalized))

    def _calculate_frequency_levels(self, audio: np.ndarray, num_bars: int = 36) -> list[float]:
        """Calculate frequency-based levels for waveform visualization."""
        if len(audio) == 0:
            return [0.0] * num_bars

        safe_audio = np.nan_to_num(
            np.clip(audio.astype(np.float32, copy=False), -1.0, 1.0),
            nan=0.0,
            posinf=1.0,
            neginf=-1.0,
        )

        rms = np.sqrt(np.mean(safe_audio**2))
        base_level = max(0.0, min(1.0, (20 * np.log10(rms + 1e-10) + 60) / 60))

        levels = []

        segment_size = max(1, len(safe_audio) // num_bars)

        for i in range(num_bars):
            start = i * segment_size
            end = min(start + segment_size, len(safe_audio))

            if start < len(safe_audio):
                segment = safe_audio[start:end]
                local_rms = np.sqrt(np.mean(segment**2)) if len(segment) > 0 else 0

                freq_response = np.exp(-0.5 * ((i - num_bars / 2) / (num_bars / 4)) ** 2)
                freq_response = 0.3 + 0.7 * freq_response

                local_level = max(0.0, min(1.0, (20 * np.log10(local_rms + 1e-10) + 60) / 60))

                blended = 0.4 * base_level + 0.6 * local_level * freq_response

                if base_level > 0.05:
                    # Use deterministic noise based on segment position - avoids random in hot path
                    # np.random adds entropy but is slow; use pre-computed pattern
                    noise = (
                        0.02 * base_level * ((i % 5) / 4.0 - 0.5)
                    )  # Small deterministic variation
                    blended = min(1.0, blended + abs(noise))

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
                session.silence_skip_streak = (
                    int(getattr(session, "silence_skip_streak", 0) or 0) + 1
                )
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
            estimated_backlog = float(getattr(status, "estimated_backlog_seconds", 0.0) or 0.0)
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
        if session.cancel_requested or self._session is not session:
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

        segment_id = getattr(segment, "id", None)
        if segment_id is None:
            segment_id = f"hotkey-seg-{session.segment_counter}"
            session.segment_counter += 1

        payload = {
            "id": segment_id,
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
            draft_state = (
                session.draft_stabilizer.consume_final_text(
                    payload["text"],
                    start=payload["start"],
                    end=payload["end"],
                )
                if session.draft_stabilizer
                else None
            )
            if (
                draft_state is not None
                and getattr(session, "transcription_mode", "dictation") != "session_paragraph"
            ):
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
        self._publish_event("hotkey_draft_partial", payload)

    def _is_debug_mode_enabled(self) -> bool:
        try:
            return bool(get_settings_manager().get_settings().advanced.debugMode)
        except Exception as e:
            logger.debug("Failed to get debug mode setting: %s", e)
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
        except Exception as e:
            logger.warning(f"Failed to get hotkey settings: {e}")
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
        if (
            phase == "submit"
            and session.debug_last_audio_log_at
            and now - session.debug_last_audio_log_at < 0.75
        ):
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
        combined = (
            np.concatenate(session.debug_audio_chunks)
            if len(session.debug_audio_chunks) > 1
            else session.debug_audio_chunks[0]
        )
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
        safe_data = make_json_safe(data)
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
            except Exception as e:
                logger.warning(f"Failed to process hotkey event: {e}")
                continue


from dataclasses import dataclass, field


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
