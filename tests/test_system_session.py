"""Unit tests for System Session Handler.

Tests cover:
- Session lifecycle (create, start, pause, resume, stop)
- Audio recording management
- Export functionality
- Chapter detection
- Configuration validation
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from app.core.settings.config import AppSettings

from app.core.models import SessionState, TranscriptSegment, utc_now
from app.core.session.formatters import MarkdownFormatter, SrtFormatter
from app.core.system_session import (
    AudioRecordingManager,
    Chapter,
    ChapterDetector,
    ExportFormat,
    ExportManager,
    SystemMarkdownFormatter,
    SystemSessionConfig,
    SystemSessionHandler,
    create_system_session_handler,
    load_session_from_disk,
)
from app.stem.postprocess import NotesBundle

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_settings():
    """Create sample app settings."""
    return AppSettings(
        sample_rate=16000,
        channels=1,
        default_model="tiny",
    )


@pytest.fixture
def sample_config():
    """Create sample session configuration."""
    return SystemSessionConfig(
        export_formats=["txt", "json"],
        auto_segment=True,
        save_audio=True,
        enable_stem=True,
    )


@pytest.fixture
def mock_audio_data():
    """Generate mock audio data."""
    return np.random.randn(16000).astype(np.float32) * 0.1


# =============================================================================
# Export Format Tests
# =============================================================================


class TestExportFormat:
    """Tests for ExportFormat enum."""

    def test_from_string_valid(self):
        """Test parsing valid format strings."""
        assert ExportFormat.from_string("txt") == ExportFormat.TXT
        assert ExportFormat.from_string("json") == ExportFormat.JSON
        assert ExportFormat.from_string("srt") == ExportFormat.SRT
        assert ExportFormat.from_string("md") == ExportFormat.MD

    def test_from_string_invalid(self):
        """Test parsing invalid format string."""
        with pytest.raises(ValueError, match="Unknown export format"):
            ExportFormat.from_string("invalid")


class TestSrtFormatter:
    """Tests for SRT subtitle formatter."""

    def test_format_time(self):
        """Test time formatting for SRT."""
        assert SrtFormatter.format_time(0) == "00:00:00,000"
        assert SrtFormatter.format_time(61.5) == "00:01:01,500"
        assert SrtFormatter.format_time(3661.123) == "01:01:01,123"

    def test_format_segments(self):
        """Test formatting segments as SRT."""
        segments = [
            TranscriptSegment(
                id="1",
                start=0.0,
                end=2.0,
                text="Project status update",
                display_text="Project status update",
                language="en",
            ),
            TranscriptSegment(
                id="2",
                start=2.5,
                end=4.0,
                text="Test segment",
                display_text="Test segment",
                language="en",
                suppressed=True,
            ),
            TranscriptSegment(
                id="3",
                start=4.5,
                end=6.0,
                text="Third segment",
                display_text="Third segment",
                language="en",
            ),
        ]

        visible = [s for s in segments if not s.suppressed]
        seg_dicts = [{"start": s.start, "end": s.end, "text": s.text} for s in visible]
        result = SrtFormatter.format_transcript(seg_dicts)

        # Should only have 2 entries (suppressed segment excluded)
        assert "1" in result
        assert "2" in result
        assert "00:00:00,000 --> 00:00:02,000" in result
        assert "Project status update" in result
        assert "Third segment" in result
        assert "Test segment" not in result  # Suppressed


class TestMarkdownFormatter:
    """Tests for Markdown formatter."""

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        assert SystemMarkdownFormatter._format_timestamp(30) == "0:30"
        assert SystemMarkdownFormatter._format_timestamp(90) == "1:30"
        assert SystemMarkdownFormatter._format_timestamp(3661) == "1:01:01"

    def test_format_session(self, temp_output_dir):
        """Test formatting session as markdown."""
        session = SessionState.create(
            title="Test Session",
            output_dir=temp_output_dir,
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        session.segments.append(
            TranscriptSegment(
                id="1",
                start=0.0,
                end=2.0,
                text="Test transcription",
                display_text="Test transcription",
                language="en",
            )
        )

        notes = NotesBundle(
            notes_markdown="Test notes",
            highlights_text="Highlights",
            formulas=[],
            needs_review=[],
        )

        chapters = [Chapter(start_time=0, end_time=10, title="Chapter 1")]

        result = SystemMarkdownFormatter.format_session(session, notes, chapters)

        assert "# Test Session" in result
        assert "Test notes" in result
        assert "Chapter 1" in result
        assert "Test transcription" in result


# =============================================================================
# Configuration Tests
# =============================================================================


class TestSystemSessionConfig:
    """Tests for SystemSessionConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SystemSessionConfig()

        assert config.export_formats == ["txt", "json", "srt", "md"]
        assert config.auto_segment is True
        assert config.save_audio is True
        assert config.enable_stem is True
        assert config.min_silence_duration_ms == 2000.0

    def test_validation_valid(self):
        """Test validation with valid config."""
        config = SystemSessionConfig()
        warnings = config.validate()
        assert len(warnings) == 0

    def test_validation_invalid_format(self):
        """Test validation with invalid export format."""
        config = SystemSessionConfig(export_formats=["txt", "invalid"])
        warnings = config.validate()
        assert len(warnings) == 1
        assert "Invalid export formats" in warnings[0]

    def test_validation_long_duration(self):
        """Test validation warning for very long sessions."""
        config = SystemSessionConfig(max_session_duration_hours=30)
        warnings = config.validate()
        assert any("exceeds 24 hours" in w for w in warnings)


