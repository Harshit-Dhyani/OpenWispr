"""Performance tests for throughput.

Tests cover:
- Audio processing throughput
- Transcription throughput
- API request throughput
- Concurrent request handling
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest


class TestAudioThroughput:
    """Tests for audio processing throughput."""

    @pytest.fixture
    def benchmark_config(self) -> dict:
        """Performance benchmark configuration."""
        return {
            "min_chunks_per_second": 10,
            "measurement_duration_seconds": 5,
        }

    def test_vad_throughput(self, benchmark_config: dict, sample_rate: int) -> None:
        """Benchmark VAD processing throughput."""
        from app.audio.vad_optimized import OptimizedVAD

        vad = OptimizedVAD(sample_rate=sample_rate)
        frame = np.zeros(int(sample_rate * 0.02), dtype=np.float32)  # 20ms frame

        chunks_processed = 0
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < benchmark_config["measurement_duration_seconds"]:
            vad.process_frame(frame)
            chunks_processed += 1

        duration = time.perf_counter() - start_time
        throughput = chunks_processed / duration

        assert throughput > benchmark_config["min_chunks_per_second"], (
            f"VAD throughput {throughput:.1f} chunks/s below threshold "
            f"{benchmark_config['min_chunks_per_second']} chunks/s"
        )

    def test_chunker_throughput(self, benchmark_config: dict) -> None:
        """Benchmark audio chunker throughput."""
        from app.stt.fast_chunker import FastChunker

        chunker = FastChunker(sample_rate=16000, chunk_duration=5.0, overlap_ratio=0.15)

        # 5 second audio chunks
        audio = np.random.randn(16000 * 5).astype(np.float32)

        chunks_created = 0
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < benchmark_config["measurement_duration_seconds"]:
            chunker.push(audio, 0.0)
            chunks_created += len(chunker.push(audio, 5.0))
            chunker.reset()

        duration = time.perf_counter() - start_time
        throughput = chunks_created / duration

        assert throughput > 1.0, f"Chunker throughput {throughput:.1f} chunks/s too low"

    def test_audio_buffer_throughput(self, benchmark_config: dict) -> None:
        """Benchmark audio buffer write/read throughput."""
        from app.audio.system_pipeline import RingBuffer

        async def benchmark():
            buffer = RingBuffer(capacity=100, buffer_size=8000)
            data = np.ones(8000, dtype=np.float32)

            operations = 0
            start_time = time.perf_counter()

            while (
                time.perf_counter() - start_time < benchmark_config["measurement_duration_seconds"]
            ):
                await buffer.write(data)
                await buffer.read()
                operations += 1

            duration = time.perf_counter() - start_time
            return operations / duration

        throughput = asyncio.run(benchmark())

        assert throughput > 100, f"Buffer throughput {throughput:.1f} ops/s too low"


class TestTranscriptionThroughput:
    """Tests for transcription throughput."""

    @pytest.fixture
    def benchmark_config(self) -> dict:
        """Performance benchmark configuration."""
        return {
            "min_segments_per_second": 0.1,
            "measurement_iterations": 10,
        }

    def test_mock_transcription_throughput(self, benchmark_config: dict) -> None:
        """Benchmark transcription throughput with mock."""
        from unittest.mock import MagicMock, patch

        with patch("app.stt.engine.WhisperModel") as mock_model_class:
            mock_model = MagicMock()
            mock_segment = MagicMock()
            mock_segment.text = "Test"
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

            transcriber._load_model()
            audio = np.zeros(16000, dtype=np.float32)

            segments_processed = 0
            start_time = time.perf_counter()

            for _ in range(benchmark_config["measurement_iterations"]):
                segments, _ = transcriber._model.transcribe(audio)
                segments_processed += len(list(segments))

            duration = time.perf_counter() - start_time
            throughput = segments_processed / duration

            # With mocked model, should be very fast
            assert throughput > 10, f"Mock transcription throughput {throughput:.1f} segs/s too low"


class TestAPIThroughput:
    """Tests for API throughput."""

    @pytest.fixture
    def benchmark_config(self) -> dict:
        """Performance benchmark configuration."""
        return {
            "min_requests_per_second": 100,
            "measurement_iterations": 1000,
        }

    def test_health_endpoint_throughput(self, benchmark_config: dict) -> None:
        """Benchmark health endpoint throughput."""
        from unittest.mock import MagicMock

        from app.api.server import health

        mock_service = MagicMock()
        mock_service.get_snapshot.return_value = MagicMock(
            health={"ok": True},
            meter_value=0.5,
            model_cache={},
        )

        start_time = time.perf_counter()

        for _ in range(benchmark_config["measurement_iterations"]):
            health(mock_service)

        duration = time.perf_counter() - start_time
        throughput = benchmark_config["measurement_iterations"] / duration

        assert throughput > benchmark_config["min_requests_per_second"], (
            f"Health endpoint throughput {throughput:.1f} req/s below threshold"
        )

    def test_device_list_throughput(self, benchmark_config: dict) -> None:
        """Benchmark device list endpoint throughput."""
        from unittest.mock import MagicMock

        from app.api.server import devices

        mock_service = MagicMock()
        mock_service.list_devices.return_value = [
            MagicMock(id=f"device-{i}", name=f"Device {i}") for i in range(10)
        ]

        start_time = time.perf_counter()

        for _ in range(benchmark_config["measurement_iterations"]):
            devices(mock_service)

        duration = time.perf_counter() - start_time
        throughput = benchmark_config["measurement_iterations"] / duration

        assert throughput > 50, f"Device list throughput {throughput:.1f} req/s too low"


class TestSerializationThroughput:
    """Tests for serialization throughput."""

    @pytest.fixture
    def benchmark_config(self) -> dict:
        """Performance benchmark configuration."""
        return {
            "min_operations_per_second": 10000,
            "measurement_iterations": 10000,
        }

    def test_settings_serialization_throughput(
        self, benchmark_config: dict, test_settings: dict
    ) -> None:
        """Benchmark settings serialization throughput."""
        import json

        start_time = time.perf_counter()

        for _ in range(benchmark_config["measurement_iterations"]):
            json.dumps(test_settings)

        duration = time.perf_counter() - start_time
        throughput = benchmark_config["measurement_iterations"] / duration

        assert throughput > 1000, f"Settings serialization {throughput:.1f} ops/s too low"

    def test_segment_serialization_throughput(self, benchmark_config: dict) -> None:
        """Benchmark segment serialization throughput."""
        import json

        from app.core.models import TranscriptSegment

        segment = TranscriptSegment(
            id="seg-1",
            start=0.0,
            end=5.0,
            text="Test",
            display_text="Test",
            language="en",
            confidence=0.85,
        )

        start_time = time.perf_counter()

        for _ in range(benchmark_config["measurement_iterations"]):
            json.dumps(segment.to_dict())

        duration = time.perf_counter() - start_time
        throughput = benchmark_config["measurement_iterations"] / duration

        assert throughput > 10000, f"Segment serialization {throughput:.1f} ops/s too low"


class TestConcurrentThroughput:
    """Tests for concurrent operation throughput."""

    @pytest.fixture
    def benchmark_config(self) -> dict:
        """Performance benchmark configuration."""
        return {
            "num_workers": 4,
            "iterations_per_worker": 100,
        }

    def test_concurrent_health_checks(self, benchmark_config: dict) -> None:
        """Test concurrent health check throughput."""
        from unittest.mock import MagicMock

        from app.api.server import health

        mock_service = MagicMock()
        mock_service.get_snapshot.return_value = MagicMock(
            health={"ok": True},
            meter_value=0.5,
            model_cache={},
        )

        def worker():
            for _ in range(benchmark_config["iterations_per_worker"]):
                health(mock_service)
            return benchmark_config["iterations_per_worker"]

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=benchmark_config["num_workers"]) as executor:
            results = list(executor.map(lambda _: worker(), range(benchmark_config["num_workers"])))

        duration = time.perf_counter() - start_time
        total_requests = sum(results)
        throughput = total_requests / duration

        assert throughput > 200, f"Concurrent health checks {throughput:.1f} req/s too low"

    def test_concurrent_vad_processing(self, benchmark_config: dict, sample_rate: int) -> None:
        """Test concurrent VAD processing."""
        from app.audio.vad_optimized import OptimizedVAD

        def worker():
            vad = OptimizedVAD(sample_rate=sample_rate)
            frame = np.zeros(int(sample_rate * 0.02), dtype=np.float32)

            for _ in range(benchmark_config["iterations_per_worker"]):
                vad.process_frame(frame)

            return benchmark_config["iterations_per_worker"]

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=benchmark_config["num_workers"]) as executor:
            results = list(executor.map(lambda _: worker(), range(benchmark_config["num_workers"])))

        duration = time.perf_counter() - start_time
        total_frames = sum(results)
        throughput = total_frames / duration

        assert throughput > 100, f"Concurrent VAD {throughput:.1f} frames/s too low"


@pytest.mark.benchmark
class TestThroughputBenchmarkSuite:
    """Comprehensive throughput benchmark suite."""

    def test_audio_pipeline_throughput(self) -> None:
        """Benchmark complete audio pipeline throughput."""
        pytest.skip("Full pipeline benchmark requires complete system")

    def test_session_creation_throughput(self) -> None:
        """Benchmark session creation throughput."""
        pytest.skip("Session creation benchmark requires full system")
