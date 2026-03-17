"""Session persistence for transcription output.

Provides SessionWriter class for writing session metadata, transcript segments,
notes, and derived outputs to disk. Thread-safe with lock protection for
append operations.

Outputs:
    - session.json: Session metadata and configuration
    - transcript.jsonl: JSON Lines format for transcript segments
    - transcript.txt: Human-readable timestamped transcript
    - notes.md: Session notes in Markdown format
    - highlights.txt: Extracted highlights
    - formulas.json: Detected formulas

Key collaborators: app.core.models (SessionState, TranscriptSegment, FormulaFinding).
Uses atomic write-through-temp-file pattern for crash safety.
"""


from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from app.core.models import FormulaFinding, SessionState, TranscriptSegment


class SessionWriter:
    """
    Manages session metadata, transcript segments, and audio data persistence.

    State owned: SessionState reference, output directory path, append lock for thread safety.

    Lifecycle: Created with optional SessionState; writes to disk on method calls.
    All file operations use atomic write-through-temp-file pattern for crash safety.

    Thread safety: Uses Lock for append operations (append_segment, append_note).
    Metadata and output writes are not locked as they overwrite existing files.
    """

    def __init__(self, session: SessionState | None = None, *, root: Path | None = None) -> None:
        self.session = session
        self.output_dir = (session.output_dir if session else root) if (session or root) else None
        self._append_lock = Lock()
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "logs").mkdir(exist_ok=True)

    def write_metadata(self) -> None:
        """Write session metadata to session.json if output_dir is configured."""
        if self.session is None or self.output_dir is None:
            return
        self._safe_write_json(self.output_dir / "session.json", self.session.to_metadata_dict())

    def append_segment(self, segment: TranscriptSegment) -> None:
        """
        Append transcript segment to transcript.jsonl and transcript.txt.

        Args:
            segment: TranscriptSegment to append.

        Raises:
            RuntimeError: If output_dir is not configured.
        """
        if self.output_dir is None:
            raise RuntimeError("SessionWriter output_dir is not configured")
        line = json.dumps(segment.to_dict(), ensure_ascii=False) + "\n"
        with self._append_lock:
            with (self.output_dir / "transcript.jsonl").open(
                "a", encoding="utf-8", newline="\n"
            ) as handle:
                handle.write(line)
                handle.flush()
            with (self.output_dir / "transcript.txt").open(
                "a", encoding="utf-8", newline="\n"
            ) as handle:
                handle.write(f"[{segment.start:.2f} - {segment.end:.2f}] {segment.display_text}\n")
                handle.flush()

    def write_outputs(
        self,
        *,
        notes_markdown: str,
        formulas: list[FormulaFinding],
        highlights_text: str,
    ) -> None:
        """
        Write session outputs: notes.md, highlights.txt, formulas.json.

        Args:
            notes_markdown: Markdown content for notes.
            formulas: List of FormulaFinding objects.
            highlights_text: Plain text highlights.

        Raises:
            RuntimeError: If output_dir is not configured.
        """
        if self.output_dir is None:
            raise RuntimeError("SessionWriter output_dir is not configured")
        self._safe_write_text(self.output_dir / "notes.md", notes_markdown)
        self._safe_write_text(self.output_dir / "highlights.txt", highlights_text)
        self._safe_write_json(
            self.output_dir / "formulas.json",
            [formula.to_dict() for formula in formulas],
        )

    def append_note(self, note: str) -> None:
        """
        Append note to notes.md.

        Args:
            note: Text to append.

        Raises:
            RuntimeError: If output_dir is not configured.
        """
        if self.output_dir is None:
            raise RuntimeError("SessionWriter output_dir is not configured")
        with self._append_lock:
            with (self.output_dir / "notes.md").open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(note)
                handle.flush()

    def write(
        self,
        payload: dict[str, Any] | None = None,
        /,
        *,
        session: dict[str, Any] | None = None,
        session_data: dict[str, Any] | None = None,
    ) -> Path:
        """
        Write arbitrary payload to session_payload.json.

        Args:
            payload: Positional dict to write.
            session: Alternative keyword dict to write.
            session_data: Alternative keyword dict to write.

        Returns:
            Path to the written payload file.

        Raises:
            RuntimeError: If output_dir is not configured.
        """
        if self.output_dir is None:
            raise RuntimeError("SessionWriter output_dir is not configured")
        material = payload or session or session_data or {}
        payload_path = self.output_dir / "session_payload.json"
        self._safe_write_json(payload_path, material)
        return payload_path

    def _safe_write_text(self, path: Path, content: str) -> None:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(content, encoding="utf-8", newline="\n")
        temp.replace(path)

    def _safe_write_json(self, path: Path, payload: object) -> None:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
