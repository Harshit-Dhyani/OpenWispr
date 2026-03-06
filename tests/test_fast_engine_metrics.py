from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.modules.setdefault("faster_whisper", SimpleNamespace(WhisperModel=object))

from app.stt.chunker import AudioChunk
from app.stt.fast_engine import FastWhisperBackend, PartialResult
from app.stt.fast_whisper_backend import WISPR_MODE
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
                text="project status update",
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

    assert processed_segments == ["project status update"]
    assert errors == []


def test_fast_engine_segment_times_are_rebased_to_chunk_offset() -> None:
    engine = FastWhisperBackend(
        model_name="small",
        download_root=".",
        device="cpu",
        compute_type="int8",
        language_mode="en",
        execution_mode="cpu_only",
    )

    partial = PartialResult(
        text="hello there",
        is_final=True,
        is_stable=True,
        start_time=0.0,
        end_time=0.85,
        language="en",
        confidence=0.91,
    )
    chunk = AudioChunk(
        started_at=1.70,
        duration=0.85,
        samples=np.zeros(13600, dtype=np.float32),
    )

    segment = engine._create_segment(partial, chunk)

    assert segment.start == 1.70
    assert segment.end == 2.55
    assert segment.source_chunk_started_at == 1.70


def test_fast_engine_rejects_repetitive_compression_loop() -> None:
    engine = FastWhisperBackend(
        model_name="small",
        download_root=".",
        device="cpu",
        compute_type="int8",
        language_mode="en",
        execution_mode="cpu_only",
    )

    suspect = SimpleNamespace(
        text="Testing the microphone. Testing the microphone. Testing the microphone. Testing the microphone.",
        compression_ratio=8.025,
        avg_logprob=-1.1,
        no_speech_prob=0.08,
    )

    assert engine._should_reject_result(suspect) is True


def test_fast_engine_keeps_normal_sentence() -> None:
    engine = FastWhisperBackend(
        model_name="small",
        download_root=".",
        device="cpu",
        compute_type="int8",
        language_mode="en",
        execution_mode="cpu_only",
    )

    normal = SimpleNamespace(
        text="Okay, so I am testing the microphone path with a longer sample sentence.",
        compression_ratio=1.7,
        avg_logprob=-0.3,
        no_speech_prob=0.02,
    )

    assert engine._should_reject_result(normal) is False


def test_fast_engine_hotkey_profile_uses_wispr_mode_for_non_tiny_model() -> None:
    engine = FastWhisperBackend(
        model_name="small",
        download_root=".",
        device="cpu",
        compute_type="int8",
        language_mode="en",
        execution_mode="cpu_only",
        vad_filter=False,
    )

    assert engine._is_hotkey_streaming is True
    assert engine._mode_config == WISPR_MODE
    assert engine.streaming_window_ms >= 2400
    assert engine.streaming_overlap_ms >= 320


def test_fast_engine_initialize_backend_loads_once_on_happy_path(monkeypatch) -> None:
    engine = FastWhisperBackend(
        model_name="small",
        download_root=".",
        device="cpu",
        compute_type="int8",
        language_mode="en",
        execution_mode="cpu_only",
    )

    calls: list[dict[str, object]] = []

    class FakeBackend:
        prefix_manager = None

        def warmup(self) -> bool:
            return True

    def fake_create_backend(**kwargs):
        calls.append(kwargs)
        return FakeBackend()

    monkeypatch.setattr(
        "app.stt.fast_engine.OptimizedWhisperFactory.create_backend",
        fake_create_backend,
    )

    backend_one = engine._initialize_backend()
    backend_two = engine._initialize_backend()

    assert backend_one is backend_two
    assert len(calls) == 1
    assert calls[0]["compute_type"] == "int8"
