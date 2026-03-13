from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Full, Queue
from typing import Any

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

try:
    import torch as torch  # type: ignore[no-redef]
except ImportError:
    torch = None

from app.core.constants import GPU_FALLBACK_KEYWORDS, ModelConstants, QualityConstants
from app.core.models import SessionHealth, TranscriptSegment, utc_now
from app.stt.chunker import AudioChunk
from app.stt.quality import assess_segment_quality


@dataclass
class SubmitStatus:
    """Detailed status returned from submit() for flow control decisions."""

    accepted: bool
    queue_depth: int
    dropped_chunks: int
    backpressure_state: str
    estimated_backlog_seconds: float
    max_queue_size: int


class WhisperTranscriber:
    def __init__(
        self,
        *,
        model_name: str,
        download_root: str,
        device: str,
        compute_type: str,
        beam_size: int,
        best_of: int,
        temperature: float,
        vad_filter: bool,
        language_mode: str,
        execution_mode: str,
        max_queue_items: int,
        vad_params: dict[str, Any] | None = None,
    ) -> None:
        self.model_name = model_name
        self.download_root = download_root
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.best_of = best_of
        self.temperature = temperature
        self.vad_filter = vad_filter
        self.language_mode = language_mode
        self.execution_mode = execution_mode
        self.vad_params = vad_params or {}
        self._segment_callbacks: list[Callable[[TranscriptSegment], None]] = []
        self._error_callbacks: list[Callable[[Exception], None]] = []
        self._health_callbacks: list[Callable[[SessionHealth], None]] = []
        self._status_callbacks: list[Callable[[str], None]] = []
        self._queue: Queue[AudioChunk] = Queue(maxsize=max_queue_items)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._model: WhisperModel | None = None
        self._gpu_mode = "unknown"
        self._runtime_device = "unknown"
        self._dropped_chunks = 0
        self._backpressure_state = "normal"
        self._max_queue_items = max_queue_items
        self._warning: str | None = (
            "Auto language detection may increase latency and hallucinations."
            if self.language_mode == "auto"
            else None
        )
        # Metrics for backlog estimation
        self._processing_times: list[float] = []
        self._processing_times_lock = threading.Lock()
        self._chunks_processed = 0
        self._avg_chunk_duration = 5.0  # Default estimate: 5 seconds per chunk

        logger.debug(
            f"WhisperTranscriber initialized: model_name={model_name}, device={device}, "
            f"compute_type={compute_type}, language_mode={language_mode}, "
            f"execution_mode={execution_mode}, max_queue_items={max_queue_items}"
        )

    def add_segment_callback(self, callback: Callable[[TranscriptSegment], None]) -> None:
        self._segment_callbacks.append(callback)

    def add_error_callback(self, callback: Callable[[Exception], None]) -> None:
        self._error_callbacks.append(callback)

    def add_health_callback(self, callback: Callable[[SessionHealth], None]) -> None:
        self._health_callbacks.append(callback)

    def add_status_callback(self, callback: Callable[[str], None]) -> None:
        self._status_callbacks.append(callback)

    def _publish_status(self, message: str) -> None:
        for callback in self._status_callbacks:
            callback(message)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.debug("Transcriber start requested but already running")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="stt-worker", daemon=True)
        self._thread.start()
        logger.debug(
            f"Transcriber started: model_name={self.model_name}, "
            f"thread_name=stt-worker, daemon=True"
        )

    def validate_runtime(self) -> None:
        model = self._load_model()
        probe = np.zeros(1600, dtype=np.float32)
        try:
            segments, _ = model.transcribe(
                probe,
                language="en",
                vad_filter=False,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                word_timestamps=False,
            )
            list(segments)
        except RuntimeError as exc:
            if (
                self.execution_mode == "gpu_only" or self._gpu_mode.startswith("cuda")
            ) and _should_fallback_to_cpu(exc):
                if self.execution_mode == "gpu_only":
                    raise RuntimeError(
                        "GPU-only mode requested, but CUDA runtime validation failed. "
                        "Install the CUDA 12 runtime and ensure cublas64_12.dll is on PATH."
                    ) from exc
                self._reload_cpu_model()
            else:
                raise

    def stop(self) -> None:
        logger.debug("Transcriber stop requested")
        self._stop.set()
        if self._thread:
            joined = self._thread.join(timeout=5)
            logger.debug(f"Transcriber stopped: thread_joined={self._thread.is_alive() is False}")

    def submit(self, chunk: AudioChunk) -> bool:
        chunk_duration = (
            len(chunk.samples) / 16000.0
            if hasattr(chunk, "samples") and chunk.samples is not None
            else 0.0
        )
        queue_depth_before = self._queue.qsize()

        if self._stop.is_set():
            logger.debug(
                f"Chunk submission rejected (stopped): chunk_duration={chunk_duration:.3f}s, "
                f"queue_depth={queue_depth_before}"
            )
            return False
        try:
            self._queue.put_nowait(chunk)
            self._backpressure_state = "normal"
            logger.debug(
                f"Chunk submitted: chunk_duration={chunk_duration:.3f}s, "
                f"queue_depth={self._queue.qsize()}, backpressure_state=normal, accepted=True"
            )
            return True
        except Full:
            self._dropped_chunks += 1
            previous_state = self._backpressure_state
            self._backpressure_state = "dropping_oldest"
            logger.debug(
                f"Queue full, attempting eviction: chunk_duration={chunk_duration:.3f}s, "
                f"queue_depth={queue_depth_before}, backpressure_state_change={previous_state}->dropping_oldest, "
                f"total_dropped={self._dropped_chunks}"
            )
            try:
                self._queue.get_nowait()
                logger.debug("Evicted oldest chunk from queue")
            except Empty:
                self._warning = "STT queue saturated; dropping newest audio chunk."
                logger.debug(
                    f"Queue empty after eviction attempt: chunk_duration={chunk_duration:.3f}s, "
                    f"backpressure_state=dropping_newest"
                )
                self._publish_health(
                    self._health_snapshot(queue_depth=self._queue.qsize(), state="dropping_newest")
                )
                return False
            try:
                self._queue.put_nowait(chunk)
                logger.debug(
                    f"Chunk accepted after eviction: chunk_duration={chunk_duration:.3f}s, "
                    f"queue_depth={self._queue.qsize()}, backpressure_state=dropping_oldest"
                )
            except Full:
                self._warning = (
                    "STT queue remained full after eviction; dropping newest audio chunk."
                )
                logger.debug(
                    f"Queue still full after eviction: chunk_duration={chunk_duration:.3f}s, "
                    f"backpressure_state=dropping_newest"
                )
                self._publish_health(
                    self._health_snapshot(queue_depth=self._queue.qsize(), state="dropping_newest")
                )
                return False
            self._warning = "STT is behind real time; dropping older audio to keep captions fresh."
            self._publish_health(self._health_snapshot(queue_depth=self._queue.qsize()))
            return True

    def _check_gpu_memory(self) -> tuple[bool, str]:
        """Check if GPU has enough memory for the model."""
        try:
            if torch is None or not torch.cuda.is_available():
                return False, "CUDA not available"

            required_gb = ModelConstants.MEMORY_REQUIREMENTS_GB.get(self.model_name, 2.0)
            if self.compute_type == "int8":
                required_gb *= ModelConstants.INT8_MEMORY_MULTIPLIER  # int8 uses less memory

            total_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            reserved_memory = torch.cuda.memory_reserved(0) / (1024**3)
            available_memory = total_memory - reserved_memory

            if available_memory < required_gb:
                return (
                    False,
                    f"GPU memory insufficient: {available_memory:.1f}GB available, {required_gb:.1f}GB required",
                )

            return True, f"GPU memory OK: {available_memory:.1f}GB available"
        except Exception as e:
            return False, f"GPU memory check failed: {e}"

    def _load_model(self) -> WhisperModel:
        if self._model is None:
            self._publish_status(f"Loading {self.model_name} model...")
            load_start_time = time.perf_counter()
            logger.debug(
                f"Starting model load: model_name={self.model_name}, "
                f"requested_device={self.device}, compute_type={self.compute_type}"
            )
            if self.execution_mode == "cpu_only" or self.device == "cpu":
                self._model = WhisperModel(
                    self.model_name,
                    device="cpu",
                    compute_type="int8",
                    download_root=self.download_root,
                )
                self._gpu_mode = "cpu/int8"
                self._runtime_device = "cpu"
                load_time_ms = (time.perf_counter() - load_start_time) * 1000
                logger.debug(
                    f"Model loaded on CPU (cpu_only mode): model_name={self.model_name}, "
                    f"device=cpu, compute_type=int8, load_time_ms={load_time_ms:.2f}"
                )
            else:
                # Check GPU memory before attempting load
                self._publish_status("Checking GPU memory...")
                gpu_ok, gpu_msg = self._check_gpu_memory()
                logger.debug(f"GPU memory check: gpu_ok={gpu_ok}, message={gpu_msg}")
                if not gpu_ok:
                    self._warning = f"{gpu_msg}. Using CPU fallback."
                    self._publish_status("Switching to CPU fallback...")
                    if self.execution_mode == "gpu_only":
                        raise RuntimeError(f"GPU-only mode requested but {gpu_msg}")
                    self._model = WhisperModel(
                        self.model_name,
                        device="cpu",
                        compute_type="int8",
                        download_root=self.download_root,
                    )
                    self._gpu_mode = "cpu/int8"
                    self._runtime_device = "cpu"
                    load_time_ms = (time.perf_counter() - load_start_time) * 1000
                    logger.debug(
                        f"Model loaded on CPU (GPU memory insufficient): model_name={self.model_name}, "
                        f"device=cpu, compute_type=int8, load_time_ms={load_time_ms:.2f}, reason={gpu_msg}"
                    )
                else:
                    try:
                        self._model = WhisperModel(
                            self.model_name,
                            device="cuda",
                            compute_type=self.compute_type,
                            download_root=self.download_root,
                        )
                        # Warm-up to validate GPU execution
                        if not self._warmup_gpu(self._model):
                            if self.execution_mode == "gpu_only":
                                raise RuntimeError("GPU-only mode requested but GPU warm-up failed")
                            self._publish_status("Switching to CPU fallback...")
                            self._model = WhisperModel(
                                self.model_name,
                                device="cpu",
                                compute_type="int8",
                                download_root=self.download_root,
                            )
                            self._gpu_mode = "cpu/int8"
                            self._runtime_device = "cpu"
                            self._warning = "GPU warm-up failed. Running on CPU fallback."
                            load_time_ms = (time.perf_counter() - load_start_time) * 1000
                            logger.debug(
                                f"Model loaded on CPU (GPU warmup failed): model_name={self.model_name}, "
                                f"device=cpu, compute_type=int8, load_time_ms={load_time_ms:.2f}"
                            )
                        else:
                            self._gpu_mode = f"cuda/{self.compute_type}"
                            self._runtime_device = "cuda"
                            load_time_ms = (time.perf_counter() - load_start_time) * 1000
                            logger.debug(
                                f"Model loaded on GPU: model_name={self.model_name}, "
                                f"device=cuda, compute_type={self.compute_type}, load_time_ms={load_time_ms:.2f}"
                            )
                    except Exception as e:
                        if self.execution_mode == "gpu_only":
                            raise
                        self._publish_status("Switching to CPU fallback...")
                        logger.debug(
                            f"GPU load failed with exception, falling back to CPU: model_name={self.model_name}, "
                            f"error={e}"
                        )
                        self._model = WhisperModel(
                            self.model_name,
                            device="cpu",
                            compute_type="int8",
                            download_root=self.download_root,
                        )
                        self._gpu_mode = "cpu/int8"
                        self._runtime_device = "cpu"
                        self._warning = "GPU unavailable. Running on CPU fallback."
                        load_time_ms = (time.perf_counter() - load_start_time) * 1000
                        logger.debug(
                            f"Model loaded on CPU (exception fallback): model_name={self.model_name}, "
                            f"device=cpu, compute_type=int8, load_time_ms={load_time_ms:.2f}, error={e}"
                        )
            self._publish_status("Model loaded successfully")
        return self._model

    def _reload_cpu_model(self) -> WhisperModel:
        """Reload model on CPU with proper GPU cleanup.

        In gpu_only mode, this method must not be called - failures must propagate.
        """
        if self.execution_mode == "gpu_only":
            raise RuntimeError(
                "GPU-only mode requested, but CUDA runtime failed during transcription. "
                "Install the CUDA 12 runtime and ensure cublas64_12.dll is on PATH."
            )

        previous_gpu_mode = self._gpu_mode
        logger.debug(
            f"Reloading model on CPU (runtime GPU failure): model_name={self.model_name}, "
            f"previous_gpu_mode={previous_gpu_mode}, switching_to=cpu/int8"
        )
        reload_start = time.perf_counter()

        self._cleanup_gpu_resources()
        self._model = WhisperModel(
            self.model_name,
            device="cpu",
            compute_type="int8",
            download_root=self.download_root,
        )
        self._gpu_mode = "cpu/int8"
        self._runtime_device = "cpu"
        self._warning = "GPU runtime failed during transcription. Running on CPU fallback."

        reload_time_ms = (time.perf_counter() - reload_start) * 1000
        logger.debug(
            f"Model reloaded on CPU: model_name={self.model_name}, "
            f"device=cpu, compute_type=int8, reload_time_ms={reload_time_ms:.2f}"
        )
        return self._model

    def _cleanup_gpu_resources(self) -> None:
        """Safely release GPU resources without hard dependency on torch.

        Handles case where torch is not installed or CUDA is unavailable.
        """
        if self._model is not None:
            del self._model
            self._model = None

        try:
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception as e:
            logger.warning(f"Failed to cleanup GPU resources: {e}")

    def cleanup(self) -> None:
        """Public cleanup method for safe resource disposal."""
        self._cleanup_gpu_resources()

    def _warmup_gpu(self, model: WhisperModel) -> bool:
        """Run dummy inference to validate GPU execution."""
        try:
            dummy_audio = np.zeros(16000, dtype=np.float32)
            segments, _ = model.transcribe(
                dummy_audio,
                language=self.language_mode if self.language_mode != "auto" else "en",
            )
            list(segments)
            return True
        except RuntimeError as exc:
            if _should_fallback_to_cpu(exc):
                return False
            raise

    def _run(self) -> None:
        try:
            model = self._load_model()
            self._publish_health(self._health_snapshot(queue_depth=self._queue.qsize()))
            logger.debug(
                f"Transcription loop started: device={self._runtime_device}, compute_type={self._gpu_mode}"
            )
            while not self._stop.is_set():
                try:
                    chunk = self._queue.get(timeout=0.25)
                except Empty:
                    continue
                chunk_duration = (
                    len(chunk.samples) / 16000.0
                    if hasattr(chunk, "samples") and chunk.samples is not None
                    else 0.0
                )
                queue_depth = self._queue.qsize()
                inference_start = time.perf_counter()
                logger.debug(
                    f"Processing chunk: chunk_duration={chunk_duration:.3f}s, "
                    f"queue_depth={queue_depth}, device={self._runtime_device}, compute_type={self._gpu_mode}"
                )
                try:
                    transcribe_kwargs: dict[str, Any] = {
                        "language": None if self.language_mode == "auto" else self.language_mode,
                        "vad_filter": self.vad_filter,
                        "beam_size": self.beam_size,
                        "best_of": self.best_of,
                        "temperature": self.temperature,
                        "word_timestamps": False,
                    }
                    if self.vad_filter and self.vad_params:
                        vad_parameters: dict[str, Any] = {}
                        if self.vad_params.get("vad_threshold") is not None:
                            vad_parameters["threshold"] = self.vad_params["vad_threshold"]
                        if self.vad_params.get("vad_min_silence_ms") is not None:
                            vad_parameters["min_silence_duration_ms"] = self.vad_params[
                                "vad_min_silence_ms"
                            ]
                        if self.vad_params.get("vad_speech_pad_ms") is not None:
                            vad_parameters["speech_pad_ms"] = self.vad_params["vad_speech_pad_ms"]
                        if vad_parameters:
                            transcribe_kwargs["vad_parameters"] = vad_parameters
                    segments, info = model.transcribe(chunk.samples, **transcribe_kwargs)
                except RuntimeError as exc:
                    if self._gpu_mode.startswith("cuda") and _should_fallback_to_cpu(exc):
                        logger.debug(
                            f"GPU runtime error during transcription: error={exc}, "
                            f"current_gpu_mode={self._gpu_mode}, switching_to_cpu_fallback"
                        )
                        if self.execution_mode == "gpu_only":
                            raise
                        model = self._reload_cpu_model()
                        self._publish_health(self._health_snapshot(queue_depth=self._queue.qsize()))
                        segments, info = model.transcribe(chunk.samples, **transcribe_kwargs)
                    else:
                        raise
                inference_time_ms = (time.perf_counter() - inference_start) * 1000
                detected_language = getattr(info, "language", self.language_mode)
                segment_count = 0
                for item in segments:
                    text = item.text.strip()
                    if not text:
                        continue
                    segment_count += 1
                    confidence = confidence_proxy(item)
                    logger.debug(
                        f"Segment produced: text_length={len(text)}, detected_language={detected_language}, "
                        f"confidence={confidence:.3f}, start={item.start:.3f}, end={item.end:.3f}"
                    )
                    quality = assess_segment_quality(
                        text,
                        confidence=confidence,
                        language_mode=self.language_mode,
                        detected_language=detected_language,
                        avg_logprob=getattr(item, "avg_logprob", None),
                        no_speech_prob=getattr(item, "no_speech_prob", None),
                        compression_ratio=getattr(item, "compression_ratio", None),
                    )
                    segment = TranscriptSegment(
                        id=f"seg-{int(chunk.started_at * 1000)}-{int(item.start * 1000)}",
                        start=chunk.started_at + float(item.start),
                        end=chunk.started_at + float(item.end),
                        text=text,
                        display_text=quality.display_text,
                        language=detected_language,
                        avg_logprob=getattr(item, "avg_logprob", None),
                        no_speech_prob=getattr(item, "no_speech_prob", None),
                        compression_ratio=getattr(item, "compression_ratio", None),
                        confidence=confidence,
                        source_chunk_started_at=chunk.started_at,
                        review_flag=quality.suppressed,
                        review_reasons=list(quality.suppression_reasons),
                        suppressed=quality.suppressed,
                        suppression_reasons=quality.suppression_reasons,
                        quality_label=quality.quality_label,
                        script_mismatch=quality.script_mismatch,
                    )
                    for callback in self._segment_callbacks:
                        callback(segment)
                total_time_ms = (time.perf_counter() - inference_start) * 1000
                logger.debug(
                    f"Transcription complete: segments_produced={segment_count}, "
                    f"detected_language={detected_language}, inference_time_ms={inference_time_ms:.2f}, "
                    f"total_processing_time_ms={total_time_ms:.2f}, chunk_duration={chunk_duration:.3f}s, "
                    f"device={self._runtime_device}"
                )
                self._publish_health(
                    self._health_snapshot(
                        last_transcript_at=utc_now(),
                        queue_depth=self._queue.qsize(),
                    )
                )
        except Exception as exc:
            logger.debug(f"Transcription loop error: error={exc}, gpu_mode={self._gpu_mode}")
            for callback in self._error_callbacks:
                callback(exc)

    def _publish_health(self, health: SessionHealth) -> None:
        logger.debug(
            f"Health update: gpu_mode={health.gpu_mode}, execution_mode={health.execution_mode}, "
            f"model_runtime_device={health.model_runtime_device}, queue_depth={health.queue_depth}, "
            f"dropped_stt_chunks={health.dropped_stt_chunks}, stt_backpressure_state={health.stt_backpressure_state}"
        )
        for callback in self._health_callbacks:
            callback(health)

    def _health_snapshot(
        self,
        *,
        last_transcript_at=None,
        queue_depth: int,
        state: str | None = None,
    ) -> SessionHealth:
        return SessionHealth(
            audio_stream_active=True,
            gpu_mode=self._gpu_mode,
            execution_mode=self.execution_mode,
            model_runtime_device=self._runtime_device,
            last_transcript_at=last_transcript_at,
            queue_depth=queue_depth,
            dropped_stt_chunks=self._dropped_chunks,
            stt_backpressure_state=state or self._backpressure_state,
            last_warning=self._warning,
        )


