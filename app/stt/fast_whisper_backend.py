"""Optimized faster-whisper backend with dual-mode support and adaptive inference.

This module provides a high-performance wrapper around faster-whisper with:
- INT8 quantization support
- Adaptive beam sizing based on latency targets
- Prefix-based context carryover
- Greedy decoding option for maximum speed
"""

from __future__ import annotations

import json
import logging
import time
import warnings
from collections.abc import Generator
from dataclasses import dataclass, field
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

ComputeType = Literal["int8", "float16", "float32"]
ModelSize = Literal[
    "tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "large-v3-turbo"
]


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


def normalize_suppress_tokens(value: Any) -> list[int] | None:
    """Normalize suppress_tokens into the format expected by faster-whisper."""
    if value is None:
        return None

    if isinstance(value, list):
        try:
            return [int(item) for item in value]
        except (TypeError, ValueError):
            logger.warning("Invalid suppress_tokens list %r; disabling token suppression", value)
            return None

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None

        try:
            if raw.startswith("[") and raw.endswith("]"):
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [int(item) for item in parsed]
                logger.warning(
                    "Invalid suppress_tokens JSON %r; disabling token suppression", value
                )
                return None

            return [int(part.strip()) for part in raw.split(",") if part.strip()]
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Invalid suppress_tokens string %r; disabling token suppression", value)
            return None

    logger.warning("Unsupported suppress_tokens value %r; disabling token suppression", value)
    return None


@dataclass(slots=True)
class InferenceConfig:
    """Configuration for a single inference pass."""

    beam_size: int = 1
    best_of: int = 1
    temperature: float = 0.0
    patience: float = 1.0
    length_penalty: float = 1.0
    suppress_tokens: list[int] | None = field(default_factory=lambda: [-1])
    condition_on_previous_text: bool = False
    compression_ratio_threshold: float = 2.4
    logprob_threshold: float = -1.0
    no_speech_threshold: float = 0.6
    initial_prompt: str | None = None
    prefix: str | None = None
    hotwords: str | None = None


@dataclass(slots=True)
class VADConfig:
    """Voice Activity Detection configuration."""

    threshold: float = 0.5
    min_silence_duration_ms: int = 200
    speech_pad_ms: int = 200
    min_speech_duration_ms: int = 250
    max_speech_duration_s: float = 30.0


@dataclass(slots=True)
class ModeConfig:
    """Configuration for a transcription mode (Wispr/System)."""

    model_size: ModelSize = "tiny"
    compute_type: ComputeType = "int8"
    target_latency_ms: float = 200.0
    max_latency_ms: float = 500.0
    beam_size: int = 1
    batch_size: int = 1
    use_vad: bool = True
    enable_prefix: bool = True
    adaptive_beam: bool = True


# Predefined mode configurations
WISPR_MODE = ModeConfig(
    model_size="tiny",
    compute_type="int8",
    target_latency_ms=150.0,
    max_latency_ms=200.0,
    beam_size=1,
    batch_size=1,
    use_vad=True,
    enable_prefix=True,
    adaptive_beam=True,
)

SYSTEM_MODE = ModeConfig(
    model_size="medium",
    compute_type="float16",
    target_latency_ms=500.0,
    max_latency_ms=1000.0,
    beam_size=5,
    batch_size=8,
    use_vad=True,
    enable_prefix=True,
    adaptive_beam=True,
)


@dataclass(slots=True)
class TranscriptionResult:
    """Result from transcription inference."""

    text: str
    language: str
    confidence: float
    start_time: float
    end_time: float
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    compression_ratio: float | None = None
    is_final: bool = False


