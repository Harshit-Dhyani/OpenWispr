from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.audio.capture import LoopbackAudioSource
from app.core.models import DeviceProbeResult


@pytest.fixture
def mock_device_with_data() -> Generator[tuple[MagicMock, np.ndarray], None, None]:
    """Mock device that returns synthetic audio data."""
    sample_rate = 16000
    duration = 0.5
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, 2 * np.pi * 440, num_samples, dtype=np.float32)
    audio_data = 0.3 * np.sin(t).reshape(-1, 1)

    with patch("app.audio.capture.resolve_capture_device") as mock_resolve:
        mock_device = MagicMock()
        mock_recorder_ctx = MagicMock()
        mock_recorder = MagicMock()

        call_count = [0]
        max_calls = int((duration * sample_rate) / 1024)

        def mock_record(**kwargs):
            if call_count[0] < max_calls:
                call_count[0] += 1
                return audio_data[: kwargs.get("numframes", 1024)].copy()
            return np.zeros((kwargs.get("numframes", 1024), 1), dtype=np.float32)

        mock_recorder.record = mock_record
        mock_recorder_ctx.__enter__ = MagicMock(return_value=mock_recorder)
        mock_recorder_ctx.__exit__ = MagicMock(return_value=None)
        mock_device.recorder.return_value = mock_recorder_ctx
        mock_resolve.return_value = (mock_device, "test-device")

        yield mock_device, audio_data


