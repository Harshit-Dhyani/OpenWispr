from __future__ import annotations

import asyncio
import logging
import time
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
from app.api.coach_service import CoachMeta, CoachPractice, CoachResult
from app.api.refiner_service import RefinerResult
from app.stt.dictation_cleanup import TranscriptComposer
from app.stt.utterance_aggregator import UtteranceAggregator


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


def _mock_user_settings(*, privacy_mode: str = "local_only") -> SimpleNamespace:
    return SimpleNamespace(
        transcription=SimpleNamespace(refinement_mode="off", transcription_mode="dictation"),
        refiner=SimpleNamespace(
            selected_model_id=None,
            runtime_enabled=False,
            cleanup_instructions="",
        ),
        hotkey=SimpleNamespace(
            enable_refiner_on_stop=False,
            save_debug_wav=False,
        ),
        coach=SimpleNamespace(
            coach_enabled=False,
            coach_detail_level="compact",
            copy_polished_by_default=True,
            coach_template_id_mic="default_english_coach",
            coach_template_id_system="default_english_coach",
            coach_prompt_custom_enabled=False,
            coach_prompt_custom_text="",
            coach_overrides={
                "tone": "friendly",
                "aggressiveness": "light",
                "filler_removal": True,
                "keep_slang": False,
                "target_style": "simple",
            },
            privacy_mode=privacy_mode,
            coach_prompt_templates=[],
        ),
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
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-1",
                text="quarterly project update for",
                display_text="quarterly project update for",
                start=0.0,
                end=1.0,
                language="en",
                confidence=0.9,
            ),
        )
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-2",
                text="for tomorrow morning",
                display_text="for tomorrow morning",
                start=0.7,
                end=1.7,
                language="en",
                confidence=0.9,
            ),
        )

    fake_settings_manager = SimpleNamespace(get_settings=lambda: _mock_user_settings())

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
    session = service._session

    stop = await service.stop_session()

    assert stop.status == "idle"
    assert stop.composed_text == "Quarterly project update for tomorrow morning."
    assert stop.final_transcription == "Quarterly project update for tomorrow morning."
    assert stop.aggregated_clean_text == "Quarterly project update for tomorrow morning."
    assert stop.postprocessed_text == "Quarterly project update for tomorrow morning."
    assert stop.paste_text == "Quarterly project update for tomorrow morning."
    assert stop.live_paste_text == "Quarterly project update for tomorrow morning."
    assert stop.transcription_mode == "dictation"
    assert stop.final_cleanup_applied is True
    assert stop.raw_transcription == "quarterly project update for tomorrow morning"
    assert stop.coach_status == "disabled"
    assert stop.coach_error is None
    assert stop.coach_result is None
    assert service.get_status().state == "idle"
    assert session is not None
    assert session.final_response is not None
    assert session.final_response.composed_text == "Quarterly project update for tomorrow morning."
    assert fake_websocket.closed == [(1000, "hotkey-session-stopped")]
    assert "hotkey_stop_ack" in events
    assert events.index("hotkey_stop_ack") < events.index("hotkey_stopped")

@pytest.mark.asyncio
async def test_hotkey_service_stop_preserves_new_websocket_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_audio = _FakeAudioSource()
    fake_transcriber = _FakeTranscriber()
    existing_websocket = _FakeWebSocket()
    new_websocket = _FakeWebSocket()
    processing_gate = asyncio.Event()

    async def fake_create_transcriber(**_: object) -> _FakeTranscriber:
        return fake_transcriber

    async def fake_process_audio_loop(_session) -> None:
        await processing_gate.wait()

    fake_settings_manager = SimpleNamespace(get_settings=lambda: _mock_user_settings())

    monkeypatch.setattr(service, "_create_audio_source", lambda **_kwargs: fake_audio)
    monkeypatch.setattr(service, "_create_transcriber", fake_create_transcriber)
    monkeypatch.setattr(service, "_process_audio_loop", fake_process_audio_loop)
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)

    await service.start_session(
        capture_source="microphone",
        device_id=None,
        model_name="small",
        language_mode="auto",
        execution_mode="auto",
    )

    service.register_websocket(existing_websocket)

    stop_task = asyncio.create_task(service.stop_session())

    for _ in range(50):
        if service._session is not None and service._session.state == "stopping":
            break
        await asyncio.sleep(0.01)

    service.register_websocket(new_websocket)
    processing_gate.set()

    stop = await stop_task

    assert stop.status == "idle"
    assert existing_websocket.closed == [(1000, "hotkey-session-stopped")]
    assert new_websocket.closed == []

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
                "text": "project status update",
                "raw_text": "project status update",
                "start": 0.0,
                "end": 1.0,
                "language": "en",
                "confidence": 0.9,
            }
        )

    fake_settings_manager = SimpleNamespace(get_settings=lambda: _mock_user_settings())

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
    session = service._session

    stop = await service.stop_session(mode="cancel")

    assert stop.status == "idle"
    assert stop.composed_text == ""
    assert stop.final_transcription == ""
    assert stop.raw_transcription == ""
    assert stop.coach_result is None
    assert stop.paste_text == ""
    assert stop.live_paste_text == ""
    assert stop.final_cleanup_applied is False
    assert session is not None