@dataclass(slots=True)
class PerformanceMetrics:
    """Track inference performance metrics."""

    inference_count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    gpu_fallback_count: int = 0
    beam_adaptations: int = 0
    _latencies: list[float] = field(default_factory=list, repr=False)

    def record(self, latency_ms: float) -> None:
        """Record a latency measurement."""
        self.inference_count += 1
        self.total_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        self._latencies.append(latency_ms)

        # Keep only last 1000 measurements for percentile calculation
        if len(self._latencies) > 1000:
            self._latencies = self._latencies[-1000:]

        self.avg_latency_ms = self.total_latency_ms / self.inference_count

        if len(self._latencies) >= 20:
            sorted_latencies = sorted(self._latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p99_idx = int(len(sorted_latencies) * 0.99)
            self.p95_latency_ms = sorted_latencies[p95_idx]
            self.p99_latency_ms = sorted_latencies[p99_idx]

    def to_dict(self) -> dict[str, Any]:
        return {
            "inference_count": self.inference_count,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "gpu_fallback_count": self.gpu_fallback_count,
            "beam_adaptations": self.beam_adaptations,
        }


class AdaptiveBeamController:
    """Dynamically adjust beam size based on latency targets."""

    def __init__(
        self,
        target_latency_ms: float,
        max_latency_ms: float,
        min_beam: int = 1,
        max_beam: int = 5,
    ) -> None:
        self.target_latency_ms = target_latency_ms
        self.max_latency_ms = max_latency_ms
        self.min_beam = min_beam
        self.max_beam = max_beam
        self.current_beam = min_beam
        self._latency_history: list[float] = []
        self._max_history = 10

    def adapt(self, measured_latency_ms: float) -> int:
        """Adapt beam size based on measured latency."""
        self._latency_history.append(measured_latency_ms)
        if len(self._latency_history) > self._max_history:
            self._latency_history.pop(0)

        avg_latency = sum(self._latency_history) / len(self._latency_history)

        if avg_latency > self.max_latency_ms and self.current_beam > self.min_beam:
            self.current_beam = max(self.min_beam, self.current_beam - 1)
            logger.debug(
                f"Reducing beam size to {self.current_beam} (avg_latency={avg_latency:.1f}ms)"
            )
        elif avg_latency < self.target_latency_ms * 0.8 and self.current_beam < self.max_beam:
            self.current_beam = min(self.max_beam, self.current_beam + 1)
            logger.debug(
                f"Increasing beam size to {self.current_beam} (avg_latency={avg_latency:.1f}ms)"
            )

        return self.current_beam

    @property
    def beam_size(self) -> int:
        return self.current_beam


class PrefixContextManager:
    """Manages prefix-based context carryover between chunks."""

    def __init__(self, max_prefix_length: int = 100, enable_overlap: bool = True) -> None:
        self.max_prefix_length = max_prefix_length
        self.enable_overlap = enable_overlap
        self._previous_text: str = ""
        self._overlap_words: int = 3

    def get_prefix(self) -> str | None:
        """Get prefix from previous transcription for context carryover."""
        if not self._previous_text or not self.enable_overlap:
            return None

        # Take last N words as prefix
        words = self._previous_text.split()
        if len(words) <= self._overlap_words:
            prefix = self._previous_text
        else:
            prefix = " ".join(words[-self._overlap_words :])

        # Truncate if too long
        if len(prefix) > self.max_prefix_length:
            prefix = prefix[-self.max_prefix_length :]

        return prefix

    def update(self, text: str, is_final: bool = True) -> None:
        """Update context with new transcription."""
        if is_final:
            self._previous_text = text
        else:
            # For partial results, only update if significantly different
            if len(text) > len(self._previous_text) * 1.2:
                self._previous_text = text

    def clear(self) -> None:
        """Clear the context."""
        self._previous_text = ""


class FastWhisperBackend:
    """Optimized faster-whisper backend with adaptive inference."""

    def __init__(
        self,
        model: WhisperModel,
        mode_config: ModeConfig,
        device: str = "cuda",
        sample_rate: int = 16000,
        language: str | None = None,
        enable_adaptive_beam: bool = True,
    ) -> None:
        self.model = model
        self.mode_config = mode_config
        self.device = device
        self.sample_rate = sample_rate
        self.language = language
        self.enable_adaptive_beam = enable_adaptive_beam

        # Components
        self.prefix_manager = PrefixContextManager() if mode_config.enable_prefix else None
        self.beam_controller: AdaptiveBeamController | None = None

        if enable_adaptive_beam and mode_config.adaptive_beam:
            self.beam_controller = AdaptiveBeamController(
                target_latency_ms=mode_config.target_latency_ms,
                max_latency_ms=mode_config.max_latency_ms,
                min_beam=1,
                max_beam=mode_config.beam_size,
            )

        # Metrics
        self.metrics = PerformanceMetrics()

        # VAD config
        self.vad_config = VADConfig()

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = None,
        prefix: str | None = None,
        hotwords: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio with optimized settings."""
        start_time = time.perf_counter()

        # Get adaptive beam size
        beam_size = (
            self.beam_controller.beam_size if self.beam_controller else self.mode_config.beam_size
        )

        # Get prefix if enabled
        if prefix is None and self.prefix_manager:
            prefix = self.prefix_manager.get_prefix()

        # Build inference config
        config = InferenceConfig(
            beam_size=beam_size,
            best_of=1 if beam_size == 1 else beam_size,
            temperature=0.0,
            patience=1.0,
            length_penalty=1.0,
            suppress_tokens=normalize_suppress_tokens("-1"),
            condition_on_previous_text=False,
            prefix=prefix,
            hotwords=hotwords,
        )

        try:
            segments, info = self.model.transcribe(
                audio,
                language=language or self.language,
                beam_size=config.beam_size,
                best_of=config.best_of,
                temperature=config.temperature,
                patience=config.patience,
                length_penalty=config.length_penalty,
                suppress_tokens=normalize_suppress_tokens(config.suppress_tokens),
                condition_on_previous_text=config.condition_on_previous_text,
                prefix=config.prefix,
                hotwords=config.hotwords,
                vad_filter=self.mode_config.use_vad,
                vad_parameters={
                    "threshold": self.vad_config.threshold,
                    "min_silence_duration_ms": self.vad_config.min_silence_duration_ms,
                    "speech_pad_ms": self.vad_config.speech_pad_ms,
                    "min_speech_duration_ms": self.vad_config.min_speech_duration_ms,
                    "max_speech_duration_s": self.vad_config.max_speech_duration_s,
                },
                word_timestamps=False,
            )

            # Collect results
            texts = []
            total_confidence = 0.0
            count = 0
            start_ts = 0.0
            end_ts = 0.0
            last_segment = None

            for segment in segments:
                text = segment.text.strip()
                if text:
                    texts.append(text)
                    total_confidence += confidence_proxy(segment)
                    count += 1
                    if count == 1:
                        start_ts = segment.start
                    end_ts = segment.end
                    last_segment = segment

            full_text = " ".join(texts)
            avg_confidence = total_confidence / count if count > 0 else 0.0
            detected_language = getattr(info, "language", language or self.language or "auto")

            latency_ms = (time.perf_counter() - start_time) * 1000
            self.metrics.record(latency_ms)

            # Adapt beam size for next inference
            if self.beam_controller:
                self.beam_controller.adapt(latency_ms)
                self.metrics.beam_adaptations += 1

            # Update prefix context
            if self.prefix_manager and full_text:
                self.prefix_manager.update(full_text, is_final=True)

            logger.debug(
                f"Transcription complete: text_length={len(full_text)}, "
                f"latency_ms={latency_ms:.2f}, beam_size={beam_size}, "
                f"language={detected_language}, confidence={avg_confidence:.3f}"
            )

            return TranscriptionResult(
                text=full_text,
                language=detected_language,
                confidence=avg_confidence,
                start_time=start_ts,
                end_time=end_ts,
                avg_logprob=getattr(last_segment, "avg_logprob", None) if last_segment else None,
                no_speech_prob=getattr(last_segment, "no_speech_prob", None)
                if last_segment
                else None,
                compression_ratio=getattr(last_segment, "compression_ratio", None)
                if last_segment
                else None,
                is_final=True,
            )

        except RuntimeError as e:
            if _should_fallback_to_cpu(e):
                raise GPURuntimeError(f"GPU inference failed: {e}") from e
            raise

    def transcribe_batch(
        self,
        audio_batch: list[np.ndarray],
        language: str | None = None,
    ) -> list[TranscriptionResult]:
        """Batch transcribe multiple audio segments (System mode optimization)."""
        if not audio_batch:
            return []

        results = []
        for audio in audio_batch:
            result = self.transcribe(audio, language=language)
            results.append(result)

        return results

    def transcribe_streaming(
        self,
        audio: np.ndarray,
        chunk_duration_ms: int = 400,
        overlap_ms: int = 80,
        language: str | None = None,
    ) -> Generator[TranscriptionResult, None, None]:
        """Streaming transcription with partial results."""
        chunk_samples = int(self.sample_rate * chunk_duration_ms / 1000)
        overlap_samples = int(self.sample_rate * overlap_ms / 1000)
        step_samples = chunk_samples - overlap_samples

        for i in range(0, len(audio), step_samples):
            chunk = audio[i : i + chunk_samples]
            if len(chunk) < chunk_samples // 2:
                break

            result = self.transcribe(chunk, language=language)
            result.is_final = (i + chunk_samples) >= len(audio)
            yield result

    def warmup(self) -> bool:
        """Warm up the model with dummy inference."""
        try:
            dummy = np.zeros(self.sample_rate, dtype=np.float32)
            segments, _info = self.model.transcribe(
                dummy,
                language=self.language,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                suppress_tokens=normalize_suppress_tokens("-1"),
                condition_on_previous_text=False,
                vad_filter=False,
                word_timestamps=False,
            )
            list(segments)
            logger.info("Model warmup complete")
            return True
        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")
            return False

    def reset_context(self) -> None:
        """Reset transcription context."""
        if self.prefix_manager:
            self.prefix_manager.clear()

    def get_metrics(self) -> dict[str, Any]:
        """Get performance metrics."""
        return {
            "mode": "wispr" if self.mode_config.model_size == "tiny" else "system",
            "model_size": self.mode_config.model_size,
            "beam_size": self.beam_controller.beam_size
            if self.beam_controller
            else self.mode_config.beam_size,
            **self.metrics.to_dict(),
        }


class GPURuntimeError(RuntimeError):
    """Exception indicating GPU runtime failure."""

    pass


class OptimizedWhisperFactory:
    """Factory for creating optimized Whisper backends."""

    @staticmethod
    def create_backend(
        mode: Literal["wispr", "system"],
        model_pool: Any,
        download_root: str,
        device: str = "cuda",
        language: str | None = None,
        model_name: str | None = None,
    ) -> FastWhisperBackend:
        """Create an optimized backend for the specified mode."""
        mode_config = WISPR_MODE if mode == "wispr" else SYSTEM_MODE
        resolved_model_name = model_name or mode_config.model_size

        model = model_pool.get_model(
            model_name=resolved_model_name,
            device=device,
            compute_type=mode_config.compute_type,
            download_root=download_root,
        )

        return FastWhisperBackend(
            model=model,
            mode_config=mode_config,
            device=device,
            language=language,
            enable_adaptive_beam=mode_config.adaptive_beam,
        )

    @staticmethod
    def create_wispr_backend(
        model_pool: Any,
        download_root: str,
        device: str = "cuda",
        language: str | None = None,
    ) -> FastWhisperBackend:
        """Create a Wispr-optimized backend (<200ms target)."""
        return OptimizedWhisperFactory.create_backend(
            mode="wispr",
            model_pool=model_pool,
            download_root=download_root,
            device=device,
            language=language,
        )

    @staticmethod
    def create_system_backend(
        model_pool: Any,
        download_root: str,
        device: str = "cuda",
        language: str | None = None,
    ) -> FastWhisperBackend:
        """Create a System-optimized backend (<1s target)."""
        return OptimizedWhisperFactory.create_backend(
            mode="system",
            model_pool=model_pool,
            download_root=download_root,
            device=device,
            language=language,
        )
