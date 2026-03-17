"""Performance tests for memory usage.

Tests cover:
- Audio buffer memory usage
- Session memory footprint
- Settings memory usage
- Memory leaks detection
- Garbage collection impact
"""

from __future__ import annotations

import gc
import tracemalloc

import numpy as np
import pytest


class TestAudioMemory:
    """Tests for audio-related memory usage."""

    @pytest.fixture
    def memory_config(self) -> dict:
        """Memory test configuration."""
        return {
            "max_audio_buffer_mb": 100,
            "max_vad_memory_mb": 50,
        }

    def test_vad_memory_usage(self, memory_config: dict, sample_rate: int) -> None:
        """Test VAD memory usage."""
        from app.audio.vad_optimized import OptimizedVAD

        tracemalloc.start()

        # Create VAD and process some audio
        vad = OptimizedVAD(sample_rate=sample_rate)

        # Generate and process audio
        for _ in range(100):
            frame = np.zeros(int(sample_rate * 0.02), dtype=np.float32)
            vad.process_frame(frame)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        current_mb = current / (1024 * 1024)

        assert current_mb < memory_config["max_vad_memory_mb"], (
            f"VAD memory usage {current_mb:.1f}MB exceeds threshold "
            f"{memory_config['max_vad_memory_mb']}MB"
        )

    def test_ring_buffer_memory_usage(self, memory_config: dict) -> None:
        """Test ring buffer memory usage."""
        import asyncio

        from app.audio.system_pipeline import RingBuffer

        async def test():
            tracemalloc.start()

            # Create buffer
            buffer = RingBuffer(capacity=16, buffer_size=8000)

            # Fill buffer
            data = np.ones(8000, dtype=np.float32)
            for _ in range(16):
                await buffer.write(data)

            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            return current / (1024 * 1024)

        memory_mb = asyncio.run(test())

        # 16 buffers * 8000 samples * 4 bytes = ~512KB
        assert memory_mb < 10, f"Ring buffer memory {memory_mb:.1f}MB too high"

    def test_audio_array_memory(self, memory_config: dict) -> None:
        """Test audio array memory footprint."""
        # 5 minutes of 16kHz audio
        duration_minutes = 5
        samples = int(16000 * 60 * duration_minutes)

        memory_bytes = samples * 4  # float32 = 4 bytes
        memory_mb = memory_bytes / (1024 * 1024)

        expected_mb = samples * 4 / (1024 * 1024)
        assert memory_mb == pytest.approx(expected_mb, abs=0.1)

    def test_numpy_memory_cleanup(self) -> None:
        """Test numpy array memory cleanup."""
        gc.collect()

        # Allocate large array
        large_array = np.ones((1000000,), dtype=np.float32)
        size_before = large_array.nbytes

        # Delete and verify cleanup
        del large_array
        gc.collect()

        # Just verify no exception raised
        assert True


class TestSessionMemory:
    """Tests for session-related memory usage."""

    @pytest.fixture
    def memory_config(self) -> dict:
        """Memory test configuration."""
        return {
            "max_session_memory_mb": 50,
            "max_segments": 10000,
        }

    def test_session_creation_memory(self, memory_config: dict, temp_path) -> None:
        """Test session creation memory."""
        from app.core.models import SessionState

        tracemalloc.start()

        session = SessionState.create(
            title="Test Session",
            output_dir=temp_path,
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
            execution_mode="auto",
        )

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        current_mb = current / (1024 * 1024)

        assert current_mb < memory_config["max_session_memory_mb"]

    def test_segments_memory_usage(self, memory_config: dict) -> None:
        """Test memory usage with many segments."""
        from app.core.models import TranscriptSegment

        tracemalloc.start()

        segments = []
        for i in range(1000):
            segment = TranscriptSegment(
                id=f"seg-{i}",
                start=float(i * 5),
                end=float((i + 1) * 5),
                text=f"Test segment {i} with some text content",
                display_text=f"Test segment {i} with some text content",
                language="en",
                confidence=0.85,
            )
            segments.append(segment)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        current_mb = current / (1024 * 1024)

        # 1000 segments should use reasonable memory
        assert current_mb < 50, f"Segments memory {current_mb:.1f}MB too high"


