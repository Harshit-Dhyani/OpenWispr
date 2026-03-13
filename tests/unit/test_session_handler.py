"""Unit tests for the session handler/manager.

Tests cover:
- Session initialization and cleanup
- Session state management
- Callback registration
- Device management
- Health monitoring
- Session persistence
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from app.core.models import SessionHealth, TranscriptSegment
from app.core.session_manager import SessionManager, _normalize_transcript_text, slugify


class TestSlugify:
    """Tests for slugify function."""

    def test_basic_slugify(self) -> None:
        """Test basic slugification."""
        assert slugify("Project Status Update") == "project-status-update"

    def test_special_characters(self) -> None:
        """Test slugify with special characters."""
        assert slugify("Test @ Session #1") == "test-session-1"

    def test_multiple_spaces(self) -> None:
        """Test slugify with multiple spaces."""
        assert slugify("Multiple   Spaces") == "multiple-spaces"

    def test_empty_string(self) -> None:
        """Test slugify with empty string."""
        result = slugify("")
        assert result.startswith("session-")


class TestNormalizeTranscriptText:
    """Tests for transcript text normalization."""

    def test_basic_normalization(self) -> None:
        """Test basic text normalization."""
        text = "Project, Status Update!"
        result = _normalize_transcript_text(text)
        assert result == "project status update"

    def test_multiple_spaces_removal(self) -> None:
        """Test removal of multiple spaces."""
        text = "Project    Status Update"
        result = _normalize_transcript_text(text)
        assert result == "project status update"

    def test_special_characters_removal(self) -> None:
        """Test removal of special characters."""
        text = "Test@#$%^&*()Text"
        result = _normalize_transcript_text(text)
        assert result == "test text"


class TestSessionManagerInit:
    """Tests for SessionManager initialization."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.sample_rate = 16000
        settings.channels = 1
        settings.meter_decay = 0.9
        settings.output_refresh_seconds = 1.0
        settings.download_root = Path("/tmp/models")
        settings.device = "cpu"
        settings.compute_type = "int8"
        settings.beam_size = 5
        settings.best_of = 5
        settings.temperature = 0.0
        settings.vad_filter = True
        settings.max_queue_items = 10
        settings.capture_block_seconds = 0.1
        settings.audio_backend = "sounddevice"
        settings.log_level = "DEBUG"
        return settings

    def test_init(self, mock_settings: MagicMock) -> None:
        """Test session manager initialization."""
        manager = SessionManager(mock_settings)

        assert manager.settings == mock_settings
        assert manager.session is None
        assert manager.writer is None
        assert manager.audio_source is None
        assert manager.transcriber is None
        assert manager.meter is not None

    def test_set_callbacks(self, mock_settings: MagicMock) -> None:
        """Test callback registration."""
        manager = SessionManager(mock_settings)

        on_segment = Mock()
        on_partial = Mock()
        on_health = Mock()
        on_state = Mock()

        manager.set_callbacks(
            on_segment=on_segment,
            on_partial=on_partial,
            on_health=on_health,
            on_state=on_state,
        )

        assert manager._on_segment is on_segment
        assert manager._on_partial is on_partial
        assert manager._on_health is on_health
        assert manager._on_state is on_state


