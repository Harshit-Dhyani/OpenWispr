from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class DraftUpdate:
    stream_id: str
    revision: int
    committed_text: str
    draft_suffix: str
    text: str
    start: float
    end: float
    stable_word_count: int


def _normalize_words(text: str) -> list[str]:
    return [token for token in (text or "").strip().split() if token]


def _join_words(words: list[str]) -> str:
    return " ".join(words).strip()


class PartialStabilizer:
    def __init__(self, *, session_id: str, stability_threshold: int = 2) -> None:
        self.session_id = session_id
        self.stream_id = f"stream-{session_id}"
        self.stability_threshold = max(1, stability_threshold)
        self.reset()

    def reset(self) -> None:
        self.revision = 0
        self._committed_words: list[str] = []
        self._last_words: list[str] = []
        self._candidate_words: list[str] = []
        self._candidate_hits = 0

    def push(self, text: str, *, start: float, end: float) -> DraftUpdate:
        words = _normalize_words(text)
        common_count = 0
        for previous, current in zip(self._last_words, words):
            if previous != current:
                break
            common_count += 1

        committed_count = len(self._committed_words)
        candidate_count = max(common_count, committed_count)
        candidate_words = words[:candidate_count]

        if candidate_words == self._candidate_words:
            self._candidate_hits += 1
        else:
            self._candidate_words = candidate_words
            self._candidate_hits = 1

        if candidate_count > committed_count and self._candidate_hits >= self.stability_threshold:
            self._committed_words = candidate_words

        self._last_words = words
        self.revision += 1

        committed_text = _join_words(self._committed_words)
        draft_suffix = _join_words(words[len(self._committed_words) :])

        return DraftUpdate(
            stream_id=self.stream_id,
            revision=self.revision,
            committed_text=committed_text,
            draft_suffix=draft_suffix,
            text=_join_words(words),
            start=start,
            end=end,
            stable_word_count=len(self._committed_words),
        )

    def consume_final_text(self, text: str, *, start: float, end: float) -> DraftUpdate:
        words = _normalize_words(text)
        self._committed_words = words
        self._last_words = words
        self._candidate_words = words
        self._candidate_hits = self.stability_threshold
        self.revision += 1
        return DraftUpdate(
            stream_id=self.stream_id,
            revision=self.revision,
            committed_text=_join_words(words),
            draft_suffix="",
            text=_join_words(words),
            start=start,
            end=end,
            stable_word_count=len(words),
        )


def build_stream_payload(
    *,
    session_id: str,
    segment_id: str,
    revision: int,
    stream_id: str,
    text: str,
    start: float,
    end: float,
    committed_text: str = "",
    draft_suffix: str = "",
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "segment_id": segment_id,
        "revision": revision,
        "stream_id": stream_id,
        "text": text,
        "start": start,
        "end": end,
        "committed_text": committed_text,
        "draft_suffix": draft_suffix,
        "metrics": metrics or {},
    }
