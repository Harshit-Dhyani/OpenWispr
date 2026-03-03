from __future__ import annotations

import asyncio
import logging
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.modules.setdefault(
    "soundcard",
    SimpleNamespace(
        all_speakers=lambda: [],
        all_microphones=lambda include_loopback=True: [],
        default_microphone=lambda: None,
    ),
)
sys.modules.setdefault("faster_whisper", SimpleNamespace(WhisperModel=object))

from app.api.server import HotkeyTranscriptionService
from app.api.refiner_service import RefinerResult


class _FakeAudioSource:
    backend_name = "test-backend"

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


class _FakeTranscriber:
    def __init__(self) -> None:
        self.callbacks = []

    def add_segment_callback(self, callback) -> None:
        self.callbacks.append(callback)

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


class _FakeWebSocket:
    def __init__(self) -> None:
        self.closed = []

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed.append((code, reason))


def _make_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        sample_rate=16000,
        channels=1,
        capture_block_seconds=0.1,
        audio_backend="auto",
        download_root=tmp_path,
        device="cpu",
        compute_type="int8",
        beam_size=1,
        best_of=1,
        temperature=0.0,
        vad_filter=True,
        max_queue_items=4,
    )


@pytest.mark.asyncio
async def test_hotkey_service_stop_closes_websocket_with_normal_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_audio = _FakeAudioSource()
    fake_transcriber = _FakeTranscriber()
    fake_websocket = _FakeWebSocket()

    async def fake_create_transcriber(**_: object) -> _FakeTranscriber:
        return fake_transcriber

    async def fake_process_audio_loop(session) -> None:
        while session.is_recording:
            await asyncio.sleep(0)

    fake_settings_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(
            transcription=SimpleNamespace(refinement_mode="off"),
            refiner=SimpleNamespace(
                selected_model_id=None,
                runtime_enabled=False,
                cleanup_instructions="",
            ),
        )
    )

    monkeypatch.setattr(service, "_create_audio_source", lambda **_kwargs: fake_audio)
    monkeypatch.setattr(service, "_create_transcriber", fake_create_transcriber)
    monkeypatch.setattr(service, "_process_audio_loop", fake_process_audio_loop)
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)

    service.register_websocket(fake_websocket)

    start = await service.start_session(
        capture_source="microphone",
        device_id=None,
        model_name="small",
        language_mode="auto",
        execution_mode="auto",
    )

    assert start.status == "recording"
    assert service.get_status().state == "recording"

    events: list[str] = []
    service.register_callback(lambda event_type, _payload: events.append(event_type))

    stop = await service.stop_session()

    assert stop.final_transcription == ""
    assert service.get_status().state == "idle"
    assert fake_websocket.closed == [(1000, "hotkey-session-stopped")]
    assert "hotkey_stop_ack" in events
    assert events.index("hotkey_stop_ack") < events.index("hotkey_stopped")


@pytest.mark.asyncio
async def test_hotkey_cancel_discards_transcription_and_skips_finalize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_audio = _FakeAudioSource()
    fake_transcriber = _FakeTranscriber()

    async def fake_create_transcriber(**_: object) -> _FakeTranscriber:
        return fake_transcriber

    async def fake_process_audio_loop(session) -> None:
        await asyncio.sleep(0)
        session.final_segments.append(
            {
                "id": "seg-1",
                "text": "hello world",
                "raw_text": "hello world",
                "start": 0.0,
                "end": 1.0,
                "language": "en",
                "confidence": 0.9,
            }
        )

    fake_settings_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(
            transcription=SimpleNamespace(refinement_mode="strict"),
            refiner=SimpleNamespace(
                selected_model_id="qwen2.5-3b-instruct",
                runtime_enabled=True,
                cleanup_instructions="",
            ),
        )
    )

    monkeypatch.setattr(service, "_create_audio_source", lambda **_kwargs: fake_audio)
    monkeypatch.setattr(service, "_create_transcriber", fake_create_transcriber)
    monkeypatch.setattr(service, "_process_audio_loop", fake_process_audio_loop)
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)

    start = await service.start_session(
        capture_source="microphone",
        device_id=None,
        model_name="small",
        language_mode="auto",
        execution_mode="auto",
    )

    assert start.status == "recording"

    stop = await service.stop_session(mode="cancel")

    assert stop.final_transcription == ""
    assert stop.raw_transcription == ""


