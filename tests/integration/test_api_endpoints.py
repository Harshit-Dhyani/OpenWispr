"""Integration tests for API endpoints.

Tests cover:
- Health check endpoint
- Device listing endpoints
- Session management endpoints
- Hotkey endpoints
- Settings endpoints
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestHealthEndpoint:
    """Tests for the health endpoint."""

    def test_health_check_basic(self, mock_fastapi_app: Mock) -> None:
        """Test basic health check response."""
        with patch("app.api.server.service") as mock_service:
            mock_service.get_snapshot.return_value = MagicMock(
                health={"audio_stream_active": True, "gpu_mode": "cpu/int8"},
                meter_value=0.5,
                model_cache={},
            )

            from app.api.server import health

            response = health(mock_service)

            assert response["ok"] is True
            assert "health" in response
            assert "meter_value" in response

    def test_health_with_model_cache(self, mock_fastapi_app: Mock) -> None:
        """Test health check includes model cache info."""
        with patch("app.api.server.service") as mock_service:
            mock_service.get_snapshot.return_value = MagicMock(
                health={"audio_stream_active": True},
                meter_value=0.5,
                model_cache={"tiny": "loaded"},
            )

            from app.api.server import health

            response = health(mock_service)

            assert response["ok"] is True
            assert "model_cache" in response


class TestDeviceEndpoints:
    """Tests for device-related endpoints."""

    def test_list_devices(self) -> None:
        """Test device listing endpoint."""
        with patch("app.api.server.service") as mock_service:
            mock_devices = [
                MagicMock(id="device-1", name="Mic 1", is_input=True),
                MagicMock(id="device-2", name="Speaker", is_loopback=True),
            ]
            mock_service.list_devices.return_value = mock_devices

            from app.api.server import devices

            response = devices(mock_service)

            assert "devices" in response
            assert len(response["devices"]) == 2

    def test_probe_device(self) -> None:
        """Test device probing endpoint."""
        with patch("app.api.server.service") as mock_service:
            mock_result = {"ok": True, "peak_rms": 0.5, "device_id": "test-device"}
            mock_service.probe_device.return_value = mock_result

            from app.api.server import probe_device_endpoint

            response = probe_device_endpoint("test-device", duration=1.0, svc=mock_service)

            assert response["ok"] is True


class TestSessionEndpoints:
    """Tests for session management endpoints."""

    def test_start_session_request_model(self) -> None:
        """Test StartSessionRequest model validation."""
        from app.api.server import StartSessionRequest

        request = StartSessionRequest(
            title="Test Session",
            output_root="/tmp/output",
            model_name="tiny",
            language_mode="en",
        )

        assert request.title == "Test Session"
        assert request.model_name == "tiny"
        assert request.language_mode == "en"

    def test_start_session_with_optional_params(self) -> None:
        """Test StartSessionRequest with optional parameters."""
        from app.api.server import StartSessionRequest

        request = StartSessionRequest(
            title="Test Session",
            output_root="/tmp/output",
            model_name="tiny",
            language_mode="en",
            device_id="device-1",
            live_mode="fast",
            execution_mode="cpu_only",
            vad_threshold=-35.0,
        )

        assert request.device_id == "device-1"
        assert request.live_mode == "fast"
        assert request.execution_mode == "cpu_only"
        assert request.vad_threshold == -35.0


class TestHotkeyEndpoints:
    """Tests for hotkey endpoints."""

    def test_hotkey_start_request(self) -> None:
        """Test HotkeyStartRequest model."""
        from app.api.server import HotkeyStartRequest

        request = HotkeyStartRequest(
            device_id="mic-1",
            model_name="small",
            language_mode="auto",
            execution_mode="gpu_only",
            transcription_mode="literal",
        )

        assert request.device_id == "mic-1"
        assert request.model_name == "small"
        assert request.transcription_mode == "literal"

    def test_hotkey_start_response(self) -> None:
        """Test HotkeyStartResponse model."""
        from app.api.server import HotkeyStartResponse

        response = HotkeyStartResponse(
            session_id="hotkey-123",
            status="recording",
            message="Session started",
        )

        assert response.session_id == "hotkey-123"
        assert response.status == "recording"

    def test_hotkey_stop_response(self) -> None:
        """Test HotkeyStopResponse model."""
        from app.api.server import HotkeyStopResponse

        response = HotkeyStopResponse(
            transcription_mode="dictation",
            composed_text="Project status update",
            final_transcription="Project status update",
            live_paste_text="Project status update",
            final_cleanup_applied=True,
            raw_transcription="project status update",
            duration_ms=5000,
            segment_count=1,
            source_backend="sounddevice",
            language_used="en",
        )

        assert response.composed_text == "Project status update"
        assert response.final_transcription == "Project status update"
        assert response.transcription_mode == "dictation"
        assert response.live_paste_text == "Project status update"
        assert response.final_cleanup_applied is True
        assert response.duration_ms == 5000
        assert response.segment_count == 1

    def test_hotkey_status_response_not_recording(self) -> None:
        """Test HotkeyStatusResponse when not recording."""
        from app.api.server import HotkeyStatusResponse

        response = HotkeyStatusResponse(
            is_recording=False,
            partial_text="",
            raw_partial_text="",
            display_partial_text="",
            audio_level=0.0,
            session_id=None,
            duration_ms=0,
        )

        assert response.is_recording is False
        assert response.session_id is None

    def test_hotkey_status_response_recording(self) -> None:
        """Test HotkeyStatusResponse when recording."""
        from app.api.server import HotkeyStatusResponse

        response = HotkeyStatusResponse(
            is_recording=True,
            partial_text="Hello",
            raw_partial_text="hello",
            display_partial_text="Hello",
            audio_level=0.5,
            session_id="hotkey-123",
            duration_ms=3000,
            levels=[0.5] * 36,
        )

        assert response.is_recording is True
        assert response.session_id == "hotkey-123"
        assert len(response.levels) == 36

    def test_hotkey_config_request(self) -> None:
        """Test HotkeyConfigRequest model."""
        from app.api.server import HotkeyConfigRequest

        request = HotkeyConfigRequest(
            chunk_seconds=0.5,
            vad_threshold_db=-35.0,
            confidence_threshold=0.6,
        )

        assert request.chunk_seconds == 0.5
        assert request.vad_threshold_db == -35.0
        assert request.confidence_threshold == 0.6

    @pytest.mark.asyncio
    async def test_coach_prompt_preview_endpoint(self) -> None:
        from app.api.server import CoachPromptPreviewRequest, coach_prompt_preview

        fake_service = SimpleNamespace(
            _get_coach_service=lambda: SimpleNamespace(
                prompt_preview=lambda _context: {
                    "system_prompt": "SYSTEM",
                    "user_prompt": "USER",
                    "resolved_template_id": "default_english_coach",
                    "resolved_template_version": 1,
                    "variables": {"original_text": "project status update"},
                    "warnings": [],
                }
            )
        )

        response = await coach_prompt_preview(
            CoachPromptPreviewRequest(
                capture_source="microphone",
                original_text="project status update",
                language_mode="en",
                detail_level="compact",
                template_id="default_english_coach",
                overrides={},
                privacy_mode="local_only",
            ),
            svc=fake_service,
        )

        assert response["resolved_template_id"] == "default_english_coach"
        assert response["resolved_template_version"] == 1
        assert response["variables"]["original_text"] == "project status update"


class TestHotkeyService:
    """Tests for HotkeyTranscriptionService."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock app settings."""
        settings = MagicMock()
        settings.sample_rate = 16000
        settings.channels = 1
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
        return settings

    def test_service_init(self, mock_settings: MagicMock) -> None:
        """Test service initialization."""
        from app.api.server import HotkeyTranscriptionService

        service = HotkeyTranscriptionService(mock_settings)

        assert service.settings == mock_settings
        assert service._session is None

    def test_get_status_no_session(self, mock_settings: MagicMock) -> None:
        """Test get_status with no active session."""
        from app.api.server import HotkeyTranscriptionService

        service = HotkeyTranscriptionService(mock_settings)
        status = service.get_status()

        assert status.is_recording is False
        assert status.session_id is None
        assert status.audio_level == 0.0

    def test_calculate_audio_level_silence(self, mock_settings: MagicMock) -> None:
        """Test audio level calculation with silence."""
        from app.api.server import HotkeyTranscriptionService

        service = HotkeyTranscriptionService(mock_settings)
        audio = MagicMock()
        audio.__len__ = Mock(return_value=1600)
        audio.astype = Mock(return_value=audio)
        audio.__getitem__ = Mock(return_value=audio)

        # Create actual numpy array for calculation
        import numpy as np

        silent_audio = np.zeros(1600, dtype=np.float32)
        level = service._calculate_audio_level(silent_audio)

        assert level == pytest.approx(0.0, abs=0.01)

    def test_calculate_audio_level_with_signal(self, mock_settings: MagicMock) -> None:
        """Test audio level calculation with signal."""
        import numpy as np

        from app.api.server import HotkeyTranscriptionService

        service = HotkeyTranscriptionService(mock_settings)
        # Create signal at -20dB
        audio = np.ones(1600, dtype=np.float32) * 0.1
        level = service._calculate_audio_level(audio)

        assert level > 0.0
        assert level <= 1.0


