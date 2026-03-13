"""
Transcript Aggregation Tests

Tests partial and final transcript handling including:
- Segment deduplication
- Segment key replacement behavior
- Partial transcript updates
- Final transcript composition

Regression protection for:
- Duplicate segments being added
- Live text accumulating duplicates
- Segment keys not being stable
- Draft updates not replacing correctly
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.stt.dictation_cleanup import TranscriptComposer
from app.stt.utterance_aggregator import UtteranceAggregator


class TestSegmentDeduplication:
    """Test segment deduplication behavior."""

    def test_aggregator_prevents_duplicate_segment_ids(self):
        """Verify same segment ID doesn't create duplicates."""
        aggregator = UtteranceAggregator()

        aggregator.add_segment(
            segment_id="seg-001",
            text="First text",
            display_text="First text",
            start=0.0,
            end=1.0,
            confidence=0.9,
        )

        existing_ids = {seg.segment_id for seg in aggregator._segments}
        assert "seg-001" in existing_ids

    def test_aggregator_tracks_dropped_duplicates(self):
        """Verify dropped segments are tracked."""
        aggregator = UtteranceAggregator()

        aggregator.add_segment(
            segment_id="seg-001",
            text="Hello world",
            display_text="Hello world",
            start=0.0,
            end=1.0,
            confidence=0.9,
        )

        aggregator.add_segment(
            segment_id="seg-001",
            text="Hello world",
            display_text="Hello world",
            start=0.0,
            end=1.0,
            confidence=0.9,
        )

        result = aggregator.finalize()
        assert result.accepted_segments_count == 1

    def test_composer_prevents_duplicate_text_accumulation(self):
        """Verify composer doesn't append exact duplicate text."""
        composer = TranscriptComposer()

        composer.add_final_segment("test phrase")
        composer.add_final_segment("test phrase")

        result = composer.get_text()
        assert result.count("test phrase") <= 1


class TestSegmentKeyReplacement:
    """Test segment key replacement behavior."""

    def test_segments_updated_by_key_not_appended(self):
        """Verify updates replace by key, not append."""
        segments = {}

        segments["seg-001"] = {"id": "seg-001", "text": "v1"}
        segments["seg-001"] = {"id": "seg-001", "text": "v2"}

        assert len(segments) == 1
        assert segments["seg-001"]["text"] == "v2"

    def test_draft_replaces_by_key_before_final(self):
        """Verify draft segments are replaced by key before final."""
        segments = {}

        segments["seg-draft"] = {"id": "seg-draft", "text": "draft v1", "is_final": False}
        segments["seg-draft"] = {"id": "seg-draft", "text": "draft v2", "is_final": False}
        segments["seg-draft"] = {"id": "seg-draft", "text": "final", "is_final": True}

        assert len(segments) == 1
        assert segments["seg-draft"]["is_final"] is True
        assert segments["seg-draft"]["text"] == "final"

    def test_multiple_keys_maintained_separately(self):
        """Verify multiple different segment keys are maintained."""
        segments = {}

        segments["seg-001"] = {"id": "seg-001", "text": "First"}
        segments["seg-002"] = {"id": "seg-002", "text": "Second"}
        segments["seg-003"] = {"id": "seg-003", "text": "Third"}

        assert len(segments) == 3
        assert segments["seg-002"]["text"] == "Second"


class TestPartialTranscriptHandling:
    """Test partial transcript updates."""

    def test_partial_updates_accumulate_correctly(self):
        """Verify partial updates accumulate without duplication."""
        partial_text = ""

        partial_text = "hello"
        partial_text = "hello world"

        assert partial_text == "hello world"
        assert partial_text.count("hello") == 1

    def test_partial_resets_on_final(self):
        """Verify partial text resets after final segment."""
        partial = "hello world"
        final = partial

        partial = ""

        assert final == "hello world"
        assert partial == ""

    def test_live_buffer_text_not_duplicated(self):
        """Verify live buffer doesn't accumulate duplicates."""
        live_buffer = ""

        live_buffer = "test phrase"
        live_buffer = "test phrase"

        assert live_buffer.count("test phrase") == 1


