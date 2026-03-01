from app.stt.chunker import AudioChunk, RollingChunker, chunk_segments


class Chunker:
    def __init__(self, *, max_chars: int = 400, chunk_size: int | None = None, overlap: int = 0) -> None:
        self.max_chars = chunk_size or max_chars
        self.overlap = overlap

    def chunk_segments(self, segments):
        return chunk_segments(segments, max_chars=self.max_chars, overlap=self.overlap)

    def __call__(self, segments):
        return self.chunk_segments(segments)


build_chunks = chunk_segments

__all__ = ["AudioChunk", "RollingChunker", "Chunker", "build_chunks", "chunk_segments"]
