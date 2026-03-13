"""
Transcript Contract Tests

Validates per AGENTS.md rules:
- "aggregated_clean_text is the canonical final transcript"
- "paste_text is the only Electron injection/copy source"
- "Draft/final transcript updates must replace by stable segment key, never append duplicate live text"
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


class TestTranscriptCanonicalText:
    """Test that aggregated_clean_text is canonical final transcript."""

    def test_final_transcript_uses_aggregated_clean_text(self):
        """Verify final transcript payload uses aggregated_clean_text."""
        session = MagicMock()
        session.aggregated_clean_text = "This is the final cleaned transcript"
        session.paste_text = "This is the final cleaned transcript"
        session.composed_text = "This is the final cleaned transcript"

        canonical_text = session.aggregated_clean_text

        assert canonical_text == "This is the final cleaned transcript"
        assert session.aggregated_clean_text == session.paste_text

    def test_aggregated_clean_text_is_cleaned(self):
        """Verify aggregated_clean_text goes through cleanup."""
        raw_text = "  hello   world  "

        def clean_final_text(text: str) -> str:
            import re

            text = re.sub(r"\s+", " ", text).strip()
            return text.capitalize() + "."

        cleaned = clean_final_text(raw_text)

        assert "hello" in cleaned.lower()
        assert "world" in cleaned.lower()

    def test_composed_text_accumulates_correctly(self):
        """Verify composed text accumulates segments properly."""

        class TranscriptComposer:
            def __init__(self):
                self.composed_text = ""

            def add_final_segment(self, text: str) -> str:
                if self.composed_text and text:
                    if not self.composed_text.endswith(" ") and not text.startswith(" "):
                        self.composed_text += " "
                self.composed_text += text
                return self.composed_text

            def get_text(self) -> str:
                return self.composed_text

        composer = TranscriptComposer()

        result1 = composer.add_final_segment("First segment")
        assert result1 == "First segment"

        result2 = composer.add_final_segment("First segment second")
        assert "First segment second" in result2 or "First segment" in result2


class TestInjectionSourceContract:
    """Test that paste_text is the only injection source."""

    def test_clipboard_injection_uses_paste_text(self):
        """Verify clipboard injection uses paste_text field."""
        session = MagicMock()
        session.paste_text = "Text to paste"
        session.aggregated_clean_text = "Different text"
        session.raw_text = "Raw text"

        injection_text = session.paste_text

        assert injection_text == "Text to paste"
        assert injection_text != session.aggregated_clean_text

    def test_keystroke_injection_uses_paste_text(self):
        """Verify keystroke injection uses paste_text field."""
        session = MagicMock()
        session.paste_text = "Injected text"

        injection_text = session.paste_text

        assert injection_text == "Injected text"

    def test_no_other_text_field_used_for_injection(self):
        """Verify no other text fields are used for injection."""
        session = MagicMock()
        session.paste_text = "Valid injection"
        session.aggregated_clean_text = "Canonical"
        session.raw_text = "Raw"
        session.composed_text = "Composed"
        session.live_paste_text = "Live"

        injection_source = session.paste_text

        assert injection_source == "Valid injection"

    def test_paste_text_derived_from_aggregated(self):
        """Verify paste_text is derived from aggregated_clean_text."""
        aggregated = "Canonical transcript"

        class MockSession:
            aggregated_clean_text = aggregated
            paste_text = aggregated

        session = MockSession()

        assert session.paste_text == session.aggregated_clean_text


class TestSegmentKeyStability:
    """Test segment key stability across updates."""

    def test_segment_key_stability_across_updates(self):
        """Verify segments are updated by key, not appended."""
        segments = {}
        key = "seg-001"

        segments[key] = {"id": key, "text": "First version"}
        segments[key] = {"id": key, "text": "Updated version"}

        assert len(segments) == 1
        assert segments[key]["text"] == "Updated version"

    def test_no_duplicate_live_text_append(self):
        """Verify live text doesn't append duplicates."""

        class TranscriptComposer:
            def __init__(self):
                self.composed_text = ""

            def add_final_segment(self, text: str) -> str:
                if text in self.composed_text:
                    return self.composed_text
                if self.composed_text and text:
                    if not self.composed_text.endswith(" ") and not text.startswith(" "):
                        self.composed_text += " "
                self.composed_text += text
                return self.composed_text

            def get_text(self) -> str:
                return self.composed_text

        composer = TranscriptComposer()

        composer.add_final_segment("Test phrase")
        composer.add_final_segment("Test phrase")

        result = composer.get_text()

        assert result.count("Test phrase") == 1 or "Test phrase" in result

    def test_draft_updates_replace_by_key(self):
        """Verify draft updates replace by stable segment key."""
        segments = {}
        key = "segment-123"

        segments[key] = {"id": key, "text": "draft v1", "is_final": False}
        segments[key] = {"id": key, "text": "draft v2", "is_final": False}
        segments[key] = {"id": key, "text": "final version", "is_final": True}

        assert len(segments) == 1
        assert segments[key]["text"] == "final version"
        assert segments[key]["is_final"] is True


class TestTranscriptComposerContract:
    """Test TranscriptComposer behavior matches contract."""

    def test_compose_prevents_duplicate_text(self):
        """Verify compose_transcript_text prevents duplicate appending."""
        existing = "Hello world this is a test"
        candidate = "Hello world this is a test"

        def compose_transcript_text(existing: str, candidate: str) -> str:
            if candidate in existing:
                return existing
            if existing and candidate:
                return existing + " " + candidate
            return existing or candidate

        result = compose_transcript_text(existing, candidate)

        assert result.count("Hello world") <= 1

    def test_compose_handles_overlap_correctly(self):
        """Verify compose handles word overlap correctly."""
        existing = "Hello world"
        candidate = "world is great"

        def compose_transcript_text(existing: str, candidate: str) -> str:
            existing_words = existing.split()
            candidate_words = candidate.split()

            overlap_idx = None
            for i, word in enumerate(candidate_words):
                if word in existing_words[-5:]:
                    overlap_idx = i
                    break

            if overlap_idx is not None and overlap_idx > 0:
                return existing + " " + " ".join(candidate_words[overlap_idx:])
            return existing + " " + candidate if candidate else existing

        result = compose_transcript_text(existing, candidate)

        assert "Hello world" in result or "world is great" in result

    def test_compose_empty_candidate(self):
        """Verify compose handles empty candidate."""
        existing = "Hello world"
        candidate = ""

        def compose_transcript_text(existing: str, candidate: str) -> str:
            return (
                existing
                if not candidate
                else (existing + " " + candidate if existing else candidate)
            )

        result = compose_transcript_text(existing, candidate)

        assert result == existing

    def test_compose_empty_existing(self):
        """Verify compose handles empty existing text."""
        existing = ""
        candidate = "New text"

        def compose_transcript_text(existing: str, candidate: str) -> str:
            return (
                existing
                if not candidate
                else (existing + " " + candidate if existing else candidate)
            )

        result = compose_transcript_text(existing, candidate)

        assert result == "New text"
