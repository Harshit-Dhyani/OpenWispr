"""Transcript stability tracking for live dictation.

Provides DraftUpdate dataclass and PartialStabilizer class for managing
text stability during real-time transcription. Tracks word stability
across revisions to determine when text can be committed as final.

The stabilizer uses a threshold-based approach: words must appear unchanged
in N consecutive recognition revisions before being promoted to committed
state. This prevents premature text commits during partial recognition
when the model is still resolving the final words of a phrase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class DraftUpdate:
    """Represents a text update with stability metadata.

    Attributes:
        stream_id: Unique identifier for the transcription stream.
        revision: Monotonically increasing revision number.
        committed_text: Text that has reached stability threshold and is final.
        draft_suffix: Unstable portion of text that may change in future revisions.
        text: Full text combining committed + draft.
        start: Start timestamp in seconds.
        end: End timestamp in seconds.
        stable_word_count: Number of words in committed_text.
    """

    stream_id: str
    revision: int
    committed_text: str
    draft_suffix: str
    text: str
    start: float
    end: float
    stable_word_count: int


def _normalize_words(text: str) -> list[str]:
    """Split text into non-empty word tokens.

    Args:
        text: Input text to tokenize.

    Returns:
        List of whitespace-separated tokens, empty list if text is empty.
    """
    return [token for token in (text or "").strip().split() if token]


def _join_words(words: list[str]) -> str:
    """Join word tokens back into a single string.

    Args:
        words: List of word tokens to join.

    Returns:
        Single string with tokens joined by single spaces, empty if input empty.
    """
    return " ".join(words).strip()


class PartialStabilizer:
    """Tracks text stability across transcription revisions.

    Maintains committed word state and determines when new words become
    stable enough to promote to committed status. Uses a hit-count threshold:
    a word must appear unchanged in N consecutive revisions to be committed.

    State owned:
        - _committed_words: Words that have reached stability threshold
        - _last_words: Words from the most recent revision
        - _candidate_words: Words currently being evaluated for stability
        - _candidate_hits: Consecutive revisions where candidate_words matched

    Lifecycle: Create one instance per transcription session.
    """

    def __init__(self, *, session_id: str, stability_threshold: int = 2) -> None:
        """Initialize the stabilizer for a session.

        Args:
            session_id: Unique identifier for this transcription session.
            stability_threshold: Revisions a word must survive unchanged (default: 2).
        """
        self.session_id = session_id
        self.stream_id = f"stream-{session_id}"
        self.stability_threshold = max(1, stability_threshold)
        self.reset()

    def reset(self) -> None:
        """Clear all state to initial values.

        Called during initialization and when a new transcription
        context begins (e.g., after a significant pause).
        """
        self.revision = 0
        self._committed_words: list[str] = []
        self._last_words: list[str] = []
        self._candidate_words: list[str] = []
        self._candidate_hits = 0

    def push(self, text: str, *, start: float, end: float) -> DraftUpdate:
        """Process a new partial transcription revision.

        Compares the new text against the previous revision to identify
        stable prefix words. Words that remain unchanged for
        stability_threshold consecutive revisions are promoted to committed.

        Args:
            text: Raw text from the current transcription revision.
            start: Start timestamp in seconds.
            end: End timestamp in seconds.

        Returns:
            DraftUpdate containing current committed state and draft suffix.
        """
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
        """Commit all text as final from a confirmed transcription.

        Called when a final transcript segment is received. Marks all
        words as committed immediately without threshold checking.

        Args:
            text: Final confirmed transcript text.
            start: Start timestamp in seconds.
            end: End timestamp in seconds.

        Returns:
            DraftUpdate with all text marked as committed.
        """
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
    """Construct a stream payload for WebSocket/SSE transmission.

    Args:
        session_id: Unique session identifier.
        segment_id: Unique segment identifier within the session.
        revision: Current revision number.
        stream_id: Stream identifier matching session.
        text: Full text content.
        start: Segment start timestamp.
        end: Segment end timestamp.
        committed_text: Text committed as stable.
        draft_suffix: Unstable draft portion.
        metrics: Optional diagnostic metrics dictionary.

    Returns:
        Dictionary payload suitable for JSON serialization.
    """
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
