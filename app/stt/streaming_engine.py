"""Optimized streaming-first transcription engine for dual-mode operation.

Supports Wispr mode (fast, low-latency) and System mode (accurate, batched)
with adaptive performance tuning and production-grade reliability.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from collections.abc import AsyncGenerator, Callable, Generator
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Literal, Protocol

import numpy as np

from app.core.models import SessionHealth, TranscriptSegment, utc_now
from app.core.settings.manager import get_settings_manager
from app.stt.chunker import AudioChunk
from app.stt.fast_whisper_backend import FastWhisperBackend, WhisperModel
from app.stt.model_pool import ModelPool, ModelSlot
from app.stt.quality import assess_segment_quality

logger = logging.getLogger(__name__)


class TranscriptionMode(Enum):
    """Transcription mode for different latency/accuracy tradeoffs."""

    WISPR = auto()  # <200ms first-word latency, tiny model
    SYSTEM = auto()  # <1s first-word latency, medium model


class EngineState(Enum):
    """Engine lifecycle states."""

    INITIALIZING = auto()
    WARMING = auto()
    READY = auto()
    PROCESSING = auto()
    PAUSED = auto()
    ERROR = auto()
    SHUTDOWN = auto()


@dataclass(slots=True)
class PerformanceMetrics:
    """Detailed performance metrics for monitoring."""

    # Latency metrics (ms)
    first_word_latency_ms: float = 0.0
    avg_chunk_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # Throughput metrics
    chunks_processed: int = 0
    words_per_second: float = 0.0
    real_time_factor: float = 1.0

    # Quality metrics
    avg_confidence: float = 0.0
    segments_produced: int = 0
    segments_suppressed: int = 0

    # Resource metrics
    queue_depth: int = 0
    memory_usage_mb: float = 0.0
    gpu_utilization_percent: float = 0.0

    # Timestamps
    last_update: float = field(default_factory=time.time)

    def record(self, latency_ms: float) -> None:
        """Record a chunk latency sample for legacy fast-engine callers."""
        self.chunks_processed += 1
        self.last_update = time.time()

        if self.chunks_processed == 1:
            self.first_word_latency_ms = latency_ms
            self.avg_chunk_latency_ms = latency_ms
            self.p50_latency_ms = latency_ms
            self.p95_latency_ms = latency_ms
            self.p99_latency_ms = latency_ms
            return

        previous_count = self.chunks_processed - 1
        self.avg_chunk_latency_ms = (
            (self.avg_chunk_latency_ms * previous_count) + latency_ms
        ) / self.chunks_processed
        self.p50_latency_ms = self.avg_chunk_latency_ms
        self.p95_latency_ms = max(self.p95_latency_ms, latency_ms)
        self.p99_latency_ms = max(self.p99_latency_ms, latency_ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "first_word_latency_ms": round(self.first_word_latency_ms, 2),
            "avg_chunk_latency_ms": round(self.avg_chunk_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "chunks_processed": self.chunks_processed,
            "words_per_second": round(self.words_per_second, 2),
            "real_time_factor": round(self.real_time_factor, 3),
            "avg_confidence": round(self.avg_confidence, 3),
            "segments_produced": self.segments_produced,
            "segments_suppressed": self.segments_suppressed,
            "queue_depth": self.queue_depth,
            "memory_usage_mb": round(self.memory_usage_mb, 2),
            "gpu_utilization_percent": round(self.gpu_utilization_percent, 1),
        }


@dataclass(slots=True)
class StreamingConfig:
    """Configuration for streaming transcription."""

    # Window configuration
    window_ms: int = 400
    overlap_ms: int = 80
    min_chunk_ms: int = 200

    # Adaptive beam sizing
    target_latency_ms: float = 200.0
    min_beam_size: int = 1
    max_beam_size: int = 5
    latency_history_size: int = 10

    # Context carryover
    prefix_context_enabled: bool = True
    max_prefix_words: int = 5
    context_decay_factor: float = 0.8

    # Partial results
    partial_threshold_ms: float = 150.0
    stabilization_window: int = 3


@dataclass(slots=True)
class PartialResult:
    """Intermediate transcription result with metadata."""

    text: str
    is_final: bool
    is_stable: bool
    start_time: float
    end_time: float
    language: str
    confidence: float
    words: list[dict[str, Any]] = field(default_factory=list)
    prefix_context: str = ""  # Carried context from previous chunk
    beam_size_used: int = 1
    inference_time_ms: float = 0.0


class ModelWarmupStrategy:
    """Configurable model warming strategies."""

    @staticmethod
    def warmup_tiny(model: WhisperModel) -> bool:
        """Fast warmup for tiny model."""
        try:
            dummy = np.zeros(8000, dtype=np.float32)  # 0.5s
            segments, _ = model.transcribe(
                dummy,
                language="en",
                beam_size=1,
                temperature=0.0,
                without_timestamps=True,
            )
            list(segments)
            return True
        except Exception as e:
            logger.warning(f"Tiny model warmup failed: {e}")
            return False

    @staticmethod
    def warmup_medium(model: WhisperModel) -> bool:
        """Full warmup for medium model."""
        try:
            # Warmup with multiple lengths
            for length in [8000, 16000, 32000]:  # 0.5s, 1s, 2s
                dummy = np.zeros(length, dtype=np.float32)
                segments, _ = model.transcribe(
                    dummy,
                    language="en",
                    beam_size=1,
                    temperature=0.0,
                    without_timestamps=True,
                )
                list(segments)
            return True
        except Exception as e:
            logger.warning(f"Medium model warmup failed: {e}")
            return False


class AdaptiveBeamController:
    """Dynamically adjusts beam size based on latency targets."""

    def __init__(
        self,
        target_latency_ms: float,
        min_beam_size: int = 1,
        max_beam_size: int = 5,
        history_size: int = 10,
    ) -> None:
        self.target_latency_ms = target_latency_ms
        self.min_beam_size = min_beam_size
        self.max_beam_size = max_beam_size
        self._latency_history: deque[float] = deque(maxlen=history_size)
        self._current_beam_size = min_beam_size
        self._lock = threading.Lock()

    def report_latency(self, latency_ms: float) -> None:
        """Report observed latency for adaptation."""
        with self._lock:
            self._latency_history.append(latency_ms)
            self._adapt_beam_size()

    def _adapt_beam_size(self) -> None:
        """Adjust beam size based on recent latency trends."""
        if len(self._latency_history) < 3:
            return

        recent_avg = sum(self._latency_history) / len(self._latency_history)
        p95 = sorted(self._latency_history)[int(len(self._latency_history) * 0.95)]

        # If consistently over target, reduce beam size
        if p95 > self.target_latency_ms * 1.2:
            if self._current_beam_size > self.min_beam_size:
                self._current_beam_size -= 1
                logger.debug(
                    f"Reduced beam size to {self._current_beam_size} "
                    f"(p95={p95:.1f}ms > target={self.target_latency_ms:.1f}ms)"
                )

        # If consistently under target, can increase for better quality
        elif recent_avg < self.target_latency_ms * 0.6:
            if self._current_beam_size < self.max_beam_size:
                self._current_beam_size += 1
                logger.debug(
                    f"Increased beam size to {self._current_beam_size} "
                    f"(avg={recent_avg:.1f}ms < target={self.target_latency_ms:.1f}ms)"
                )

    @property
    def current_beam_size(self) -> int:
        """Get current beam size recommendation."""
        with self._lock:
            return self._current_beam_size

    def reset(self) -> None:
        """Reset to initial state."""
        with self._lock:
            self._latency_history.clear()
            self._current_beam_size = self.min_beam_size


class ContextCarryoverManager:
    """Manages prefix-based context carryover between chunks."""

    def __init__(
        self,
        max_prefix_words: int = 5,
        decay_factor: float = 0.8,
    ) -> None:
        self.max_prefix_words = max_prefix_words
        self.decay_factor = decay_factor
        self._context: str = ""
        self._reliability: float = 1.0
        self._lock = threading.Lock()

    def update_context(self, text: str, confidence: float) -> None:
        """Update carried context from completed transcription."""
        with self._lock:
            if confidence < 0.6 or not text.strip():
                self._reliability *= self.decay_factor
                return

            # Take last N words as context
            words = text.strip().split()
            if len(words) > self.max_prefix_words:
                context_words = words[-self.max_prefix_words :]
            else:
                context_words = words

            self._context = " ".join(context_words)
            self._reliability = min(1.0, confidence)

    def get_prefix(self) -> str:
        """Get current prefix context for next chunk."""
        with self._lock:
            if self._reliability < 0.3:
                return ""
            return self._context

    def reset(self) -> None:
        """Clear context."""
        with self._lock:
            self._context = ""
            self._reliability = 1.0


class StreamingInferenceEngine:
    """High-performance streaming inference with adaptive tuning."""

    def __init__(
        self,
        model: WhisperModel,
        mode: TranscriptionMode,
        config: StreamingConfig | None = None,
        sample_rate: int = 16000,
    ) -> None:
        self.model = model
        self.mode = mode
        self.config = config or StreamingConfig()
        self.sample_rate = sample_rate

        # Adaptive components
        target_latency = 200.0 if mode == TranscriptionMode.WISPR else 1000.0
        self.beam_controller = AdaptiveBeamController(
            target_latency_ms=target_latency,
            min_beam_size=self.config.min_beam_size,
            max_beam_size=self.config.max_beam_size,
            history_size=self.config.latency_history_size,
        )
        self.context_manager = ContextCarryoverManager(
            max_prefix_words=self.config.max_prefix_words,
            decay_factor=self.config.context_decay_factor,
        )

        # Audio buffering
        max_buffer_samples = int(sample_rate * 30)  # 30s max
        self._buffer: deque[float] = deque(maxlen=max_buffer_samples)
        self._buffer_lock = threading.Lock()
        self._buffer_start_time = 0.0
        self._stream_time = 0.0

        # Partial result stabilization
        self._partial_history: deque[PartialResult] = deque(maxlen=self.config.stabilization_window)
        self._last_final_end = 0.0

        # Metrics
        self._first_word_emitted = False
        self._first_word_latency_ms: float | None = None
        self._total_words = 0
        self._start_time = time.time()

    def push_audio(
        self,
        samples: np.ndarray,
        timestamp: float | None = None,
    ) -> None:
        """Push audio samples to the streaming buffer."""
        with self._buffer_lock:
            if timestamp is not None:
                self._stream_time = timestamp
            self._buffer.extend(samples.tolist())

    def process_stream(
        self,
        language: str | None = None,
        yield_partial: bool = True,
    ) -> Generator[PartialResult, None, None]:
        """Process buffered audio and yield partial results."""
        window_samples = int(self.sample_rate * self.config.window_ms / 1000)
        overlap_samples = int(self.sample_rate * self.config.overlap_ms / 1000)
        step_samples = window_samples - overlap_samples
        min_samples = int(self.sample_rate * self.config.min_chunk_ms / 1000)

        while True:
            with self._buffer_lock:
                if len(self._buffer) < max(window_samples, min_samples):
                    break

                # Extract window
                extract_samples = min(window_samples, len(self._buffer))
                window = np.fromiter(
                    (self._buffer[i] for i in range(extract_samples)),
                    dtype=np.float32,
                    count=extract_samples,
                )

                # Advance buffer
                advance = min(step_samples, len(self._buffer) - overlap_samples)
                for _ in range(advance):
                    self._buffer.popleft()

                window_start = self._buffer_start_time
                self._buffer_start_time += advance / self.sample_rate

            # Get adaptive parameters
            beam_size = self.beam_controller.current_beam_size
            prefix_context = (
                self.context_manager.get_prefix() if self.config.prefix_context_enabled else ""
            )

            # Transcribe window
            result = self._transcribe_window(
                window,
                window_start,
                language,
                beam_size=beam_size,
                prefix=prefix_context,
            )

            if result.text.strip():
                # Track first word latency
                if not self._first_word_emitted:
                    self._first_word_latency_ms = result.inference_time_ms
                    self._first_word_emitted = True

                # Update beam controller
                self.beam_controller.report_latency(result.inference_time_ms)

                # Stabilize partial results
                is_stable = self._is_stable_result(result)
                result.is_stable = is_stable

                if yield_partial:
                    yield result

                # Check for final utterance
                if self._is_complete_utterance(result.text) and is_stable:
                    final_result = PartialResult(
                        text=result.text,
                        is_final=True,
                        is_stable=True,
                        start_time=result.start_time,
                        end_time=result.end_time,
                        language=result.language,
                        confidence=result.confidence,
                        words=result.words,
                        beam_size_used=beam_size,
                        inference_time_ms=result.inference_time_ms,
                    )
                    yield final_result

                    # Update context for next chunk
                    self.context_manager.update_context(result.text, result.confidence)
                    self._last_final_end = final_result.end_time
                    self._total_words += len(result.text.split())

    def _transcribe_window(
        self,
        audio: np.ndarray,
        start_time: float,
        language: str | None,
        beam_size: int = 1,
        prefix: str = "",
    ) -> PartialResult:
        """Transcribe a single audio window."""
        inference_start = time.perf_counter()

        # Prepare transcription parameters
        transcribe_kwargs: dict[str, Any] = {
            "language": language,
            "beam_size": beam_size,
            "best_of": beam_size,
            "temperature": 0.0,
            "patience": 1.0,
            "length_penalty": 1.0,
            "vad_filter": True,
            "vad_parameters": {
                "threshold": 0.35 if self.mode == TranscriptionMode.WISPR else 0.4,
                "min_silence_duration_ms": 200,
                "speech_pad_ms": 200,
            },
            "word_timestamps": False,
            "without_timestamps": True,
        }

        if prefix:
            transcribe_kwargs["initial_prompt"] = prefix

        try:
            segments, info = self.model.transcribe(audio, **transcribe_kwargs)
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return PartialResult(
                text="",
                is_final=False,
                is_stable=False,
                start_time=start_time,
                end_time=start_time,
                language=language or "auto",
                confidence=0.0,
                beam_size_used=beam_size,
                inference_time_ms=(time.perf_counter() - inference_start) * 1000,
            )

        # Collect results
        texts = []
        end_time = start_time
        confidence = 0.0
        count = 0

        for segment in segments:
            text = segment.text.strip()
            if text:
                texts.append(text)
                end_time = start_time + getattr(segment, "end", 0)
                # Calculate confidence proxy
                avg_logprob = getattr(segment, "avg_logprob", 0)
                no_speech_prob = getattr(segment, "no_speech_prob", 0)
                seg_confidence = max(0.0, min(0.99, 0.65 + (avg_logprob + 1.2) / 1.2 * 0.25))
                seg_confidence -= no_speech_prob * 0.25
                confidence += max(0.0, seg_confidence)
                count += 1

        full_text = " ".join(texts)
        avg_confidence = confidence / count if count > 0 else 0.0
        inference_time_ms = (time.perf_counter() - inference_start) * 1000

        detected_language = getattr(info, "language", language or "auto")

        return PartialResult(
            text=full_text,
            is_final=False,
            is_stable=False,
            start_time=start_time,
            end_time=end_time,
            language=detected_language,
            confidence=avg_confidence,
            prefix_context=prefix,
            beam_size_used=beam_size,
            inference_time_ms=inference_time_ms,
        )

    def _is_stable_result(self, result: PartialResult) -> bool:
        """Check if result has stabilized across multiple windows."""
        self._partial_history.append(result)

        if len(self._partial_history) < 2:
            return False

        # Check if text is consistent across recent windows
        recent_texts = [r.text.strip() for r in self._partial_history]
        if len(set(recent_texts)) == 1:
            return True

        # Check for high confidence
        if result.confidence > 0.85:
            return True

        return False

    def _is_complete_utterance(self, text: str) -> bool:
        """Check if text looks like a complete utterance."""
        text = text.strip()
        if not text:
            return False

        # Check for sentence-ending punctuation
        if text[-1] in ".!?":
            return True

        # Check for natural pause indicators
        words = text.split()
        if len(words) >= 12:
            return True

        if len(words) >= 5 and len(text) >= 24:
            return True

        return False

    def flush(self, language: str | None = None) -> PartialResult | None:
        """Process remaining buffer and return final result."""
        with self._buffer_lock:
            if not self._buffer:
                return None

            audio = np.fromiter(self._buffer, dtype=np.float32, count=len(self._buffer))
            start_time = self._buffer_start_time
            self._buffer.clear()

        if len(audio) < 8000:  # Less than 500ms
            return None

        result = self._transcribe_window(
            audio,
            start_time,
            language,
            beam_size=self.beam_controller.current_beam_size,
        )

        if not result.text.strip():
            return None

        return PartialResult(
            text=result.text,
            is_final=True,
            is_stable=True,
            start_time=result.start_time,
            end_time=result.end_time,
            language=result.language,
            confidence=result.confidence,
            beam_size_used=result.beam_size_used,
            inference_time_ms=result.inference_time_ms,
        )

    def get_metrics(self) -> dict[str, Any]:
        """Get engine metrics."""
        elapsed = time.time() - self._start_time
        words_per_sec = self._total_words / elapsed if elapsed > 0 else 0

        return {
            "first_word_latency_ms": self._first_word_latency_ms,
            "total_words": self._total_words,
            "words_per_second": round(words_per_sec, 2),
            "current_beam_size": self.beam_controller.current_beam_size,
            "context_reliability": self.context_manager._reliability,
        }

    def reset(self) -> None:
        """Reset engine state."""
        with self._buffer_lock:
            self._buffer.clear()
        self._partial_history.clear()
        self.context_manager.reset()
        self.beam_controller.reset()
        self._first_word_emitted = False
        self._first_word_latency_ms = None


class DualModeTranscriptionEngine:
    """Dual-mode transcription engine supporting Wispr and System modes."""

    def __init__(
        self,
        model_pool: ModelPool | None = None,
        wispr_model: str = "tiny",
        system_model: str = "medium",
        download_root: str = "./models",
        device: str = "auto",
        warmup_on_init: bool = True,
    ) -> None:
        self.model_pool = model_pool or ModelPool()
        self.wispr_model_name = wispr_model
        self.system_model_name = system_model
        self.download_root = download_root
        self.device = device

        # Model slots
        self._wispr_slot: ModelSlot | None = None
        self._system_slot: ModelSlot | None = None

        # Engines
        self._wispr_engine: StreamingInferenceEngine | None = None
        self._system_engine: StreamingInferenceEngine | None = None
        self._current_engine: StreamingInferenceEngine | None = None
        self._current_mode: TranscriptionMode = TranscriptionMode.WISPR

        # State
        self._state = EngineState.INITIALIZING
        self._state_lock = threading.RLock()
        self._error: Exception | None = None

        # Async queue
        self._queue: asyncio.Queue[AudioChunk] = asyncio.Queue(maxsize=64)
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

        # Callbacks
        self._segment_callbacks: list[Callable[[TranscriptSegment], None]] = []
        self._partial_callbacks: list[Callable[[PartialResult], None]] = []
        self._error_callbacks: list[Callable[[Exception], None]] = []
        self._health_callbacks: list[Callable[[SessionHealth], None]] = []

        # Metrics
        self._metrics = PerformanceMetrics()
        self._latency_history: deque[float] = deque(maxlen=100)
        self._confidence_history: deque[float] = deque(maxlen=100)

        if warmup_on_init:
            self._initialize()

    def _initialize(self) -> None:
        """Initialize models and engines."""
        with self._state_lock:
            self._state = EngineState.WARMING

        try:
            # Acquire Wispr model (tiny, int8 for speed)
            self._wispr_slot = self.model_pool.acquire(
                model_name=self.wispr_model_name,
                device=self._resolve_device("wispr"),
                compute_type="int8",
                download_root=self.download_root,
            )

            # Warmup Wispr model
            if ModelWarmupStrategy.warmup_tiny(self._wispr_slot.model):
                logger.info(f"Wispr model ({self.wispr_model_name}) warmed successfully")
            else:
                logger.warning(f"Wispr model warmup incomplete")

            # Acquire System model (medium, fp16 or int8 based on GPU)
            compute_type = "float16" if self._has_gpu() else "int8"
            self._system_slot = self.model_pool.acquire(
                model_name=self.system_model_name,
                device=self._resolve_device("system"),
                compute_type=compute_type,
                download_root=self.download_root,
            )

            # Warmup System model
            if ModelWarmupStrategy.warmup_medium(self._system_slot.model):
                logger.info(f"System model ({self.system_model_name}) warmed successfully")
            else:
                logger.warning(f"System model warmup incomplete")

            # Create engines
            wispr_config = StreamingConfig(
                window_ms=400,
                overlap_ms=80,
                target_latency_ms=200.0,
                min_beam_size=1,
                max_beam_size=3,
            )

            system_config = StreamingConfig(
                window_ms=1000,
                overlap_ms=200,
                target_latency_ms=1000.0,
                min_beam_size=1,
                max_beam_size=5,
            )

            self._wispr_engine = StreamingInferenceEngine(
                model=self._wispr_slot.model,
                mode=TranscriptionMode.WISPR,
                config=wispr_config,
            )

            self._system_engine = StreamingInferenceEngine(
                model=self._system_slot.model,
                mode=TranscriptionMode.SYSTEM,
                config=system_config,
            )

            # Default to Wispr mode
            self._current_engine = self._wispr_engine
            self._current_mode = TranscriptionMode.WISPR

            with self._state_lock:
                self._state = EngineState.READY

            logger.info("DualModeTranscriptionEngine initialized successfully")

        except Exception as e:
            logger.error(f"Engine initialization failed: {e}")
            self._error = e
            with self._state_lock:
                self._state = EngineState.ERROR
            raise

    def _resolve_device(self, mode: str) -> str:
        """Resolve device based on mode and availability."""
        if self.device != "auto":
            return self.device

        if mode == "wispr":
            # Wispr mode prefers CPU with int8 for low latency
            return "cpu"
        else:
            # System mode uses GPU if available
            return "cuda" if self._has_gpu() else "cpu"

    def _has_gpu(self) -> bool:
        """Check if GPU is available."""
        try:
            import torch

            return torch.cuda.is_available()
        except ImportError:
            return False

    @property
    def state(self) -> EngineState:
        """Get current engine state."""
        with self._state_lock:
            return self._state

    @property
    def is_ready(self) -> bool:
        """Check if engine is ready for transcription."""
        return self.state == EngineState.READY

    def set_mode(self, mode: TranscriptionMode) -> None:
        """Switch between Wispr and System modes."""
        with self._state_lock:
            if mode == TranscriptionMode.WISPR:
                self._current_engine = self._wispr_engine
            else:
                self._current_engine = self._system_engine
            self._current_mode = mode

        logger.info(f"Switched to {mode.name} mode")

    async def start(self) -> None:
        """Start the async transcription worker."""
        if self._task and not self._task.done():
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("Transcription engine started")

    async def stop(self) -> None:
        """Stop the transcription worker."""
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Flush remaining audio
        if self._current_engine:
            final = self._current_engine.flush()
            if final:
                await self._handle_result(final)

        logger.info("Transcription engine stopped")

    async def submit(self, chunk: AudioChunk) -> bool:
        """Submit audio chunk for transcription with backpressure handling."""
        if self._state != EngineState.READY:
            logger.warning(f"Cannot submit chunk: engine state is {self._state.name}")
            return False

        try:
            self._queue.put_nowait(chunk)
            self._metrics.queue_depth = self._queue.qsize()
            return True
        except asyncio.QueueFull:
            logger.warning("Queue full, chunk dropped")
            return False

    async def _worker_loop(self) -> None:
        """Main async worker loop."""
        with self._state_lock:
            self._state = EngineState.PROCESSING

        try:
            while not self._stop_event.is_set():
                try:
                    chunk = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=0.1,
                    )
                except asyncio.TimeoutError:
                    continue

                await self._process_chunk(chunk)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Worker loop error")
            self._error = e
            with self._state_lock:
                self._state = EngineState.ERROR
            for callback in self._error_callbacks:
                callback(e)

    async def _process_chunk(self, chunk: AudioChunk) -> None:
        """Process a single audio chunk."""
        if not self._current_engine:
            return

        start_time = time.perf_counter()

        # Push audio to engine
        self._current_engine.push_audio(chunk.samples, chunk.started_at)

        # Process and emit results
        settings = get_settings_manager().get_settings()
        language = getattr(settings.hotkey, "language", "en") or "en"

        for result in self._current_engine.process_stream(language=language):
            await self._handle_result(result, chunk)

        # Update metrics
        latency_ms = (time.perf_counter() - start_time) * 1000
        self._latency_history.append(latency_ms)
        self._update_metrics()

    async def _handle_result(
        self,
        result: PartialResult,
        chunk: AudioChunk | None = None,
    ) -> None:
        """Handle transcription result."""
        # Emit partial callback
        for callback in self._partial_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback(result)
            else:
                callback(result)

        # Convert to segment if final
        if result.is_final:
            segment = self._create_segment(result, chunk)

            for callback in self._segment_callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback(segment)
                else:
                    callback(segment)

            self._metrics.segments_produced += 1
            self._confidence_history.append(result.confidence)

            # Track first word latency
            if result.inference_time_ms > 0 and self._metrics.first_word_latency_ms == 0:
                self._metrics.first_word_latency_ms = result.inference_time_ms

    def _create_segment(
        self,
        result: PartialResult,
        chunk: AudioChunk | None,
    ) -> TranscriptSegment:
        """Convert partial result to transcript segment."""
        settings = get_settings_manager().get_settings()
        language_mode = getattr(settings.hotkey, "language", "en") or "en"
        quality = assess_segment_quality(
            result.text,
            confidence=result.confidence,
            language_mode=language_mode,
            detected_language=result.language,
        )

        return TranscriptSegment(
            id=f"seg-{int(time.time() * 1000)}-{hash(result.text) & 0xFFFF}",
            start=result.start_time,
            end=result.end_time,
            text=result.text,
            display_text=quality.display_text,
            language=result.language,
            confidence=result.confidence,
            review_flag=quality.suppressed,
            review_reasons=list(quality.suppression_reasons),
            suppressed=quality.suppressed,
            suppression_reasons=quality.suppression_reasons,
            quality_label=quality.quality_label,
            script_mismatch=quality.script_mismatch,
            source_chunk_started_at=chunk.started_at if chunk else None,
        )

    def _update_metrics(self) -> None:
        """Update performance metrics."""
        if self._latency_history:
            sorted_latencies = sorted(self._latency_history)
            n = len(sorted_latencies)
            self._metrics.avg_chunk_latency_ms = sum(sorted_latencies) / n
            self._metrics.p50_latency_ms = sorted_latencies[int(n * 0.5)]
            self._metrics.p95_latency_ms = sorted_latencies[int(n * 0.95)]
            self._metrics.p99_latency_ms = sorted_latencies[int(n * 0.99)]

        if self._confidence_history:
            self._metrics.avg_confidence = sum(self._confidence_history) / len(
                self._confidence_history
            )

        self._metrics.chunks_processed = len(self._latency_history)
        self._metrics.last_update = time.time()

    def add_segment_callback(self, callback: Callable[[TranscriptSegment], None]) -> None:
        """Add callback for final segments."""
        self._segment_callbacks.append(callback)

    def add_partial_callback(self, callback: Callable[[PartialResult], None]) -> None:
        """Add callback for partial results."""
        self._partial_callbacks.append(callback)

    def add_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """Add callback for errors."""
        self._error_callbacks.append(callback)

    def add_health_callback(self, callback: Callable[[SessionHealth], None]) -> None:
        """Add callback for health updates."""
        self._health_callbacks.append(callback)

    def get_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        return self._metrics

    def get_health(self) -> SessionHealth:
        """Get current health status."""
        return SessionHealth(
            audio_stream_active=self.state == EngineState.PROCESSING,
            gpu_mode="cuda" if self._has_gpu() else "cpu",
            model_runtime_device=self._resolve_device(self._current_mode.name.lower()),
            queue_depth=self._metrics.queue_depth,
            last_transcript_at=utc_now() if self._metrics.chunks_processed > 0 else None,
        )

    def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up DualModeTranscriptionEngine")

        # Release model slots
        if self._wispr_slot:
            self.model_pool.release(self._wispr_slot)
        if self._system_slot:
            self.model_pool.release(self._system_slot)

        with self._state_lock:
            self._state = EngineState.SHUTDOWN

        logger.info("DualModeTranscriptionEngine cleanup complete")
