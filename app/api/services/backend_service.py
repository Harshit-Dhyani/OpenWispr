from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from app.api.services.model_service import ModelService
from app.api.services.refinement_queue import RefinementQueue
from app.api.services.streaming_metrics import StreamingMetrics
from app.audio.capture import LoopbackAudioSource
from app.core.language_profiles import available_language_codes
from app.core.model_catalog import MODEL_CATALOG, get_model_catalog_entry, runtime_name_for_model
from app.core.models import (
    AudioDeviceInfo,
    FormulaFinding,
    SessionHealth,
    SessionState,
    TranscriptSegment,
)
from app.core.session_manager import SessionManager
from app.core.settings.config import AppSettings
from app.core.settings.manager import get_settings_manager
from app.stt.stability import PartialStabilizer, build_stream_payload

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ModelCacheEntry:
    model_name: str
    model: Any
    gpu_mode: str
    runtime_device: str
    loaded_at: float


@dataclass(slots=True)
class BackendSnapshot:
    session: dict[str, Any] | None
    transcript: list[dict[str, Any]]
    suppressed_transcript: list[dict[str, Any]]
    formulas: list[dict[str, Any]]
    needs_review: list[dict[str, Any]]
    health: dict[str, Any]
    meter_value: float
    available_models: list[str]
    available_languages: list[str]
    available_live_modes: list[str]
    available_execution_modes: list[str]
    runtime_revision: int
    loading: bool
    loading_message: str
    model_cache: dict[str, Any]


