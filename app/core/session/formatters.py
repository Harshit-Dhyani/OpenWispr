"""Session export formatters for system audio capture."""

from __future__ import annotations

from datetime import timedelta
from enum import Enum


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
        minutes, seconds = divmod(remainder, 60)
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
        """Format entire transcript as SRT."""
        output = []
        for i, seg in enumerate(segments, 1):
            output.append(SrtFormatter.format_segment(seg, i))
        return "\n".join(output)


class MarkdownFormatter:
    """Formatter for Markdown export."""

    @staticmethod
    def format_time(seconds: float) -> str:
        """Convert seconds to readable timestamp."""
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
        """Format entire transcript as Markdown."""
        lines = [f"# {title}\n"]
        for seg in segments:
            if include_timestamps:
                lines.append(MarkdownFormatter.format_segment(seg))
            else:
                lines.append(seg.get("text", "").strip())
        return "\n".join(lines)