@pytest.mark.asyncio
async def test_hotkey_stop_returns_deterministic_transcript_when_coach_is_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_audio = _FakeAudioSource()
    fake_transcriber = _FakeTranscriber()

    async def fake_create_transcriber(**_: object) -> _FakeTranscriber:
        return fake_transcriber

    async def fake_process_audio_loop(session) -> None:
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-1",
                text="whenever i try to do loops",
                display_text="whenever i try to do loops",
                start=0.0,
                end=1.0,
                language="en",
                confidence=0.91,
            ),
        )
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-2",
                text="to do loops in python they confuse me",
                display_text="to do loops in python they confuse me",
                start=0.7,
                end=1.8,
                language="en",
                confidence=0.88,
            ),
        )

    user_settings = _mock_user_settings()
    user_settings.coach.coach_enabled = False
    fake_settings_manager = SimpleNamespace(get_settings=lambda: user_settings)

    monkeypatch.setattr(service, "_create_audio_source", lambda **_kwargs: fake_audio)
    monkeypatch.setattr(service, "_create_transcriber", fake_create_transcriber)
    monkeypatch.setattr(service, "_process_audio_loop", fake_process_audio_loop)
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)

    await service.start_session(
        capture_source="microphone",
        device_id=None,
        model_name="small",
        language_mode="auto",
        execution_mode="auto",
    )

    stop = await service.stop_session()

    assert stop.aggregated_clean_text == "Whenever i try to do loops in python they confuse me."
    assert stop.paste_text == stop.aggregated_clean_text
    assert stop.transcription_mode == "dictation"
    assert stop.final_cleanup_applied is True
    assert stop.coach_result is None
    assert stop.coach_status == "disabled"


@pytest.mark.asyncio
async def test_hotkey_stop_applies_literal_mode_postprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_audio = _FakeAudioSource()
    fake_transcriber = _FakeTranscriber()

    async def fake_create_transcriber(**_: object) -> _FakeTranscriber:
        return fake_transcriber

    async def fake_process_audio_loop(session) -> None:
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-1",
                text="version zero dot zero dot one dot zero zero zero",
                display_text="version zero dot zero dot one dot zero zero zero",
                start=0.0,
                end=1.0,
                language="en",
                confidence=0.92,
            ),
        )
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-2",
                text="token zero one zero zero zero library H T T P X client",
                display_text="token zero one zero zero zero library H T T P X client",
                start=1.0,
                end=2.0,
                language="en",
                confidence=0.92,
            ),
        )

    user_settings = _mock_user_settings()
    user_settings.transcription.transcription_mode = "literal"
    fake_settings_manager = SimpleNamespace(get_settings=lambda: user_settings)

    monkeypatch.setattr(service, "_create_audio_source", lambda **_kwargs: fake_audio)
    monkeypatch.setattr(service, "_create_transcriber", fake_create_transcriber)
    monkeypatch.setattr(service, "_process_audio_loop", fake_process_audio_loop)
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)

    await service.start_session(
        capture_source="microphone",
        device_id=None,
        model_name="small",
        language_mode="en",
        execution_mode="auto",
        transcription_mode="literal",
    )

    stop = await service.stop_session()

    assert stop.transcription_mode == "literal"
    assert stop.final_transcription == "version 0.0.1.000 token 01000 library HTTPX client"
    assert stop.paste_text == stop.final_transcription
    assert stop.live_paste_text


