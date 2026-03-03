from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np

sys.modules.setdefault("faster_whisper", SimpleNamespace(WhisperModel=object))

from app.stt.chunker import AudioChunk
from app.stt.fast_engine import FastWhisperBackend
from app.stt.streaming_engine import PerformanceMetrics


def test_performance_metrics_record_alias_updates_latency_fields() -> None:
    metrics = PerformanceMetrics()

    metrics.record(123.0)
    metrics.record(77.0)

    assert metrics.chunks_processed == 2
    assert metrics.first_word_latency_ms == 123.0
    assert metrics.avg_chunk_latency_ms > 0.0
    assert metrics.p95_latency_ms >= 123.0


def test_fast_engine_worker_loop_survives_metrics_failure() -> None:
    engine = FastWhisperBackend(
        model_name="small",
        download_root=".",
        device="cpu",
        compute_type="int8",
        language_mode="en",
        execution_mode="cpu_only",
    )

    errors: list[Exception] = []
    processed_segments: list[str] = []

    class FakeBackend:
        def transcribe(self, _audio: np.ndarray, **_kwargs: object):
            return SimpleNamespace(
                text="hello world",
                start_time=0.0,
                end_time=0.5,
                language="en",
                confidence=0.9,
            )

    class ExplodingMetrics:
        def record(self, _latency_ms: float) -> None:
            raise RuntimeError("metrics boom")

        def to_dict(self) -> dict[str, float]:
            return {}

    engine._adaptive_beam = None
    engine._context_manager = None
    engine._performance_metrics = ExplodingMetrics()
    engine._initialize_backend = lambda: FakeBackend()  # type: ignore[method-assign]
    engine.add_error_callback(errors.append)
    engine.add_segment_callback(
        lambda segment: (
            processed_segments.append(segment.text),
            engine._stop.set(),
        )
    )

    engine._queue.put(
        AudioChunk(started_at=0.0, duration=0.5, samples=np.zeros(8000, dtype=np.float32))
    )

    engine._run()

    assert processed_segments == ["hello world"]
    assert errors == []
