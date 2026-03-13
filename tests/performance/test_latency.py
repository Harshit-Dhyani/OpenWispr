"""Performance tests for latency benchmarks.

Tests cover:
- Audio processing latency
- Transcription latency
- API response latency
- WebSocket message latency
"""

from __future__ import annotations

import asyncio
import statistics
import time

import numpy as np
import pytest


class TestAudioLatency:
    """Tests for audio processing latency."""

    @pytest.fixture
    def benchmark_config(self) -> dict:
        """Performance benchmark configuration."""
        return {
            "max_latency_ms": 100,
            "measurement_iterations": 100,
        }

    def test_vad_processing_latency(self, benchmark_config: dict, sample_rate: int) -> None:
        """Benchmark VAD processing latency."""
        from app.audio.vad_optimized import OptimizedVAD

        vad = OptimizedVAD(sample_rate=sample_rate)
        frame = np.zeros(int(sample_rate * 0.02), dtype=np.float32)  # 20ms frame

        latencies = []
        for _ in range(benchmark_config["measurement_iterations"]):
            start = time.perf_counter()
            vad.process_frame(frame)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)
        p95_latency = np.percentile(latencies, 95)

        assert avg_latency < benchmark_config["max_latency_ms"], (
            f"Average VAD latency {avg_latency:.2f}ms exceeds threshold "
            f"{benchmark_config['max_latency_ms']}ms"
        )
        assert p95_latency < benchmark_config["max_latency_ms"] * 1.5, (
            f"P95 VAD latency {p95_latency:.2f}ms exceeds threshold"
        )

    def test_rms_calculation_latency(self, benchmark_config: dict) -> None:
        """Benchmark RMS calculation latency."""
        from app.audio.system_pipeline import SystemPipeline, SystemPipelineConfig

        config = SystemPipelineConfig()
        pipeline = SystemPipeline(config)

        audio = np.random.randn(16000).astype(np.float32)

        latencies = []
        for _ in range(benchmark_config["measurement_iterations"]):
            start = time.perf_counter()
            pipeline._calculate_rms(audio)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)

        assert avg_latency < 10, f"RMS calculation too slow: {avg_latency:.2f}ms"

    def test_audio_chunking_latency(self, benchmark_config: dict) -> None:
        """Benchmark audio chunking latency."""
        from app.stt.fast_chunker import FastChunker

        chunker = FastChunker(sample_rate=16000, chunk_duration=5.0, overlap_ratio=0.15)
        audio = np.random.randn(16000 * 5).astype(np.float32)  # 5 seconds

        latencies = []
        for _ in range(benchmark_config["measurement_iterations"]):
            start = time.perf_counter()
            chunker.push(audio, 0.0)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)
            chunker.reset()

        avg_latency = statistics.mean(latencies)

        assert avg_latency < 50, f"Chunking too slow: {avg_latency:.2f}ms"


class TestTranscriptionLatency:
    """Tests for transcription latency."""

    @pytest.fixture
    def benchmark_config(self) -> dict:
        """Performance benchmark configuration."""
        return {
            "max_latency_ms": 5000,
            "warmup_iterations": 3,
            "measurement_iterations": 10,
        }

    @pytest.mark.slow
    def test_mock_transcription_latency(self, benchmark_config: dict) -> None:
        """Benchmark transcription latency with mock model."""
        from unittest.mock import MagicMock, patch

        # Mock the model for consistent timing
        with patch("app.stt.engine.WhisperModel") as mock_model_class:
            mock_model = MagicMock()
            mock_segment = MagicMock()
            mock_segment.text = "Test"
            mock_segment.start = 0.0
            mock_segment.end = 1.0
            mock_info = MagicMock()
            mock_info.language = "en"

            mock_model.transcribe.return_value = ([mock_segment], mock_info)
            mock_model_class.return_value = mock_model

            from app.stt.engine import WhisperTranscriber

            transcriber = WhisperTranscriber(
                model_name="tiny",
                download_root="/tmp/models",
                device="cpu",
                compute_type="int8",
                beam_size=1,
                best_of=1,
                temperature=0.0,
                vad_filter=False,
                language_mode="en",
                execution_mode="auto",
                max_queue_items=10,
            )

            # Warmup
            transcriber._load_model()

            audio = np.zeros(16000, dtype=np.float32)

            latencies = []
            for _ in range(benchmark_config["measurement_iterations"]):
                start = time.perf_counter()
                segments, info = transcriber._model.transcribe(audio)
                list(segments)  # Consume generator
                end = time.perf_counter()
                latencies.append((end - start) * 1000)

            avg_latency = statistics.mean(latencies)

            # With mocked model, should be very fast
            assert avg_latency < 100, f"Mock transcription too slow: {avg_latency:.2f}ms"