@pytest.mark.asyncio
async def test_hotkey_session_paragraph_emits_only_stop_time_final_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_audio = _FakeAudioSource()
    fake_transcriber = _FakeTranscriber()
    events: list[tuple[str, dict[str, object]]] = []

    async def fake_create_transcriber(**_: object) -> _FakeTranscriber:
        return fake_transcriber

    async def fake_process_audio_loop(session) -> None:
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-1",
                text="project status update for",
                display_text="project status update for",
                start=0.0,
                end=1.0,
                language="en",
                confidence=0.91,
            ),
        )
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-2",
                text="for tomorrow morning delivery",
                display_text="for tomorrow morning delivery",
                start=0.7,
                end=1.8,
                language="en",
                confidence=0.89,
            ),
        )

    user_settings = _mock_user_settings()
    user_settings.transcription.transcription_mode = "session_paragraph"
    user_settings.coach.coach_enabled = True
    fake_settings_manager = SimpleNamespace(get_settings=lambda: user_settings)

    monkeypatch.setattr(service, "_create_audio_source", lambda **_kwargs: fake_audio)
    monkeypatch.setattr(service, "_create_transcriber", fake_create_transcriber)
    monkeypatch.setattr(service, "_process_audio_loop", fake_process_audio_loop)
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)
    monkeypatch.setattr(
        service,
        "_get_coach_service",
        lambda: SimpleNamespace(
            generate=lambda context, fallback_text: CoachResult(
                original=context.text,
                polished="Polished project status update for tomorrow morning delivery.",
                diff=[],
                tips=[],
                mistakes=[],
                practice=CoachPractice(),
                meta=CoachMeta(
                    model="local-coach",
                    confidence=0.98,
                    cache_hit=False,
                    provider="local_llm",
                ),
            )
        ),
    )
    service.register_callback(lambda event_type, payload: events.append((event_type, payload)))

    await service.start_session(
        capture_source="microphone",
        device_id=None,
        model_name="small",
        language_mode="en",
        execution_mode="auto",
        transcription_mode="session_paragraph",
    )

    stop = await service.stop_session()

    assert stop.transcription_mode == "session_paragraph"
    assert stop.final_transcription == "Project status update for tomorrow morning delivery."
    assert stop.coach_status == "generated"
    assert stop.coach_result is not None
    assert stop.coach_result.polished == "Polished project status update for tomorrow morning delivery."
    assert stop.paste_text == "Polished project status update for tomorrow morning delivery."
    assert stop.live_paste_text == stop.final_transcription
    assert all(event_type != "hotkey_commit_final" for event_type, _payload in events)
    assert any(event_type == "hotkey_stopped" for event_type, _payload in events)
    final_text_events = [payload for event_type, payload in events if event_type == "final_text"]
    assert len(final_text_events) == 1
    assert final_text_events[0]["mode"] == "session_paragraph"
    assert final_text_events[0]["text"] == "Project status update for tomorrow morning delivery."


def test_hotkey_segment_callback_emits_live_buffer_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    events: list[tuple[str, dict[str, object]]] = []
    fake_settings_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(
            advanced=SimpleNamespace(debugMode=False),
            hotkey=SimpleNamespace(save_debug_wav=False),
        )
    )
    fake_session = SimpleNamespace(
        session_id="hotkey-live-buffer",
        capture_source="microphone",
        cancel_requested=False,
        suppress_stream_events=False,
        display_partial_text="",
        raw_partial_text="",
        partial_text="",
        final_segments=[],
        aggregator=UtteranceAggregator(),
        composer=TranscriptComposer(),
        raw_composed_text="",
        latest_live_buffer_text="",
        first_partial_at=None,
        draft_stabilizer=SimpleNamespace(
            consume_final_text=lambda text, start, end: SimpleNamespace(
                revision=1,
                stream_id="stream-1",
                committed_text=text,
            )
        ),
        language_mode="en",
        language_used="en",
        finalization_error=None,
        correlation_id="hotkey-live-buffer",
        silence_skip_streak=0,
        transcription_mode="dictation",
    )

    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)
    monkeypatch.setattr(service, "_publish_event", lambda event_type, payload: events.append((event_type, payload)))
    service._session = fake_session

    service._on_transcription_segment(
        fake_session,
        SimpleNamespace(
            id="seg-live-buffer",
            text="set threshold to zero point two three",
            display_text="set threshold to zero point two three",
            start=0.0,
            end=1.0,
            language="en",
            confidence=0.88,
            suppressed=False,
            suppression_reasons=[],
            review_reasons=[],
        ),
    )

    event_type, payload = events[-1]
    assert event_type == "hotkey_commit_final"
    assert payload["live_buffer_text"] == "Set threshold to 0.23."
    assert payload["transcription_mode"] == "dictation"


