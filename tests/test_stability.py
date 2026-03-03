from __future__ import annotations

import sys
import types

sys.modules.setdefault("faster_whisper", types.SimpleNamespace(WhisperModel=object))

from app.stt.stability import PartialStabilizer


def test_partial_stabilizer_commits_only_after_repeated_prefix() -> None:
    stabilizer = PartialStabilizer(session_id="sess-1", stability_threshold=2)

    first = stabilizer.push("hello there", start=0.0, end=0.6)
    second = stabilizer.push("hello there", start=0.0, end=0.7)
    third = stabilizer.push("hello there", start=0.0, end=0.8)
    fourth = stabilizer.push("hello there world", start=0.0, end=1.0)

    assert first.committed_text == ""
    assert second.committed_text == ""
    assert third.committed_text == "hello there"
    assert fourth.committed_text == "hello there"
    assert fourth.draft_suffix == "world"


def test_partial_stabilizer_consumes_final_text() -> None:
    stabilizer = PartialStabilizer(session_id="sess-2", stability_threshold=2)
    stabilizer.push("draft text", start=0.0, end=0.5)
    final_state = stabilizer.consume_final_text("draft text finished", start=0.0, end=1.0)

    assert final_state.committed_text == "draft text finished"
    assert final_state.draft_suffix == ""
