from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from app.audio.capture import LoopbackAudioSource
from app.core.config import AppSettings
from app.core.models import (
    AudioDeviceInfo,
    FormulaFinding,
    SessionHealth,
    SessionState,
    TranscriptSegment,
)
from app.core.session_manager import SessionManager


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

    def list_devices(self) -> list[dict[str, Any]]:
        return [serialize_device(device) for device in self.manager.list_devices()]

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
                available_models=["tiny", "base", "small", "medium", "large-v3"],
                available_languages=["auto", "hi", "en"],
                available_live_modes=["realtime", "low_latency", "balanced", "high_accuracy"],
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

        with self._model_cache_lock:
            if model_name in self._model_cache:
                entry = self._model_cache[model_name]
                return {
                    "status": "cached",
                    "model_name": model_name,
                    "gpu_mode": entry.gpu_mode,
                    "runtime_device": entry.runtime_device,
                }

        # Cancel any existing preload
        if self._preload_thread and self._preload_thread.is_alive():
            self._preload_cancelled.set()
            self._preload_thread.join(timeout=1)

        self._preload_cancelled.clear()

        def _load():
            import time

            def emit_progress(progress: float, message: str, stage: str):
                self._publish_event(
                    "preload_progress",
                    {
                        "model_name": model_name,
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

                # Phase 1: Downloading (0-30%)
                emit_progress(0.0, f"Downloading {model_name} model...", "downloading")
                for i in range(5):
                    if self._preload_cancelled.is_set():
                        return
                    time.sleep(0.4)
                    progress = 0.05 * (i + 1)
                    emit_progress(progress, f"Downloading {model_name} model...", "downloading")

                if self._preload_cancelled.is_set():
                    return

                emit_progress(0.30, f"Loading {model_name} into memory...", "loading")

                # Phase 2: Loading (30-70%)
                # Start model loading in background while emitting progress
                model_future = None
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
                                    model_name,
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
                                        f"Failed to load model {model_name} after {max_retries} attempts: {last_error}"
                                    ) from last_error

                    model_future = executor.submit(load_model_with_retry)

                    # Emit progress while loading
                    for i in range(8):
                        if self._preload_cancelled.is_set():
                            executor.shutdown(wait=False)
                            return
                        time.sleep(0.3)
                        progress = 0.30 + 0.05 * (i + 1)
                        emit_progress(progress, f"Loading {model_name} into memory...", "loading")

                    model = model_future.result(timeout=30)
                    executor.shutdown()
                except Exception as load_exc:
                    emit_progress(0.0, f"Failed to load {model_name}: {load_exc}", "error")
                    return

                if self._preload_cancelled.is_set():
                    del model
                    return

                # Phase 3: Warming (70-100%)
                emit_progress(0.70, "Warming up model...", "warming")

                # Warm-up with progress
                import numpy as np

                dummy_audio = np.zeros(16000, dtype=np.float32)

                for i in range(5):
                    if self._preload_cancelled.is_set():
                        del model
                        return
                    time.sleep(0.2)
                    progress = 0.70 + 0.06 * (i + 1)
                    emit_progress(progress, "Warming up model...", "warming")

                segments, _ = model.transcribe(dummy_audio, language="en", beam_size=1)
                list(segments)

                if self._preload_cancelled.is_set():
                    del model
                    return

                with self._model_cache_lock:
                    self._model_cache[model_name] = ModelCacheEntry(
                        model_name=model_name,
                        model=model,
                        gpu_mode=gpu_mode,
                        runtime_device=runtime_device,
                        loaded_at=time.time(),
                    )

                emit_progress(
                    1.0,
                    f"{model_name} ready",
                    "complete",
                )

            except Exception as exc:
                emit_progress(0.0, f"Failed to load {model_name}: {exc}", "error")

        self._preload_thread = threading.Thread(
            target=_load, name=f"preload-{model_name}", daemon=True
        )
        self._preload_thread.start()

        return {
            "status": "loading",
            "model_name": model_name,
            "message": f"Loading {model_name} in background...",
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
        with self._lock:
            self._loading = True
            self._loading_message = f"Loading model {model_name}..."
            self._revision += 1
        self._publish_event("loading", {"loading": True, "message": self._loading_message})
        try:
            session = self.manager.start_session(
                title=title,
                output_root=Path(output_root),
                model_name=model_name,
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
            self._publish_event("loading", {"loading": False, "message": ""})
            return self._session_state
        except Exception:
            with self._lock:
                self._loading = False
                self._loading_message = ""
                self._revision += 1
            self._publish_event("loading", {"loading": False, "message": ""})
            raise

    def stop_session(self) -> dict[str, Any] | None:
        self.manager.stop_session()
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
        result = LoopbackAudioSource.probe_device(
            device_id=device_id,
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
            duration=duration,
            output_dir=output_dir,
        )
        return result.to_dict()

    def _on_segment(self, segment: TranscriptSegment) -> None:
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
        event_type = "suppressed_segment" if segment.suppressed else "segment"
        self._publish_event(event_type, serialize_segment(segment))

    def _on_partial(self, text: str, start: float, end: float) -> None:
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
            except Exception:
                continue


def serialize_device(device: AudioDeviceInfo) -> dict[str, Any]:
    return {
        "id": device.id,
        "name": device.name,
        "kind": device.kind,
        "is_loopback": device.is_loopback,
        "channels": device.channels,
        "sample_rate": device.sample_rate,
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
