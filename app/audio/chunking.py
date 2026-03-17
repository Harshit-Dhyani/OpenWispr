"""Transcript chunking utilities for audio processing pipelines.

Provides build_chunks function for splitting transcript segments into
smaller chunks suitable for downstream processing. Handles overflow
preservation via overlap parameter.

Used by audio pipelines to prepare transcript segments for coach/refiner
services or other text processing stages.
"""

from __future__ import annotations


def build_chunks(
    transcript: list[dict[str, object]],
    /,
    *,
    max_chars: int = 400,
    chunk_size: int | None = None,
    overlap: int = 0,
) -> list[dict[str, object]]:
    """Split transcript segments into character-bounded chunks.

    Accumulates transcript segments until the character limit is reached,
    then emits a chunk. Preserves segment references for downstream processing.

    Args:
        transcript: List of segment dicts with 'text' key containing transcript text.
        max_chars: Maximum characters per chunk (default 400).
        chunk_size: Override max_chars if provided.
        overlap: Number of segments to preserve at chunk boundary (default 0).

    Returns:
        List of chunk dicts with 'text' (joined string) and 'segments' (original segment refs).

    Example:
        >>> segments = [{"text": "Hello"}, {"text": "world"}, {"text": "test"}]
        >>> chunks = build_chunks(segments, max_chars=10, overlap=1)
        >>> # May produce: [{"text": "Hello world", "segments": [...]}]
    """
    limit = chunk_size or max_chars
    chunks: list[dict[str, object]] = []
    current: list[dict[str, object]] = []
    current_len = 0

    for segment in transcript:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        projected = current_len + len(text) + (1 if current else 0)
        if current and projected > limit:
            chunks.append(
                {
                    "text": " ".join(str(item["text"]).strip() for item in current).strip(),
                    "segments": list(current),
                }
            )
            current = list(current[-overlap:]) if overlap else []
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