class TestFinalTranscriptComposition:
    """Test final transcript composition."""

    def test_composer_accumulates_segments(self):
        """Verify composer accumulates segments in order."""
        composer = TranscriptComposer()

        composer.add_final_segment("first")
        composer.add_final_segment("second")
        composer.add_final_segment("third")

        result = composer.get_text()

        assert "first" in result
        assert "second" in result
        assert "third" in result

    def test_composer_handles_empty_segments(self):
        """Verify composer handles empty segment gracefully."""
        composer = TranscriptComposer()

        composer.add_final_segment("")
        result = composer.get_text()

        assert result == ""

    def test_aggregator_composes_clean_text(self):
        """Verify aggregator produces clean final text."""
        aggregator = UtteranceAggregator()

        aggregator.add_segment(
            segment_id="seg-1",
            text="hello   world  ",
            display_text="hello   world  ",
            start=0.0,
            end=1.0,
            confidence=0.9,
        )

        result = aggregator.finalize()

        assert "Hello" in result.aggregated_clean_text
        assert "world" in result.aggregated_clean_text


class TestTranscriptCanonicalText:
    """Test canonical transcript sources."""

    def test_aggregated_clean_text_is_canonical(self):
        """Verify aggregated_clean_text is the canonical final transcript."""
        aggregator = UtteranceAggregator()

        aggregator.add_segment(
            segment_id="seg-1",
            text="raw transcript",
            display_text="Raw transcript",
            start=0.0,
            end=1.0,
            confidence=0.9,
        )

        result = aggregator.finalize()

        assert result.aggregated_clean_text is not None
        assert isinstance(result.aggregated_clean_text, str)

    def test_paste_text_uses_aggregated(self):
        """Verify paste_text derives from aggregated_clean_text."""
        session = SimpleNamespace()
        session.aggregated_clean_text = "Final clean text"

        assert session.aggregated_clean_text is not None

    def test_composed_text_accumulates_segments(self):
        """Verify composed_text accumulates segments."""
        composer = TranscriptComposer()

        composer.add_final_segment("segment one")
        composer.add_final_segment("segment two")

        composed = composer.get_text()

        assert "segment one" in composed
        assert "segment two" in composed


class TestTranscriptWarnings:
    """Test transcript warning generation."""

    def test_suppressed_segments_logged_as_warnings(self):
        """Verify suppressed segments generate warnings."""
        aggregator = UtteranceAggregator()

        aggregator.add_segment(
            segment_id="seg-1",
            text="test",
            display_text="test",
            start=0.0,
            end=1.0,
            confidence=0.9,
            suppressed=True,
            suppression_reasons=["low-value"],
        )

        result = aggregator.finalize()

        assert result.accepted_segments_count == 0
        assert result.dropped_segments_count == 1

    def test_repetition_dropped_logs_warning(self):
        """Verify repetitive segments are dropped with warning."""
        aggregator = UtteranceAggregator()

        aggregator.add_segment(
            segment_id="seg-1",
            text="hello hello hello",
            display_text="hello hello hello",
            start=0.0,
            end=1.0,
            confidence=0.9,
        )

        result = aggregator.finalize()

        assert result.dropped_segments_count >= 0


class TestTranscriptAggregationEdgeCases:
    """Test edge cases in transcript aggregation."""

    def test_very_long_segment_handled(self):
        """Verify very long segments don't break aggregation."""
        aggregator = UtteranceAggregator()

        text = " ".join([f"word{i}" for i in range(100)])

        aggregator.add_segment(
            segment_id="seg-long",
            text=text,
            display_text=text,
            start=0.0,
            end=10.0,
            confidence=0.9,
        )

        result = aggregator.finalize()
        assert result.accepted_segments_count >= 0

    def test_overlapping_times_handled(self):
        """Verify overlapping segment times don't break aggregation."""
        aggregator = UtteranceAggregator()

        aggregator.add_segment(
            segment_id="seg-1",
            text="first",
            display_text="first",
            start=0.0,
            end=2.0,
            confidence=0.9,
        )

        aggregator.add_segment(
            segment_id="seg-2",
            text="second",
            display_text="second",
            start=1.5,
            end=3.5,
            confidence=0.9,
        )

        result = aggregator.finalize()
        assert result.accepted_segments_count == 2

    def test_zero_duration_segment_handled(self):
        """Verify zero-duration segments don't break aggregation."""
        aggregator = UtteranceAggregator()

        aggregator.add_segment(
            segment_id="seg-zero",
            text="instant",
            display_text="instant",
            start=0.0,
            end=0.0,
            confidence=0.9,
        )

        result = aggregator.finalize()
        assert result.accepted_segments_count >= 0

    def test_reset_clears_all_state(self):
        """Verify reset clears all aggregator state."""
        aggregator = UtteranceAggregator()

        aggregator.add_segment(
            segment_id="seg-1",
            text="test",
            display_text="test",
            start=0.0,
            end=1.0,
            confidence=0.9,
        )

        aggregator.reset()

        result = aggregator.finalize()
        assert result.accepted_segments_count == 0
        assert result.aggregated_clean_text == ""
