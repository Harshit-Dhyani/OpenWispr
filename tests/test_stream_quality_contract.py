from __future__ import annotations

import numpy as np
import pytest

import app.stt.engine as engine_module
from app.core.config import AppSettings, resolve_live_profile
from app.core.models import SessionState, TranscriptSegment
from app.core.session_manager import SessionManager
from app.stt.chunker import AudioChunk
from app.stt.engine import WhisperTranscriber
from app.stt.quality import assess_segment_quality


def test_quality_filter_suppresses_repeated_punctuation():
    result = assess_segment_quality(
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",
        confidence=0.2,
        language_mode="en",
        detected_language="en",
    )

    assert result.suppressed is True
    assert result.quality_label == "junk"
    assert "punctuation-heavy" in result.suppression_reasons


def test_quality_filter_keeps_normal_english_sentence():
    result = assess_segment_quality(
        "Today we solve the equation x plus y equals ten.",
        confidence=0.82,
        language_mode="en",
        detected_language="en",
    )

    assert result.suppressed is False
    assert result.quality_label == "ok"


def test_quality_filter_suppresses_likely_no_speech_decode():
    result = assess_segment_quality(
        "You",
        confidence=0.42,
        language_mode="en",
        detected_language="en",
        no_speech_prob=0.91,
        avg_logprob=-1.3,
    )

    assert result.suppressed is True
    assert "likely-no-speech" in result.suppression_reasons


def test_transcriber_submit_drops_oldest_when_queue_is_full():
    transcriber = WhisperTranscriber(
        model_name="tiny",
        download_root="models",
        device="cpu",
        compute_type="int8",
        beam_size=1,
        best_of=1,
        temperature=0.0,
        vad_filter=True,
        language_mode="en",
        execution_mode="cpu_only",
        max_queue_items=1,
    )

    first = AudioChunk(started_at=0.0, ended_at=1.0, samples=np.zeros(16, dtype=np.float32))
    second = AudioChunk(started_at=1.0, ended_at=2.0, samples=np.ones(16, dtype=np.float32))

    assert transcriber.submit(first) is True
    assert transcriber.submit(second) is True

    retained = transcriber._queue.get_nowait()
    assert retained.started_at == 1.0
    assert transcriber._dropped_chunks == 1


def test_live_profile_low_latency_is_shorter_than_balanced():
    settings = AppSettings()
    low_latency = resolve_live_profile("low_latency", settings)
    balanced = resolve_live_profile("balanced", settings)

    assert low_latency["chunk_seconds"] < balanced["chunk_seconds"]
    assert low_latency["overlap_seconds"] < balanced["overlap_seconds"]


def test_realtime_profile_is_shorter_than_low_latency():
    settings = AppSettings()
    realtime = resolve_live_profile("realtime", settings)
    low_latency = resolve_live_profile("low_latency", settings)

    assert realtime["chunk_seconds"] < low_latency["chunk_seconds"]
    assert realtime["overlap_seconds"] < low_latency["overlap_seconds"]


def test_balanced_profile_provides_more_than_one_second_of_context():
    settings = AppSettings()
    balanced = resolve_live_profile("balanced", settings)

    assert balanced["chunk_seconds"] >= 1.0
    assert balanced["overlap_seconds"] >= 0.2


def test_session_manager_suppresses_overlap_duplicates():
    manager = SessionManager(AppSettings())
    manager.session = SessionState.create(
        title="Study Session",
        output_dir=manager.settings.export_root / "study-session",
        model_name="small",
        language_mode="en",
        device_id="default",
        live_mode="balanced",
        execution_mode="cpu_only",
    )

    first = TranscriptSegment(
        id="seg-1",
        start=5.2,
        end=7.2,
        text="I'm not a fan of the",
        display_text="I'm not a fan of the",
        language="en",
        confidence=0.49,
    )
    duplicate = TranscriptSegment(
        id="seg-2",
        start=7.2,
        end=9.2,
        text="I'm not a fan of the",
        display_text="I'm not a fan of the",
        language="en",
        confidence=0.49,
    )

    manager.session.segments.append(first)
    manager.session.segments.append(duplicate)
    manager._apply_overlap_dedupe(duplicate)

    assert duplicate.suppressed is True
    assert "overlap-duplicate" in duplicate.suppression_reasons


def test_gpu_only_validation_fails_fast_when_cuda_runtime_is_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")

    monkeypatch.setattr(engine_module, "WhisperModel", FakeModel)

    transcriber = WhisperTranscriber(
        model_name="base",
        download_root="models",
        device="cuda",
        compute_type="float16",
        beam_size=1,
        best_of=1,
        temperature=0.0,
        vad_filter=True,
        language_mode="en",
        execution_mode="gpu_only",
        max_queue_items=4,
    )

    with pytest.raises(RuntimeError, match="GPU-only mode requested"):
        transcriber.validate_runtime()