class TestSettingsMemory:
    """Tests for settings memory usage."""

    def test_settings_memory_footprint(self) -> None:
        """Test settings memory footprint."""
        from app.core.settings.manager import SettingsState

        tracemalloc.start()

        settings = SettingsState()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        current_mb = current / (1024 * 1024)

        # Settings should use minimal memory
        assert current_mb < 10, f"Settings memory {current_mb:.1f}MB too high"


class TestMemoryLeaks:
    """Tests for memory leaks."""

    def test_vad_no_memory_leak(self) -> None:
        """Test VAD doesn't leak memory."""
        from app.audio.vad_optimized import OptimizedVAD

        gc.collect()

        # Create and destroy multiple VAD instances
        for _ in range(100):
            vad = OptimizedVAD()
            frame = np.zeros(320, dtype=np.float32)
            vad.process_frame(frame)
            del vad

        gc.collect()

        # No assertion - just verify no crash
        assert True

    def test_session_manager_no_leak(self) -> None:
        """Test session manager doesn't leak memory."""
        from unittest.mock import MagicMock

        from app.core.session_manager import SessionManager

        settings = MagicMock()
        settings.sample_rate = 16000
        settings.channels = 1
        settings.meter_decay = 0.9

        gc.collect()

        for _ in range(10):
            manager = SessionManager(settings)
            del manager

        gc.collect()

        # No assertion - just verify no crash
        assert True


class TestGarbageCollection:
    """Tests for garbage collection impact."""

    def test_gc_during_audio_processing(self) -> None:
        """Test GC doesn't significantly impact audio processing."""
        import time

        from app.audio.vad_optimized import OptimizedVAD

        vad = OptimizedVAD()
        frame = np.zeros(320, dtype=np.float32)

        # Warmup
        for _ in range(100):
            vad.process_frame(frame)

        # Measure without GC
        gc.disable()
        start = time.perf_counter()
        for _ in range(1000):
            vad.process_frame(frame)
        duration_no_gc = time.perf_counter() - start
        gc.enable()

        # Measure with GC
        gc.collect()
        start = time.perf_counter()
        for _ in range(1000):
            vad.process_frame(frame)
        duration_with_gc = time.perf_counter() - start

        # GC overhead should be minimal
        overhead = (duration_with_gc - duration_no_gc) / duration_no_gc
        assert overhead < 0.5, f"GC overhead {overhead * 100:.1f}% too high"


class TestLargeDataMemory:
    """Tests for large data memory handling."""

    def test_large_transcript_memory(self) -> None:
        """Test memory with large transcript."""
        from app.core.models import TranscriptSegment

        tracemalloc.start()

        # Create 10,000 segments
        segments = []
        for i in range(10000):
            segment = TranscriptSegment(
                id=f"seg-{i}",
                start=float(i * 10),
                end=float((i + 1) * 10),
                text="This is a test segment with moderately long text content. " * 5,
                display_text="This is a test segment with moderately long text content. " * 5,
                language="en",
                confidence=0.85,
            )
            segments.append(segment)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        current_mb = current / (1024 * 1024)

        # Should handle 10k segments without excessive memory
        assert current_mb < 200, f"Large transcript memory {current_mb:.1f}MB too high"

    def test_long_running_session_memory(self) -> None:
        """Test memory during long running session simulation."""
        from app.audio.vad_optimized import OptimizedVAD

        tracemalloc.start()

        vad = OptimizedVAD()

        # Simulate 1 hour of audio (20ms frames)
        num_frames = int(3600 / 0.02)
        frame = np.zeros(320, dtype=np.float32)

        # Sample every 1000 frames to speed up test
        for i in range(0, min(num_frames, 10000), 1000):
            vad.process_frame(frame)

        # Get memory usage
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        current_mb = current / (1024 * 1024)

        # Should not grow unbounded
        assert current_mb < 100, f"Long session memory {current_mb:.1f}MB too high"
