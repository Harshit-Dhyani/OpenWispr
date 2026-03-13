from __future__ import annotations

from app.stt.dictation_cleanup import (
    clean_final_text,
    clean_final_text_from_segments,
    compose_transcript_text,
    merge_segment_texts,
    normalize_dictation_text,
    stabilize_partial_text,
)


def test_normalize_dictation_text_removes_extra_spacing():
    assert (
        normalize_dictation_text("  quarterly   project   update  ! ")
        == "quarterly project update!"
    )


def test_stabilize_partial_prefers_existing_for_tiny_regressions():
    previous = "Quarterly project update"
    candidate = "quarterly project updat"

    assert stabilize_partial_text(previous, candidate) == "Quarterly project update"


def test_clean_final_text_collapses_adjacent_duplicates_and_punctuates():
    result = clean_final_text_from_segments(
        [
            "quarterly project update",
            "quarterly project update",
            "quarterly project update today",
        ]
    )

    assert result.raw_final_text == "quarterly project update quarterly project update today"
    assert result.clean_final_text == "Quarterly project update quarterly project update today."
    assert result.display_partial_text == "Quarterly project update today"


def test_clean_final_text_suppresses_isolated_filler():
    result = clean_final_text_from_segments(["okay"])

    assert result.raw_final_text == "okay"
    assert result.clean_final_text == ""


def test_clean_final_text_suppresses_common_hallucinated_endings():
    result = clean_final_text_from_segments(["thank you"])

    assert result.raw_final_text == "thank you"
    assert result.clean_final_text == ""


def test_compose_transcript_text_dedupes_overlap():
    merged = compose_transcript_text("quarterly project update for", "for tomorrow morning")

    assert merged == "quarterly project update for tomorrow morning"


def test_compose_transcript_text_drops_near_duplicate_tail():
    merged = compose_transcript_text(
        "today we are testing the dictation pipeline",
        "today we are testing the dictation pipeline",
    )

    assert merged == "today we are testing the dictation pipeline"


def test_compose_transcript_text_appends_non_overlapping_segment():
    merged = compose_transcript_text("quarterly project update", "for tomorrow morning")

    assert merged == "quarterly project update for tomorrow morning"


def test_compose_transcript_text_normalizes_punctuation_differences():
    merged = compose_transcript_text("quarterly project update", "Quarterly project update,")

    assert merged == "Quarterly project update,"


def test_compose_transcript_text_joins_hyphenated_tail_without_space():
    merged = compose_transcript_text("state-of-the-", "art models")

    assert merged == "state-of-the-art models"


def test_compose_transcript_text_replaces_refined_tail():
    merged = compose_transcript_text("quarterly project updat", "quarterly project update")

    assert merged == "quarterly project update"


def test_clean_final_text_formats_composed_string():
    assert clean_final_text("quarterly   project update") == "Quarterly project update."


def test_clean_final_text_collapses_repeated_sentence_loops():
    text = "Please review the release notes. Please review the release notes. Please review the release notes."

    assert clean_final_text(text) == "Please review the release notes."


def test_merge_segment_texts_replaces_refined_tail_segment():
    segments = [
        {
            "text": "Quarterly project updat",
            "raw_text": "quarterly project updat",
        }
    ]

    merged = merge_segment_texts(segments, "quarterly project update")

    assert merged is True
    assert segments[0]["raw_text"] == "quarterly project update"
    assert segments[0]["text"] == "Quarterly project update"
