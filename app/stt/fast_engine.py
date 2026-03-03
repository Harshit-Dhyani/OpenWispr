"""Optimized transcription engine for real-time Hindi/English transcription.

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
from faster_whisper import WhisperModel

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
from app.stt.quality import assess_segment_quality


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
    patience: float = 1.0  # No patience, fastest
    length_penalty: float = 1.0
    suppress_tokens: str = "-1"  # Suppress all special tokens
    initial_prompt: str | None = None
    condition_on_previous_text: bool = False  # Disable for speed
    fp16: bool = False  # Use int8 instead


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

    # Optimized configurations based on language characteristics
    CONFIGS: dict[str, LanguageConfig] = {
        "hi": LanguageConfig(
            # Higher temperature for Hindi phonetic diversity
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
            # Lower temperature for English precision
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
            # Balanced for auto-detection
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

    # Maximum cache size for LRU eviction
    MAX_CACHE_SIZE = 500

    def __init__(self) -> None:
        # Use OrderedDict for LRU cache - moves accessed items to end
        self._lang_cache: OrderedDict[str, str] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_hits = 0
        self._cache_misses = 0

    def get_config(self, language: str) -> LanguageConfig:
        """Get optimized config for language."""
        return self.CONFIGS.get(language, self.CONFIGS["auto"])

    def detect_language(self, audio: np.ndarray, model: WhisperModel) -> str:
        """Fast language detection with caching."""
        # Create audio fingerprint for cache lookup
        fingerprint = self._audio_fingerprint(audio)

        with self._cache_lock:
            if fingerprint in self._lang_cache:
                self._cache_hits += 1
                # Move to end (most recently used)
                self._lang_cache.move_to_end(fingerprint)
                return self._lang_cache[fingerprint]
            self._cache_misses += 1

        # Detect language using model
        try:
            _, info = model.transcribe(
                audio[:16000],  # Use first second for speed
                language=None,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                vad_filter=True,
                vad_parameters={"threshold": 0.5, "min_silence_duration_ms": 100},
            )
            detected = getattr(info, "language", "auto")
        except Exception as e:
            logger.warning(f"Language detection failed: {e}, falling back to 'auto'")
            detected = "auto"

        with self._cache_lock:
            self._lang_cache[fingerprint] = detected
            # LRU eviction: remove oldest entries when cache exceeds max size
            while len(self._lang_cache) > self.MAX_CACHE_SIZE:
                # popitem(False) removes the first inserted (least recently used) item
                self._lang_cache.popitem(last=False)

        return detected

    def _audio_fingerprint(self, audio: np.ndarray) -> str:
        """Generate a quick fingerprint for audio caching."""
        # Use first and last 100 samples + length as fingerprint
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


class ModelPool:
    """Thread-safe cache for Whisper models to avoid reload overhead."""

    _instance: ModelPool | None = None
    _lock = threading.Lock()

    def __new__(cls) -> ModelPool:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    # Model TTL in seconds (30 minutes of inactivity)
    MODEL_TTL_SECONDS = 1800

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._models: dict[str, WhisperModel] = {}
        self._model_locks: dict[str, threading.Lock] = {}
        self._pool_lock = threading.Lock()
        self._model_metadata: dict[str, dict[str, Any]] = {}

    def _cleanup_expired_models(self) -> None:
        """Remove models that have exceeded TTL."""
        now = time.time()
        expired_keys = [
            key
            for key, meta in self._model_metadata.items()
            if now - meta.get("last_access", 0) > self.MODEL_TTL_SECONDS
        ]
        for key in expired_keys:
            self.release_model(key)
            logger.debug(f"Expired model removed from pool: {key}")

    def get_model(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        download_root: str,
    ) -> WhisperModel:
        """Get or create a cached model."""
        cache_key = f"{model_name}:{device}:{compute_type}"

        # Cleanup expired models periodically
        self._cleanup_expired_models()

        # Fast path: model already exists
        if cache_key in self._models:
            # Update access time
            with self._pool_lock:
                if cache_key in self._model_metadata:
                    self._model_metadata[cache_key]["last_access"] = time.time()
                    self._model_metadata[cache_key]["access_count"] = (
                        self._model_metadata[cache_key].get("access_count", 0) + 1
                    )
            return self._models[cache_key]

        # Slow path: create model with per-key lock
        with self._pool_lock:
            if cache_key not in self._model_locks:
                self._model_locks[cache_key] = threading.Lock()

        with self._model_locks[cache_key]:
            # Double-check after acquiring lock
            if cache_key in self._models:
                return self._models[cache_key]

            # Create new model with retry logic
            max_retries = 3
            last_error = None
            model = None

            for attempt in range(max_retries):
                try:
                    model = WhisperModel(
                        model_name,
                        device=device,
                        compute_type=compute_type,  # Use provided compute_type from configuration
                        download_root=download_root,
                    )
                    break
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                    else:
                        raise RuntimeError(
                            f"Failed to load model {model_name} after {max_retries} attempts: {last_error}"
                        ) from last_error

            with self._pool_lock:
                self._models[cache_key] = model
                self._model_metadata[cache_key] = {
                    "created_at": time.time(),
                    "access_count": 0,
                    "last_access": time.time(),
                }

            return model

    def release_model(self, cache_key: str) -> None:
        """Release a model from the pool (for cleanup)."""
        with self._pool_lock:
            if cache_key in self._models:
                del self._models[cache_key]
            if cache_key in self._model_locks:
                del self._model_locks[cache_key]
            if cache_key in self._model_metadata:
                del self._model_metadata[cache_key]

    def warmup_model(self, cache_key: str) -> bool:
        """Warm up a model with dummy inference."""
        if cache_key not in self._models:
            return False

        model = self._models[cache_key]
        try:
            dummy = np.zeros(16000, dtype=np.float32)
            segments, _ = model.transcribe(dummy, beam_size=1, temperature=0.0)
            list(segments)  # Consume generator
            return True
        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")
            return False

    def get_pool_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        with self._pool_lock:
            return {
                "cached_models": list(self._models.keys()),
                "model_count": len(self._models),
                "metadata": dict(self._model_metadata),
            }

    def clear_pool(self) -> None:
        """Clear all cached models."""
        with self._pool_lock:
            self._models.clear()
            self._model_locks.clear()
            self._model_metadata.clear()


class CudaStreamManager:
    """Manages CUDA streams for parallel GPU operations."""

    def __init__(self, num_streams: int = 2) -> None:
        self.num_streams = num_streams
        self._streams: list[Any] = []
        self._current = 0
        self._lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize CUDA streams if available."""
        if self._initialized:
            return True

        if not HAS_TORCH or not torch.cuda.is_available():
            return False

        try:
            self._streams = [torch.cuda.Stream() for _ in range(self.num_streams)]
            self._initialized = True
            return True
        except Exception as exc:
            logger.debug(f"CUDA stream initialization failed: {exc}")
            return False

    def get_stream(self) -> Any:
        """Get next available CUDA stream in round-robin fashion."""
        if not self._initialized:
            return None

        with self._lock:
            stream = self._streams[self._current]
            self._current = (self._current + 1) % self.num_streams
            return stream

    def synchronize_all(self) -> None:
        """Synchronize all CUDA streams."""
        if not self._initialized:
            return

        for stream in self._streams:
            stream.synchronize()