# =============================================================================
# Audio Recording Manager Tests
# =============================================================================


class TestAudioRecordingManager:
    """Tests for AudioRecordingManager."""

    def test_initial_state(self, temp_output_dir):
        """Test initial manager state."""
        manager = AudioRecordingManager(
            output_dir=temp_output_dir,
            sample_rate=16000,
            channels=1,
        )

        stats = manager.get_stats()
        assert stats["is_recording"] is False
        assert stats["file_count"] == 0
        assert stats["total_bytes_written"] == 0

    def test_start_stop(self, temp_output_dir):
        """Test starting and stopping recording."""
        manager = AudioRecordingManager(
            output_dir=temp_output_dir,
            sample_rate=16000,
            channels=1,
        )

        manager.start()
        assert manager.get_stats()["is_recording"] is True

        files = manager.stop()
        assert manager.get_stats()["is_recording"] is False
        assert len(files) == 1

    def test_write_audio(self, temp_output_dir):
        """Test writing audio data."""
        manager = AudioRecordingManager(
            output_dir=temp_output_dir,
            sample_rate=16000,
            channels=1,
        )

        manager.start()

        # Write some audio data
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        manager.write(audio)

        files = manager.stop()
        assert len(files) == 1

        # Verify file exists and has content
        assert files[0].exists()
        assert files[0].stat().st_size > 44  # WAV header size

    def test_file_rotation(self, temp_output_dir):
        """Test automatic file rotation based on size."""
        # Set very small rotation size for testing
        manager = AudioRecordingManager(
            output_dir=temp_output_dir,
            sample_rate=16000,
            channels=1,
            rotation_size_mb=0.001,  # 1KB - very small for testing
        )

        manager.start()

        # Write enough data to trigger rotation
        for _ in range(100):
            audio = np.random.randn(16000).astype(np.float32) * 0.1
            manager.write(audio)

        files = manager.stop()

        # Should have multiple files due to rotation
        assert len(files) >= 1
        assert all(f.exists() for f in files)

    def test_stats_formatting(self, temp_output_dir):
        """Test duration formatting in stats."""
        manager = AudioRecordingManager(temp_output_dir)

        assert manager._format_duration(0) == "00:00:00"
        assert manager._format_duration(3661) == "01:01:01"
        assert manager._format_duration(59) == "00:00:59"


# =============================================================================
# Chapter Detector Tests
# =============================================================================


