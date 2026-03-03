"""Optimized transcription engine for real-time Hindi/English transcription.

This module provides backward-compatible API while using the new optimized
streaming engine and model pool internally.

Targets sub-300ms end-to-end latency with model caching, streaming transcription,
language-specific optimizations, and CUDA stream support.
"""

from __future__ import annotations

import logging
import threading
import time
import warnings
from collections import OrderedDict, deque
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from queue import Empty, Full, Queue
from typing import Any, Literal

import numpy as np

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=UserWarning)

try:
    import torch
    import torch.cuda

    HAS_TORCH = True
except ImportError:
    torch = None
    HAS_TORCH = False

from app.core.models import SessionHealth, TranscriptSegment, utc_now
from app.stt.chunker import AudioChunk
from app.stt.fast_whisper_backend import (
    FastWhisperBackend,
    GPURuntimeError,
    InferenceConfig,
    ModeConfig,
    OptimizedWhisperFactory,
    SYSTEM_MODE,
    WISPR_MODE,
)
from app.stt.model_pool import ModelPool
from app.stt.quality import assess_segment_quality
from app.stt.streaming_engine import (
    AdaptiveBeamController,
    ContextCarryoverManager,
    PartialResult,
    PerformanceMetrics,
)

def _should_fallback_to_cpu(exc: Exception) -> bool:
    """Check if error indicates GPU failure requiring CPU fallback."""
    text = str(exc).lower()
    fallback_keywords = [
        "cublas",
        "cuda",
        "cudnn",
        "gpu",
        "out of memory",
        "curand",
        "cusolver",
        "cusparse",
        "nccl",
        "thrust",
        "device-side assert",
        "an illegal memory access",
        "cuda error",
        "no kernel image",
        "nvidia",
    ]
    return any(kw in text for kw in fallback_keywords)


def confidence_proxy(raw_segment: Any) -> float:
    """Calculate confidence score from segment metadata."""
    avg_logprob = getattr(raw_segment, "avg_logprob", None)
    no_speech_prob = getattr(raw_segment, "no_speech_prob", None)
    compression_ratio = getattr(raw_segment, "compression_ratio", None)

    score = 0.65
    if avg_logprob is not None:
        score += max(min((avg_logprob + 1.2) / 1.2, 0.25), -0.35)
    if no_speech_prob is not None:
        score -= min(max(no_speech_prob, 0.0), 1.0) * 0.25
    if compression_ratio is not None and compression_ratio > 2.2:
        score -= min((compression_ratio - 2.2) * 0.08, 0.2)
    return max(0.0, min(score, 0.99))


@dataclass(slots=True)
class VADConfig:
    """Voice Activity Detection configuration per language."""

    threshold: float = 0.5
    min_silence_duration_ms: int = 200
    speech_pad_ms: int = 200
    min_speech_duration_ms: int = 250
    max_speech_duration_s: float = 30.0


@dataclass(slots=True)
class TranscriptionConfig:
    """Configuration for transcription optimized for minimal latency."""

    temperature: float = 0.0
    beam_size: int = 1
    best_of: int = 1
    patience: float = 1.0
    length_penalty: float = 1.0
    suppress_tokens: list[int] | None = field(default_factory=lambda: [-1])
    initial_prompt: str | None = None
    condition_on_previous_text: bool = False
    fp16: bool = False


@dataclass(slots=True)
class LanguageConfig:
    """Per-language transcription configuration."""

    temperature: float = 0.0
    beam_size: int = 1
    best_of: int = 1
    patience: float = 1.0
    length_penalty: float = 1.0
    compression_ratio_threshold: float = 2.4
    logprob_threshold: float = -1.0
    no_speech_threshold: float = 0.6
    condition_on_previous_text: bool = False
    vad_config: VADConfig = field(default_factory=VADConfig)