@dataclass(slots=True)
class PartialResult:
    """Intermediate transcription result."""

    text: str
    is_final: bool
    start_time: float
    end_time: float
    language: str
    confidence: float


class StreamingTranscriber:
    """Streaming transcription that processes audio as it arrives."""

    def __init__(
        self,
        model: WhisperModel,
        language_optimizer: LanguageOptimizer,
        cuda_manager: CudaStreamManager | None = None,
        sample_rate: int = 16000,
        streaming_window_ms: int = 400,
        streaming_overlap_ms: int = 80,
    ) -> None:
        self.model = model
        self.optimizer = language_optimizer
        self.cuda_manager = cuda_manager
        self.sample_rate = sample_rate
        self.streaming_window_ms = streaming_window_ms
        self.streaming_overlap_ms = streaming_overlap_ms

        # Streaming buffer with max size to prevent unbounded growth
        # Max 30 seconds of audio at 16kHz = 480,000 samples
        max_buffer_samples = int(self.sample_rate * 30)
        self._buffer: deque[float] = deque(maxlen=max_buffer_samples)
        self._buffer_start_time = 0.0
        self._stream_time = 0.0
        self._lock = threading.Lock()

        # Partial result tracking
        self._pending_text = ""
        self._last_final_end = 0.0

    def push_audio(self, samples: np.ndarray, timestamp: float | None = None) -> None:
        """Push audio samples to the streaming buffer."""
        with self._lock:
            if timestamp is not None:
                self._stream_time = timestamp
            self._buffer.extend(samples.tolist())

    def process_stream(
        self,
        language: str | None = None,
        yield_partial: bool = True,
    ) -> Generator[PartialResult, None, None]:
        """Process buffered audio and yield partial results."""
        window_samples = int(self.sample_rate * self.streaming_window_ms / 1000)
        overlap_samples = int(self.sample_rate * self.streaming_overlap_ms / 1000)
        step_samples = window_samples - overlap_samples

        while True:
            with self._lock:
                if len(self._buffer) < window_samples:
                    break

                # Extract window
                window = np.fromiter(
                    (self._buffer[i] for i in range(window_samples)),
                    dtype=np.float32,
                    count=window_samples,
                )

                # Advance buffer
                for _ in range(step_samples):
                    self._buffer.popleft()

                window_start = self._buffer_start_time
                self._buffer_start_time += step_samples / self.sample_rate

            # Process window with error handling
            try:
                result = self._transcribe_window(window, window_start, language)
            except Exception as exc:
                logger.error(f"Transcription error in process_stream: {exc}")
                # Continue to next window on error
                continue

            if result.text.strip():
                if yield_partial:
                    yield result

                # Check if this looks like a complete utterance
                if self._is_complete_utterance(result.text):
                    final_result = PartialResult(
                        text=result.text,
                        is_final=True,
                        start_time=result.start_time,
                        end_time=result.end_time,
                        language=result.language,
                        confidence=result.confidence,
                    )
                    yield final_result
                    self._last_final_end = final_result.end_time

    def _transcribe_window(
        self,
        audio: np.ndarray,
        start_time: float,
        language: str | None = None,
    ) -> PartialResult:
        """Transcribe a single audio window."""
        window_duration = len(audio) / self.sample_rate if len(audio) > 0 else 0.0
        transcribe_start = time.perf_counter()

        # Auto-detect language if needed
        if language is None:
            language = self.optimizer.detect_language(audio, self.model)

        config = self.optimizer.get_config(language)

        # Build VAD parameters
        vad_params = {
            "threshold": config.vad_config.threshold,
            "min_silence_duration_ms": config.vad_config.min_silence_duration_ms,
            "speech_pad_ms": config.vad_config.speech_pad_ms,
            "min_speech_duration_ms": config.vad_config.min_speech_duration_ms,
            "max_speech_duration_s": config.vad_config.max_speech_duration_s,
        }

        # Use CUDA stream if available
        stream = self.cuda_manager.get_stream() if self.cuda_manager else None

        if stream and HAS_TORCH:
            with torch.cuda.stream(stream):
                segments, info = self.model.transcribe(
                    audio,
                    language=language if language != "auto" else None,
                    beam_size=config.beam_size,
                    best_of=config.best_of,
                    temperature=config.temperature,
                    patience=config.patience,
                    length_penalty=config.length_penalty,
                    vad_filter=True,
                    vad_parameters=vad_params,
                    word_timestamps=False,
                )
        else:
            segments, info = self.model.transcribe(
                audio,
                language=language if language != "auto" else None,
                beam_size=config.beam_size,
                best_of=config.best_of,
                temperature=config.temperature,
                patience=config.patience,
                length_penalty=config.length_penalty,
                vad_filter=True,
                vad_parameters=vad_params,
                word_timestamps=False,
            )

        # Collect text from segments
        texts = []
        end_time = start_time
        confidence = 0.0
        count = 0

        for segment in segments:
            text = segment.text.strip()
            if text:
                texts.append(text)
                end_time = start_time + segment.end
                confidence += confidence_proxy(segment)
                count += 1

        full_text = " ".join(texts)
        avg_confidence = confidence / count if count > 0 else 0.0
        inference_time_ms = (time.perf_counter() - transcribe_start) * 1000
        detected_language = getattr(info, "language", language or "auto")

        logger.debug(
            f"Partial transcription: window_duration={window_duration:.3f}s, "
            f"inference_time_ms={inference_time_ms:.2f}, segments_produced={count}, "
            f"detected_language={detected_language}, confidence={avg_confidence:.3f}, "
            f"text_length={len(full_text)}"
        )

        return PartialResult(
            text=full_text,
            is_final=False,
            start_time=start_time,
            end_time=end_time,
            language=detected_language,
            confidence=avg_confidence,
        )

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
        if len(words) >= 12:  # Longer utterances likely complete
            return True

        if len(words) >= 5 and len(text) >= 24:
            return True

        return False

    def flush(self, language: str | None = None) -> PartialResult | None:
        """Process remaining buffer and return final result."""
        with self._lock:
            if not self._buffer:
                return None

            audio = np.fromiter(self._buffer, dtype=np.float32, count=len(self._buffer))
            start_time = self._buffer_start_time
            self._buffer.clear()

        if len(audio) < 8000:  # Less than 500ms
            return None

        result = self._transcribe_window(audio, start_time, language)
        if not result.text.strip():
            return None
        word_count = len(result.text.split())
        if result.confidence < 0.55 and word_count < 4:
            return None
        return PartialResult(
            text=result.text,
            is_final=True,
            start_time=result.start_time,
            end_time=result.end_time,
            language=result.language,
            confidence=result.confidence,
        )


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
    """High-performance Whisper backend with streaming and optimizations."""

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

        # Components
        self.model_pool = ModelPool()
        self.language_optimizer = LanguageOptimizer()
        self.cuda_manager = CudaStreamManager(num_cuda_streams)

        # State
        self._model: WhisperModel | None = None
        self._gpu_mode = "unknown"
        self._runtime_device = "unknown"
        self._warning: str | None = None
        self._dropped_chunks = 0
        self._backpressure_state = "normal"
        self._transcriber: StreamingTranscriber | None = None

        logger.debug(
            "FastWhisperBackend initialized: "
            f"model_name={model_name}, device={device}, compute_type={compute_type}, "
            f"language_mode={language_mode}, execution_mode={execution_mode}, "
            f"max_queue_items={max_queue_items}"
        )

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

    def load_model(self) -> WhisperModel:
        return self._initialize_model()

    def set_language_mode(self, language_mode: str) -> None:
        self.language_mode = language_mode

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
            logger.debug(
                f"Chunk submission rejected (stopped): chunk_duration={chunk_duration:.3f}s, "
                f"queue_depth={queue_depth_before}, backpressure_state=stopped"
            )
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
            logger.debug(
                f"Chunk submitted: chunk_duration={chunk_duration:.3f}s, "
                f"queue_depth={self._queue.qsize()}, backpressure_state=normal, accepted=True"
            )
        except Full:
            self._dropped_chunks += 1
            previous_state = self._backpressure_state
            self._backpressure_state = "dropping"
            accepted = False
            logger.debug(
                f"Chunk dropped (queue full): chunk_duration={chunk_duration:.3f}s, "
                f"queue_depth={self._queue.qsize()}, backpressure_state_change={previous_state}->dropping, "
                f"total_dropped={self._dropped_chunks}"
            )

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

    def _check_gpu_memory(self) -> tuple[bool, str]:
        """Check if GPU has sufficient memory."""
        if not HAS_TORCH or not torch.cuda.is_available():
            return False, "CUDA not available"

        # Memory requirements for different compute types (in GB)
        # Values include model weights + CUDA overhead + workspace
        memory_requirements = {
            "tiny": {"int8": 0.5, "float16": 0.6, "float32": 0.8},
            "base": {"int8": 0.6, "float16": 0.8, "float32": 1.2},
            "small": {"int8": 1.0, "float16": 1.3, "float32": 2.0},
            "medium": {"int8": 3.0, "float16": 4.0, "float32": 6.0},
            "large-v1": {"int8": 5.0, "float16": 6.5, "float32": 10.0},
            "large-v2": {"int8": 5.0, "float16": 6.5, "float32": 10.0},
            "large-v3": {"int8": 6.0, "float16": 7.5, "float32": 11.0},
            "large-v3-turbo": {"int8": 4.0, "float16": 5.0, "float32": 7.5},
        }

        model_memory = memory_requirements.get(
            self.model_name, {"int8": 2.0, "float16": 2.5, "float32": 4.0}
        )
        required_gb = model_memory.get(self.compute_type, model_memory.get("int8", 2.0))
        # Add 10% buffer for CUDA overhead and temporary allocations
        required_gb *= 1.1

        try:
            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            reserved = torch.cuda.memory_reserved(0) / (1024**3)
            available = total - reserved

            if available < required_gb:
                return False, f"GPU memory: {available:.1f}GB < {required_gb:.1f}GB required"

            return True, f"GPU memory OK: {available:.1f}GB available"
        except Exception as e:
            return False, f"GPU check failed: {e}"

    def _initialize_model(self) -> WhisperModel:
        """Initialize model with GPU/CPU selection."""
        if self._model is not None:
            return self._model

        self._publish_status(f"Loading {self.model_name} model...")
        load_start_time = time.perf_counter()
        logger.debug(
            f"Starting model load: model_name={self.model_name}, "
            f"requested_device={self.device}, compute_type={self.compute_type}"
        )

        # CPU-only mode
        if self.execution_mode == "cpu_only" or self.device == "cpu":
            self._model = self.model_pool.get_model(
                self.model_name,
                "cpu",
                "int8",
                self.download_root,
            )
            self._gpu_mode = "cpu/int8"
            self._runtime_device = "cpu"
            load_time_ms = (time.perf_counter() - load_start_time) * 1000
            logger.debug(
                f"Model loaded on CPU: model_name={self.model_name}, "
                f"device=cpu, compute_type=int8, load_time_ms={load_time_ms:.2f}"
            )
            self._publish_status("Model loaded (CPU)")
            return self._model

        # Try GPU first
        gpu_ok, gpu_msg = self._check_gpu_memory()
        self._publish_status(gpu_msg)
        logger.debug(f"GPU memory check: gpu_ok={gpu_ok}, message={gpu_msg}")

        if gpu_ok:
            try:
                self._model = self.model_pool.get_model(
                    self.model_name,
                    "cuda",
                    self.compute_type,
                    self.download_root,
                )

                # Warmup and validate
                if self._warmup(self._model):
                    self._gpu_mode = f"cuda/{self.compute_type}"
                    self._runtime_device = "cuda"
                    load_time_ms = (time.perf_counter() - load_start_time) * 1000
                    logger.debug(
                        f"Model loaded on GPU: model_name={self.model_name}, "
                        f"device=cuda, compute_type={self.compute_type}, "
                        f"load_time_ms={load_time_ms:.2f}"
                    )

                    # Initialize CUDA streams
                    if self.cuda_manager.initialize():
                        self._publish_status("CUDA streams initialized")

                    self._publish_status("Model loaded (GPU)")
                    return self._model

                # Warmup failed, fall through to CPU
                if self.execution_mode == "gpu_only":
                    raise RuntimeError("GPU warm-up failed in gpu_only mode")

            except Exception as e:
                if self.execution_mode == "gpu_only":
                    raise
                self._warning = f"GPU load failed: {e}. Using CPU."
                self._publish_status(self._warning)
                logger.debug(
                    f"GPU load failed, falling back to CPU: model_name={self.model_name}, "
                    f"error={e}, previous_gpu_mode=cuda/{self.compute_type}"
                )

        # CPU fallback
        if self.execution_mode == "gpu_only":
            raise RuntimeError(gpu_msg)

        self._model = self.model_pool.get_model(
            self.model_name,
            "cpu",
            "int8",
            self.download_root,
        )
        self._gpu_mode = "cpu/int8"
        self._runtime_device = "cpu"
        load_time_ms = (time.perf_counter() - load_start_time) * 1000
        logger.debug(
            f"Model loaded on CPU (fallback): model_name={self.model_name}, "
            f"device=cpu, compute_type=int8, load_time_ms={load_time_ms:.2f}, "
            f"reason={'GPU-only mode enforced GPU failure' if self.execution_mode == 'gpu_only' else 'GPU warmup failed'}"
        )
        self._publish_status("Model loaded (CPU fallback)")
        return self._model

    def _warmup(self, model: WhisperModel) -> bool:
        """Warm up model with dummy inference."""
        try:
            dummy = np.zeros(16000, dtype=np.float32)
            segments, _ = model.transcribe(
                dummy,
                language=self.language_mode if self.language_mode != "auto" else "en",
                beam_size=1,
                temperature=0.0,
            )
            list(segments)
            return True
        except RuntimeError as e:
            if _should_fallback_to_cpu(e):
                return False
            raise

    def _run(self) -> None:
        """Main transcription worker loop."""
        try:
            model = self._initialize_model()
            self._publish_health(self._health_snapshot())

            # Create streaming transcriber
            self._transcriber = StreamingTranscriber(
                model=model,
                language_optimizer=self.language_optimizer,
                cuda_manager=self.cuda_manager,
                sample_rate=16000,
                streaming_window_ms=self.streaming_window_ms,
                streaming_overlap_ms=self.streaming_overlap_ms,
            )

            while not self._stop.is_set():
                try:
                    chunk = self._queue.get(timeout=0.1)
                except Empty:
                    continue

                chunk_duration = (
                    len(chunk.samples) / 16000.0
                    if hasattr(chunk, "samples") and chunk.samples is not None
                    else 0.0
                )
                queue_depth = self._queue.qsize()
                start_time = time.perf_counter()

                logger.debug(
                    f"Processing chunk: chunk_duration={chunk_duration:.3f}s, "
                    f"queue_depth={queue_depth}, device={self._runtime_device}, compute_type={self._gpu_mode}"
                )

                try:
                    safe_samples = np.nan_to_num(
                        np.clip(chunk.samples.astype(np.float32, copy=False), -1.0, 1.0),
                        nan=0.0,
                        posinf=1.0,
                        neginf=-1.0,
                    )
                    # Push audio to streaming transcriber
                    self._transcriber.push_audio(safe_samples, chunk.started_at)

                    # Process and yield results
                    partial_count = 0
                    final_count = 0
                    for partial in self._transcriber.process_stream(
                        language=self.language_mode if self.language_mode != "auto" else None,
                        yield_partial=True,
                    ):
                        partial_count += 1
                        self._publish_partial(partial)

                        if partial.is_final:
                            final_count += 1
                            segment = self._partial_to_segment(partial, chunk)
                            logger.debug(
                                f"Final segment produced: text_length={len(partial.text)}, "
                                f"detected_language={partial.language}, confidence={partial.confidence:.3f}, "
                                f"start_time={partial.start_time:.3f}, end_time={partial.end_time:.3f}"
                            )
                            for callback in self._segment_callbacks:
                                callback(segment)

                    logger.debug(
                        f"Chunk processed: partial_results={partial_count}, final_segments={final_count}, "
                        f"chunk_duration={chunk_duration:.3f}s"
                    )

                except RuntimeError as e:
                    if self._gpu_mode.startswith("cuda") and _should_fallback_to_cpu(e):
                        logger.debug(
                            f"GPU runtime error detected: error={e}, "
                            f"current_gpu_mode={self._gpu_mode}, switching_to_cpu_fallback"
                        )
                        if self.execution_mode == "gpu_only":
                            raise
                        self._handle_gpu_failure()
                    else:
                        raise

                # Track latency
                latency = time.perf_counter() - start_time
                latency_ms = latency * 1000
                self._processing_times.append(latency)
                self._chunks_processed += 1
                self._avg_latency_ms = (self._avg_latency_ms * 0.9) + (latency_ms * 0.1)

                logger.debug(
                    f"Transcription latency: inference_time_ms={latency_ms:.2f}, "
                    f"avg_latency_ms={self._avg_latency_ms:.2f}, chunk_duration={chunk_duration:.3f}s, "
                    f"device={self._runtime_device}"
                )

                self._publish_health(self._health_snapshot())

            # Flush remaining audio
            if self._transcriber:
                final = self._transcriber.flush()
                if final:
                    self._publish_partial(final)

        except Exception as e:
            for callback in self._error_callbacks:
                callback(e)

    def _partial_to_segment(
        self,
        partial: PartialResult,
        chunk: AudioChunk,
    ) -> TranscriptSegment:
        """Convert partial result to transcript segment with quality assessment."""
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

        previous_gpu_mode = self._gpu_mode
        self._publish_status("GPU failure detected, reloading on CPU...")
        logger.debug(
            f"GPU failure handling: previous_gpu_mode={previous_gpu_mode}, "
            f"switching_to=cpu/int8, model_name={self.model_name}"
        )

        # Cleanup GPU - synchronize streams first to prevent race conditions
        if HAS_TORCH and torch.cuda.is_available():
            # Ensure all CUDA streams are idle before releasing the model
            self.cuda_manager.synchronize_all()
            torch.cuda.synchronize()

        if self._model is not None:
            # Get the actual compute_type used when model was created
            actual_compute_type = self.compute_type if self._runtime_device == "cuda" else "int8"
            cache_key = f"{self.model_name}:cuda:{actual_compute_type}"
            self.model_pool.release_model(cache_key)
            self._model = None

        if HAS_TORCH and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

        # Reload on CPU
        reload_start = time.perf_counter()
        self._model = self.model_pool.get_model(
            self.model_name,
            "cpu",
            "int8",
            self.download_root,
        )
        reload_time_ms = (time.perf_counter() - reload_start) * 1000
        self._gpu_mode = "cpu/int8"
        self._runtime_device = "cpu"
        self._warning = "GPU failure. Switched to CPU fallback."

        logger.debug(
            f"GPU to CPU fallback complete: model_name={self.model_name}, "
            f"new_device=cpu, new_compute_type=int8, reload_time_ms={reload_time_ms:.2f}"
        )

        # Recreate transcriber with new model
        if self._transcriber:
            self._transcriber.model = self._model

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
            "model_pool": self.model_pool.get_pool_stats(),
            "gpu_mode": self._gpu_mode,
            "queue_depth": self._queue.qsize(),
        }

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        if self.cuda_manager:
            self.cuda_manager.synchronize_all()
        if self._model is not None:
            cache_key = f"{self.model_name}:{self._runtime_device}:"
            cache_key += self.compute_type if self._runtime_device == "cuda" else "int8"
            self.model_pool.release_model(cache_key)
            self._model = None
        # Clear language optimizer cache
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
    compute_type = "float16" if device != "cpu" else "int8"
    return FastWhisperBackend(
        model_name=model_name,
        download_root=download_root,
        device=device,
        compute_type=compute_type,
        language_mode=language_mode,
        execution_mode=execution_mode,
        streaming_window_ms=800,
        streaming_overlap_ms=160,
        num_cuda_streams=3,
    )


def create_low_latency_transcriber(
    model_name: str = "base",
    download_root: str = "./models",
    device: str = "auto",
    language_mode: str = "auto",
    execution_mode: str = "auto",
) -> FastWhisperBackend:
    """Create a transcriber optimized for low latency."""
    compute_type = "float16" if device != "cpu" else "int8"
    return FastWhisperBackend(
        model_name=model_name,
        download_root=download_root,
        device=device,
        compute_type=compute_type,
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
    compute_type = "float16" if device != "cpu" else "int8"
    return FastWhisperBackend(
        model_name=model_name,
        download_root=download_root,
        device=device,
        compute_type=compute_type,
        language_mode=language_mode,
        execution_mode=execution_mode,
        streaming_window_ms=1600,
        streaming_overlap_ms=320,
        num_cuda_streams=2,
    )


# Alias for backward compatibility
FastTranscriber = FastWhisperBackend