def _should_fallback_to_cpu(exc: RuntimeError) -> bool:
    text = str(exc).lower()
    return any(kw in text for kw in GPU_FALLBACK_KEYWORDS)


def confidence_proxy(raw_segment: Any) -> float:
    avg_logprob = getattr(raw_segment, "avg_logprob", None)
    no_speech_prob = getattr(raw_segment, "no_speech_prob", None)
    compression_ratio = getattr(raw_segment, "compression_ratio", None)

    score = QualityConstants.CONFIDENCE_PROXY_BASE
    if avg_logprob is not None:
        score += max(
            min(
                (avg_logprob + QualityConstants.CONFIDENCE_PROXY_AVG_LOGPROB_OFFSET)
                / QualityConstants.CONFIDENCE_PROXY_AVG_LOGPROB_SCALE,
                QualityConstants.CONFIDENCE_PROXY_MAX_BONUS,
            ),
            -QualityConstants.CONFIDENCE_PROXY_MAX_PENALTY,
        )
    if no_speech_prob is not None:
        score -= (
            min(max(no_speech_prob, 0.0), 1.0) * QualityConstants.CONFIDENCE_PROXY_NO_SPEECH_SCALE
        )
    if (
        compression_ratio is not None
        and compression_ratio > QualityConstants.CONFIDENCE_PROXY_COMPRESSION_THRESHOLD
    ):
        score -= min(
            (compression_ratio - QualityConstants.CONFIDENCE_PROXY_COMPRESSION_THRESHOLD)
            * QualityConstants.CONFIDENCE_PROXY_COMPRESSION_PENALTY_SCALE,
            QualityConstants.CONFIDENCE_PROXY_COMPRESSION_MAX_PENALTY,
        )
    return max(0.0, min(score, QualityConstants.CONFIDENCE_PROXY_MAX_SCORE))
