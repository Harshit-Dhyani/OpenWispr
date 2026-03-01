from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_audio_device() -> Generator[MagicMock, None, None]:
    """Mock audio device for testing."""
    with patch("app.audio.devices.sc.all_microphones") as mock_mics:
        with patch("app.audio.devices.sc.all_speakers") as mock_speakers:
            mock_mic = MagicMock()
            mock_mic.id = "test-mic-id"
            mock_mic.name = "Test Microphone"
            mock_mic.isloopback = True
            mock_mic.channels = 2
            mock_mics.return_value = [mock_mic]
            mock_speakers.return_value = []
            yield mock_mic


@pytest.fixture
def mock_recorder() -> Generator[MagicMock, None, None]:
    """Mock audio recorder for testing."""
    with patch("app.audio.capture.resolve_capture_device") as mock_resolve:
        mock_device = MagicMock()
        mock_recorder_ctx = MagicMock()
        mock_recorder = MagicMock()
        mock_recorder_ctx.__enter__ = MagicMock(return_value=mock_recorder)
        mock_recorder_ctx.__exit__ = MagicMock(return_value=None)
        mock_device.recorder.return_value = mock_recorder_ctx
        mock_resolve.return_value = (mock_device, "test-device")
        yield mock_recorder


@pytest.fixture
def sample_segment_data() -> dict[str, Any]:
    """Provide sample segment data for testing."""
    return {
        "id": "seg-001",
        "start": 0.0,
        "end": 5.0,
        "text": "Test transcript segment",
        "display_text": "Test transcript segment",
        "language": "en",
        "confidence": 0.85,
        "review_flag": False,
        "suppressed": False,
    }


@pytest.fixture
def mock_whisper_model() -> Generator[MagicMock, None, None]:
    """Mock WhisperModel for testing."""
    with patch("app.stt.engine.WhisperModel") as mock_model_class:
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        yield mock_model


@pytest.fixture
def mock_torch_cuda() -> Generator[MagicMock, None, None]:
    """Mock torch.cuda for GPU testing."""
    with patch("app.stt.engine.torch") as mock_torch:
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_properties.return_value.total_memory = 10 * (1024**3)
        mock_torch.cuda.memory_reserved.return_value = 1 * (1024**3)
        mock_torch.cuda.empty_cache = MagicMock()
        mock_torch.cuda.synchronize = MagicMock()
        yield mock_torch