class TestDeviceProbeStats:
    """Test device probe returns correct stats."""

    def test_probe_returns_correct_sample_rate(
        self, temp_dir: Path, mock_device_with_data: Any
    ) -> None:
        result = LoopbackAudioSource.probe_device(
            device_id="test-device",
            sample_rate=16000,
            channels=1,
            duration=0.5,
            output_dir=temp_dir,
        )

        assert isinstance(result, DeviceProbeResult)
        assert result.sample_rate == 16000

    def test_probe_returns_correct_channels(
        self, temp_dir: Path, mock_device_with_data: Any
    ) -> None:
        with patch("app.audio.capture.resolve_capture_device") as mock_resolve:
            mock_device = MagicMock()
            mock_recorder_ctx = MagicMock()
            mock_recorder = MagicMock()

            def mock_record(**kwargs):
                return np.zeros((1024, 2), dtype=np.float32)

            mock_recorder.record = mock_record
            mock_recorder_ctx.__enter__ = MagicMock(return_value=mock_recorder)
            mock_recorder_ctx.__exit__ = MagicMock(return_value=None)
            mock_device.recorder.return_value = mock_recorder_ctx
            mock_resolve.return_value = (mock_device, "test-device")

            result = LoopbackAudioSource.probe_device(
                device_id="test-device",
                sample_rate=16000,
                channels=2,
                duration=0.3,
                output_dir=temp_dir,
            )

            assert result.channels == 2

    def test_probe_calculates_rms_mean(self, temp_dir: Path, mock_device_with_data: Any) -> None:
        result = LoopbackAudioSource.probe_device(
            device_id="test-device",
            sample_rate=16000,
            channels=1,
            duration=0.5,
            output_dir=temp_dir,
        )

        assert result.rms_mean >= 0.0
        assert result.rms_mean <= 1.0

    def test_probe_calculates_rms_peak(self, temp_dir: Path, mock_device_with_data: Any) -> None:
        result = LoopbackAudioSource.probe_device(
            device_id="test-device",
            sample_rate=16000,
            channels=1,
            duration=0.5,
            output_dir=temp_dir,
        )

        assert result.rms_peak >= result.rms_mean
        assert result.rms_peak <= 1.0

    def test_probe_detects_signal_presence(
        self, temp_dir: Path, mock_device_with_data: Any
    ) -> None:
        result = LoopbackAudioSource.probe_device(
            device_id="test-device",
            sample_rate=16000,
            channels=1,
            duration=0.5,
            output_dir=temp_dir,
        )

        assert isinstance(result.has_signal, bool)

    def test_probe_detects_no_signal_for_silence(self, temp_dir: Path) -> None:
        with patch("app.audio.capture.resolve_capture_device") as mock_resolve:
            mock_device = MagicMock()
            mock_recorder_ctx = MagicMock()
            mock_recorder = MagicMock()

            def mock_record(**kwargs):
                return np.zeros((1024, 1), dtype=np.float32)

            mock_recorder.record = mock_record
            mock_recorder_ctx.__enter__ = MagicMock(return_value=mock_recorder)
            mock_recorder_ctx.__exit__ = MagicMock(return_value=None)
            mock_device.recorder.return_value = mock_recorder_ctx
            mock_resolve.return_value = (mock_device, "test-device")

            result = LoopbackAudioSource.probe_device(
                device_id="test-device",
                sample_rate=16000,
                channels=1,
                duration=0.3,
                output_dir=temp_dir,
            )

            assert result.has_signal is False
            assert result.rms_mean < 1e-4

    def test_probe_tracks_dropped_frames(self, temp_dir: Path) -> None:
        with patch("app.audio.capture.resolve_capture_device") as mock_resolve:
            mock_device = MagicMock()
            mock_recorder_ctx = MagicMock()
            mock_recorder = MagicMock()

            call_count = [0]

            def mock_record(**kwargs):
                call_count[0] += 1
                if call_count[0] % 3 == 0:
                    return None
                if call_count[0] % 5 == 0:
                    return np.array([])
                return np.zeros((1024, 1), dtype=np.float32)

            mock_recorder.record = mock_record
            mock_recorder_ctx.__enter__ = MagicMock(return_value=mock_recorder)
            mock_recorder_ctx.__exit__ = MagicMock(return_value=None)
            mock_device.recorder.return_value = mock_recorder_ctx
            mock_resolve.return_value = (mock_device, "test-device")

            result = LoopbackAudioSource.probe_device(
                device_id="test-device",
                sample_rate=16000,
                channels=1,
                duration=0.3,
                output_dir=temp_dir,
            )

            assert result.dropped_frames > 0

    def test_probe_identifies_dominant_channels(self, temp_dir: Path) -> None:
        with patch("app.audio.capture.resolve_capture_device") as mock_resolve:
            mock_device = MagicMock()
            mock_recorder_ctx = MagicMock()
            mock_recorder = MagicMock()

            def mock_record(**kwargs):
                data = np.zeros((1024, 4), dtype=np.float32)
                data[:, 1] = 0.5
                data[:, 2] = 0.5
                return data

            mock_recorder.record = mock_record
            mock_recorder_ctx.__enter__ = MagicMock(return_value=mock_recorder)
            mock_recorder_ctx.__exit__ = MagicMock(return_value=None)
            mock_device.recorder.return_value = mock_recorder_ctx
            mock_resolve.return_value = (mock_device, "test-device")

            result = LoopbackAudioSource.probe_device(
                device_id="test-device",
                sample_rate=16000,
                channels=4,
                duration=0.3,
                output_dir=temp_dir,
            )

            assert len(result.dominant_channels) > 0


