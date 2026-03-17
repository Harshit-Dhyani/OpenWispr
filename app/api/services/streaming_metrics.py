"""Streaming metrics collection for transcription performance monitoring.

Provides StreamingMetrics class for tracking transcription pipeline latency:
- Draft (live) transcript emission timing
- Commit (final) transcript emission timing
- Refinement processing duration
- Superseded refinement tracking (debounced jobs cancelled)

Thread-safe with locking. Maintains rolling window of recent samples for
average latency calculations.
"""

from __future__ import annotations

import logging
from collections import deque
from threading import Lock

logger = logging.getLogger(__name__)


class StreamingMetrics:
    """Streaming transcription performance metrics collector.

    Tracks transcription pipeline latency with thread-safe rolling windows.
    Maintains recent samples for average latency calculations.

    State ownership:
    - In-memory metrics only; not persisted
    - Rolling windows: draft_emit (100), commit_emit (100), refine (50)
    - Lock protects all metric updates

    Metrics tracked:
    - draft_emit_ms: live transcript emission timing
    - commit_emit_ms: final transcript emission timing
    - refine_ms: refinement processing duration
    - superseded_refines: debounced jobs cancelled before execution
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._draft_emit_ms: deque[float] = deque(maxlen=100)
        self._commit_emit_ms: deque[float] = deque(maxlen=100)
        self._refine_ms: deque[float] = deque(maxlen=50)
        self._superseded_refines = 0

    def record_draft(self, emit_ms: float) -> None:
        with self._lock:
            self._draft_emit_ms.append(float(emit_ms))

    def record_commit(self, emit_ms: float) -> None:
        with self._lock:
            self._commit_emit_ms.append(float(emit_ms))

    def record_refine(self, duration_ms: float) -> None:
        with self._lock:
            self._refine_ms.append(float(duration_ms))

    def record_superseded_refine(self) -> None:
        with self._lock:
            self._superseded_refines += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "draft_emit_ms_avg": _avg(self._draft_emit_ms),
                "commit_emit_ms_avg": _avg(self._commit_emit_ms),
                "refine_ms_avg": _avg(self._refine_ms),
                "draft_samples": len(self._draft_emit_ms),
                "commit_samples": len(self._commit_emit_ms),
                "refine_samples": len(self._refine_ms),
                "superseded_refines": self._superseded_refines,
            }

    def log_trace(
        self,
        *,
        session_id: str,
        segment_id: str,
        stage: str,
        duration_ms: float,
        extra: str = "",
    ) -> None:
        logger.info(
            "stream_trace session=%s segment=%s stage=%s duration_ms=%.2f %s",
            session_id,
            segment_id,
            stage,
            duration_ms,
            extra.strip(),
        )


def _avg(values: deque[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)
