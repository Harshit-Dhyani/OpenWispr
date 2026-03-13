from __future__ import annotations

import sys
import types

sys.modules.setdefault("faster_whisper", types.SimpleNamespace(WhisperModel=object))
sys.modules.setdefault(
    "soundcard",
    types.SimpleNamespace(
        all_speakers=lambda: [],
        all_microphones=lambda include_loopback=True: [],
        default_microphone=lambda: None,
    ),
)

from app.api.services.backend_service import BackendService
from app.core.models import TranscriptSegment
from app.core.settings.config import AppSettings
from app.stt.stability import PartialStabilizer


def test_backend_service_emits_draft_then_commit_events_in_order(monkeypatch) -> None:
    service = BackendService(AppSettings())
    events: list[str] = []

    service.register_event_callback(lambda event_type, payload: events.append(event_type))
    service._session_state = {"session_id": "session-123"}  # type: ignore[attr-defined]
    service._stabilizer = PartialStabilizer(session_id="session-123", stability_threshold=1)  # type: ignore[attr-defined]
    monkeypatch.setattr(service._refinement_queue, "enqueue", lambda **kwargs: None)

    service._on_partial("project status update", 0.0, 0.5)
    service._on_segment(
        TranscriptSegment(
            id="seg-1",
            start=0.0,
            end=0.8,
            text="project status update",
            display_text="project status update",
            language="en",
            confidence=0.9,
        )
    )

    assert "draft_partial" in events
    assert "commit_final" in events
    assert events.index("draft_partial") < events.index("commit_final")