class TestSettingsEndpoints:
    """Tests for settings-related endpoints."""

    def test_model_selection_request(self) -> None:
        """Test ModelSelectionRequest model."""
        from app.api.server import ModelSelectionRequest

        request = ModelSelectionRequest(
            category="transcription",
            model_id="whisper-tiny",
        )

        assert request.category == "transcription"
        assert request.model_id == "whisper-tiny"

    def test_refinement_mode_request(self) -> None:
        """Test RefinementModeRequest model."""
        from app.api.server import RefinementModeRequest

        request = RefinementModeRequest(mode="aggressive")

        assert request.mode == "aggressive"

    def test_preload_model_request(self) -> None:
        """Test PreloadModelRequest model."""
        from app.api.server import PreloadModelRequest

        request = PreloadModelRequest(
            model_name="base",
            execution_mode="auto",
        )

        assert request.model_name == "base"
        assert request.execution_mode == "auto"


class TestAttachPdfEndpoint:
    """Tests for PDF attachment endpoint."""

    def test_attach_pdf_request(self) -> None:
        """Test AttachPdfRequest model."""
        from app.api.server import AttachPdfRequest

        request = AttachPdfRequest(path="/documents/test.pdf")

        assert request.path == "/documents/test.pdf"


class TestEndpointLogging:
    """Tests for endpoint logging decorator."""

    def test_log_endpoint_decorator(self) -> None:
        """Test log_endpoint decorator exists."""
        from app.api.server import log_endpoint

        assert callable(log_endpoint)

    def test_get_request_info(self) -> None:
        """Test request info extraction."""
        from app.api.server import _get_request_info

        mock_request = MagicMock()
        mock_request.dict.return_value = {"device_id": "test", "password": "secret123"}

        info = _get_request_info({"request": mock_request})

        assert "device_id" in info
        assert "password" not in info  # Should be sanitized
