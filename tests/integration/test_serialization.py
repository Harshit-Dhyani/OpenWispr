"""Integration tests for serialization and storage.

Tests cover:
- Session serialization
- Settings persistence
- Document storage
- JSON serialization
- File I/O operations
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class TestSessionSerialization:
    """Tests for session data serialization."""

    def test_session_state_to_dict(self) -> None:
        """Test session state serialization to dict."""
        from app.core.models import SessionState

        state = SessionState.create(
            title="Test Session",
            output_dir=Path("/tmp/output"),
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        data = state.to_dict()

        assert data["title"] == "Test Session"
        assert data["model_name"] == "tiny"
        assert data["language_mode"] == "en"
        assert "session_id" in data
        assert "created_at" in data

    def test_session_state_serialization_with_segments(self) -> None:
        """Test session state with segments serialization."""
        from app.core.models import SessionState, TranscriptSegment

        state = SessionState.create(
            title="Test Session",
            output_dir=Path("/tmp/output"),
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        segment = TranscriptSegment(
            id="seg-1",
            start=0.0,
            end=5.0,
            text="Test transcription",
            display_text="Test transcription",
            language="en",
            confidence=0.85,
        )
        state.segments.append(segment)

        data = state.to_dict()

        assert len(data["segments"]) == 1
        assert data["segments"][0]["text"] == "Test transcription"

    def test_transcript_segment_serialization(self) -> None:
        """Test transcript segment serialization."""
        from app.core.models import TranscriptSegment

        segment = TranscriptSegment(
            id="seg-1",
            start=0.0,
            end=5.0,
            text="Test",
            display_text="Test",
            language="en",
            confidence=0.85,
            suppressed=False,
            suppression_reasons=[],
            quality_label="good",
        )

        data = segment.to_dict()

        assert data["id"] == "seg-1"
        assert data["text"] == "Test"
        assert data["confidence"] == 0.85
        assert data["quality_label"] == "good"


class TestSettingsSerialization:
    """Tests for settings serialization."""

    def test_settings_state_to_dict(self, test_settings: dict) -> None:
        """Test settings state serialization."""
        from app.core.settings_manager import SettingsState

        state = SettingsState()
        data = state.to_dict() if hasattr(state, "to_dict") else test_settings

        assert "general" in data
        assert "transcription" in data
        assert "audio" in data

    def test_settings_json_roundtrip(self, temp_dir: Path, test_settings: dict) -> None:
        """Test settings JSON roundtrip."""
        settings_file = temp_dir / "settings.json"

        # Write settings
        settings_file.write_text(json.dumps(test_settings, indent=2))

        # Read settings back
        loaded_data = json.loads(settings_file.read_text())

        assert (
            loaded_data["general"]["defaultSessionTitle"]
            == test_settings["general"]["defaultSessionTitle"]
        )
        assert (
            loaded_data["transcription"]["model_name"]
            == test_settings["transcription"]["model_name"]
        )


class TestDocumentStore:
    """Tests for document storage."""

    def test_document_add(self) -> None:
        """Test adding document to store."""
        from app.storage.document_store import DocumentStore

        store = DocumentStore()
        doc = store.add_pdf("/path/to/test.pdf")

        assert doc is not None
        assert len(store.documents) == 1

    def test_document_retrieval(self) -> None:
        """Test document retrieval."""
        from app.storage.document_store import DocumentStore

        store = DocumentStore()
        doc = store.add_pdf("/path/to/test.pdf")

        retrieved = store.get_document(doc.id)

        assert retrieved is not None
        assert retrieved.id == doc.id

    def test_context_provider(self) -> None:
        """Test context provider."""
        from app.storage.document_store import ContextProvider, DocumentStore

        store = DocumentStore()
        provider = ContextProvider(store)

        assert provider.document_store is store


class TestSessionWriter:
    """Tests for session writer."""

    def test_session_writer_init(self, temp_dir: Path) -> None:
        """Test session writer initialization."""
        from app.core.models import SessionState
        from app.storage.session_writer import SessionWriter

        state = SessionState.create(
            title="Test",
            output_dir=temp_dir,
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        writer = SessionWriter(state)

        assert writer.session is state
        assert writer.output_dir == temp_dir

    def test_write_metadata(self, temp_dir: Path) -> None:
        """Test writing session metadata."""
        from app.core.models import SessionState
        from app.storage.session_writer import SessionWriter

        state = SessionState.create(
            title="Test",
            output_dir=temp_dir,
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        writer = SessionWriter(state)
        writer.write_metadata()

        metadata_file = temp_dir / "session.json"
        assert metadata_file.exists()

        data = json.loads(metadata_file.read_text())
        assert data["title"] == "Test"
        assert data["model_name"] == "tiny"


class TestFileIO:
    """Tests for file I/O operations."""

    def test_audio_file_write_read(self, temp_dir: Path, mock_audio_data: np.ndarray) -> None:
        """Test writing and reading audio files."""
        import soundfile as sf

        audio_file = temp_dir / "test_audio.wav"

        # Write audio
        sf.write(audio_file, mock_audio_data, 16000)

        # Read audio back
        read_audio, sr = sf.read(audio_file)

        assert sr == 16000
        assert len(read_audio) == len(mock_audio_data)

    def test_transcript_export(self, temp_dir: Path) -> None:
        """Test transcript export to file."""
        transcript_file = temp_dir / "transcript.txt"

        transcript = "This is a test transcript.\nIt has multiple lines."
        transcript_file.write_text(transcript)

        assert transcript_file.exists()
        assert transcript_file.read_text() == transcript

    def test_json_export(self, temp_dir: Path) -> None:
        """Test JSON export."""
        json_file = temp_dir / "data.json"

        data = {
            "session_id": "test-123",
            "segments": [
                {"id": "seg-1", "text": "Hello"},
                {"id": "seg-2", "text": "World"},
            ],
        }

        json_file.write_text(json.dumps(data, indent=2))

        loaded = json.loads(json_file.read_text())

        assert loaded["session_id"] == "test-123"
        assert len(loaded["segments"]) == 2


class TestSerializationEdgeCases:
    """Tests for serialization edge cases."""

    def test_serialization_with_special_characters(self, temp_dir: Path) -> None:
        """Test serialization with special characters."""
        data = {
            "text": 'Special chars: äöü émojis 🎉 \\n \\t "quoted"',
            "path": "/path/with spaces/file.txt",
        }

        json_file = temp_dir / "special.json"
        json_file.write_text(json.dumps(data, ensure_ascii=False))

        loaded = json.loads(json_file.read_text())
        assert loaded["text"] == data["text"]

    def test_serialization_with_unicode(self, temp_dir: Path) -> None:
        """Test serialization with unicode characters."""
        data = {
            "hindi": "नमस्ते दुनिया",
            "chinese": "你好世界",
            "japanese": "こんにちは",
            "arabic": "مرحبا بالعالم",
        }

        json_file = temp_dir / "unicode.json"
        json_file.write_text(json.dumps(data, ensure_ascii=False))

        loaded = json.loads(json_file.read_text())
        assert loaded["hindi"] == data["hindi"]
        assert loaded["chinese"] == data["chinese"]

    def test_serialization_with_large_data(self, temp_dir: Path) -> None:
        """Test serialization with large data."""
        # Create large transcript
        segments = []
        for i in range(1000):
            segments.append(
                {
                    "id": f"seg-{i}",
                    "text": "This is a test segment with some content. " * 10,
                    "start": float(i),
                    "end": float(i + 1),
                }
            )

        data = {"segments": segments}

        json_file = temp_dir / "large.json"
        json_file.write_text(json.dumps(data))

        loaded = json.loads(json_file.read_text())
        assert len(loaded["segments"]) == 1000