@pytest.mark.asyncio
async def test_hotkey_stop_rebuilds_transcript_when_aggregator_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_audio = _FakeAudioSource()
    fake_transcriber = _FakeTranscriber()

    async def fake_create_transcriber(**_: object) -> _FakeTranscriber:
        return fake_transcriber

    async def fake_process_audio_loop(session) -> None:
        original_add_segment = session.aggregator.add_segment

        def broken_add_segment(*args, **kwargs):
            raise RuntimeError("forced-aggregator-failure")

        session.aggregator.add_segment = broken_add_segment
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-1",
                text="project status update from fallback rebuild",
                display_text="project status update from fallback rebuild",
                start=0.0,
                end=1.0,
                language="en",
                confidence=0.91,
            ),
        )
        session.aggregator.add_segment = original_add_segment

    user_settings = _mock_user_settings()
    user_settings.coach.coach_enabled = False
    fake_settings_manager = SimpleNamespace(get_settings=lambda: user_settings)

    monkeypatch.setattr(service, "_create_audio_source", lambda **_kwargs: fake_audio)
    monkeypatch.setattr(service, "_create_transcriber", fake_create_transcriber)
    monkeypatch.setattr(service, "_process_audio_loop", fake_process_audio_loop)
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)

    await service.start_session(
        capture_source="microphone",
        device_id=None,
        model_name="small",
        language_mode="en",
        execution_mode="auto",
    )

    stop = await service.stop_session()

    assert stop.final_transcription == "Project status update from fallback rebuild."
    assert stop.aggregated_clean_text == "Project status update from fallback rebuild."
    assert any("aggregation_error" in warning for warning in stop.warnings or [])


@pytest.mark.asyncio
async def test_hotkey_transcriber_uses_low_latency_decode_defaults(
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
        language_mode="en",
        execution_mode="auto",
    )

    assert captured_kwargs["model_name"] == "small"
    assert captured_kwargs["language_mode"] == "en"
    assert captured_kwargs["beam_size"] == 1
    assert captured_kwargs["best_of"] == 1
    assert captured_kwargs["temperature"] == 0.0
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
        composer=TranscriptComposer(),
        raw_composed_text="",
    )

    events: list[str] = []
    service.register_callback(lambda event_type, _payload: events.append(event_type))
    service._session = fake_session

    service._on_partial_transcription(fake_session, "how are you", 0.0, 1.0)

    assert events == ["hotkey_draft_partial"]


def test_hotkey_partial_callback_keeps_live_text_raw_until_stop(tmp_path: Path) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    live_text = "please review the release notes please review the release notes"
    fake_session = SimpleNamespace(
        cancel_requested=False,
        suppress_stream_events=False,
        session_id="hotkey-session-raw-live",
        draft_stabilizer=SimpleNamespace(
            push=lambda text, start, end: SimpleNamespace(
                text=text,
                revision=1,
                stream_id="hotkey-stream-raw-live",
                committed_text="",
                draft_suffix=text,
            )
        ),
        first_partial_at=None,
        raw_partial_text="",
        display_partial_text="",
        partial_text="",
    )
    service._session = fake_session

    service._on_partial_transcription(fake_session, live_text, 0.0, 1.0)

    assert fake_session.display_partial_text == live_text
    assert fake_session.partial_text == live_text


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
        aggregator=UtteranceAggregator(),
        first_partial_at=None,
        composer=TranscriptComposer(),
        raw_composed_text="",
        finalization_error=None,
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
    assert fake_session.raw_composed_text == "how are you"


