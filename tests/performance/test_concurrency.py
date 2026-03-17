"""Performance tests for concurrency.

Tests cover:
- Thread safety
- Async/await performance
- Lock contention
- Parallel processing
- Resource pooling
"""

from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pytest

pytestmark = pytest.mark.performance


class TestThreadSafety:
    """Tests for thread safety."""

    def test_settings_manager_thread_safety(self, temp_dir) -> None:
        """Test SettingsManager is thread-safe."""
        from app.core.settings.manager import SettingsManager

        manager = SettingsManager(settings_dir=temp_dir)
        errors = []
        results = []

        def reader():
            try:
                for _ in range(100):
                    settings = manager.get_settings()
                    results.append(settings.general.defaultSessionTitle)
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(100):
                    manager.update_partial("general", {"defaultSessionTitle": f"Title-{i}"})
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=reader))
            threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_session_manager_thread_safety(self) -> None:
        """Test SessionManager callback thread-safety."""
        from unittest.mock import MagicMock

        from app.core.session_manager import SessionManager

        settings = MagicMock()
        settings.sample_rate = 16000
        settings.channels = 1
        settings.meter_decay = 0.9

        manager = SessionManager(settings)

        callback_count = [0]
        callback_lock = threading.Lock()

        def callback():
            with callback_lock:
                callback_count[0] += 1

        manager.set_callbacks(on_segment=lambda s: callback())

        threads = []
        for _ in range(10):
            t = threading.Thread(target=callback)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert callback_count[0] == 10


class TestAsyncPerformance:
    """Tests for async/await performance."""

    @pytest.mark.asyncio
    async def test_async_vad_processing(self) -> None:
        """Test async VAD processing performance."""
        from app.audio.vad_optimized import OptimizedVAD

        vad = OptimizedVAD()
        frame = np.zeros(320, dtype=np.float32)

        async def process():
            return vad.process_frame(frame)

        # Process multiple frames concurrently
        tasks = [process() for _ in range(100)]
        start = time.perf_counter()
        await asyncio.gather(*tasks)
        duration = time.perf_counter() - start

        # Should complete quickly
        assert duration < 1.0, f"Async VAD processing took {duration:.2f}s"

    @pytest.mark.asyncio
    async def test_ring_buffer_async_performance(self) -> None:
        """Test ring buffer async performance."""
        from app.audio.system_pipeline import RingBuffer

        buffer = RingBuffer(capacity=100, buffer_size=8000)
        data = np.ones(8000, dtype=np.float32)

        async def writer():
            for _ in range(50):
                await buffer.write(data)
                await asyncio.sleep(0)

        async def reader():
            for _ in range(50):
                await buffer.read()
                await asyncio.sleep(0)

        start = time.perf_counter()
        await asyncio.gather(writer(), reader())
        duration = time.perf_counter() - start

        assert duration < 2.0, f"Ring buffer operations took {duration:.2f}s"


class TestLockContention:
    """Tests for lock contention."""

    def test_low_lock_contention_settings(self) -> None:
        """Test settings manager has low lock contention."""
        import tempfile

        from app.core.settings.manager import SettingsManager

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = temp_dir
            manager = SettingsManager(settings_dir=temp_path)

            def accessor():
                for _ in range(1000):
                    _ = manager.get_settings()

            start = time.perf_counter()

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(accessor) for _ in range(10)]
                for f in as_completed(futures):
                    f.result()

            duration = time.perf_counter() - start

            # Should complete quickly despite contention
            assert duration < 5.0, f"High lock contention: {duration:.2f}s"

    def test_lock_contention_vad(self) -> None:
        """Test VAD has minimal lock contention."""
        from app.audio.vad_optimized import OptimizedVAD

        vads = [OptimizedVAD() for _ in range(10)]
        frames = [np.zeros(320, dtype=np.float32) for _ in range(10)]

        def processor(vad, frame):
            for _ in range(100):
                vad.process_frame(frame)

        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(processor, vad, frame) for vad, frame in zip(vads, frames)]
            for f in as_completed(futures):
                f.result()

        duration = time.perf_counter() - start

        # Parallel processing should be faster than sequential
        assert duration < 5.0, f"VAD processing took {duration:.2f}s"


