"""Session export formatters for system audio capture."""

from __future__ import annotations

from datetime import timedelta
from enum import Enum
from io import StringIO


class ExportFormat(Enum):
    """Supported export formats."""

    TXT = "txt"
    JSON = "json"
    SRT = "srt"
    MD = "md"

    @classmethod
    def from_string(cls, value: str) -> ExportFormat:
        """Convert string to ExportFormat enum."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Unknown export format: {value}")


class SrtFormatter:
    """Formatter for SRT subtitle export."""

    @staticmethod
    def format_time(seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
        td = timedelta(seconds=seconds)
        hours, remainder = divmod(td.seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        milliseconds = int(td.microseconds / 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    @staticmethod
    def format_segment(segment: dict, index: int) -> str:
        """Format a single segment as SRT."""
        start = SrtFormatter.format_time(segment.get("start", 0))
        end = SrtFormatter.format_time(segment.get("end", 0))
        text = segment.get("text", "").strip()
        return f"{index}\n{start} --> {end}\n{text}\n"

    @staticmethod
    def format_transcript(segments: list[dict]) -> str:
        """Format entire transcript as SRT using efficient string building."""
        if not segments:
            return ""
        buf = StringIO()
        for i, seg in enumerate(segments, 1):
            start = SrtFormatter.format_time(seg.get("start", 0))
            end = SrtFormatter.format_time(seg.get("end", 0))
            text = seg.get("text", "").strip()
            buf.write(str(i))
            buf.write("\n")
            buf.write(start)
            buf.write(" --> ")
            buf.write(end)
            buf.write("\n")
            buf.write(text)
            buf.write("\n\n")
        return buf.getvalue()


class MarkdownFormatter:
    """Formatter for Markdown export."""

    @staticmethod
    def format_time(seconds: float) -> str:
        """Format seconds as readable timestamp."""
        mins, secs = divmod(int(seconds), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"

    @staticmethod
    def format_segment(segment: dict) -> str:
        """Format a single segment as Markdown."""
        start = MarkdownFormatter.format_time(segment.get("start", 0))
        text = segment.get("text", "").strip()
        return f"[{start}] {text}"

    @staticmethod
    def format_transcript(
        segments: list[dict],
        title: str = "Transcript",
        include_timestamps: bool = True,
    ) -> str:
        """Format entire transcript as Markdown using efficient string building."""
        buf = StringIO()
        buf.write("# ")
        buf.write(title)
        buf.write("\n\n")

        if include_timestamps:
            for seg in segments:
                buf.write("[")
                buf.write(MarkdownFormatter.format_time(seg.get("start", 0)))
                buf.write("] ")
                buf.write(seg.get("text", "").strip())
                buf.write("\n")
        else:
            for seg in segments:
                buf.write(seg.get("text", "").strip())
                buf.write("\n")

        return buf.getvalue()