def test_hotkey_segment_callback_skips_duplicate_commit_events(tmp_path: Path) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    revisions = iter([2, 3])
    fake_session = SimpleNamespace(
        cancel_requested=False,
        suppress_stream_events=False,
        session_id="hotkey-session-1",
        language_mode="auto",
        language_used="auto",
        raw_partial_text="",
        display_partial_text="",
        partial_text="",
        first_partial_at=None,
        final_segments=[],
        aggregator=UtteranceAggregator(),
        composer=TranscriptComposer(),
        raw_composed_text="",
        finalization_error=None,
        draft_stabilizer=SimpleNamespace(
            consume_final_text=lambda text, start, end: SimpleNamespace(
                revision=next(revisions),
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
    service._on_transcription_segment(fake_session, segment)

    assert events == ["hotkey_commit_final"]
    assert len(fake_session.final_segments) == 1
    assert fake_session.raw_composed_text == "how are you"


@pytest.mark.asyncio
async def test_hotkey_stop_returns_real_coach_for_microphone_when_generated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_audio = _FakeAudioSource()
    fake_transcriber = _FakeTranscriber()

    async def fake_create_transcriber(**_: object) -> _FakeTranscriber:
        return fake_transcriber

    async def fake_process_audio_loop(session) -> None:
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-1",
                text="hello there this is raw transcript",
                display_text="hello there this is raw transcript",
                start=0.0,
                end=1.0,
                language="en",
                confidence=0.9,
            ),
        )

    user_settings = _mock_user_settings(privacy_mode="allow_llm")
    user_settings.coach.coach_enabled = True
    fake_settings_manager = SimpleNamespace(get_settings=lambda: user_settings)

    monkeypatch.setattr(service, "_create_audio_source", lambda **_kwargs: fake_audio)
    monkeypatch.setattr(service, "_create_transcriber", fake_create_transcriber)
    monkeypatch.setattr(service, "_process_audio_loop", fake_process_audio_loop)
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)
    monkeypatch.setattr(
        service,
        "_refine_final_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("mic finalize should not call refiner")),
    )
    monkeypatch.setattr(
        service,
        "_get_coach_service",
        lambda: SimpleNamespace(
            generate=lambda context, fallback_text: CoachResult(
                original=context.text,
                polished="Hello there, this is the polished transcript.",
                diff=[],
                tips=[],
                mistakes=[],
                practice=CoachPractice(),
                meta=CoachMeta(
                    model="local-coach",
                    confidence=0.97,
                    cache_hit=False,
                    provider="local_llm",
                ),
            )
        ),
    )

    await service.start_session(
        capture_source="microphone",
        device_id=None,
        model_name="small",
        language_mode="en",
        execution_mode="auto",
    )

    stop = await service.stop_session()

    assert stop.coach_status == "generated"
    assert stop.coach_result is not None
    assert stop.coach_result.polished == "Hello there, this is the polished transcript."
    assert stop.paste_text == "Hello there, this is the polished transcript."
    assert stop.aggregated_clean_text == "Hello there this is raw transcript."


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


@pytest.mark.asyncio
async def test_hotkey_silence_gate_keeps_low_energy_speech_chunk(tmp_path: Path) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))

    class _Transcriber:
        def __init__(self) -> None:
            self.submitted = False
            self.last_chunk = None

        def submit(self, chunk):
            self.submitted = True
            self.last_chunk = chunk
            return SimpleNamespace(accepted=True, queue_depth=0)

    transcriber = _Transcriber()
    fake_session = SimpleNamespace(
        transcriber=transcriber,
        cancel_requested=False,
        debug_audio_chunks=[],
        skipped_silent_chunks=0,
        submitted_audio_seconds=0.0,
        duration_ms=850,
        session_id="hotkey-low-energy",
        backlog_warning_at=0.0,
    )

    audio = np.full(13600, 0.0012, dtype=np.float32)
    await service._transcribe_chunk(fake_session, audio)

    assert fake_session.skipped_silent_chunks == 0
    assert transcriber.submitted is True
    assert transcriber.last_chunk is not None
    assert transcriber.last_chunk.started_at == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_hotkey_silence_gate_relaxes_after_repeated_empty_skips(tmp_path: Path) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))

    class _Transcriber:
        def submit(self, _chunk):
            return SimpleNamespace(accepted=True, queue_depth=0)

    fake_session = SimpleNamespace(
        transcriber=_Transcriber(),
        cancel_requested=False,
        capture_source="microphone",
        debug_audio_chunks=[],
        skipped_silent_chunks=0,
        silence_skip_streak=0,
        adaptive_silence_gate_relaxed=False,
        final_segments=[],
        submitted_audio_seconds=0.0,
        duration_ms=850,
        session_id="hotkey-adaptive-gate",
        backlog_warning_at=0.0,
    )

    audio = np.full(1600, 1e-5, dtype=np.float32)
    await service._transcribe_chunk(fake_session, audio)
    await service._transcribe_chunk(fake_session, audio)
    await service._transcribe_chunk(fake_session, audio)

    assert fake_session.adaptive_silence_gate_relaxed is True
    assert fake_session.silence_skip_streak == 3