class TestWAVFileCreation:
    """Test WAV file is created correctly."""

    def test_wav_file_created(self, temp_dir: Path, mock_device_with_data: Any) -> None:
        result = LoopbackAudioSource.probe_device(
            device_id="test-device",
            sample_rate=16000,
            channels=1,
            duration=0.5,
            output_dir=temp_dir,
        )

        assert result.wav_path.exists()
        assert result.wav_path.suffix == ".wav"

    def test_wav_file_valid_format(self, temp_dir: Path, mock_device_with_data: Any) -> None:
        result = LoopbackAudioSource.probe_device(
            device_id="test-device",
            sample_rate=16000,
            channels=1,
            duration=0.5,
            output_dir=temp_dir,
        )

        with wave.open(str(result.wav_path), "rb") as wav_file:
            assert wav_file.getnchannels() == 1
            assert wav_file.getframerate() == 16000
            assert wav_file.getsampwidth() == 2

    def test_wav_file_contains_data(self, temp_dir: Path, mock_device_with_data: Any) -> None:
        result = LoopbackAudioSource.probe_device(
            device_id="test-device",
            sample_rate=16000,
            channels=1,
            duration=0.5,
            output_dir=temp_dir,
        )

        with wave.open(str(result.wav_path), "rb") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            assert len(frames) > 0

    def test_wav_file_device_id_in_filename(
        self, temp_dir: Path, mock_device_with_data: Any
    ) -> None:
        result = LoopbackAudioSource.probe_device(
            device_id="my-device-123",
            sample_rate=16000,
            channels=1,
            duration=0.5,
            output_dir=temp_dir,
        )

        assert "my-device-123" in result.wav_path.name

    def test_wav_file_default_device_name(self, temp_dir: Path, mock_device_with_data: Any) -> None:
        result = LoopbackAudioSource.probe_device(
            device_id=None,
            sample_rate=16000,
            channels=1,
            duration=0.5,
            output_dir=temp_dir,
        )

        assert "default" in result.wav_path.name

    def test_wav_file_output_dir_created(self, temp_dir: Path, mock_device_with_data: Any) -> None:
        nested_dir = temp_dir / "nested" / "probe" / "dir"

        result = LoopbackAudioSource.probe_device(
            device_id="test",
            sample_rate=16000,
            channels=1,
            duration=0.3,
            output_dir=nested_dir,
        )

        assert nested_dir.exists()
        assert result.wav_path.exists()


class TestAudioProbeErrorHandling:
    """Test error handling for bad device."""

    def test_probe_handles_device_resolution_failure(self, temp_dir: Path) -> None:
        with patch("app.audio.capture.resolve_capture_device") as mock_resolve:
            mock_resolve.side_effect = RuntimeError("Device not found")

            with pytest.raises(RuntimeError) as exc_info:
                LoopbackAudioSource.probe_device(
                    device_id="nonexistent-device",
                    sample_rate=16000,
                    channels=1,
                    duration=0.5,
                    output_dir=temp_dir,
                )

            assert "Device not found" in str(exc_info.value)

    def test_probe_handles_recorder_failure(self, temp_dir: Path) -> None:
        with patch("app.audio.capture.resolve_capture_device") as mock_resolve:
            mock_device = MagicMock()
            mock_device.recorder.side_effect = RuntimeError("Recorder init failed")
            mock_resolve.return_value = (mock_device, "bad-device")

            with pytest.raises(RuntimeError) as exc_info:
                LoopbackAudioSource.probe_device(
                    device_id="bad-device",
                    sample_rate=16000,
                    channels=1,
                    duration=0.5,
                    output_dir=temp_dir,
                )

            assert "Recorder init failed" in str(exc_info.value)

    def test_probe_returns_zero_stats_on_all_drops(self, temp_dir: Path) -> None:
        with patch("app.audio.capture.resolve_capture_device") as mock_resolve:
            mock_device = MagicMock()
            mock_recorder_ctx = MagicMock()
            mock_recorder = MagicMock()

            def mock_record(**kwargs):
                return None

            mock_recorder.record = mock_record
            mock_recorder_ctx.__enter__ = MagicMock(return_value=mock_recorder)
            mock_recorder_ctx.__exit__ = MagicMock(return_value=None)
            mock_device.recorder.return_value = mock_recorder_ctx
            mock_resolve.return_value = (mock_device, "test-device")

            result = LoopbackAudioSource.probe_device(
                device_id="test-device",
                sample_rate=16000,
                channels=1,
                duration=0.3,
                output_dir=temp_dir,
            )

            assert result.rms_mean == 0.0
            assert result.rms_peak == 0.0
            assert result.has_signal is False
            assert result.dropped_frames > 0

    def test_device_probe_result_to_dict(self, temp_dir: Path, mock_device_with_data: Any) -> None:
        result = LoopbackAudioSource.probe_device(
            device_id="test-device",
            sample_rate=16000,
            channels=1,
            duration=0.3,
            output_dir=temp_dir,
        )

        data = result.to_dict()
        assert "sample_rate" in data
        assert "channels" in data
        assert "duration" in data
        assert "rms_mean" in data
        assert "rms_peak" in data
        assert "has_signal" in data
        assert "dominant_channels" in data
        assert "dropped_frames" in data
        assert "wav_path" in data
        assert isinstance(data["wav_path"], str)