class TestAPILatency:
    """Tests for API response latency."""

    @pytest.fixture
    def benchmark_config(self) -> dict:
        """Performance benchmark configuration."""
        return {
            "max_latency_ms": 100,
            "measurement_iterations": 100,
        }

    def test_health_endpoint_latency(self, benchmark_config: dict) -> None:
        """Benchmark health check endpoint latency."""
        from unittest.mock import MagicMock

        from app.api.server import health

        mock_service = MagicMock()
        mock_service.get_snapshot.return_value = MagicMock(
            health={"ok": True},
            meter_value=0.5,
            model_cache={},
        )

        latencies = []
        for _ in range(benchmark_config["measurement_iterations"]):
            start = time.perf_counter()
            health(mock_service)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)
        p99_latency = np.percentile(latencies, 99)

        assert avg_latency < benchmark_config["max_latency_ms"]
        assert p99_latency < benchmark_config["max_latency_ms"] * 2

    def test_device_list_latency(self, benchmark_config: dict) -> None:
        """Benchmark device listing latency."""
        from unittest.mock import MagicMock

        from app.api.server import devices

        mock_service = MagicMock()
        mock_service.list_devices.return_value = [
            MagicMock(id=f"device-{i}", name=f"Device {i}") for i in range(10)
        ]

        latencies = []
        for _ in range(benchmark_config["measurement_iterations"]):
            start = time.perf_counter()
            devices(mock_service)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)

        assert avg_latency < benchmark_config["max_latency_ms"]


class TestSerializationLatency:
    """Tests for serialization latency."""

    @pytest.fixture
    def benchmark_config(self) -> dict:
        """Performance benchmark configuration."""
        return {
            "max_latency_ms": 10,
            "measurement_iterations": 1000,
        }

    def test_settings_serialization_latency(
        self, benchmark_config: dict, test_settings: dict
    ) -> None:
        """Benchmark settings serialization latency."""
        import json

        latencies = []
        for _ in range(benchmark_config["measurement_iterations"]):
            start = time.perf_counter()
            json.dumps(test_settings)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)

        assert avg_latency < benchmark_config["max_latency_ms"]

    def test_segment_serialization_latency(self, benchmark_config: dict) -> None:
        """Benchmark segment serialization latency."""
        import json

        from app.core.models import TranscriptSegment

        segment = TranscriptSegment(
            id="seg-1",
            start=0.0,
            end=5.0,
            text="Test segment with some text content",
            display_text="Test segment with some text content",
            language="en",
            confidence=0.85,
        )

        latencies = []
        for _ in range(benchmark_config["measurement_iterations"]):
            start = time.perf_counter()
            json.dumps(segment.to_dict())
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)

        assert avg_latency < 1.0, f"Segment serialization too slow: {avg_latency:.2f}ms"


class TestMemoryLatency:
    """Tests for memory-related latency."""

    @pytest.fixture
    def benchmark_config(self) -> dict:
        """Performance benchmark configuration."""
        return {
            "max_latency_ms": 50,
            "measurement_iterations": 100,
        }

    def test_numpy_array_copy_latency(self, benchmark_config: dict) -> None:
        """Benchmark numpy array copy latency."""
        audio = np.random.randn(16000 * 5).astype(np.float32)  # 5 seconds

        latencies = []
        for _ in range(benchmark_config["measurement_iterations"]):
            start = time.perf_counter()
            _ = audio.copy()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)

        assert avg_latency < benchmark_config["max_latency_ms"]

    def test_ring_buffer_operation_latency(self, benchmark_config: dict) -> None:
        """Benchmark ring buffer operation latency."""
        from app.audio.system_pipeline import RingBuffer

        async def benchmark():
            buffer = RingBuffer(capacity=16, buffer_size=8000)
            data = np.ones(8000, dtype=np.float32)

            latencies = []
            for _ in range(benchmark_config["measurement_iterations"]):
                start = time.perf_counter()
                await buffer.write(data)
                await buffer.read()
                end = time.perf_counter()
                latencies.append((end - start) * 1000)

            return statistics.mean(latencies)

        avg_latency = asyncio.run(benchmark())

        assert avg_latency < benchmark_config["max_latency_ms"]


@pytest.mark.benchmark
class TestBenchmarkSuite:
    """Comprehensive benchmark suite."""

    def test_full_pipeline_latency(self) -> None:
        """Benchmark full pipeline latency."""
        pytest.skip("Full pipeline benchmark requires full system setup")

    def test_end_to_end_transcription_latency(self) -> None:
        """Benchmark end-to-end transcription latency."""
        pytest.skip("E2E benchmark requires complete system")