@pytest.mark.asyncio
async def test_hotkey_transcriber_disables_backend_vad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    captured_kwargs: dict[str, object] = {}

    class FakeFastTranscriber:
        def __init__(self, **kwargs: object) -> None:
            captured_kwargs.update(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "app.stt.fast_engine",
        SimpleNamespace(FastTranscriber=FakeFastTranscriber),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.core.config",
        SimpleNamespace(resolve_live_profile=lambda *_args, **_kwargs: None),
    )

    await service._create_transcriber(
        model_name="small",
        language_mode="auto",
        execution_mode="auto",
    )

    assert captured_kwargs["model_name"] == "small"
    assert captured_kwargs["vad_filter"] is False


def test_hotkey_partial_callback_emits_single_draft_event(tmp_path: Path) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_session = SimpleNamespace(
        cancel_requested=False,
        suppress_stream_events=False,
        session_id="hotkey-session-1",
        draft_stabilizer=SimpleNamespace(
            push=lambda text, start, end: SimpleNamespace(
                text=text,
                revision=1,
                stream_id="hotkey-stream-1",
                committed_text="",
                draft_suffix=text,
            )
        ),
        first_partial_at=None,
        raw_partial_text="",
        display_partial_text="",
        partial_text="",
    )

    events: list[str] = []
    service.register_callback(lambda event_type, _payload: events.append(event_type))
    service._session = fake_session

    service._on_partial_transcription(fake_session, "how are you", 0.0, 1.0)

    assert events == ["hotkey_draft_partial"]


def test_hotkey_segment_callback_emits_only_commit_final(tmp_path: Path) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_session = SimpleNamespace(
        cancel_requested=False,
        suppress_stream_events=False,
        session_id="hotkey-session-1",
        language_mode="auto",
        language_used="auto",
        raw_partial_text="",
        display_partial_text="",
        partial_text="",
        final_segments=[],
        first_partial_at=None,
        draft_stabilizer=SimpleNamespace(
            consume_final_text=lambda text, start, end: SimpleNamespace(
                revision=2,
                stream_id="hotkey-stream-1",
                committed_text=text,
            )
        ),
    )
    service._session = fake_session

    events: list[str] = []
    service.register_callback(lambda event_type, _payload: events.append(event_type))

    segment = SimpleNamespace(
        id="seg-1",
        text="how are you",
        display_text="how are you",
        start=0.0,
        end=1.0,
        language="en",
        confidence=0.9,
    )

    service._on_transcription_segment(fake_session, segment)

    assert events == ["hotkey_commit_final"]


def test_hotkey_model_resolution_uses_source_specific_model_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_settings_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id="whisper-tiny",
                system_asr_model_id="whisper-medium",
                default_asr_model_id="whisper-large-v3-turbo",
                model_name="medium",
            )
        )
    )

    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)

    assert service._resolve_hotkey_model_name("microphone", None) == "tiny"
    assert service._resolve_hotkey_model_name("system", None) == "medium"


def test_hotkey_partial_callback_logs_debug_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_session = SimpleNamespace(
        cancel_requested=False,
        suppress_stream_events=False,
        session_id="hotkey-session-1",
        draft_stabilizer=SimpleNamespace(
            push=lambda text, start, end: SimpleNamespace(
                text=text,
                revision=1,
                stream_id="hotkey-stream-1",
                committed_text="",
                draft_suffix=text,
            )
        ),
        first_partial_at=None,
        raw_partial_text="",
        display_partial_text="",
        partial_text="",
    )
    fake_settings_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(advanced=SimpleNamespace(debugMode=True))
    )

    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)
    service._session = fake_session

    with caplog.at_level(logging.DEBUG):
        service._on_partial_transcription(fake_session, "hello from mic", 0.0, 1.0)

    assert "Hotkey ASR partial" in caplog.text
    assert "hello from mic" in caplog.text