class LanguageOptimizer:
    """Language-specific optimizations for Hindi/English transcription."""

    CONFIGS: dict[str, LanguageConfig] = {
        "hi": LanguageConfig(
            temperature=0.3,
            beam_size=3,
            best_of=3,
            patience=1.5,
            length_penalty=1.2,
            compression_ratio_threshold=2.6,
            logprob_threshold=-0.8,
            no_speech_threshold=0.72,
            condition_on_previous_text=True,
            vad_config=VADConfig(
                threshold=0.35,
                min_silence_duration_ms=350,
                speech_pad_ms=260,
                min_speech_duration_ms=350,
                max_speech_duration_s=20.0,
            ),
        ),
        "en": LanguageConfig(
            temperature=0.0,
            beam_size=1,
            best_of=1,
            patience=1.0,
            length_penalty=1.0,
            compression_ratio_threshold=2.2,
            logprob_threshold=-1.2,
            no_speech_threshold=0.78,
            condition_on_previous_text=False,
            vad_config=VADConfig(
                threshold=0.38,
                min_silence_duration_ms=380,
                speech_pad_ms=260,
                min_speech_duration_ms=350,
                max_speech_duration_s=25.0,
            ),
        ),
        "auto": LanguageConfig(
            temperature=0.15,
            beam_size=2,
            best_of=2,
            patience=1.2,
            length_penalty=1.0,
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.75,
            condition_on_previous_text=True,
            vad_config=VADConfig(
                threshold=0.36,
                min_silence_duration_ms=360,
                speech_pad_ms=260,
                min_speech_duration_ms=350,
                max_speech_duration_s=20.0,
            ),
        ),
    }

    MAX_CACHE_SIZE = 500

    def __init__(self) -> None:
        self._lang_cache: OrderedDict[str, str] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_hits = 0
        self._cache_misses = 0

    def get_config(self, language: str) -> LanguageConfig:
        """Get optimized config for language."""
        return self.CONFIGS.get(language, self.CONFIGS["auto"])

    def detect_language(self, audio: np.ndarray, model: Any) -> str:
        """Fast language detection with caching."""
        fingerprint = self._audio_fingerprint(audio)

        with self._cache_lock:
            if fingerprint in self._lang_cache:
                self._cache_hits += 1
                self._lang_cache.move_to_end(fingerprint)
                return self._lang_cache[fingerprint]
            self._cache_misses += 1

        try:
            from faster_whisper import WhisperModel

            if isinstance(model, WhisperModel):
                segments, info = model.transcribe(
                    audio[:16000],
                    language=None,
                    beam_size=1,
                    best_of=1,
                    temperature=0.0,
                    vad_filter=True,
                    vad_parameters={"threshold": 0.5, "min_silence_duration_ms": 100},
                )
                list(segments)  # Consume generator
                detected = getattr(info, "language", "auto")
            else:
                detected = "auto"
        except Exception as e:
            logger.warning(f"Language detection failed: {e}, falling back to 'auto'")
            detected = "auto"

        with self._cache_lock:
            self._lang_cache[fingerprint] = detected
            while len(self._lang_cache) > self.MAX_CACHE_SIZE:
                self._lang_cache.popitem(last=False)

        return detected

    def _audio_fingerprint(self, audio: np.ndarray) -> str:
        """Generate a quick fingerprint for audio caching."""
        samples = min(len(audio), 200)
        if samples < 100:
            return f"len_{len(audio)}"
        first = audio[:100]
        last = audio[-100:] if len(audio) >= 200 else audio[-samples // 2 :]
        hash_val = hash(first.tobytes() + last.tobytes())
        return f"{hash_val}_{len(audio)}"

    @property
    def cache_stats(self) -> dict[str, int]:
        """Get cache hit/miss statistics."""
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "size": len(self._lang_cache),
        }

    def clear_cache(self) -> None:
        """Clear the language detection cache."""
        with self._cache_lock:
            self._lang_cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0


@dataclass(slots=True)
class SubmitStatus:
    """Detailed status returned from submit() for flow control decisions."""

    accepted: bool
    queue_depth: int
    dropped_chunks: int
    backpressure_state: str
    estimated_backlog_seconds: float
    max_queue_size: int


