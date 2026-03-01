from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from app.core.models import FormulaFinding, SessionState, TranscriptSegment


class SessionWriter:
    def __init__(self, session: SessionState | None = None, *, root: Path | None = None) -> None:
        self.session = session
        self.output_dir = (session.output_dir if session else root) if (session or root) else None
        self._append_lock = Lock()
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "logs").mkdir(exist_ok=True)

    def write_metadata(self) -> None:
        if self.session is None or self.output_dir is None:
            return
        self._safe_write_json(self.output_dir / "session.json", self.session.to_metadata_dict())

    def append_segment(self, segment: TranscriptSegment) -> None:
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
        if self.output_dir is None:
            raise RuntimeError("SessionWriter output_dir is not configured")
        self._safe_write_text(self.output_dir / "notes.md", notes_markdown)
        self._safe_write_text(self.output_dir / "highlights.txt", highlights_text)
        self._safe_write_json(
            self.output_dir / "formulas.json",
            [formula.to_dict() for formula in formulas],
        )

    def append_note(self, note: str) -> None:
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
