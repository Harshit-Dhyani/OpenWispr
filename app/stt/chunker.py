from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(slots=True, init=False)
class AudioChunk:
    started_at: float
    ended_at: float
    samples: np.ndarray

    def __init__(
        self,
        *,
        started_at: float,
        samples: np.ndarray,
        ended_at: float | None = None,
        duration: float | None = None,
    ) -> None:
        if ended_at is None:
            if duration is None:
                raise TypeError("AudioChunk requires either ended_at or duration")
            ended_at = started_at + duration
        self.started_at = started_at
        self.ended_at = ended_at
        self.samples = samples

    @property
    def duration(self) -> float:
        return self.ended_at - self.started_at


class RollingChunker:
    def __init__(self, *, sample_rate: int, chunk_seconds: float, overlap_seconds: float) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_seconds)
        self.overlap_size = int(sample_rate * overlap_seconds)
        self.step_size = self.chunk_size - self.overlap_size
        if self.step_size <= 0:
            raise ValueError("overlap_seconds must be smaller than chunk_seconds")
        self._buffer = deque[float]()
        self._buffer_start_time = 0.0
        self._next_chunk_start = 0.0
        self._initialized = False

    def push(
        self,
        samples: np.ndarray,
        stream_time_seconds: float | None = None,
        *,
        stream_time: float | None = None,
    ) -> list[AudioChunk]:
        if stream_time_seconds is None:
            if stream_time is None:
                raise TypeError("push() requires stream_time_seconds or stream_time")
            stream_time_seconds = stream_time

        if not self._initialized:
            self._buffer_start_time = stream_time_seconds - (len(samples) / self.sample_rate)
            self._next_chunk_start = self._buffer_start_time
            self._initialized = True

        self._buffer.extend(float(sample) for sample in samples)
        chunks: list[AudioChunk] = []
        while len(self._buffer) >= self.chunk_size:
            samples_out = np.fromiter(
                (self._buffer[index] for index in range(self.chunk_size)),
                dtype=np.float32,
                count=self.chunk_size,
            )
            chunk_start = self._next_chunk_start
            chunk_end = chunk_start + (self.chunk_size / self.sample_rate)
            chunks.append(AudioChunk(started_at=chunk_start, ended_at=chunk_end, samples=samples_out))
            for _ in range(self.step_size):
                self._buffer.popleft()
            self._buffer_start_time += self.step_size / self.sample_rate
            self._next_chunk_start += self.step_size / self.sample_rate
        return chunks


def chunk_segments(
    transcript: list[dict[str, object]],
    *,
    max_chars: int = 400,
    overlap: int = 0,
) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    current: list[dict[str, object]] = []
    current_len = 0
    carry: list[dict[str, object]] = []

    for segment in transcript:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        projected = current_len + len(text) + (1 if current else 0)
        if current and projected > max_chars:
            chunks.append(
                {
                    "text": " ".join(str(item["text"]).strip() for item in current).strip(),
                    "segments": list(current),
                }
            )
            carry = current[-overlap:] if overlap else []
            current = list(carry)
            current_len = sum(len(str(item["text"]).strip()) for item in current)
        current.append(segment)
        current_len += len(text) + (1 if current_len else 0)

    if current:
        chunks.append(
            {
                "text": " ".join(str(item["text"]).strip() for item in current).strip(),
                "segments": list(current),
            }
        )
    return chunks
