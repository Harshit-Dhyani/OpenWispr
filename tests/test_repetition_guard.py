from __future__ import annotations

from app.stt.repetition_guard import dedupe_boundary, is_repetitive_segment, trim_repetitive_segment


def test_repetition_guard_rejects_obvious_sentence_loops() -> None:
    text = "I like apples. I like apples. I like apples. I like apples."
    assert is_repetitive_segment(text, compression_ratio=8.0, avg_logprob=-1.1) is True


def test_repetition_guard_preserves_normal_dictation_text() -> None:
    text = "The project status update is scheduled for tomorrow morning."
    assert is_repetitive_segment(text, compression_ratio=1.6, avg_logprob=-0.2) is False


def test_trim_repetitive_segment_collapses_adjacent_sentence_repeats() -> None:
    text = "Please review the release notes. Please review the release notes. Please review the release notes."
    assert trim_repetitive_segment(text) == "Please review the release notes."


def test_dedupe_boundary_merges_suffix_prefix_overlap() -> None:
    assert dedupe_boundary("hello my name is", "my name is Alex") == "hello my name is Alex"
