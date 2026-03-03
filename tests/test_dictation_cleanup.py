from __future__ import annotations

from app.stt.dictation_cleanup import (
    clean_final_text_from_segments,
    merge_segment_texts,
    normalize_dictation_text,
    stabilize_partial_text,
)


def test_normalize_dictation_text_removes_extra_spacing():
    assert normalize_dictation_text("  hello   world  ! ") == "hello world!"


def test_stabilize_partial_prefers_existing_for_tiny_regressions():
    previous = "Hello world"
    candidate = "hello worl"

    assert stabilize_partial_text(previous, candidate) == "Hello world"


def test_clean_final_text_collapses_adjacent_duplicates_and_punctuates():
    result = clean_final_text_from_segments(
        [
            "hello world",
            "hello world",
            "hello world again",
        ]
    )

    assert result.raw_final_text == "hello world hello world again"
    assert result.clean_final_text == "Hello world hello world again."
    assert result.display_partial_text == "Hello world again"


def test_clean_final_text_suppresses_isolated_filler():
    result = clean_final_text_from_segments(["okay"])

    assert result.raw_final_text == "okay"
    assert result.clean_final_text == ""


def test_clean_final_text_suppresses_common_hallucinated_endings():
    result = clean_final_text_from_segments(["thank you"])

    assert result.raw_final_text == "thank you"
    assert result.clean_final_text == ""


def test_merge_segment_texts_replaces_refined_tail_segment():
    segments = [
        {
            "text": "Hello worl",
            "raw_text": "hello worl",
        }
    ]

    merged = merge_segment_texts(segments, "hello world")

    assert merged is True
    assert segments[0]["raw_text"] == "hello world"
    assert segments[0]["text"] == "Hello world"