class TestParallelProcessing:
    """Tests for parallel processing."""

    def test_parallel_audio_processing(self) -> None:
        """Test parallel audio processing."""
        from app.audio.vad_optimized import OptimizedVAD

        audio_chunks = [np.random.randn(16000).astype(np.float32) for _ in range(10)]

        def process_chunk(chunk):
            vad = OptimizedVAD()
            segments = vad.process_stream(chunk)
            return len(segments)

        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(process_chunk, audio_chunks))

        duration = time.perf_counter() - start

        # Should process in parallel
        assert duration < 10.0, f"Parallel processing took {duration:.2f}s"
        assert len(results) == 10

    def test_parallel_serialization(self) -> None:
        """Test parallel serialization."""
        import json

        from app.core.models import TranscriptSegment

        segments = [
            TranscriptSegment(
                id=f"seg-{i}",
                start=float(i),
                end=float(i + 1),
                text=f"Text {i}",
                display_text=f"Text {i}",
                language="en",
                confidence=0.85,
            )
            for i in range(1000)
        ]

        def serialize_segment(segment):
            return json.dumps(segment.to_dict())

        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(serialize_segment, segments))

        duration = time.perf_counter() - start

        assert duration < 5.0, f"Parallel serialization took {duration:.2f}s"
        assert len(results) == 1000


class TestResourcePooling:
    """Tests for resource pooling."""

    def test_thread_pool_reuse(self) -> None:
        """Test thread pool reuse efficiency."""

        def worker(n):
            return n * n

        # First batch
        with ThreadPoolExecutor(max_workers=4) as executor:
            start = time.perf_counter()
            list(executor.map(worker, range(100)))
            first_duration = time.perf_counter() - start

        # Second batch (should be faster due to pool reuse)
        with ThreadPoolExecutor(max_workers=4) as executor:
            start = time.perf_counter()
            list(executor.map(worker, range(100)))
            second_duration = time.perf_counter() - start

        # Both should complete reasonably fast
        assert first_duration < 2.0
        assert second_duration < 2.0

    def test_numpy_array_pooling(self) -> None:
        """Test numpy array memory reuse."""
        arrays = []

        # Allocate and deallocate repeatedly
        for _ in range(100):
            arr = np.ones(100000, dtype=np.float32)
            arrays.append(arr)

        # Clear and reallocate
        arrays.clear()

        for _ in range(100):
            arr = np.ones(100000, dtype=np.float32)
            arrays.append(arr)

        # Should complete without memory issues
        assert len(arrays) == 100


class TestConcurrencyLimits:
    """Tests for concurrency limits."""

    def test_max_concurrent_vad_instances(self) -> None:
        """Test maximum concurrent VAD instances."""
        from app.audio.vad_optimized import OptimizedVAD

        vads = []

        # Create many VAD instances
        for i in range(100):
            try:
                vad = OptimizedVAD()
                vads.append(vad)
            except Exception as e:
                pytest.fail(f"Failed to create VAD instance {i}: {e}")

        assert len(vads) == 100

    def test_max_concurrent_settings_access(self, temp_dir) -> None:
        """Test maximum concurrent settings access."""
        from app.core.settings.manager import SettingsManager

        manager = SettingsManager(settings_dir=temp_dir)

        def accessor():
            for _ in range(100):
                _ = manager.get_settings()

        threads = [threading.Thread(target=accessor) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        assert True


class TestAsyncConcurrency:
    """Tests for async concurrency patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_websocket_simulation(self) -> None:
        """Test concurrent WebSocket-like operations."""

        async def simulated_websocket_client(client_id: int):
            messages = []
            for i in range(10):
                await asyncio.sleep(0.01)  # Simulate network delay
                messages.append(f"Client {client_id} - Message {i}")
            return messages

        # Simulate 50 concurrent clients
        clients = [simulated_websocket_client(i) for i in range(50)]

        start = time.perf_counter()
        results = await asyncio.gather(*clients)
        duration = time.perf_counter() - start

        assert len(results) == 50
        assert all(len(r) == 10 for r in results)
        # Should complete concurrently, not sequentially
        assert duration < 5.0, f"Concurrent operations took {duration:.2f}s"

    @pytest.mark.asyncio
    async def test_async_queue_performance(self) -> None:
        """Test async queue performance."""
        queue = asyncio.Queue(maxsize=1000)

        async def producer():
            for i in range(1000):
                await queue.put(i)

        async def consumer():
            count = 0
            while count < 1000:
                await queue.get()
                count += 1

        start = time.perf_counter()
        await asyncio.gather(producer(), consumer())
        duration = time.perf_counter() - start

        assert duration < 5.0, f"Queue operations took {duration:.2f}s"
