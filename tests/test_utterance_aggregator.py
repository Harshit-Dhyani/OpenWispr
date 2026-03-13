from __future__ import annotations

from app.stt.utterance_aggregator import UtteranceAggregator


def test_utterance_aggregator_merges_overlap_into_single_paragraph() -> None:
    aggregator = UtteranceAggregator()

    aggregator.add_segment(
        segment_id="seg-1",
        text="whenever I try to do loops",
        start=0.0,
        end=1.0,
        confidence=0.92,
    )
    aggregator.add_segment(
        segment_id="seg-2",
        text="to do loops in python they confuse me",
        start=0.8,
        end=2.0,
        confidence=0.91,
    )

    result = aggregator.finalize()

    assert result.aggregated_raw_text == "whenever I try to do loops to do loops in python they confuse me"
    assert result.aggregated_clean_text == "Whenever I try to do loops in python they confuse me."
    assert result.accepted_segments_count == 2
    assert result.merged_segments_count == 1


def test_utterance_aggregator_drops_repeated_segment_tail() -> None:
    aggregator = UtteranceAggregator()

    aggregator.add_segment(segment_id="seg-1", text="today we are testing the dictation pipeline")
    aggregator.add_segment(segment_id="seg-2", text="today we are testing the dictation pipeline")

    result = aggregator.finalize()

    assert result.aggregated_clean_text == "Today we are testing the dictation pipeline."
    assert result.accepted_segments_count == 1
    assert result.dropped_segments_count == 1


def test_utterance_aggregator_skips_suppressed_segments() -> None:
    aggregator = UtteranceAggregator()

    aggregator.add_segment(
        segment_id="seg-1",
        text="um",
        suppressed=True,
        suppression_reasons=["low_value_filler"],
    )
    aggregator.add_segment(
        segment_id="seg-2",
        text="this is the kept text",
        start=0.5,
        end=1.2,
        confidence=0.87,
    )

    result = aggregator.finalize()

    assert result.aggregated_clean_text == "This is the kept text."
    assert result.accepted_segments_count == 1
    assert result.dropped_segments_count == 1
    assert "suppressed:low_value_filler" in result.warnings


def test_utterance_aggregator_accepts_legacy_positional_arguments() -> None:
    aggregator = UtteranceAggregator()

    aggregator.add_segment("seg-1", "project status update", "project status update", start=0.0, end=1.0)

    result = aggregator.finalize()

    assert result.aggregated_clean_text == "Project status update."
    assert result.accepted_segments_count == 1


def test_utterance_aggregator_trims_repetitive_loop_segment() -> None:
    aggregator = UtteranceAggregator()

    aggregator.add_segment(
        segment_id="seg-1",
        text="Please review the release notes. Please review the release notes. Please review the release notes.",
        start=0.0,
        end=1.0,
        confidence=0.82,
    )

    result = aggregator.finalize()

    assert result.aggregated_clean_text == "Please review the release notes."
    assert result.accepted_segments_count == 1
    assert "trimmed:repetition" in result.warnings