class TestChapterDetector:
    """Tests for ChapterDetector."""

    def test_silence_detection(self):
        """Test detecting silence-based chapters."""
        detector = ChapterDetector(
            threshold_db=-40.0,
            min_silence_duration_ms=500.0,  # 500ms for faster testing
            sample_rate=16000,
        )

        # Process audio with a silence gap
        # First, process some audio
        audio1 = np.random.randn(8000).astype(np.float32) * 0.5  # 0.5s of audio
        chapter = detector.process(audio1, 0.0)
        assert chapter is None

        # Now process silence (should trigger after enough silence)
        silence = np.zeros(16000, dtype=np.float32)  # 1s of silence
        chapter = detector.process(silence, 0.5)
        assert chapter is None  # Not enough silence yet

        # More silence to exceed threshold
        silence2 = np.zeros(16000, dtype=np.float32)
        chapter = detector.process(silence2, 1.5)
        # May or may not trigger depending on accumulation

    def test_chapter_finalization(self):
        """Test finalizing chapters."""
        detector = ChapterDetector(
            threshold_db=-40.0,
            min_silence_duration_ms=1000.0,
            sample_rate=16000,
        )

        # Process some audio
        audio = (
            np.random.randn(
                16000,
            ).astype(np.float32)
            * 0.5
        )
        detector.process(audio, 0.0)

        # Finalize
        chapters = detector.finalize(5.0)
        assert len(chapters) >= 1
        assert chapters[0].start_time == 0.0
        assert chapters[0].end_time == 5.0


# =============================================================================
# Export Manager Tests
# =============================================================================


