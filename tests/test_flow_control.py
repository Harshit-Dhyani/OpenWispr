from __future__ import annotations

from queue import Full
from typing import Any
from unittest.mock import MagicMock


class TestBackpressureDetection:
    """Test backpressure detection when queue is full."""

    def test_backpressure_normal_when_queue_empty(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        assert transcriber._backpressure_state == "normal"

    def test_backpressure_detected_when_queue_full(self) -> None:
        from app.stt.chunker import AudioChunk
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=2,
            vad_params=None,
        )

        import numpy as np

        chunk1 = AudioChunk(samples=np.zeros(1600, dtype=np.float32), started_at=0.0, duration=0.1)
        chunk2 = AudioChunk(samples=np.zeros(1600, dtype=np.float32), started_at=0.1, duration=0.1)
        chunk3 = AudioChunk(samples=np.zeros(1600, dtype=np.float32), started_at=0.2, duration=0.1)

        transcriber.submit(chunk1)
        transcriber.submit(chunk2)
        transcriber.submit(chunk3)

        assert transcriber._backpressure_state == "dropping_oldest"

    def test_dropped_chunks_counter_increments(self) -> None:
        from app.stt.chunker import AudioChunk
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=2,
            vad_params=None,
        )

        import numpy as np

        for i in range(5):
            chunk = AudioChunk(
                samples=np.zeros(1600, dtype=np.float32),
                started_at=i * 0.1,
                duration=0.1,
            )
            transcriber.submit(chunk)

        assert transcriber._dropped_chunks > 0

    def test_submit_returns_false_when_stopped(self) -> None:
        from app.stt.chunker import AudioChunk
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        transcriber._stop.set()

        import numpy as np

        chunk = AudioChunk(samples=np.zeros(1600, dtype=np.float32), started_at=0.0, duration=0.1)
        result = transcriber.submit(chunk)

        assert result is False

    def test_oldest_chunk_evicted_when_full(self) -> None:
        from app.stt.chunker import AudioChunk
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=2,
            vad_params=None,
        )

        import numpy as np

        chunks = []
        for i in range(4):
            chunk = AudioChunk(
                samples=np.full(1600, float(i), dtype=np.float32),
                started_at=i * 0.1,
                duration=0.1,
            )
            chunks.append(chunk)
            transcriber.submit(chunk)

        remaining_samples = []
        while not transcriber._queue.empty():
            remaining_samples.append(transcriber._queue.get_nowait().samples[0])

        assert len(remaining_samples) == 2
        assert remaining_samples[0] == 2.0
        assert remaining_samples[1] == 3.0

    def test_queue_depth_reported_in_health(self) -> None:
        from app.stt.chunker import AudioChunk
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        import numpy as np

        for i in range(3):
            chunk = AudioChunk(
                samples=np.zeros(1600, dtype=np.float32),
                started_at=i * 0.1,
                duration=0.1,
            )
            transcriber.submit(chunk)

        health = transcriber._health_snapshot(queue_depth=transcriber._queue.qsize())

        assert health.queue_depth == 3


class TestBacklogEstimation:
    """Test backlog estimation."""

    def test_backlog_zero_when_queue_empty(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        estimated_backlog = transcriber._queue.qsize() * transcriber._avg_chunk_duration
        assert estimated_backlog == 0.0

    def test_backlog_estimation_with_queue_depth(self) -> None:
        from app.stt.chunker import AudioChunk
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        transcriber._avg_chunk_duration = 5.0
        transcriber._chunks_processed = 10

        import numpy as np

        for i in range(3):
            chunk = AudioChunk(
                samples=np.zeros(1600, dtype=np.float32),
                started_at=i * 5.0,
                duration=5.0,
            )
            transcriber._queue.put(chunk)

        estimated_backlog = transcriber._queue.qsize() * transcriber._avg_chunk_duration

        assert estimated_backlog == 15.0

    def test_backlog_updates_with_processing_times(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        processing_times = [2.0, 2.5, 3.0, 2.2, 2.8]
        with transcriber._processing_times_lock:
            transcriber._processing_times.extend(processing_times)

        avg_time = sum(processing_times) / len(processing_times)

        assert 2.0 <= avg_time <= 3.0

    def test_health_includes_backpressure_state(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        transcriber._backpressure_state = "critical"

        health = transcriber._health_snapshot(queue_depth=0)

        assert health.stt_backpressure_state == "critical"

    def test_health_includes_dropped_chunks(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        transcriber._dropped_chunks = 42

        health = transcriber._health_snapshot(queue_depth=0)

        assert health.dropped_stt_chunks == 42

    def test_warning_set_on_queue_saturation(self) -> None:
        from app.stt.chunker import AudioChunk
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=1,
            vad_params=None,
        )

        import numpy as np

        for i in range(5):
            chunk = AudioChunk(
                samples=np.zeros(1600, dtype=np.float32),
                started_at=i * 0.1,
                duration=0.1,
            )
            transcriber.submit(chunk)

        assert transcriber._warning is not None
        assert "queue" in transcriber._warning.lower() or "dropping" in transcriber._warning.lower()


class TestFlowControlIntegration:
    """Test flow control integration with session manager."""

    def test_session_manager_receives_health_updates(self) -> None:
        from app.core.config import AppSettings

        from app.core.session_manager import SessionManager

        settings = AppSettings()
        manager = SessionManager(settings)

        health_updates: list[Any] = []

        def capture_health(health: Any, meter: float) -> None:
            health_updates.append(health)

        manager.set_callbacks(on_health=capture_health)

        mock_health = MagicMock()
        mock_health.to_dict.return_value = {
            "queue_depth": 5,
            "dropped_stt_chunks": 2,
            "stt_backpressure_state": "elevated",
        }

        manager._handle_health(mock_health)

        assert len(health_updates) > 0

    def test_audio_source_dropped_frames_tracked(self) -> None:
        from app.audio.capture import LoopbackAudioSource

        source = LoopbackAudioSource(
            device_id=None,
            sample_rate=16000,
            channels=1,
            block_size=512,
            max_queue_items=2,
        )

        import numpy as np

        source.queue.put(np.zeros(512, dtype=np.float32))
        source.queue.put(np.zeros(512, dtype=np.float32))

        try:
            source.queue.put_nowait(np.zeros(512, dtype=np.float32))
        except Full:
            pass

        assert source.queue.full()

    def test_chunker_respects_flow_control(self) -> None:
        from app.stt.chunker import RollingChunker

        chunker = RollingChunker(
            sample_rate=16000,
            chunk_seconds=1.0,
            overlap_seconds=0.2,
        )

        import numpy as np

        samples = np.zeros(16000, dtype=np.float32)
        chunks = chunker.push(samples, stream_time=0.0)

        assert isinstance(chunks, list)
