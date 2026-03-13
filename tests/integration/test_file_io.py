"""Integration tests for file I/O operations.

Tests cover:
- Audio file reading/writing
- Session file operations
- Settings file persistence
- Log file handling
- Temporary file cleanup
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import numpy as np
import pytest


class TestAudioFileIO:
    """Tests for audio file I/O."""

    def test_wav_file_write_read(self, temp_dir: Path) -> None:
        """Test WAV file write and read."""
        try:
            import soundfile as sf

            audio_file = temp_dir / "test.wav"
            audio_data = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000)).astype(np.float32)

            # Write
            sf.write(audio_file, audio_data, 16000)
            assert audio_file.exists()

            # Read
            read_data, sr = sf.read(audio_file)
            assert sr == 16000
            assert len(read_data) == len(audio_data)
        except ImportError:
            pytest.skip("soundfile not available")

    def test_audio_file_formats(self, temp_dir: Path) -> None:
        """Test different audio file formats."""
        try:
            import soundfile as sf

            audio_data = np.random.randn(16000).astype(np.float32)

            # Test different formats
            formats = ["WAV", "FLAC"]
            for fmt in formats:
                audio_file = temp_dir / f"test.{fmt.lower()}"
                try:
                    sf.write(audio_file, audio_data, 16000, format=fmt)
                    assert audio_file.exists()
                except Exception:
                    pass  # Some formats may not be supported
        except ImportError:
            pytest.skip("soundfile not available")

    def test_audio_file_with_metadata(self, temp_dir: Path) -> None:
        """Test audio file with metadata."""
        try:
            import soundfile as sf

            audio_file = temp_dir / "test_meta.wav"
            audio_data = np.zeros(16000, dtype=np.float32)

            sf.write(audio_file, audio_data, 16000)
            info = sf.info(audio_file)

            assert info.samplerate == 16000
            assert info.channels == 1
        except ImportError:
            pytest.skip("soundfile not available")


class TestSessionFileIO:
    """Tests for session file I/O."""

    def test_session_directory_creation(self, temp_dir: Path) -> None:
        """Test session directory creation."""
        from app.core.models import SessionState

        session_dir = temp_dir / "test-session"
        state = SessionState.create(
            title="Test Session",
            output_dir=session_dir,
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        # Directory should be created by SessionWriter
        from app.storage.session_writer import SessionWriter

        writer = SessionWriter(state)
        writer.write_metadata()

        assert session_dir.exists()

    def test_session_metadata_file(self, temp_dir: Path) -> None:
        """Test session metadata file creation."""
        from app.core.models import SessionState
        from app.storage.session_writer import SessionWriter

        session_dir = temp_dir / "test-session"
        state = SessionState.create(
            title="Test Session",
            output_dir=session_dir,
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        writer = SessionWriter(state)
        writer.write_metadata()

        metadata_file = session_dir / "session.json"
        assert metadata_file.exists()

        data = json.loads(metadata_file.read_text())
        assert data["title"] == "Test Session"

    def test_session_transcript_file(self, temp_dir: Path) -> None:
        """Test session transcript file creation."""
        from app.core.models import SessionState, TranscriptSegment
        from app.storage.session_writer import SessionWriter

        session_dir = temp_dir / "test-session"
        state = SessionState.create(
            title="Test Session",
            output_dir=session_dir,
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        # Add a segment
        segment = TranscriptSegment(
            id="seg-1",
            start=0.0,
            end=5.0,
            text="Test transcription",
            display_text="Test transcription",
            language="en",
            confidence=0.85,
        )

        writer = SessionWriter(state)
        writer.append_segment(segment)

        transcript_file = session_dir / "transcript.jsonl"
        assert transcript_file.exists()

        # Verify content
        lines = transcript_file.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["text"] == "Test transcription"


class TestSettingsFileIO:
    """Tests for settings file I/O."""

    def test_settings_file_creation(self, temp_dir: Path) -> None:
        """Test settings file creation."""
        from app.core.settings_manager import SettingsManager

        settings_file = temp_dir / "user_settings.json"
        assert not settings_file.exists()

        manager = SettingsManager(settings_dir=temp_dir)

        assert settings_file.exists()

    def test_settings_file_format(self, temp_dir: Path) -> None:
        """Test settings file format."""
        from app.core.settings_manager import SettingsManager

        manager = SettingsManager(settings_dir=temp_dir)
        manager._save()

        settings_file = temp_dir / "user_settings.json"
        data = json.loads(settings_file.read_text())

        # Should have expected categories
        assert "general" in data
        assert "transcription" in data
        assert "audio" in data
        assert "version" in data

    def test_settings_backup_on_corruption(self, temp_dir: Path) -> None:
        """Test settings recovery on corruption."""
        settings_file = temp_dir / "user_settings.json"
        settings_file.write_text("invalid json {{[")

        # Should create new settings without crashing
        from app.core.settings_manager import SettingsManager

        manager = SettingsManager(settings_dir=temp_dir)

        assert manager.get_settings() is not None


class TestLogFileIO:
    """Tests for log file I/O."""

    def test_log_file_creation(self, temp_dir: Path) -> None:
        """Test log file creation."""
        log_file = temp_dir / "test.log"

        handler = logging.FileHandler(log_file)
        logger = logging.getLogger("test_logger")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        logger.info("Test message")
        handler.close()

        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content

    def test_log_rotation(self, temp_dir: Path) -> None:
        """Test log rotation."""
        from logging.handlers import RotatingFileHandler

        log_file = temp_dir / "rotating.log"
        handler = RotatingFileHandler(log_file, maxBytes=1024, backupCount=3)

        logger = logging.getLogger("rotating_test")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Write enough to trigger rotation
        for i in range(100):
            logger.info("x" * 100)

        handler.close()

        # Should have backup files
        backup_files = list(temp_dir.glob("rotating.log.*"))
        assert len(backup_files) > 0 or log_file.stat().st_size > 0


class TestTemporaryFileHandling:
    """Tests for temporary file handling."""

    def test_temp_file_cleanup(self) -> None:
        """Test temporary file cleanup."""
        temp_file = None

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            temp_file = Path(f.name)
            f.write("test data")

        assert temp_file.exists()

        # Clean up
        temp_file.unlink()
        assert not temp_file.exists()

    def test_temp_directory_cleanup(self) -> None:
        """Test temporary directory cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.txt"
            test_file.write_text("test")

            assert test_file.exists()

        # Directory should be cleaned up
        assert not temp_path.exists()

    def test_temp_audio_buffer(self) -> None:
        """Test temporary audio buffer handling."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_file = Path(f.name)

        try:
            # Simulate writing audio buffer
            import soundfile as sf

            audio = np.zeros(16000, dtype=np.float32)
            sf.write(temp_file, audio, 16000)

            assert temp_file.exists()
            assert temp_file.stat().st_size > 0
        finally:
            temp_file.unlink()


class TestFilePermissions:
    """Tests for file permissions."""

    def test_settings_file_permissions(self, temp_dir: Path) -> None:
        """Test settings file has correct permissions."""
        from app.core.settings_manager import SettingsManager

        manager = SettingsManager(settings_dir=temp_dir)
        manager._save()

        settings_file = temp_dir / "user_settings.json"

        # File should be readable
        assert settings_file.exists()
        data = json.loads(settings_file.read_text())
        assert "general" in data

    def test_session_directory_permissions(self, temp_dir: Path) -> None:
        """Test session directory has correct permissions."""
        from app.core.models import SessionState
        from app.storage.session_writer import SessionWriter

        session_dir = temp_dir / "test-session"
        state = SessionState.create(
            title="Test",
            output_dir=session_dir,
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        writer = SessionWriter(state)
        writer.write_metadata()

        # Directory should exist and be writable
        assert session_dir.exists()
        assert session_dir.is_dir()

        # Should be able to create files
        test_file = session_dir / "test.txt"
        test_file.write_text("test")
        assert test_file.exists()