def test_hotkey_audio_chunk_diagnostics_reports_signal_stats(tmp_path: Path) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)

    stats = service._audio_chunk_diagnostics(audio, 16000)

    assert stats["duration_ms"] > 0.0
    assert stats["rms"] > 0.0
    assert stats["peak"] == pytest.approx(1.0)
    assert stats["clipping_ratio"] > 0.0


def test_hotkey_debug_wav_is_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    monkeypatch.chdir(tmp_path)
    fake_session = SimpleNamespace(
        session_id="hotkey-test",
        debug_audio_chunks=[
            np.array([0.0, 0.25, -0.25, 0.5, -0.5], dtype=np.float32),
            np.array([0.1, -0.1], dtype=np.float32),
        ],
    )

    wav_path = service._write_hotkey_debug_wav(fake_session)

    assert wav_path is not None
    saved = Path(wav_path)
    assert saved.exists()
    with wave.open(str(saved), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 16000
        assert wav_file.getnframes() == 7


@pytest.mark.asyncio
async def test_hotkey_silence_gate_skips_nearly_silent_chunk(tmp_path: Path) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))

    class _Transcriber:
        def __init__(self) -> None:
            self.submitted = False

        def submit(self, _chunk):
            self.submitted = True
            return SimpleNamespace(accepted=True, queue_depth=0)

    transcriber = _Transcriber()
    fake_session = SimpleNamespace(
        transcriber=transcriber,
        cancel_requested=False,
        debug_audio_chunks=[],
        skipped_silent_chunks=0,
        duration_ms=1400,
        session_id="hotkey-silent",
    )

    audio = np.full(1600, 1e-5, dtype=np.float32)
    await service._transcribe_chunk(fake_session, audio)

    assert fake_session.skipped_silent_chunks == 1
    assert transcriber.submitted is False


def test_hotkey_segment_callback_skips_suppressed_segment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    events: list[tuple[str, dict[str, object]]] = []
    fake_settings_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(advanced=SimpleNamespace(debugMode=True))
    )
    fake_session = SimpleNamespace(
        session_id="hotkey-test",
        cancel_requested=False,
        suppress_stream_events=False,
        display_partial_text="",
        raw_partial_text="",
        partial_text="",
        final_segments=[],
        first_partial_at=None,
        correlation_id="hotkey-test",
    )

    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)
    monkeypatch.setattr(service, "_publish_event", lambda event_type, payload: events.append((event_type, payload)))
    service._session = fake_session

    suppressed_segment = SimpleNamespace(
        text="hello hello hello",
        display_text="hello hello hello",
        start=0.0,
        end=1.2,
        suppressed=True,
        suppression_reasons=["low-entropy"],
        review_reasons=["low-entropy"],
    )

    service._on_transcription_segment(fake_session, suppressed_segment)

    assert fake_session.final_segments == []
    assert events == []


@pytest.mark.asyncio
async def test_refiner_debug_logs_input_and_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_settings_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(advanced=SimpleNamespace(debugMode=True))
    )

    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)
    service._refiner_service = SimpleNamespace(
        refine_text=lambda *args, **kwargs: RefinerResult(
            text="Hello world.",
            mode="strict",
            model_id="phi-3-mini-4k-instruct",
            used_runtime=True,
        )
    )

    with caplog.at_level(logging.DEBUG):
        result = await service._refine_final_text(
            text="hello world",
            language_hint="en",
            refinement_mode="strict",
            refiner_model_id="phi-3-mini-4k-instruct",
            runtime_enabled=True,
            cleanup_instructions="",
        )

    assert result is not None
    assert "Hotkey refiner input" in caplog.text
    assert "hello world" in caplog.text
    assert "Hotkey refiner output" in caplog.text
    assert "Hello world." in caplog.text
