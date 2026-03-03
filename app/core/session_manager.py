from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from app.audio.capture import LoopbackAudioSource, MeterSmoother
from app.audio.devices import list_audio_devices
from app.core.config import AppSettings, resolve_live_profile
from app.core.logging_utils import configure_logging
from app.core.models import AudioDeviceInfo, SessionHealth, SessionState, TranscriptSegment, utc_now
from app.stem.postprocess import StemNoteProcessor
from app.storage.document_store import ContextProvider, DocumentStore
from app.storage.session_store import SessionWriter
from app.stt.fast_chunker import FastChunker
from app.stt.fast_engine import FastTranscriber

WhisperTranscriber = FastTranscriber


class SessionManager:
    CHUNK_DURATION_MS = 200
    TARGET_LATENCY_MS = 500
    MAX_WORKERS = 2

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.session: SessionState | None = None
        self.writer: SessionWriter | None = None
        self.document_store = DocumentStore()
        self.context_provider = ContextProvider(self.document_store)
        self.note_processor = StemNoteProcessor()
        self.audio_source: LoopbackAudioSource | None = None
        self.chunker: FastChunker | None = None
        self.transcriber: FastTranscriber | None = None
        self.logger = None
        self.meter = MeterSmoother(decay=settings.meter_decay)
        self._audio_thread: threading.Thread | None = None
        self._processing_executor: ThreadPoolExecutor | None = None
        self._stop_event = threading.Event()
        self._last_rebuild_at = 0.0
        self._outputs_dirty = False
        self._last_processed_segment_index = -1
        self._pending_chunks: int = 0
        self._pending_lock = threading.Lock()
        self._on_segment: Callable[[TranscriptSegment], None] | None = None
        self._on_partial: Callable[[str, float, float], None] | None = None
        self._on_health: Callable[[SessionHealth, float], None] | None = None
        self._on_state: Callable[[SessionState], None] | None = None
        self._callback_lock = threading.Lock()
        self._session_lock = threading.Lock()
        self._preloaded_model: Any = None
        self._preload_lock = threading.Lock()
        self._loop_counter: int = 0
        self._last_loop_log: float = 0.0
        self._chunks_processed: int = 0

    def set_callbacks(
        self,
        *,
        on_segment=None,
        on_partial=None,
        on_health=None,
        on_state=None,
    ) -> None:
        registered = []
        if on_segment:
            registered.append("on_segment")
        if on_partial:
            registered.append("on_partial")
        if on_health:
            registered.append("on_health")
        if on_state:
            registered.append("on_state")

        with self._callback_lock:
            self._on_segment = on_segment
            self._on_partial = on_partial
            self._on_health = on_health
            self._on_state = on_state

        if self.logger:
            self.logger.debug(
                "callbacks_registered",
                extra={
                    "registered": registered,
                    "session_id": self.session.session_id if self.session else None,
                },
            )

    def preload_model(
        self,
        model_name: str,
        language_mode: str,
        execution_mode: str,
    ) -> dict[str, Any]:
        session_slug = self.session.session_id if self.session else None

        if self.logger:
            self.logger.debug(
                "preload_model_start",
                extra={
                    "model_name": model_name,
                    "language_mode": language_mode,
                    "execution_mode": execution_mode,
                    "session_id": session_slug,
                },
            )

        with self._preload_lock:
            if self._preloaded_model is not None:
                if self.logger:
                    self.logger.debug(
                        "preload_model_already_loaded",
                        extra={
                            "device": self._preloaded_model.get("device", "unknown"),
                            "session_id": session_slug,
                        },
                    )
                return {
                    "status": "already_loaded",
                    "device": self._preloaded_model.get("device", "unknown"),
                }

            transcriber = WhisperTranscriber(
                model_name=model_name,
                download_root=str(self.settings.download_root),
                device=self.settings.device,
                compute_type=self.settings.compute_type,
                beam_size=self.settings.beam_size,
                best_of=self.settings.best_of,
                temperature=self.settings.temperature,
                vad_filter=self.settings.vad_filter,
                language_mode=language_mode,
                execution_mode=execution_mode,
                max_queue_items=self.settings.max_queue_items,
            )

            start_time = time.perf_counter()
            model = transcriber.load_model()
            load_time_ms = (time.perf_counter() - start_time) * 1000

            self._preloaded_model = {
                "transcriber": transcriber,
                "model": model,
                "device": transcriber._gpu_mode,
                "load_time_ms": load_time_ms,
            }

            if self.logger:
                self.logger.debug(
                    "preload_model_complete",
                    extra={
                        "model_name": model_name,
                        "execution_mode": execution_mode,
                        "device": transcriber._gpu_mode,
                        "load_time_ms": round(load_time_ms, 2),
                        "session_id": session_slug,
                    },
                )

            return {
                "status": "loaded",
                "device": transcriber._gpu_mode,
                "load_time_ms": load_time_ms,
            }

    def list_devices(self) -> list[AudioDeviceInfo]:
        return list_audio_devices()

    def attach_pdf(self, path: str) -> None:
        if self.session is None:
            return
        document = self.document_store.add_pdf(path)
        self.session.documents.append(document)
        if self.writer:
            self.writer.write_metadata()
        self._emit_state()

    def start_session(
        self,
        *,
        title: str,
        output_root: Path,
        model_name: str,
        language_mode: str,
        device_id: str | None,
        live_mode: str,
        execution_mode: str,
        vad_params: dict[str, Any] | None = None,
        enable_streaming: bool = True,
    ) -> SessionState:
        if self.session and self.session.status == "running":
            raise RuntimeError("Session already running")

        self.document_store = DocumentStore()
        self.context_provider = ContextProvider(self.document_store)

        output_dir = output_root / slugify(title)
        self.session = SessionState.create(
            title=title,
            output_dir=output_dir,
            model_name=model_name,
            language_mode=language_mode,
            device_id=device_id or "default",
            live_mode=live_mode,
            execution_mode=execution_mode,
        )
        self.writer = SessionWriter(self.session)
        self.logger = configure_logging(output_dir / "logs", self.settings.log_level)

        self.logger.debug(
            "session_start_init",
            extra={
                "session_id": self.session.session_id,
                "title": title,
                "export_root": str(output_root),
                "model_name": model_name,
                "language_mode": language_mode,
                "live_mode": live_mode,
                "execution_mode": execution_mode,
                "device_id": device_id or "default",
                "enable_streaming": enable_streaming,
            },
        )

        self.writer.write_metadata()

        live_profile = resolve_live_profile(live_mode, self.settings)
        chunk_duration = live_profile["chunk_seconds"]
        self.chunker = FastChunker(
            sample_rate=self.settings.sample_rate,
            chunk_duration=chunk_duration,
            overlap_ratio=max(0.05, min(live_profile["overlap_seconds"] / chunk_duration, 0.4)),
        )

        block_size = max(
            256,
            int(self.settings.sample_rate * self.settings.capture_block_seconds),
        )
        self.audio_source = LoopbackAudioSource(
            device_id=device_id,
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
            block_size=block_size,
            max_queue_items=self.settings.max_queue_items * 2,
            audio_backend=self.settings.audio_backend,
        )
        self.audio_source.on_error = self._handle_error

        with self._preload_lock:
            if self._preloaded_model and self._preloaded_model.get("transcriber"):
                cached = self._preloaded_model
                self.transcriber = cached["transcriber"]
                if self.transcriber.model_name == model_name:
                    self.transcriber.set_language_mode(language_mode)
                    self.transcriber.set_execution_mode(execution_mode)
                    self.transcriber.set_streaming_profile(
                        streaming_window_ms=max(800, int(chunk_duration * 1000)),
                        streaming_overlap_ms=max(120, int(live_profile["overlap_seconds"] * 1000)),
                    )
                else:
                    self._preloaded_model = None
                    self.transcriber = None
            else:
                self.transcriber = None

        if self.transcriber is None:
            self.transcriber = WhisperTranscriber(
                model_name=model_name,
                download_root=str(self.settings.download_root),
                device=self.settings.device,
                compute_type=self.settings.compute_type,
                beam_size=self.settings.beam_size,
                best_of=self.settings.best_of,
                temperature=self.settings.temperature,
                vad_filter=False if live_mode == "ultra" else self.settings.vad_filter,
                language_mode=language_mode,
                execution_mode=execution_mode,
                max_queue_items=self.settings.max_queue_items,
                vad_params=vad_params,
                streaming_window_ms=max(800, int(chunk_duration * 1000)),
                streaming_overlap_ms=max(120, int(live_profile["overlap_seconds"] * 1000)),
            )

        self.transcriber.add_segment_callback(self._handle_segment)
        self.transcriber.add_partial_callback(self._handle_partial)
        self.transcriber.add_error_callback(self._handle_error)
        self.transcriber.add_health_callback(self._handle_health)

        self.logger.debug(
            "transcriber_callbacks_registered",
            extra={
                "session_id": self.session.session_id,
                "model_name": model_name,
                "execution_mode": execution_mode,
            },
        )

        try:
            self._stop_event.clear()
            self._last_rebuild_at = 0.0
            self._outputs_dirty = False
            self._last_processed_segment_index = -1
            self._pending_chunks = 0
            self._loop_counter = 0
            self._last_loop_log = 0.0
            self._chunks_processed = 0

            self.session.health.execution_mode = execution_mode
            self.session.health.last_warning = self._get_language_warning(language_mode)
            self.session.health.audio_backend = None
            self.session.health.audio_backend_fallbacks = []
            self.session.health.audio_device_error = None

            self.logger.debug(
                "session_components_reset",
                extra={
                    "session_id": self.session.session_id,
                    "preloaded_model": self._preloaded_model is not None,
                },
            )

            if self._preloaded_model is None:
                self.logger.debug(
                    "loading_model",
                    extra={
                        "session_id": self.session.session_id,
                        "model_name": model_name,
                    },
                )
                self.transcriber.load_model()
                self.logger.debug(
                    "model_loaded",
                    extra={
                        "session_id": self.session.session_id,
                        "model_name": model_name,
                    },
                )
            else:
                self.logger.debug(
                    "using_preloaded_model",
                    extra={
                        "session_id": self.session.session_id,
                        "model_name": model_name,
                    },
                )

            self.transcriber.start()
            self.audio_source.start()

            self.logger.debug(
                "audio_pipeline_started",
                extra={
                    "session_id": self.session.session_id,
                    "device_id": device_id or "default",
                },
            )

            self._processing_executor = ThreadPoolExecutor(
                max_workers=self.MAX_WORKERS,
                thread_name_prefix="stt-worker",
            )

            self.logger.debug(
                "thread_pool_created",
                extra={
                    "session_id": self.session.session_id,
                    "max_workers": self.MAX_WORKERS,
                },
            )

            self._audio_thread = threading.Thread(
                target=self._audio_loop_parallel if enable_streaming else self._audio_loop,
                name="audio-loop",
                daemon=True,
            )
            self._audio_thread.start()

            self.logger.debug(
                "audio_thread_started",
                extra={
                    "session_id": self.session.session_id,
                    "thread_name": "audio-loop",
                    "streaming_mode": enable_streaming,
                },
            )

            self.session.status = "running"
            if self.writer:
                self.writer.write_metadata()
            self._emit_state()

            self.logger.debug(
                "session_started_success",
                extra={
                    "session_id": self.session.session_id,
                    "status": "running",
                    "model_name": model_name,
                    "language_mode": language_mode,
                    "live_mode": live_mode,
                    "execution_mode": execution_mode,
                },
            )

            return self.session

        except Exception as e:
            if self.logger:
                self.logger.exception(
                    "session_start_failed",
                    extra={
                        "session_id": self.session.session_id if self.session else None,
                        "error": str(e),
                    },
                )
            if self.session:
                self.session.status = "error"
                self.session.health.audio_stream_active = False
                if self.writer:
                    self.writer.write_metadata()
                self._emit_state()
            self.audio_source = None
            self.transcriber = None
            self._audio_thread = None
            self._processing_executor = None
            raise

    def stop_session(self) -> None:
        session_slug = self.session.session_id if self.session else None

        if self.logger:
            self.logger.debug(
                "session_stop_init",
                extra={
                    "session_id": session_slug,
                    "current_status": self.session.status if self.session else None,
                },
            )

        self._stop_event.set()

        if self.audio_source:
            self.audio_source.stop()
            if self.logger:
                self.logger.debug(
                    "audio_source_stopped",
                    extra={"session_id": session_slug},
                )

        if self.transcriber:
            self.transcriber.stop()
            if self.logger:
                self.logger.debug(
                    "transcriber_stopped",
                    extra={"session_id": session_slug},
                )

        if self._processing_executor:
            self._processing_executor.shutdown(wait=True, cancel_futures=True)
            if self.logger:
                self.logger.debug(
                    "thread_pool_shutdown",
                    extra={"session_id": session_slug},
                )

        if self._audio_thread:
            joined = self._audio_thread.join(timeout=3)
            if self.logger:
                self.logger.debug(
                    "audio_thread_joined",
                    extra={
                        "session_id": session_slug,
                        "joined": joined is not None,
                        "alive": self._audio_thread.is_alive() if self._audio_thread else None,
                    },
                )

        if self.session:
            self.session.status = "stopped"
            self._rebuild_outputs(force=True)
            if self.writer:
                self.writer.write_metadata()

        self._emit_state()

        if self.logger:
            self.logger.debug(
                "session_stopped_success",
                extra={
                    "session_id": session_slug,
                    "status": "stopped",
                    "total_chunks_processed": self._chunks_processed,
                },
            )

    def _audio_loop(self) -> None:
        assert self.audio_source is not None
        assert self.chunker is not None
        stream_time = 0.0
        loop_count = 0
        last_log_time = time.monotonic()

        if self.logger:
            self.logger.debug(
                "audio_loop_started",
                extra={
                    "session_id": self.session.session_id if self.session else None,
                    "mode": "sequential",
                },
            )

        while not self._stop_event.is_set():
            samples = self.audio_source.read(timeout=0.05)
            loop_count += 1

            print(
                f"[AUDIO_LOOP] samples read: {'None' if samples is None else f'{len(samples)} samples'}"
            )

            if samples is None:
                continue

            stream_time += len(samples) / self.settings.sample_rate
            chunks = self.chunker.push(samples, stream_time)
            chunk_count = len(chunks)
            self._chunks_processed += chunk_count

            print(f"[AUDIO_LOOP] chunks created: {chunk_count} (total: {self._chunks_processed})")

            if self.session:
                self.session.health.audio_stream_active = True
                self.session.health.dropped_frames = self.audio_source.dropped_frames

            for chunk in chunks:
                if self.transcriber:
                    print(f"[AUDIO_LOOP] submitting chunk to transcriber")
                    self.transcriber.submit(chunk)
                else:
                    print(f"[AUDIO_LOOP] WARNING: no transcriber available")

            self._maybe_rebuild_outputs()
            self._emit_health()

            now = time.monotonic()
            if now - last_log_time >= 1.0:
                extra_dict = {
                    "session_id": self.session.session_id if self.session else None,
                    "loops": loop_count,
                    "chunks_submitted": chunk_count,
                    "total_chunks": self._chunks_processed,
                    "stream_time": round(stream_time, 3),
                    "dropped_frames": self.audio_source.dropped_frames,
                }
                print(f"[AUDIO_LOOP] logging extra dict: {extra_dict}")
                if self.logger:
                    self.logger.debug(
                        "audio_loop_stats",
                        extra=extra_dict,
                    )
                loop_count = 0
                last_log_time = now

        if self.logger:
            self.logger.debug(
                "audio_loop_ended",
                extra={
                    "session_id": self.session.session_id if self.session else None,
                    "total_chunks_processed": self._chunks_processed,
                    "final_stream_time": round(stream_time, 3),
                },
            )

    def _audio_loop_parallel(self) -> None:
        assert self.audio_source is not None
        assert self.chunker is not None
        assert self._processing_executor is not None

        stream_time = 0.0
        last_health_emit = 0.0
        loop_count = 0
        last_log_time = time.monotonic()

        if self.logger:
            self.logger.debug(
                "audio_loop_started",
                extra={
                    "session_id": self.session.session_id if self.session else None,
                    "mode": "parallel",
                    "max_workers": self.MAX_WORKERS,
                },
            )

        while not self._stop_event.is_set():
            samples = self.audio_source.read(timeout=0.02)
            loop_count += 1

            if samples is None:
                continue

            stream_time += len(samples) / self.settings.sample_rate
            chunks = self.chunker.push(samples, stream_time)
            chunk_count = len(chunks)
            self._chunks_processed += chunk_count

            if self.session:
                self.session.health.audio_stream_active = True
                self.session.health.dropped_frames = self.audio_source.dropped_frames

            for chunk in chunks:
                with self._pending_lock:
                    self._pending_chunks += 1
                self._processing_executor.submit(self._process_chunk, chunk)

            now = time.monotonic()
            if now - last_health_emit > 0.1:
                self._maybe_rebuild_outputs()
                self._emit_health()
                last_health_emit = now

            if now - last_log_time >= 1.0:
                with self._pending_lock:
                    pending = self._pending_chunks
                if self.logger:
                    self.logger.debug(
                        "audio_loop_stats",
                        extra={
                            "session_id": self.session.session_id if self.session else None,
                            "loops": loop_count,
                            "chunks_submitted": chunk_count,
                            "total_chunks": self._chunks_processed,
                            "pending_chunks": pending,
                            "stream_time": round(stream_time, 3),
                            "dropped_frames": self.audio_source.dropped_frames,
                        },
                    )
                loop_count = 0
                last_log_time = now

        if self.logger:
            self.logger.debug(
                "audio_loop_ended",
                extra={
                    "session_id": self.session.session_id if self.session else None,
                    "total_chunks_processed": self._chunks_processed,
                    "final_stream_time": round(stream_time, 3),
                },
            )

    def _process_chunk(self, chunk: Any) -> None:
        chunk_start = time.perf_counter()
        try:
            if self.transcriber and not self._stop_event.is_set():
                self.transcriber.submit(chunk)
        finally:
            with self._pending_lock:
                self._pending_chunks -= 1
            if self.logger and self.logger.isEnabledFor(10):
                elapsed_ms = (time.perf_counter() - chunk_start) * 1000
                if elapsed_ms > 100:
                    self.logger.debug(
                        "slow_chunk_processing",
                        extra={
                            "session_id": self.session.session_id if self.session else None,
                            "elapsed_ms": round(elapsed_ms, 2),
                        },
                    )

    def _handle_partial(self, text: str, start: float, end: float) -> None:
        if self.logger:
            self.logger.debug(
                "partial_transcript",
                extra={
                    "session_id": self.session.session_id if self.session else None,
                    "text_preview": text[:50] if text else "",
                    "text_length": len(text) if text else 0,
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "duration": round(end - start, 3),
                },
            )

        with self._callback_lock:
            callback = self._on_partial
        if callback and not self._stop_event.is_set():
            callback(text, start, end)

    def _handle_segment(self, segment: TranscriptSegment) -> None:
        if self.session is None or self.writer is None:
            return

        handle_start = time.perf_counter()

        self.session.segments.append(segment)
        self._apply_overlap_dedupe(segment)

        if segment.suppressed:
            self.session.suppressed_segments.append(segment)

        self.session.health.last_transcript_at = utc_now()
        self.writer.append_segment(segment)

        self._outputs_dirty = True
        self._rebuild_outputs_incremental()

        with self._callback_lock:
            callback = self._on_segment
        if callback:
            callback(segment)

        self._emit_health()
        self._emit_state()

        if self.logger:
            latency_ms = (time.perf_counter() - handle_start) * 1000
            self.logger.debug(
                "segment_processed",
                extra={
                    "session_id": self.session.session_id,
                    "segment_index": len(self.session.segments) - 1,
                    "text_preview": segment.display_text[:80] if segment.display_text else "",
                    "text_length": len(segment.display_text) if segment.display_text else 0,
                    "start": round(segment.start, 3),
                    "end": round(segment.end, 3),
                    "duration": round(segment.end - segment.start, 3),
                    "confidence": round(segment.confidence, 3),
                    "suppressed": segment.suppressed,
                    "latency_ms": round(latency_ms, 2),
                },
            )

    def _apply_overlap_dedupe(self, segment: TranscriptSegment) -> None:
        if self.session is None or segment.suppressed:
            return
        normalized = _normalize_transcript_text(segment.display_text)
        if not normalized:
            return

        duplicates = 0
        for previous in reversed(self.session.segments[:-1]):
            if previous.suppressed:
                continue
            if (segment.start - previous.start) > 10.0:
                break
            if _normalize_transcript_text(previous.display_text) == normalized:
                duplicates += 1
                if duplicates >= 1:
                    segment.suppressed = True
                    segment.quality_label = "junk" if segment.confidence < 0.55 else "weak"
                    segment.suppression_reasons = sorted(
                        set([*segment.suppression_reasons, "overlap-duplicate"])
                    )
                    segment.review_flag = True
                    segment.review_reasons = sorted(
                        set([*segment.review_reasons, "overlap-duplicate"])
                    )
                    return

    def _rebuild_outputs(self, *, force: bool = False) -> None:
        if self.session is None or self.writer is None:
            return
        if not force and not self._outputs_dirty:
            return
        visible_segments = [segment for segment in self.session.segments if not segment.suppressed]
        bundle = self.note_processor.build(visible_segments)
        self.session.formulas = bundle.formulas
        self.session.needs_review = bundle.needs_review
        self.writer.write_outputs(
            notes_markdown=bundle.notes_markdown,
            formulas=bundle.formulas,
            highlights_text=bundle.highlights_text,
        )
        self._last_rebuild_at = time.monotonic()
        self._outputs_dirty = False
        self._last_processed_segment_index = len(self.session.segments) - 1

    def _rebuild_outputs_incremental(self) -> None:
        if self.session is None or self.writer is None:
            return
        if self._last_processed_segment_index < 0:
            self._rebuild_outputs(force=True)
            return

        new_segments = []
        for i, segment in enumerate(self.session.segments):
            if i > self._last_processed_segment_index and not segment.suppressed:
                new_segments.append(segment)

        if not new_segments:
            return

        bundle = self.note_processor.build_incremental(
            existing_segments=[
                s
                for s in self.session.segments[: self._last_processed_segment_index + 1]
                if not s.suppressed
            ],
            new_segments=new_segments,
            existing_formulas=self.session.formulas,
            existing_needs_review=self.session.needs_review,
        )

        self.session.formulas = bundle.formulas
        self.session.needs_review = bundle.needs_review
        self.writer.write_outputs(
            notes_markdown=bundle.notes_markdown,
            formulas=bundle.formulas,
            highlights_text=bundle.highlights_text,
        )
        self._last_rebuild_at = time.monotonic()
        self._outputs_dirty = False
        self._last_processed_segment_index = len(self.session.segments) - 1

    def _maybe_rebuild_outputs(self) -> None:
        if not self._outputs_dirty:
            return
        if (time.monotonic() - self._last_rebuild_at) < self.settings.output_refresh_seconds:
            return
        self._rebuild_outputs(force=True)

    def _handle_health(self, health: SessionHealth) -> None:
        with self._session_lock:
            session = self.session
        if session is None:
            with self._callback_lock:
                callback = self._on_health
            if callback:
                callback(health, 0.0)
            return
        session.health.gpu_mode = health.gpu_mode
        session.health.execution_mode = health.execution_mode
        session.health.model_runtime_device = health.model_runtime_device
        session.health.last_transcript_at = health.last_transcript_at
        session.health.queue_depth = health.queue_depth
        session.health.dropped_stt_chunks = health.dropped_stt_chunks
        session.health.stt_backpressure_state = health.stt_backpressure_state
        session.health.estimated_backlog_seconds = health.estimated_backlog_seconds
        session.health.last_error = health.last_error
        session.health.last_warning = health.last_warning
        if self.audio_source:
            session.health.audio_backend = self.audio_source.backend_name
            session.health.audio_backend_fallbacks = list(self.audio_source.backend_fallbacks)
        self._emit_health()

    def _emit_health(self) -> None:
        with self._session_lock:
            session = self.session
        if session is None:
            return
        if self.audio_source:
            session.health.dropped_frames = self.audio_source.dropped_frames
            session.health.audio_backend = self.audio_source.backend_name
            session.health.audio_backend_fallbacks = list(self.audio_source.backend_fallbacks)
            meter_value = self.meter.update(self.audio_source.level_rms)
        else:
            meter_value = 0.0
        with self._pending_lock:
            pending = self._pending_chunks
        with self._callback_lock:
            callback = self._on_health
        if callback:
            callback(session.health, meter_value)

        if self.logger:
            self._loop_counter += 1
            now = time.monotonic()
            if now - self._last_loop_log >= 5.0:
                self.logger.debug(
                    "health_status",
                    extra={
                        "session_id": session.session_id,
                        "status": session.status,
                        "model_name": session.model_name,
                        "language_mode": session.language_mode,
                        "live_mode": session.live_mode,
                        "execution_mode": session.health.execution_mode,
                        "gpu_mode": session.health.gpu_mode,
                        "audio_active": session.health.audio_stream_active,
                        "dropped_frames": session.health.dropped_frames,
                        "audio_backend": session.health.audio_backend,
                        "pending_chunks": pending,
                        "total_segments": len(session.segments),
                        "meter_value": round(meter_value, 3),
                    },
                )
                self._last_loop_log = now
                self._loop_counter = 0

    def _emit_state(self) -> None:
        with self._session_lock:
            session = self.session
        if session:
            with self._callback_lock:
                callback = self._on_state
            if callback:
                callback(session)

    def _handle_error(self, exc: Exception) -> None:
        error_message = str(exc)
        error_type = "runtime"

        if "audio" in error_message.lower() or "device" in error_message.lower():
            error_type = "audio_device"
        elif (
            "cuda" in error_message.lower()
            or "gpu" in error_message.lower()
            or "cublas" in error_message.lower()
        ):
            error_type = "gpu_runtime"

        if self.logger:
            self.logger.exception(
                "runtime_error",
                extra={
                    "session_id": self.session.session_id if self.session else None,
                    "error_type": error_type,
                    "error": error_message,
                    "session_status": self.session.status if self.session else None,
                },
            )

        if self.session:
            self.session.health.last_error = error_message
            self.session.status = "error"
            self.session.health.audio_stream_active = False
            self.session.health.audio_device_error = (
                error_message if error_type == "audio_device" else None
            )
            if self.audio_source:
                self.session.health.audio_backend = self.audio_source.backend_name
                self.session.health.audio_backend_fallbacks = list(
                    self.audio_source.backend_fallbacks
                )

            if error_type == "audio_device":
                self.session.health.last_warning = (
                    f"Audio device error: {error_message}. "
                    "Session artifacts preserved. Reconnect the device to resume."
                )
            elif error_type == "gpu_runtime":
                self.session.health.last_warning = (
                    f"GPU runtime error: {error_message}. "
                    "Session artifacts preserved. Check CUDA installation or switch to CPU mode."
                )

            if self.writer:
                self.writer.write_metadata()
                self.writer.append_note(
                    f"\n\n[Runtime Error - {error_type.upper()}]\n{error_message}\n"
                )

            self._rebuild_outputs(force=True)
            self._emit_health()
            self._emit_state()

    def _get_language_warning(self, language_mode: str) -> str | None:
        if language_mode == "auto":
            return "Auto language detection may increase latency. Using optimized path for Hindi/English."
        if language_mode in ("hi", "hin"):
            return "Hindi mode active. Using optimized transcription parameters."
        return None


def slugify(text: str) -> str:
    lowered = "".join(character.lower() if character.isalnum() else "-" for character in text)
    parts = [part for part in lowered.split("-") if part]
    return "-".join(parts) or f"session-{int(time.time())}"


def _normalize_transcript_text(text: str) -> str:
    return " ".join(
        "".join(
            character.lower() if character.isalnum() or character.isspace() else " "
            for character in text
        ).split()
    )
