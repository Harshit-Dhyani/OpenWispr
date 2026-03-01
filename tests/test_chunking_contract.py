from __future__ import annotations

from tests._contracts import chunk_text, filtered_call, instantiate, resolve_symbol


CHUNK_MODULES = [
    "app.audio.chunking",
    "app.audio.chunker",
    "app.audio.chunks",
    "app.core.chunking",
]

CHUNK_SYMBOLS = [
    "chunk_text",
    "chunk_segments",
    "build_chunks",
    "make_chunks",
    "Chunker",
]


def test_chunking_preserves_order_and_produces_multiple_chunks():
    target = resolve_symbol(CHUNK_MODULES, CHUNK_SYMBOLS)
    transcript = [
        {"start": 0.0, "end": 1.2, "text": "alpha one"},
        {"start": 1.2, "end": 2.4, "text": "bravo two"},
        {"start": 2.4, "end": 3.6, "text": "charlie three"},
        {"start": 3.6, "end": 4.8, "text": "delta four"},
    ]

    if isinstance(target, type):
        instance = instantiate(target, max_chars=22, chunk_size=22, overlap=0)
        runner = getattr(instance, "__call__", None)
        if runner is None:
            runner = getattr(instance, "chunk_segments", None) or getattr(
                instance, "chunk_text", None
            )
        chunks = filtered_call(
            runner,
            transcript,
            max_chars=22,
            chunk_size=22,
            overlap=0,
            segments=transcript,
            transcript=transcript,
        )
    else:
        chunks = filtered_call(
            target,
            transcript,
            max_chars=22,
            chunk_size=22,
            overlap=0,
            segments=transcript,
            transcript=transcript,
        )

    chunks = list(chunks)
    assert len(chunks) >= 2

    texts = [chunk_text(chunk) for chunk in chunks]
    assert all(text.strip() for text in texts)

    joined = " ".join(texts)
    assert joined.index("alpha") < joined.index("bravo") < joined.index("charlie") < joined.index("delta")
    assert "alpha one" in joined
    assert "delta four" in joined