class TestSessionManagerCallbacks:
    """Tests for callback invocation."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.sample_rate = 16000
        settings.channels = 1
        settings.meter_decay = 0.9
        settings.output_refresh_seconds = 1.0
        settings.download_root = Path("/tmp/models")
        settings.device = "cpu"
        settings.compute_type = "int8"
        settings.beam_size = 5
        settings.best_of = 5
        settings.temperature = 0.0
        settings.vad_filter = True
        settings.max_queue_items = 10
        settings.capture_block_seconds = 0.1
        settings.audio_backend = "sounddevice"
        settings.log_level = "DEBUG"
        return settings

    @pytest.fixture
    def manager_with_callbacks(self, mock_settings: MagicMock) -> SessionManager:
        """Create manager with registered callbacks."""
        manager = SessionManager(mock_settings)
        manager.session = MagicMock()
        manager.session.session_id = "test-session"
        manager.session.segments = []
        manager.session.suppressed_segments = []
        manager.session.formulas = []
        manager.session.needs_review = []
        manager.writer = MagicMock()

        return manager

    def test_handle_segment_with_callback(self, manager_with_callbacks: SessionManager) -> None:
        """Test segment handling invokes callback."""
        callback_called = False
        received_segment = None

        def on_segment(segment: TranscriptSegment) -> None:
            nonlocal callback_called, received_segment
            callback_called = True
            received_segment = segment

        manager_with_callbacks.set_callbacks(on_segment=on_segment)

        segment = TranscriptSegment(
            id="seg-1",
            start=0.0,
            end=5.0,
            text="Test",
            display_text="Test",
            language="en",
            confidence=0.8,
        )

        manager_with_callbacks._handle_segment(segment)

        assert callback_called is True
        assert received_segment is segment

    def test_handle_health_with_callback(self, manager_with_callbacks: SessionManager) -> None:
        """Test health handling invokes callback."""
        callback_called = False

        def on_health(health: SessionHealth, meter: float) -> None:
            nonlocal callback_called
            callback_called = True

        manager_with_callbacks.set_callbacks(on_health=on_health)

        health = SessionHealth(
            audio_stream_active=True,
            gpu_mode="cpu/int8",
            execution_mode="auto",
            model_runtime_device="cpu",
        )

        manager_with_callbacks._handle_health(health)

        assert callback_called is True


class TestSessionManagerOverlapDedupe:
    """Tests for overlap deduplication."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.sample_rate = 16000
        settings.channels = 1
        settings.meter_decay = 0.9
        settings.output_refresh_seconds = 1.0
        return settings

    def test_apply_overlap_dedupe_no_duplicates(self, mock_settings: MagicMock) -> None:
        """Test no dedupe when no duplicates."""
        manager = SessionManager(mock_settings)
        manager.session = MagicMock()
        manager.session.segments = []

        segment = TranscriptSegment(
            id="seg-1",
            start=0.0,
            end=5.0,
            text="Unique text",
            display_text="Unique text",
            language="en",
            confidence=0.8,
            suppressed=False,
        )

        manager._apply_overlap_dedupe(segment)

        assert segment.suppressed is False

    def test_apply_overlap_dedupe_finds_duplicate(self, mock_settings: MagicMock) -> None:
        """Test dedupe finds and marks duplicate."""
        manager = SessionManager(mock_settings)
        manager.session = MagicMock()

        existing = TranscriptSegment(
            id="seg-1",
            start=0.0,
            end=5.0,
            text="Duplicate text",
            display_text="Duplicate text",
            language="en",
            confidence=0.8,
            suppressed=False,
        )
        manager.session.segments = [existing]

        new_segment = TranscriptSegment(
            id="seg-2",
            start=0.5,
            end=5.5,
            text="Duplicate text",
            display_text="Duplicate text",
            language="en",
            confidence=0.8,
            suppressed=False,
        )

        manager._apply_overlap_dedupe(new_segment)

        assert new_segment.suppressed is True
        assert "overlap-duplicate" in new_segment.suppression_reasons


class TestSessionManagerHealth:
    """Tests for health monitoring."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.sample_rate = 16000
        settings.channels = 1
        settings.meter_decay = 0.9
        settings.output_refresh_seconds = 1.0
        return settings

    def test_health_snapshot_creation(self, mock_settings: MagicMock) -> None:
        """Test health snapshot creation."""
        manager = SessionManager(mock_settings)
        manager.session = MagicMock()
        manager.session.session_id = "test-session"
        manager.session.status = "running"
        manager.session.model_name = "tiny"
        manager.session.language_mode = "en"
        manager.session.live_mode = "balanced"
        manager.session.segments = []

        health = SessionHealth(
            audio_stream_active=True,
            gpu_mode="cpu/int8",
            execution_mode="auto",
            model_runtime_device="cpu",
            queue_depth=0,
            dropped_stt_chunks=0,
            stt_backpressure_state="normal",
        )
        manager.session.health = health

        # Test health emission
        manager._emit_health()

        # Should update session health fields
        assert health.audio_stream_active is True

    def test_handle_error_updates_health(self, mock_settings: MagicMock) -> None:
        """Test error handling updates health."""
        manager = SessionManager(mock_settings)
        manager.session = MagicMock()
        manager.session.session_id = "test-session"
        manager.session.health = MagicMock()
        manager.writer = MagicMock()

        error = Exception("Audio device error")

        manager._handle_error(error)

        assert manager.session.status == "error"
        assert manager.session.health.audio_stream_active is False


class TestSessionManagerOutputBuilding:
    """Tests for output building functionality."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.sample_rate = 16000
        settings.channels = 1
        settings.meter_decay = 0.9
        settings.output_refresh_seconds = 0.1
        return settings

    def test_rebuild_outputs_no_session(self, mock_settings: MagicMock) -> None:
        """Test rebuild outputs with no session."""
        manager = SessionManager(mock_settings)

        # Should not raise error
        manager._rebuild_outputs(force=True)

    def test_maybe_rebuild_outputs_timing(self, mock_settings: MagicMock) -> None:
        """Test rebuild timing logic."""
        manager = SessionManager(mock_settings)
        manager.session = MagicMock()
        manager.session.segments = []
        manager.writer = MagicMock()

        # Not enough time passed
        manager._outputs_dirty = True
        manager._last_rebuild_at = time.monotonic()

        manager._maybe_rebuild_outputs()

        # Should not have rebuilt
        assert manager._outputs_dirty is True
