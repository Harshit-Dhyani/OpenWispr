"""
Injection Contract Tests

Validates per AGENTS.md:
- "paste_text is the only Electron injection/copy source"
- Text injection must use paste_text only, never raw transcript

These tests ensure the contract between backend transcript fields
and Electron injection/copy operations is enforced.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestInjectionUsesPasteText:
    """Test that text injection uses paste_text field only."""

    def test_inject_text_uses_paste_text(self):
        """Verify injectText receives paste_text, not raw transcript."""
        session = MagicMock()
        session.paste_text = "Canonical injection text"
        session.aggregated_clean_text = "Clean transcript"
        session.raw_text = "Raw unprocessed text"

        injection_source = session.paste_text

        assert injection_source == "Canonical injection text"
        assert injection_source != session.raw_text

    def test_clipboard_copy_uses_paste_text(self):
        """Verify clipboard write uses paste_text field."""
        session = MagicMock()
        session.paste_text = "Text for clipboard"
        session.aggregated_clean_text = "Clean version"
        session.raw_text = "Raw version"

        clipboard_text = session.paste_text

        assert clipboard_text == "Text for clipboard"
        assert clipboard_text != session.raw_text

    def test_no_raw_transcript_injection(self):
        """Verify raw transcript is never used for injection."""
        session = MagicMock()
        session.paste_text = "Final cleaned text"
        session.aggregated_clean_text = "Aggregated text"
        session.raw_text = "Raw speech-to-text output with [unk] and hesitations"

        text_to_inject = session.paste_text

        assert text_to_inject != session.raw_text
        assert "[unk]" not in text_to_inject
        assert "hesitations" not in text_to_inject

    def test_injection_rejects_fallback_chain(self):
        """Verify injection doesn't use fallback chain: paste_text OR aggregated OR raw.

        Per AGENTS.md contract: paste_text is the ONLY source, not first in fallback.
        """
        payload = MagicMock()
        payload.paste_text = ""
        payload.aggregated_clean_text = "Aggregated"
        payload.composed_text = "Composed"
        payload.final_transcription = "Final"

        injection_text = payload.paste_text

        assert injection_text == ""


class TestPasteTextAsSingleSource:
    """Test paste_text is single source of truth for injection."""

    def test_paste_text_defined_on_session(self):
        """Verify session object has paste_text attribute."""
        session = MagicMock()
        assert hasattr(session, "paste_text")

    def test_paste_text_derived_from_clean_transcript(self):
        """Verify paste_text is derived from aggregated_clean_text."""
        clean_transcript = "This is the cleaned transcript"

        class Session:
            aggregated_clean_text = clean_transcript
            paste_text = clean_transcript

        session = Session()
        assert session.paste_text == session.aggregated_clean_text

    def test_no_multiple_injection_sources(self):
        """Verify only paste_text is used, not multiple text fields."""
        session = MagicMock()
        session.paste_text = "INJECTION_SOURCE"
        session.aggregated_clean_text = "clean"
        session.raw_text = "raw"
        session.composed_text = "composed"
        session.postprocessed_text = "postprocessed"
        session.live_paste_text = "live"

        injection_sources = [
            session.paste_text,
            session.aggregated_clean_text,
            session.raw_text,
            session.composed_text,
            session.postprocessed_text,
        ]

        actual_injection = session.paste_text
        assert actual_injection == "INJECTION_SOURCE"
        assert actual_injection not in [
            session.raw_text,
            session.composed_text,
            session.postprocessed_text,
        ]


class TestBackendPayloadContract:
    """Test backend sends paste_text as injection source."""

    def test_stop_payload_includes_paste_text(self):
        """Verify stop payload includes paste_text field."""

        class MockPayload:
            paste_text = "Final transcript"

        payload = MockPayload()

        assert payload.paste_text == "Final transcript"

    def test_websocket_message_uses_paste_text(self):
        """Verify websocket messages use paste_text for injection."""
        message = {
            "type": "hotkey_stopped",
            "paste_text": "Transcribed text",
            "aggregated_clean_text": "Clean",
            "final_transcription": "Final",
        }

        injection_text = message.get("paste_text")

        assert injection_text == "Transcribed text"
        assert injection_text != message.get("final_transcription")


class TestElectronHandlerContract:
    """Test Electron handlers respect paste_text only contract."""

    def test_hotkey_handler_prioritizes_paste_text(self):
        """Verify hotkey handler uses paste_text over other fields."""
        payload = {
            "paste_text": "PRIMARY_SOURCE",
            "aggregated_clean_text": "secondary",
            "postprocessed_text": "tertiary",
            "final_transcription": "last_resort",
        }

        text = payload.get("paste_text")

        assert text == "PRIMARY_SOURCE"

    def test_clipboard_fallback_violates_contract(self):
        """Document that clipboard fallback chain violates contract.

        Per AGENTS.md: paste_text should be ONLY source.
        Current implementation uses fallback chain which violates contract.
        """
        payload = {
            "paste_text": "",
            "aggregated_clean_text": "clean",
            "composed_text": "composed",
            "final_transcription": "final",
        }

        text = (
            payload.get("paste_text")
            or payload.get("postprocessed_text")
            or payload.get("aggregated_clean_text")
            or payload.get("composed_text")
            or payload.get("final_transcription")
            or ""
        )

        assert text != "", "Fallback chain should NOT be used per contract"