class BackendService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.manager = SessionManager(settings)
        self.manager.set_callbacks(
            on_segment=self._on_segment,
            on_partial=self._on_partial,
            on_health=self._on_health,
            on_state=self._on_state,
        )
        self._lock = Lock()
        self._meter_value = 0.0
        self._health = SessionHealth().to_dict()
        self._session_state: dict[str, Any] | None = None
        self._transcript: list[dict[str, Any]] = []
        self._suppressed_transcript: list[dict[str, Any]] = []
        self._formulas: list[dict[str, Any]] = []
        self._needs_review: list[dict[str, Any]] = []
        self._revision = 0
        self._event_callbacks: list[Callable[[str, dict[str, Any]], None]] = []
        self._event_lock = Lock()
        self._loading = False
        self._loading_message = ""
        # Model cache for preloading
        self._model_cache: dict[str, ModelCacheEntry] = {}
        self._model_cache_lock = Lock()
        self._preload_thread: threading.Thread | None = None
        self._preload_cancelled = threading.Event()
        self._model_service = ModelService(settings.download_root)
        self._streaming_metrics = StreamingMetrics()
        self._stabilizer: PartialStabilizer | None = None
        self._refinement_queue = RefinementQueue(
            download_root=settings.download_root,
            publish_event=self._publish_event,
            metrics=self._streaming_metrics,
        )

    def list_devices(self) -> list[dict[str, Any]]:
        return [serialize_device(device) for device in self.manager.list_devices()]

    def get_streaming_metrics(self) -> dict[str, object]:
        return self._streaming_metrics.snapshot()

    def get_snapshot(self) -> BackendSnapshot:
        with self._lock:
            with self._model_cache_lock:
                cache_info = {
                    model_name: {
                        "gpu_mode": entry.gpu_mode,
                        "runtime_device": entry.runtime_device,
                        "loaded_at": entry.loaded_at,
                    }
                    for model_name, entry in self._model_cache.items()
                }
            return BackendSnapshot(
                session=self._session_state,
                transcript=list(self._transcript),
                suppressed_transcript=list(self._suppressed_transcript),
                formulas=list(self._formulas),
                needs_review=list(self._needs_review),
                health=dict(self._health),
                meter_value=self._meter_value,
                available_models=[
                    entry.runtime_model_name
                    for entry in MODEL_CATALOG
                    if entry.category == "asr"
                    and entry.enabled_runtime
                    and entry.runtime_model_name
                ],
                available_languages=available_language_codes(),
                available_live_modes=[
                    "ultra",
                    "realtime",
                    "low_latency",
                    "balanced",
                    "high_accuracy",
                ],
                available_execution_modes=["auto", "gpu_only", "cpu_only"],
                runtime_revision=self._revision,
                loading=self._loading,
                loading_message=self._loading_message,
                model_cache=cache_info,
            )

    def get_snapshot_payload(self) -> dict[str, Any]:
        snapshot = self.get_snapshot()
        return {
            "session": snapshot.session,
            "transcript": snapshot.transcript[-500:],
            "suppressed_transcript": snapshot.suppressed_transcript[-200:],
            "formulas": snapshot.formulas[-200:],
            "needs_review": snapshot.needs_review[-200:],
            "health": snapshot.health,
            "meter_value": snapshot.meter_value,
            "available_models": snapshot.available_models,
            "available_languages": snapshot.available_languages,
            "available_live_modes": snapshot.available_live_modes,
            "available_execution_modes": snapshot.available_execution_modes,
            "runtime_revision": snapshot.runtime_revision,
            "loading": snapshot.loading,
            "loading_message": snapshot.loading_message,
            "model_cache": snapshot.model_cache,
        }

    def get_model_catalog_payload(self) -> dict[str, Any]:
        return self._model_service.get_catalog_payload(get_settings_manager().get_settings())

    def get_model_install_state(self) -> list[dict[str, Any]]:
        return self._model_service.get_installed_state()

    def get_cached_model(self, model_name: str) -> ModelCacheEntry | None:
        """Get a cached model if available."""
        with self._model_cache_lock:
            return self._model_cache.get(model_name)

    def is_model_cached(self, model_name: str) -> bool:
        """Check if a model is cached."""
        with self._model_cache_lock:
            return model_name in self._model_cache

    def preload_model(
        self,
        model_name: str,
        execution_mode: str = "auto",
    ) -> dict[str, Any]:
        """Preload a model into cache for instant session start.

        Returns immediately if model is already cached.
        Runs loading in background thread to avoid blocking.
        """
        import time

        runtime_model_name = runtime_name_for_model(model_name) or model_name

        with self._model_cache_lock:
            if runtime_model_name in self._model_cache:
                entry = self._model_cache[runtime_model_name]
                return {
                    "status": "cached",
                    "model_name": runtime_model_name,
                    "model_id": model_name if get_model_catalog_entry(model_name) else None,
                    "gpu_mode": entry.gpu_mode,
                    "runtime_device": entry.runtime_device,
                }

        # Cancel any existing preload
        if self._preload_thread and self._preload_thread.is_alive():
            self._preload_cancelled.set()
            self._preload_thread.join(timeout=1)

        self._preload_cancelled.clear()

        def _load():

            def emit_progress(progress: float, message: str, stage: str):
                self._publish_event(
                    "preload_progress",
                    {
                        "model_name": runtime_model_name,
                        "model_id": model_name if get_model_catalog_entry(model_name) else None,
                        "stage": stage,
                        "progress": progress,
                        "message": message,
                    },
                )

            try:
                # Import here to avoid circular dependencies
                from faster_whisper import WhisperModel

                device = self.settings.device
                compute_type = self.settings.compute_type

                # Determine device based on execution mode
                runtime_device = device
                gpu_mode = "unknown"

                if execution_mode == "cpu_only":
                    runtime_device = "cpu"
                    compute_type = "int8"
                    gpu_mode = "cpu/int8"
                else:
                    # Check GPU availability
                    try:
                        import torch

                        if torch.cuda.is_available():
                            runtime_device = "cuda"
                            gpu_mode = f"cuda/{compute_type}"
                        else:
                            runtime_device = "cpu"
                            compute_type = "int8"
                            gpu_mode = "cpu/int8"
                    except ImportError:
                        runtime_device = "cpu"
                        compute_type = "int8"
                        gpu_mode = "cpu/int8"

                # Phase 1: Preparing model
                emit_progress(0.0, f"Preparing {runtime_model_name} model...", "preparing")

                if self._preload_cancelled.is_set():
                    return

                # Phase 2: Loading model into memory
                # Start model loading in background
                model_future = None
                executor = None
                try:
                    from concurrent.futures import ThreadPoolExecutor

                    executor = ThreadPoolExecutor(max_workers=1)

                    # Always use int8 for minimal GPU memory
                    compute_type = "int8"

                    def load_model_with_retry():
                        max_retries = 3
                        last_error = None
                        for attempt in range(max_retries):
                            try:
                                return WhisperModel(
                                    runtime_model_name,
                                    device=runtime_device,
                                    compute_type=compute_type,
                                    download_root=str(self.settings.download_root),
                                )
                            except Exception as e:
                                last_error = e
                                if attempt < max_retries - 1:
                                    emit_progress(
                                        0.30 + 0.05 * attempt,
                                        f"Retrying load (attempt {attempt + 2})...",
                                        "loading",
                                    )
                                    time.sleep(0.5)
                                else:
                                    raise RuntimeError(
                                        f"Failed to load model {runtime_model_name} after {max_retries} attempts: {last_error}"
                                    ) from last_error

                    model_future = executor.submit(load_model_with_retry)

                    # Wait for model to load (real progress happens in background thread)
                    model = model_future.result(timeout=30)
                except Exception as load_exc:
                    emit_progress(0.0, f"Failed to load {runtime_model_name}: {load_exc}", "error")
                    return
                finally:
                    if executor is not None:
                        executor.shutdown(wait=False)

                if self._preload_cancelled.is_set():
                    del model
                    return

                # Phase 3: Warming up model
                emit_progress(0.8, "Warming up model...", "warming")

                import numpy as np

                dummy_audio = np.zeros(16000, dtype=np.float32)

                # Run warmup transcription
                if self._preload_cancelled.is_set():
                    del model
                    return

                segments, _ = model.transcribe(dummy_audio, language="en", beam_size=1)
                list(segments)

                if self._preload_cancelled.is_set():
                    del model
                    return

                with self._model_cache_lock:
                    self._model_cache[runtime_model_name] = ModelCacheEntry(
                        model_name=runtime_model_name,
                        model=model,
                        gpu_mode=gpu_mode,
                        runtime_device=runtime_device,
                        loaded_at=time.time(),
                    )

                emit_progress(
                    1.0,
                    f"{runtime_model_name} ready",
                    "complete",
                )

            except Exception as exc:
                emit_progress(0.0, f"Failed to load {runtime_model_name}: {exc}", "error")

        self._preload_thread = threading.Thread(
            target=_load, name=f"preload-{runtime_model_name}", daemon=True
        )
        self._preload_thread.start()

        return {
            "status": "loading",
            "model_name": runtime_model_name,
            "model_id": model_name if get_model_catalog_entry(model_name) else None,
            "message": f"Loading {runtime_model_name} in background...",
        }

    def clear_model_cache(self) -> dict[str, Any]:
        """Clear all cached models to free memory."""
        with self._model_cache_lock:
            cleared = list(self._model_cache.keys())
            # Release model references
            for entry in self._model_cache.values():
                del entry.model
            self._model_cache.clear()

        return {"status": "cleared", "models": cleared}

    def start_session(
        self,
        *,
        title: str,
        output_root: str,
        model_name: str,
        language_mode: str,
        device_id: str | None,
        live_mode: str,
        execution_mode: str,
        vad_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        runtime_model_name = runtime_name_for_model(model_name) or model_name
        with self._lock:
            self._loading = True
            self._loading_message = f"Loading model {runtime_model_name}..."
            self._revision += 1
        self._publish_event("loading", {"loading": True, "message": self._loading_message})
        try:
            session = self.manager.start_session(
                title=title,
                output_root=Path(output_root),
                model_name=runtime_model_name,
                language_mode=language_mode,
                device_id=device_id,
                live_mode=live_mode,
                execution_mode=execution_mode,
                vad_params=vad_params,
            )
            with self._lock:
                self._session_state = serialize_session(session)
                self._transcript = [
                    serialize_segment(segment)
                    for segment in session.segments
                    if not segment.suppressed
                ]
                self._suppressed_transcript = [
                    serialize_segment(segment) for segment in session.suppressed_segments
                ]
                self._formulas = [serialize_formula(formula) for formula in session.formulas]
                self._needs_review = [
                    serialize_segment(segment) for segment in session.needs_review
                ]
                self._loading = False
                self._loading_message = ""
                self._revision += 1
            self._stabilizer = PartialStabilizer(
                session_id=session.session_id,
                stability_threshold=2 if live_mode in ("realtime", "low_latency") else 3,
            )
            self._publish_event("loading", {"loading": False, "message": ""})
            return self._session_state
        except Exception as exc:
            logger.error(f"Session start failed: {exc}")
            with self._lock:
                self._loading = False
                self._loading_message = ""
                self._revision += 1
            self._publish_event("loading", {"loading": False, "message": ""})
            raise

    def stop_session(self) -> dict[str, Any] | None:
        self.manager.stop_session()
        if self._stabilizer is not None:
            self._stabilizer.reset()
        with self._lock:
            return self._session_state

    def attach_pdf(self, path: str) -> dict[str, Any] | None:
        self.manager.attach_pdf(path)
        with self._lock:
            return self._session_state

    def probe_device(self, device_id: str | None, duration: float = 3.0) -> dict[str, Any]:
        """Probe a device to check if it's working and capture audio stats."""
        output_dir = (
            self.manager.session.output_dir / "debug"
            if self.manager.session is not None
            else Path.cwd() / "sessions" / "_device-probes"
        )
        try:
            result = LoopbackAudioSource.probe_device(
                device_id=device_id,
                sample_rate=self.settings.sample_rate,
                channels=self.settings.channels,
                duration=duration,
                output_dir=output_dir,
                audio_backend=self.settings.audio_backend,
            )
            payload = result.to_dict()
            payload["ok"] = True
            return payload
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "device_id": device_id or "default",
                "duration": duration,
                "backend": self.settings.audio_backend,
            }

    def _on_segment(self, segment: TranscriptSegment) -> None:
        emit_started = time.perf_counter()
        with self._lock:
            target = self._suppressed_transcript if segment.suppressed else self._transcript
            target.append(serialize_segment(segment))
            if self._session_state is not None:
                if segment.suppressed:
                    self._session_state["suppressed_count"] = len(self._suppressed_transcript)
                else:
                    self._session_state["segment_count"] = len(self._transcript)
                self._session_state["formula_count"] = len(self._formulas)
                self._session_state["review_count"] = len(self._needs_review)
            self._revision += 1
            session_id = self._session_state["session_id"] if self._session_state else "unknown"
        event_type = "suppressed_segment" if segment.suppressed else "segment"
        serialized = serialize_segment(segment)
        self._publish_event(event_type, serialized)
        if self._stabilizer is not None and not segment.suppressed:
            draft_state = self._stabilizer.consume_final_text(
                serialized["display_text"] or serialized["text"],
                start=serialized["start"],
                end=serialized["end"],
            )
            commit_payload = build_stream_payload(
                session_id=session_id,
                segment_id=serialized["id"],
                revision=draft_state.revision,
                stream_id=draft_state.stream_id,
                text=serialized["display_text"] or serialized["text"],
                start=serialized["start"],
                end=serialized["end"],
                committed_text=draft_state.committed_text,
                draft_suffix="",
                metrics={"emit_ms": round((time.perf_counter() - emit_started) * 1000, 2)},
            )
            commit_payload["segment"] = serialized
            self._publish_event("commit_final", commit_payload)
            self._streaming_metrics.record_commit(commit_payload["metrics"]["emit_ms"])
            self._streaming_metrics.log_trace(
                session_id=session_id,
                segment_id=serialized["id"],
                stage="commit",
                duration_ms=commit_payload["metrics"]["emit_ms"],
                extra=f"device={self._health.get('model_runtime_device', 'unknown')}",
            )
            user_settings = get_settings_manager().get_settings()
            self._refinement_queue.enqueue(
                session_id=session_id,
                segment=serialized,
                refinement_mode=user_settings.transcription.refinement_mode,
                refinement_profile=getattr(
                    user_settings.transcription, "refinement_profile", "raw"
                ),
                model_id=user_settings.refiner.selected_model_id,
                runtime_enabled=user_settings.refiner.runtime_enabled,
                language_hint=serialized["language"] or "auto",
            )

    def _on_partial(self, text: str, start: float, end: float) -> None:
        emit_started = time.perf_counter()
        segment = {
            "id": f"partial-{int(start * 1000)}-{int(end * 1000)}",
            "start": start,
            "end": end,
            "text": text,
            "display_text": text,
            "language": "auto",
            "confidence": 0.0,
            "review_flag": False,
            "review_reasons": [],
            "suppressed": False,
            "suppression_reasons": [],
            "quality_label": "weak",
            "script_mismatch": False,
            "is_partial": True,
        }
        self._publish_event("segment", segment)
        if self._stabilizer is None:
            return
        session_id = self._session_state["session_id"] if self._session_state else "unknown"
        draft_state = self._stabilizer.push(text, start=start, end=end)
        emit_ms = round((time.perf_counter() - emit_started) * 1000, 2)
        payload = build_stream_payload(
            session_id=session_id,
            segment_id=segment["id"],
            revision=draft_state.revision,
            stream_id=draft_state.stream_id,
            text=draft_state.text,
            start=start,
            end=end,
            committed_text=draft_state.committed_text,
            draft_suffix=draft_state.draft_suffix,
            metrics={"emit_ms": emit_ms},
        )
        self._publish_event("draft_partial", payload)
        self._streaming_metrics.record_draft(emit_ms)

    def _on_health(self, health: SessionHealth, meter_value: float) -> None:
        with self._lock:
            self._health = health.to_dict()
            self._meter_value = meter_value
            self._revision += 1
        self._publish_event("health", {"health": self._health, "meter_value": meter_value})

    def _on_state(self, state: SessionState) -> None:
        with self._lock:
            self._session_state = serialize_session(state)
            self._transcript = [
                serialize_segment(segment) for segment in state.segments if not segment.suppressed
            ]
            self._suppressed_transcript = [
                serialize_segment(segment) for segment in state.suppressed_segments
            ]
            self._formulas = [serialize_formula(formula) for formula in state.formulas]
            self._needs_review = [serialize_segment(segment) for segment in state.needs_review]
            self._revision += 1
        self._publish_event("state", self.get_snapshot_payload())
        self._publish_event("formulas", self._formulas)

    def register_event_callback(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        with self._event_lock:
            if callback not in self._event_callbacks:
                self._event_callbacks.append(callback)

    def unregister_event_callback(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        with self._event_lock:
            if callback in self._event_callbacks:
                self._event_callbacks.remove(callback)

    def _publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        with self._event_lock:
            callbacks = list(self._event_callbacks)
        for callback in callbacks:
            try:
                callback(event_type, data)
            except Exception as exc:
                logger.debug(f"Event callback failed for {event_type}: {exc}")
                continue


def serialize_device(device: AudioDeviceInfo) -> dict[str, Any]:
    return {
        "id": device.id,
        "name": device.name,
        "kind": device.kind,
        "is_loopback": device.is_loopback,
        "channels": device.channels,
        "sample_rate": device.sample_rate,
        "backend_candidates": list(device.backend_candidates),
        "is_input": device.is_input,
        "is_output": device.is_output,
        "supports_loopback": device.supports_loopback,
        "driver": device.driver,
    }


def serialize_segment(segment: TranscriptSegment) -> dict[str, Any]:
    return segment.to_dict()


def serialize_formula(formula: FormulaFinding) -> dict[str, Any]:
    return formula.to_dict()


def serialize_health(health: SessionHealth) -> dict[str, Any]:
    return health.to_dict()


def serialize_session(state: SessionState) -> dict[str, Any]:
    payload = state.to_metadata_dict()
    payload["segments"] = [serialize_segment(segment) for segment in state.segments]
    payload["suppressed_segments"] = [
        serialize_segment(segment) for segment in state.suppressed_segments
    ]
    payload["formulas"] = [serialize_formula(formula) for formula in state.formulas]
    payload["needs_review"] = [serialize_segment(segment) for segment in state.needs_review]
    payload["health"] = serialize_health(state.health)
    return payload
