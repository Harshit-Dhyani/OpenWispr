from __future__ import annotations


def build_chunks(
    transcript: list[dict[str, object]],
    /,
    *,
    max_chars: int = 400,
    chunk_size: int | None = None,
    overlap: int = 0,
) -> list[dict[str, object]]:
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
