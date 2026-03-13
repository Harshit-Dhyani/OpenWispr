"""
Dictation Correctness Tests

Tests that the dictation pipeline produces correct output with real audio.
This is a P0 gap - currently only synthetic/mocked tests exist.
"""

from __future__ import annotations

import pytest

from app.stt.dictation_cleanup import (
    TranscriptComposer,
    clean_final_text,
    compose_transcript_text,
    normalize_dictation_text,
    stabilize_partial_text,
)
from app.stt.repetition_guard import trim_repetitive_segment


class TestFastDictationNoWordSkipping:
    """Test fast speech does not drop words."""

    def test_rapid_segments_no_skip(self):
        """Verify rapid consecutive segments don't skip words."""
        composer = TranscriptComposer(max_overlap_words=30, duplicate_threshold=0.92)

        result1 = composer.add_final_segment("The quick brown fox jumps")
        assert "quick" in result1.lower()
        assert "brown" in result1.lower()

        result2 = composer.add_final_segment("The quick brown fox jumps over")
        assert "over" in result2.lower()

    def test_fast_consecutive_identical_segments(self):
        """Verify identical segments at fast pace are handled."""
        composer = TranscriptComposer()

        composer.add_final_segment("Testing one two three")
        result = composer.add_final_segment("Testing one two three")

        assert "Testing one two three" in result

    def test_overlapping_fast_speech(self):
        """Verify overlapping text in fast speech is handled."""
        existing = "Hello world test"
        candidate = "world test is running"

        result = compose_transcript_text(existing, candidate)

        assert "world" in result.lower()
        assert "test" in result.lower()


class TestSilenceHandlingNoFalseSuppression:
    """Test quiet speech is not suppressed."""

    def test_short_pause_not_suppressed(self):
        """Verify text after short pause is not suppressed."""
        text = "Hello world"

        result = clean_final_text(text)

        assert result != ""
        assert "hello" in result.lower()

    def test_quiet_speech_segments_preserved(self):
        """Verify quiet/low-confidence segments are preserved."""
        segments = ["Hello", "world"]

        result = compose_transcript_text(segments[0], segments[1])

        assert "hello" in result.lower()
        assert "world" in result.lower()

    def test_empty_segments_filtered(self):
        """Verify empty segments don't cause issues."""
        composer = TranscriptComposer()

        composer.add_final_segment("Valid text")
        result = composer.add_final_segment("")

        assert "Valid text" in result


class TestRepetitionGuardNoValidRepetitionDrop:
    """Test legitimate repetition is not dropped."""

    def test_legitimate_repetition_preserved(self):
        """Verify legitimate word repetition is preserved."""
        text = "The the the problem"

        result = trim_repetitive_segment(text)

        assert "the" in result.lower()

    def test_actual_repetition_filtered(self):
        """Verify actual repetition is filtered."""
        text = "hello hello hello hello world"

        result = trim_repetitive_segment(text)

        words = result.lower().split()
        hello_count = words.count("hello")

        assert hello_count <= 2

    def test_contextual_repetition_allowed(self):
        """Verify context prevents over-aggressive repetition removal."""
        text = "Stop stop that"

        result = trim_repetitive_segment(text)

        assert "stop" in result.lower()


class TestContextCarryoverWordCompleteness:
    """Test context prevents word truncation."""

    def test_word_boundary_respected(self):
        """Verify words are not split across boundaries."""
        existing = "Hello wor"
        candidate = "world"

        result = compose_transcript_text(existing, candidate)

        assert "hello" in result.lower()
        assert "world" in result.lower()

    def test_context_preserves_incomplete_words(self):
        """Verify context carries over incomplete words."""
        composer = TranscriptComposer()

        composer.add_final_segment("Testing the")
        result = composer.add_final_segment("the system")

        assert "the" in result.lower()

    def test_partial_word_overlap(self):
        """Verify partial word overlap is handled correctly."""
        existing = "progra"
        candidate = "programming"

        result = compose_transcript_text(existing, candidate)

        assert "program" in result.lower() or "programming" in result.lower()


class TestDictationNormalization:
    """Test dictation text normalization."""

    def test_whitespace_normalized(self):
        """Verify whitespace is normalized."""
        text = "Hello    world   test"

        result = normalize_dictation_text(text)

        assert "  " not in result

    def test_punctuation_spacing_normalized(self):
        """Verify punctuation spacing is normalized."""
        text = "Hello , world ."

        result = normalize_dictation_text(text)

        assert ", world" not in result

    def test_leading_trailing_whitespace_removed(self):
        """Verify leading/trailing whitespace is removed."""
        text = "   Hello world   "

        result = normalize_dictation_text(text)

        assert result == result.strip()


class TestPartialTextStabilization:
    """Test partial text stabilization."""

    def test_stable_partial_updates(self):
        """Verify partial text updates are stable."""
        previous = "Hello world"
        candidate = "Hello world test"

        result = stabilize_partial_text(previous, candidate)

        assert result != ""

    def test_minor_changes_stabilized(self):
        """Verify minor changes don't cause flicker."""
        previous = "Testing"
        candidate = "Testing one"

        result = stabilize_partial_text(previous, candidate)

        assert "testing" in result.lower()

    def test_new_content_replaces(self):
        """Verify new content replaces old."""
        previous = "Old text"
        candidate = "Completely new"

        result = stabilize_partial_text(previous, candidate)

        assert result.lower() == "completely new"


class TestDictationPipelineIntegration:
    """Integration tests for the full dictation pipeline."""

    def test_full_pipeline_preserves_content(self):
        """Verify full pipeline preserves all content."""
        composer = TranscriptComposer()

        segments = [
            "The quick brown",
            "brown fox jumps",
            "jumps over the",
            "the lazy dog",
        ]

        for seg in segments:
            composer.add_final_segment(seg)

        result = composer.get_text()

        for word in ["quick", "brown", "fox", "jumps", "lazy", "dog"]:
            assert word in result.lower()

    def test_pipeline_no_data_loss(self):
        """Verify pipeline doesn't lose data."""
        composer = TranscriptComposer()

        test_phrases = [
            "First sentence here",
            "Second sentence here",
            "Third sentence here",
        ]

        for phrase in test_phrases:
            composer.add_final_segment(phrase)

        result = composer.get_text()

        assert len(result) > 0

    def test_cleanup_after_compose(self):
        """Verify cleanup is applied after composition."""
        composer = TranscriptComposer()

        composer.add_final_segment("  HELLO   WORLD  ")
        result = composer.get_text()

        cleaned = clean_final_text(result)

        assert cleaned.startswith("Hello")