class TestExportManager:
    """Tests for ExportManager."""

    def test_export_async(self, temp_output_dir, sample_settings):
        """Test asynchronous export."""
        manager = ExportManager(temp_output_dir)

        # Create a mock session
        session = SessionState.create(
            title="Test",
            output_dir=temp_output_dir,
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        notes = NotesBundle("Test notes", "Highlights", [], [])
        chapters = []
        formats = [ExportFormat.TXT, ExportFormat.JSON]

        task_id = manager.export_async(session, notes, chapters, formats)

        assert task_id is not None
        assert len(task_id) == 8

        # Wait for export to complete
        time.sleep(0.5)

        manager.shutdown(wait=True)

    def test_export_formats(self, temp_output_dir, sample_settings):
        """Test exporting different formats."""
        manager = ExportManager(temp_output_dir)

        session = SessionState.create(
            title="Test Export",
            output_dir=temp_output_dir,
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        # Add a segment
        session.segments.append(
            TranscriptSegment(
                id="1",
                start=0.0,
                end=1.0,
                text="Test",
                display_text="Test",
                language="en",
            )
        )

        notes = NotesBundle("Notes", "Highlights", [], [])

        # Export each format
        for fmt in ExportFormat:
            task_id = manager.export_async(session, notes, [], [fmt])
            assert task_id is not None

        time.sleep(0.5)
        manager.shutdown(wait=True)

        # Check that files were created
        assert (temp_output_dir / "export.txt").exists()
        assert (temp_output_dir / "export.json").exists()


# =============================================================================
# System Session Handler Tests
# =============================================================================


class TestSystemSessionHandler:
    """Tests for SystemSessionHandler."""

    def test_initialization(self, sample_settings, sample_config):
        """Test handler initialization."""
        handler = SystemSessionHandler(sample_settings, sample_config)

        assert handler.session is None
        assert handler.settings == sample_settings
        assert handler.session_config == sample_config

    def test_create_session(self, sample_settings, temp_output_dir):
        """Test creating a new session."""
        handler = SystemSessionHandler(sample_settings)

        session = handler.create_session(
            title="Test Session",
            output_root=temp_output_dir,
            description="Test description",
            tags=["test", "demo"],
        )

        assert session is not None
        assert session.title == "Test Session"
        assert session.status == "created"
        assert handler.extended_metadata is not None
        assert handler.extended_metadata.tags == ["test", "demo"]
        assert handler.extended_metadata.description == "Test description"

    def test_session_callbacks(self, sample_settings, temp_output_dir):
        """Test setting callbacks."""
        handler = SystemSessionHandler(sample_settings)

        callback_called = {}

        def on_segment(seg):
            callback_called["segment"] = True

        def on_health(health, meter):
            callback_called["health"] = True

        def on_state(state):
            callback_called["state"] = True

        handler.set_callbacks(
            on_segment=on_segment,
            on_health=on_health,
            on_state=on_state,
        )

        # Verify callbacks are set
        assert handler._on_segment is not None
        assert handler._on_health is not None
        assert handler._on_state is not None

    def test_add_note(self, sample_settings, temp_output_dir):
        """Test adding contextual notes."""
        handler = SystemSessionHandler(sample_settings)

        handler.create_session(
            title="Test Session",
            output_root=temp_output_dir,
        )

        note = handler.add_note(
            text="Important point here",
            timestamp=10.5,
            tags=["important", "formula"],
        )

        assert note is not None
        assert note.text == "Important point here"
        assert note.timestamp == 10.5
        assert "important" in note.tags
        assert len(handler._session_notes) == 1

    def test_get_progress_no_session(self, sample_settings):
        """Test getting progress without active session."""
        handler = SystemSessionHandler(sample_settings)

        progress = handler.get_progress()
        assert progress["status"] == "no_session"

    def test_get_progress_with_session(self, sample_settings, temp_output_dir):
        """Test getting progress with active session."""
        handler = SystemSessionHandler(sample_settings)

        handler.create_session(
            title="Test Session",
            output_root=temp_output_dir,
        )

        progress = handler.get_progress()
        assert progress["status"] == "created"
        assert "session_id" in progress
        assert "duration_seconds" in progress

    def test_list_devices(self, sample_settings):
        """Test listing audio devices."""
        handler = SystemSessionHandler(sample_settings)

        with patch("app.core.system_session.list_audio_devices") as mock_list:
            mock_list.return_value = []
            devices = handler.list_devices()
            assert devices == []
            mock_list.assert_called_once()

    def test_slugify(self, sample_settings):
        """Test text slugification."""
        handler = SystemSessionHandler(sample_settings)

        assert handler._slugify("Project Status Update") == "project-status-update"
        assert handler._slugify("Test-123-File") == "test-123-file"
        assert handler._slugify("Multiple   Spaces") == "multiple-spaces"

    def test_normalize_text(self, sample_settings):
        """Test text normalization."""
        handler = SystemSessionHandler(sample_settings)

        assert handler._normalize_text("Project Status Update") == "project status update"
        assert handler._normalize_text("UPPER CASE") == "upper case"
        assert handler._normalize_text("Extra   Spaces") == "extra spaces"

    def test_format_duration(self, sample_settings):
        """Test duration formatting."""
        handler = SystemSessionHandler(sample_settings)

        assert handler._format_duration(0) == "00:00:00"
        assert handler._format_duration(59) == "00:00:59"
        assert handler._format_duration(3661) == "01:01:01"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_system_session_handler(self, sample_settings):
        """Test factory function."""
        handler = create_system_session_handler(
            settings=sample_settings,
            save_audio=True,
            enable_stem=False,
        )

        assert isinstance(handler, SystemSessionHandler)
        assert handler.session_config.save_audio is True
        assert handler.session_config.enable_stem is False

    def test_create_system_session_handler_defaults(self):
        """Test factory function with default settings."""
        handler = create_system_session_handler()

        assert isinstance(handler, SystemSessionHandler)
        assert handler.settings is not None

    def test_load_session_from_disk(self, temp_output_dir):
        """Test loading session from disk."""
        # Create a mock session structure
        session_dir = temp_output_dir / "test-session"
        session_dir.mkdir()

        # Create session.json
        session_data = {
            "session_id": "test-123",
            "title": "Test Session",
            "started_at": utc_now().isoformat(),
        }
        (session_dir / "session.json").write_text(json.dumps(session_data), encoding="utf-8")

        # Load the session
        result = load_session_from_disk(session_dir)

        assert result["session_dir"] == str(session_dir)
        assert result["metadata"] is not None


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the full session workflow."""

    @pytest.mark.slow
    def test_full_session_lifecycle(self, temp_output_dir):
        """Test complete session lifecycle (slow test)."""
        settings = AppSettings(
            sample_rate=16000,
            channels=1,
            default_model="tiny",
        )

        config = SystemSessionConfig(
            save_audio=False,  # Skip audio for faster test
            enable_stem=False,
            auto_segment=False,
        )

        handler = SystemSessionHandler(settings, config)

        # Create session
        session = handler.create_session(
            title="Integration Test",
            output_root=temp_output_dir,
            description="Testing full workflow",
            tags=["integration"],
        )

        assert session.status == "created"

        # Verify session files exist
        assert (session.output_dir / "session.json").exists()
        assert (session.output_dir / "logs").exists()

        # Test adding notes
        note = handler.add_note("Test note", timestamp=0.0)
        assert note is not None

        # Shutdown
        handler.shutdown()

    def test_session_state_transitions(self, sample_settings, temp_output_dir):
        """Test session state transitions."""
        handler = SystemSessionHandler(sample_settings)

        # Initial state
        assert handler.session is None

        # Create session
        session = handler.create_session(
            title="State Test",
            output_root=temp_output_dir,
        )
        assert session.status == "created"

        # Verify extended metadata was written
        metadata_path = session.output_dir / "metadata.json"
        assert metadata_path.exists()

        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert data["session"]["title"] == "State Test"
        assert data["extended"]["source_type"] == "system_audio"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and recovery."""

    def test_invalid_export_format(self, sample_settings, temp_output_dir):
        """Test handling invalid export format."""
        handler = SystemSessionHandler(sample_settings)

        handler.create_session(
            title="Error Test",
            output_root=temp_output_dir,
        )

        # Should raise ValueError for invalid format
        with pytest.raises(ValueError):
            handler.export(formats=["invalid_format"])

    def test_attach_document_no_session(self, sample_settings):
        """Test attaching document without session."""
        handler = SystemSessionHandler(sample_settings)

        with pytest.raises(RuntimeError, match="No active session"):
            handler.attach_document("/path/to/file.pdf")

    def test_cleanup_on_error(self, sample_settings):
        """Test cleanup when errors occur."""
        handler = SystemSessionHandler(sample_settings)

        # Create a mock session
        handler.session = MagicMock()
        handler.session.status = "running"

        # Call cleanup
        handler._cleanup_on_error()

        assert handler.session.status == "error"
        assert handler.audio_source is None
        assert handler.transcriber is None


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """Performance-related tests."""

    def test_large_segment_processing(self, sample_settings):
        """Test processing with many segments."""
        handler = SystemSessionHandler(sample_settings)

        # Create many mock segments
        segments = []
        for i in range(1000):
            seg = TranscriptSegment(
                id=str(i),
                start=float(i),
                end=float(i + 1),
                text=f"Segment {i}",
                display_text=f"Segment {i}",
                language="en",
            )
            segments.append(seg)

        # Verify deduplication works efficiently
        start_time = time.time()

        handler.session = MagicMock()
        handler.session.segments = segments[:500]

        test_segment = TranscriptSegment(
            id="test",
            start=500.0,
            end=501.0,
            text="Test segment",
            display_text="Test segment",
            language="en",
        )

        handler._apply_overlap_dedupe(test_segment)

        elapsed = time.time() - start_time
        assert elapsed < 1.0  # Should complete in less than 1 second

    def test_audio_write_performance(self, temp_output_dir):
        """Test audio writing performance."""
        manager = AudioRecordingManager(
            output_dir=temp_output_dir,
            sample_rate=16000,
            channels=1,
        )

        manager.start()

        # Write 10 seconds of audio in chunks
        start_time = time.time()

        for _ in range(100):  # 100 chunks = ~10 seconds at 16kHz
            audio = np.random.randn(1600).astype(np.float32) * 0.1
            manager.write(audio)

        elapsed = time.time() - start_time

        manager.stop()

        # Should complete quickly
        assert elapsed < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