@pytest.mark.asyncio
async def test_hotkey_transcribe_chunk_uses_monotonic_audio_offsets(tmp_path: Path) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))

    class _Transcriber:
        def __init__(self) -> None:
            self.chunks = []

        def submit(self, chunk):
            self.chunks.append(chunk)
            return SimpleNamespace(accepted=True, queue_depth=0)

    transcriber = _Transcriber()
    fake_session = SimpleNamespace(
        transcriber=transcriber,
        cancel_requested=False,
        debug_audio_chunks=[],
        skipped_silent_chunks=0,
        submitted_audio_seconds=0.0,
        duration_ms=0,
        session_id="hotkey-offsets",
        backlog_warning_at=0.0,
    )

    audio = np.full(16000, 0.002, dtype=np.float32)
    await service._transcribe_chunk(fake_session, audio)
    await service._transcribe_chunk(fake_session, audio)

    assert len(transcriber.chunks) == 2
    assert transcriber.chunks[0].started_at == pytest.approx(0.0)
    assert transcriber.chunks[1].started_at == pytest.approx(1.0)


def test_hotkey_segment_callback_keeps_mic_phrase_despite_soft_suppression(tmp_path: Path) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    events: list[tuple[str, dict[str, object]]] = []
    fake_settings_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(
            advanced=SimpleNamespace(debugMode=False),
            hotkey=SimpleNamespace(save_debug_wav=False),
        )
    )
    fake_session = SimpleNamespace(
        session_id="hotkey-soft-suppress",
        capture_source="microphone",
        cancel_requested=False,
        suppress_stream_events=False,
        display_partial_text="",
        raw_partial_text="",
        partial_text="",
        final_segments=[],
        aggregator=UtteranceAggregator(),
        composer=TranscriptComposer(),
        raw_composed_text="",
        first_partial_at=None,
        draft_stabilizer=None,
        language_mode="en",
        language_used="en",
        finalization_error=None,
        correlation_id="hotkey-soft-suppress",
    )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)
    monkeypatch.setattr(service, "_publish_event", lambda event_type, payload: events.append((event_type, payload)))
    service._session = fake_session

    segment = SimpleNamespace(
        id="seg-soft",
        text="Okay, so lets try it",
        display_text="Okay, so lets try it",
        start=0.0,
        end=0.85,
        language="en",
        confidence=0.82,
        suppressed=True,
        suppression_reasons=["low-value-filler"],
        review_reasons=["low-value-filler"],
    )

    service._on_transcription_segment(fake_session, segment)

    monkeypatch.undo()

    assert len(fake_session.final_segments) == 1
    assert fake_session.final_segments[0]["raw_text"] == "Okay, so lets try it"
    assert fake_session.aggregator.finalize().accepted_segments_count == 1


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
            text="Project status update.",
            mode="strict",
            model_id="phi-3-mini-4k-instruct",
            used_runtime=True,
        )
    )

    with caplog.at_level(logging.DEBUG):
        result = await service._refine_final_text(
            text="project status update",
            language_hint="en",
            refinement_mode="strict",
            refinement_profile="clean_dictation",
            refiner_model_id="phi-3-mini-4k-instruct",
            runtime_enabled=True,
            cleanup_instructions="",
        )

    assert result is not None
    assert "Hotkey refiner input" in caplog.text
    assert "project status update" in caplog.text
    assert "Hotkey refiner output" in caplog.text
    assert "Project status update." in caplog.text