class FastWhisperBackend:
    """High-performance Whisper backend with streaming and optimizations.

    This class now uses the new optimized components internally while maintaining
    backward compatibility with the existing API.
    """

    def __init__(
        self,
        *,
        model_name: str,
        download_root: str,
        device: str,
        compute_type: str,
        language_mode: str,
        execution_mode: str,
        beam_size: int = 1,
        best_of: int = 1,
        temperature: float = 0.0,
        vad_filter: bool = True,
        max_queue_items: int = 32,
        vad_params: dict[str, Any] | None = None,
        streaming_window_ms: int = 400,
        streaming_overlap_ms: int = 80,
        num_cuda_streams: int = 2,
    ) -> None:
        self.model_name = model_name
        self.download_root = download_root
        self.device = device
        self.compute_type = compute_type
        self.language_mode = language_mode
        self.execution_mode = execution_mode
        self.beam_size = beam_size
        self.best_of = best_of
        self.temperature = temperature
        self.vad_filter = vad_filter
        self.vad_params = vad_params or {}
        self.max_queue_items = max_queue_items
        self.streaming_window_ms = streaming_window_ms
        self.streaming_overlap_ms = streaming_overlap_ms

        # Use the new optimized model pool
        self.model_pool = ModelPool()

        # Language optimizer
        self.language_optimizer = LanguageOptimizer()

        # Determine mode config
        if "tiny" in model_name:
            self._mode_config = WISPR_MODE
        else:
            self._mode_config = SYSTEM_MODE

        # State
        self._backend: FastWhisperBackend | None = None
        self._gpu_mode = "unknown"
        self._runtime_device = "unknown"
        self._warning: str | None = None
        self._dropped_chunks = 0
        self._backpressure_state = "normal"

        # New optimization components
        self._adaptive_beam: AdaptiveBeamController | None = None
        self._context_manager: ContextCarryoverManager | None = None
        if self._mode_config.adaptive_beam:
            self._adaptive_beam = AdaptiveBeamController(
                target_latency_ms=self._mode_config.target_latency_ms,
                min_beam_size=self._mode_config.beam_size,
                max_beam_size=5,
            )
        if self._mode_config.enable_prefix:
            self._context_manager = ContextCarryoverManager()

        # Callbacks
        self._segment_callbacks: list[Callable[[TranscriptSegment], None]] = []
        self._partial_callbacks: list[Callable[..., None]] = []
        self._error_callbacks: list[Callable[[Exception], None]] = []
        self._health_callbacks: list[Callable[[SessionHealth], None]] = []
        self._status_callbacks: list[Callable[[str], None]] = []

        # Threading
        self._queue: Queue[AudioChunk] = Queue(maxsize=max_queue_items)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        # Metrics
        self._processing_times: deque[float] = deque(maxlen=100)
        self._chunks_processed = 0
        self._avg_latency_ms = 0.0
        self._performance_metrics = PerformanceMetrics()

        logger.debug(
            "FastWhisperBackend initialized: "
            f"model_name={model_name}, device={device}, compute_type={compute_type}, "
            f"language_mode={language_mode}, execution_mode={execution_mode}, "
            f"max_queue_items={max_queue_items}"
        )

    def _initialize_backend(self) -> FastWhisperBackend:
        """Initialize the optimized backend."""
        if self._backend is not None:
            return self._backend

        self._publish_status(f"Loading {self.model_name} model...")
        load_start_time = time.perf_counter()

        # Determine device and compute type
        actual_device = self.device
        actual_compute_type = self.compute_type

        if self.execution_mode == "cpu_only" or self.device == "cpu":
            actual_device = "cpu"
            actual_compute_type = "int8"
        elif self.execution_mode == "auto":
            # Check GPU availability
            if HAS_TORCH and torch.cuda.is_available():
                actual_device = "cuda"
            else:
                actual_device = "cpu"
                actual_compute_type = "int8"

        try:
            # Create backend using factory
            self._backend = OptimizedWhisperFactory.create_backend(
                mode="wispr" if "tiny" in self.model_name else "system",
                model_pool=self.model_pool,
                download_root=self.download_root,
                device=actual_device,
                language=self.language_mode if self.language_mode != "auto" else None,
            )

            # Warmup
            if self._backend.warmup():
                self._gpu_mode = f"{actual_device}/{actual_compute_type}"
                self._runtime_device = actual_device

            load_time_ms = (time.perf_counter() - load_start_time) * 1000
            logger.info(
                f"Model loaded: {self.model_name} on {actual_device} ({actual_compute_type}) "
                f"in {load_time_ms:.1f}ms"
            )

            self._publish_status(f"Model loaded ({actual_device.upper()})")
            return self._backend

        except GPURuntimeError as e:
            if self.execution_mode == "gpu_only":
                raise RuntimeError(f"GPU load failed in gpu_only mode: {e}")

            # Fallback to CPU
            self._warning = f"GPU load failed: {e}. Using CPU."
            self._publish_status(self._warning)
            logger.warning(self._warning)

            self._backend = OptimizedWhisperFactory.create_backend(
                mode="wispr" if "tiny" in self.model_name else "system",
                model_pool=self.model_pool,
                download_root=self.download_root,
                device="cpu",
                language=self.language_mode if self.language_mode != "auto" else None,
            )
            self._backend.warmup()

            self._gpu_mode = "cpu/int8"
            self._runtime_device = "cpu"
            self._publish_status("Model loaded (CPU fallback)")
            return self._backend

    def add_segment_callback(self, callback: Callable[[TranscriptSegment], None]) -> None:
        self._segment_callbacks.append(callback)

    def add_partial_callback(self, callback: Callable[..., None]) -> None:
        self._partial_callbacks.append(callback)

    def add_error_callback(self, callback: Callable[[Exception], None]) -> None:
        self._error_callbacks.append(callback)

    def add_health_callback(self, callback: Callable[[SessionHealth], None]) -> None:
        self._health_callbacks.append(callback)

    def add_status_callback(self, callback: Callable[[str], None]) -> None:
        self._status_callbacks.append(callback)

    def _publish_status(self, message: str) -> None:
        for callback in self._status_callbacks:
            callback(message)

    def _publish_partial(self, result: PartialResult) -> None:
        for callback in self._partial_callbacks:
            try:
                callback(result.text, result.start_time, result.end_time)
            except TypeError:
                callback(result)

    def load_model(self) -> Any:
        """Load and return the underlying model."""
        backend = self._initialize_backend()
        return backend.model

    def set_language_mode(self, language_mode: str) -> None:
        self.language_mode = language_mode
        if self._backend:
            self._backend.language = language_mode

    def set_execution_mode(self, execution_mode: str) -> None:
        self.execution_mode = execution_mode

    def set_streaming_profile(
        self,
        *,
        streaming_window_ms: int,
        streaming_overlap_ms: int,
    ) -> None:
        self.streaming_window_ms = max(800, streaming_window_ms)
        self.streaming_overlap_ms = min(
            max(120, streaming_overlap_ms),
            max(120, self.streaming_window_ms - 120),
        )

    def start(self) -> None:
        """Start the transcription worker thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="fast-stt-worker",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the transcription worker thread."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def submit(self, chunk: AudioChunk) -> SubmitStatus:
        """Submit audio chunk for transcription with backpressure handling."""
        chunk_duration = len(chunk.samples) / 16000.0 if hasattr(chunk, "samples") else 0.0
        queue_depth_before = self._queue.qsize()

        if self._stop.is_set():
            return SubmitStatus(
                accepted=False,
                queue_depth=queue_depth_before,
                dropped_chunks=self._dropped_chunks,
                backpressure_state="stopped",
                estimated_backlog_seconds=self._estimate_backlog(),
                max_queue_size=self.max_queue_items,
            )

        try:
            self._queue.put_nowait(chunk)
            self._backpressure_state = "normal"
            accepted = True
        except Full:
            self._dropped_chunks += 1
            self._backpressure_state = "dropping"
            accepted = False

        return SubmitStatus(
            accepted=accepted,
            queue_depth=self._queue.qsize(),
            dropped_chunks=self._dropped_chunks,
            backpressure_state=self._backpressure_state,
            estimated_backlog_seconds=self._estimate_backlog(),
            max_queue_size=self.max_queue_items,
        )

    def _estimate_backlog(self) -> float:
        """Estimate backlog in seconds based on processing history."""
        if not self._processing_times:
            return 0.0
        avg_time = sum(self._processing_times) / len(self._processing_times)
        return avg_time * self._queue.qsize()

    def _run(self) -> None:
        """Main transcription worker loop."""
        try:
            backend = self._initialize_backend()
            self._publish_health(self._health_snapshot())

            while not self._stop.is_set():
                try:
                    chunk = self._queue.get(timeout=0.1)
                except Empty:
                    continue

                start_time = time.perf_counter()

                # Get prefix context if enabled
                prefix = None
                if self._context_manager:
                    prefix = self._context_manager.get_prefix()

                # Get adaptive beam size
                beam_size = self.beam_size
                if self._adaptive_beam:
                    beam_size = self._adaptive_beam.current_beam_size

                try:
                    # Transcribe with optimized settings
                    safe_samples = np.nan_to_num(
                        np.clip(chunk.samples.astype(np.float32, copy=False), -1.0, 1.0),
                        nan=0.0,
                        posinf=1.0,
                        neginf=-1.0,
                    )

                    result = backend.transcribe(
                        safe_samples,
                        language=self.language_mode if self.language_mode != "auto" else None,
                        prefix=prefix,
                    )

                    # Report latency for adaptive beam
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    if self._adaptive_beam:
                        self._adaptive_beam.report_latency(latency_ms)

                    # Update context carryover
                    if self._context_manager and result.text:
                        self._context_manager.update_context(result.text, result.confidence)

                    # Convert to segment
                    partial = PartialResult(
                        text=result.text,
                        is_final=True,
                        is_stable=True,
                        start_time=result.start_time,
                        end_time=result.end_time,
                        language=result.language,
                        confidence=result.confidence,
                        prefix_context=prefix or "",
                        beam_size_used=beam_size,
                        inference_time_ms=latency_ms,
                    )

                    self._publish_partial(partial)
                    segment = self._create_segment(partial, chunk)

                    for callback in self._segment_callbacks:
                        callback(segment)

                    if self._performance_metrics:
                        try:
                            self._performance_metrics.record(latency_ms)
                        except Exception as exc:
                            logger.warning("Failed to record STT metrics: %s", exc)

                except GPURuntimeError:
                    if self.execution_mode != "gpu_only":
                        self._handle_gpu_failure()
                    else:
                        raise

                # Track latency
                latency = time.perf_counter() - start_time
                latency_ms = latency * 1000
                self._processing_times.append(latency)
                self._chunks_processed += 1
                self._avg_latency_ms = (self._avg_latency_ms * 0.9) + (latency_ms * 0.1)

                self._publish_health(self._health_snapshot())

        except Exception as e:
            logger.exception("Worker loop error")
            for callback in self._error_callbacks:
                callback(e)

    def _create_segment(
        self,
        partial: PartialResult,
        chunk: AudioChunk,
    ) -> TranscriptSegment:
        """Convert partial result to transcript segment."""
        quality = assess_segment_quality(
            partial.text,
            confidence=partial.confidence,
            language_mode=self.language_mode,
            detected_language=partial.language,
        )

        return TranscriptSegment(
            id=f"seg-{int(time.time() * 1000)}-{hash(partial.text) & 0xFFFF}",
            start=partial.start_time,
            end=partial.end_time,
            text=partial.text,
            display_text=quality.display_text,
            language=partial.language,
            confidence=partial.confidence,
            review_flag=quality.suppressed,
            review_reasons=list(quality.suppression_reasons),
            suppressed=quality.suppressed,
            suppression_reasons=quality.suppression_reasons,
            quality_label=quality.quality_label,
            script_mismatch=quality.script_mismatch,
            source_chunk_started_at=chunk.started_at,
        )

    def _handle_gpu_failure(self) -> None:
        """Handle GPU failure by reloading on CPU."""
        if self.execution_mode == "gpu_only":
            raise RuntimeError("GPU failure in gpu_only mode")

        self._publish_status("GPU failure detected, reloading on CPU...")
        self._warning = "GPU failure. Switched to CPU fallback."

        # Clear backend to force re-initialization
        self._backend = None

        if HAS_TORCH and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

        # Re-initialize on CPU
        backend = self._initialize_backend()
        self._gpu_mode = "cpu/int8"
        self._runtime_device = "cpu"

        self._publish_status("Model reloaded on CPU")

    def _publish_health(self, health: SessionHealth) -> None:
        for callback in self._health_callbacks:
            callback(health)

    def _health_snapshot(self) -> SessionHealth:
        return SessionHealth(
            audio_stream_active=True,
            gpu_mode=self._gpu_mode,
            execution_mode=self.execution_mode,
            model_runtime_device=self._runtime_device,
            last_transcript_at=utc_now(),
            queue_depth=self._queue.qsize(),
            dropped_stt_chunks=self._dropped_chunks,
            stt_backpressure_state=self._backpressure_state,
            estimated_backlog_seconds=self._estimate_backlog(),
            last_warning=self._warning,
        )

    @property
    def stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            "chunks_processed": self._chunks_processed,
            "avg_latency_ms": self._avg_latency_ms,
            "language_cache": self.language_optimizer.cache_stats,
            "model_pool": self.model_pool.get_stats(),
            "gpu_mode": self._gpu_mode,
            "queue_depth": self._queue.qsize(),
            "backend_metrics": self._performance_metrics.to_dict()
            if self._performance_metrics
            else {},
        }

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        if HAS_TORCH and torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.language_optimizer.clear_cache()


# Convenience functions for creating optimized transcriber instances


def create_realtime_transcriber(
    model_name: str = "tiny",
    download_root: str = "./models",
    device: str = "auto",
    language_mode: str = "auto",
    execution_mode: str = "auto",
) -> FastWhisperBackend:
    """Create a transcriber optimized for realtime performance."""
    return FastWhisperBackend(
        model_name=model_name,
        download_root=download_root,
        device=device,
        compute_type="int8" if device == "cpu" else "float16",
        language_mode=language_mode,
        execution_mode=execution_mode,
        streaming_window_ms=400,
        streaming_overlap_ms=80,
        num_cuda_streams=2,
    )


def create_low_latency_transcriber(
    model_name: str = "base",
    download_root: str = "./models",
    device: str = "auto",
    language_mode: str = "auto",
    execution_mode: str = "auto",
) -> FastWhisperBackend:
    """Create a transcriber optimized for low latency."""
    return FastWhisperBackend(
        model_name=model_name,
        download_root=download_root,
        device=device,
        compute_type="int8" if device == "cpu" else "float16",
        language_mode=language_mode,
        execution_mode=execution_mode,
        streaming_window_ms=1000,
        streaming_overlap_ms=220,
        num_cuda_streams=2,
    )


def create_balanced_transcriber(
    model_name: str = "small",
    download_root: str = "./models",
    device: str = "auto",
    language_mode: str = "auto",
    execution_mode: str = "auto",
) -> FastWhisperBackend:
    """Create a transcriber with balanced accuracy/speed."""
    return FastWhisperBackend(
        model_name=model_name,
        download_root=download_root,
        device=device,
        compute_type="int8" if device == "cpu" else "float16",
        language_mode=language_mode,
        execution_mode=execution_mode,
        streaming_window_ms=1600,
        streaming_overlap_ms=320,
        num_cuda_streams=2,
    )


# Alias for backward compatibility
FastTranscriber = FastWhisperBackend