@pytest.mark.asyncio
async def test_hotkey_stop_skips_refiner_and_coach_when_no_final_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_audio = _FakeAudioSource()
    fake_transcriber = _FakeTranscriber()

    async def fake_create_transcriber(**_: object) -> _FakeTranscriber:
        return fake_transcriber

    async def fake_process_audio_loop(_session) -> None:
        await asyncio.sleep(0)

    user_settings = _mock_user_settings()
    user_settings.hotkey.enable_refiner_on_stop = True
    user_settings.transcription.refinement_mode = "strict"
    user_settings.transcription.refinement_profile = "clean_dictation"
    user_settings.refiner.runtime_enabled = True
    user_settings.coach.coach_enabled = True
    fake_settings_manager = SimpleNamespace(get_settings=lambda: user_settings)

    refiner_calls = {"count": 0}
    coach_calls = {"count": 0}

    async def fake_refine_final_text(**_: object):
        refiner_calls["count"] += 1
        return RefinerResult(text="", mode="strict", model_id="fake", used_runtime=False)

    class _CoachService:
        def generate(self, *_args, **_kwargs):
            coach_calls["count"] += 1
            return CoachResult(
                polished="",
                rationale="",
                alternatives=[],
                practice=CoachPractice(drill="", prompt="", focus=""),
                meta=CoachMeta(provider="cache", detail_level="compact", privacy_mode="local_only"),
            )

    monkeypatch.setattr(service, "_create_audio_source", lambda **_kwargs: fake_audio)
    monkeypatch.setattr(service, "_create_transcriber", fake_create_transcriber)
    monkeypatch.setattr(service, "_process_audio_loop", fake_process_audio_loop)
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)
    monkeypatch.setattr(service, "_refine_final_text", fake_refine_final_text)
    monkeypatch.setattr(service, "_get_coach_service", lambda: _CoachService())

    await service.start_session(
        capture_source="microphone",
        device_id=None,
        model_name="small",
        language_mode="auto",
        execution_mode="auto",
    )

    stop_started = time.perf_counter()
    stop = await service.stop_session(mode="finish")
    stop_elapsed = time.perf_counter() - stop_started

    assert stop.status == "idle"
    assert stop.final_transcription == ""
    assert stop.paste_text == ""
    assert stop.coach_status == "disabled"
    assert stop_elapsed < 1.0
    assert refiner_calls["count"] == 0
    assert coach_calls["count"] == 0


@pytest.mark.asyncio
async def test_hotkey_stop_refiner_timeout_falls_back_without_blocking_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = HotkeyTranscriptionService(_make_settings(tmp_path))
    fake_audio = _FakeAudioSource()
    fake_transcriber = _FakeTranscriber()

    async def fake_create_transcriber(**_: object) -> _FakeTranscriber:
        return fake_transcriber

    async def fake_process_audio_loop(session) -> None:
        await asyncio.sleep(0)
        service._on_transcription_segment(
            session,
            SimpleNamespace(
                id="seg-1",
                text="standup notes are ready",
                display_text="standup notes are ready",
                start=0.0,
                end=0.8,
                language="en",
                confidence=0.9,
            ),
        )

    user_settings = _mock_user_settings()
    user_settings.hotkey.enable_refiner_on_stop = True
    user_settings.transcription.refinement_mode = "strict"
    user_settings.transcription.refinement_profile = "clean_dictation"
    user_settings.refiner.runtime_enabled = True
    user_settings.coach.coach_enabled = False
    fake_settings_manager = SimpleNamespace(get_settings=lambda: user_settings)

    refiner_calls = {"count": 0}

    async def fake_refine_final_text(**_: object):
        refiner_calls["count"] += 1
        await asyncio.sleep(0.05)
        return RefinerResult(
            text="Standup notes are ready.",
            mode="strict",
            model_id="fake",
            used_runtime=True,
        )

    monkeypatch.setattr(service, "_create_audio_source", lambda **_kwargs: fake_audio)
    monkeypatch.setattr(service, "_create_transcriber", fake_create_transcriber)
    monkeypatch.setattr(service, "_process_audio_loop", fake_process_audio_loop)
    monkeypatch.setattr("app.api.server.get_settings_manager", lambda: fake_settings_manager)
    monkeypatch.setattr("app.api.server._HOTKEY_REFINER_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(service, "_refine_final_text", fake_refine_final_text)

    await service.start_session(
        capture_source="microphone",
        device_id=None,
        model_name="small",
        language_mode="auto",
        execution_mode="auto",
    )

    stop_started = time.perf_counter()
    stop = await service.stop_session(mode="finish")
    stop_elapsed = time.perf_counter() - stop_started

    assert stop.status == "idle"
    assert stop_elapsed < 1.0
    assert stop.final_transcription == "Standup notes are ready."
    assert "refiner_timeout" in stop.warnings
    assert refiner_calls["count"] == 1
