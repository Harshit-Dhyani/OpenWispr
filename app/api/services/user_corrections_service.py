"""User corrections service for learning from manual transcription edits.

This module provides:
- Recording of user corrections to the database
- Automatic application of learned corrections to future transcripts
- Usage statistics tracking for corrections
- Import/export of corrections as JSON

The service enables the system to learn from user feedback and improve
transcription accuracy over time.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from app.storage.history_db import HistoryDatabase

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorrectionRecord:
    """Record of a user correction."""

    id: str
    original_text: str
    corrected_text: str
    context: str | None
    correction_type: str
    confidence: float | None
    apply_count: int
    last_applied_at: str | None
    created_at: str
    updated_at: str


class UserCorrectionsService:
    """Service for managing user corrections and learning from them.

    This service tracks user corrections and applies them automatically
    in future transcriptions. Corrections can be:
    - manual: User explicitly corrected the text
    - learned: System learned from repeated patterns
    - dictionary: From dictionary entries
    - snippet: From snippet expansions
    """

    def __init__(self, db: HistoryDatabase) -> None:
        self._db = db

    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        """Normalize text for matching (lowercase, trimmed)."""
        return " ".join(text.lower().strip().split())

    def record_correction(
        self,
        original_text: str,
        corrected_text: str,
        *,
        context: str | None = None,
        correction_type: str = "manual",
        confidence: float | None = None,
    ) -> CorrectionRecord:
        """Record a user correction.

        Args:
            original_text: The original (incorrect) text
            corrected_text: The corrected text
            context: Optional context (e.g., "code", "email")
            correction_type: Type of correction ("manual", "learned", "dictionary", "snippet")
            confidence: Confidence score if applicable

        Returns:
            The created correction record
        """
        if not original_text or not corrected_text:
            raise ValueError("original_text and corrected_text cannot be empty")

        original_normalized = self._normalize_for_matching(original_text)

        # Check if correction already exists
        existing = self._db.query_one(
            """
            SELECT id FROM user_corrections
            WHERE original_text = ? AND corrected_text = ?
            """,
            (original_normalized, corrected_text),
        )

        if existing:
            # Update existing correction
            self._db.execute(
                """
                UPDATE user_corrections
                SET apply_count = apply_count + 1,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (existing["id"],),
            )
            return self.get_correction(existing["id"])

        correction_id = uuid.uuid4().hex
        self._db.execute(
            """
            INSERT INTO user_corrections(
                id, original_text, corrected_text, context, correction_type,
                confidence, apply_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1,
                strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            """,
            (
                correction_id,
                original_normalized,
                corrected_text,
                context,
                correction_type,
                confidence,
            ),
        )

        logger.info(
            "Recorded correction: %r -> %r (type: %s)",
            original_text,
            corrected_text,
            correction_type,
        )

        return self.get_correction(correction_id)

    def get_correction(self, correction_id: str) -> CorrectionRecord | None:
        """Get a correction by ID.

        Returns:
            CorrectionRecord if found, None otherwise.
        """
        row = self._db.query_one(
            """
            SELECT id, original_text, corrected_text, context, correction_type,
                   confidence, apply_count, last_applied_at, created_at, updated_at
            FROM user_corrections
            WHERE id = ?
            """,
            (correction_id,),
        )

        if not row:
            return None

        return CorrectionRecord(
            id=row["id"],
            original_text=row["original_text"],
            corrected_text=row["corrected_text"],
            context=row["context"],
            correction_type=row["correction_type"],
            confidence=row["confidence"],
            apply_count=int(row["apply_count"] or 0),
            last_applied_at=row["last_applied_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def apply_corrections(
        self,
        text: str,
        *,
        context: str | None = None,
        commit_usage: bool = False,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Apply user corrections to text.

        Args:
            text: Input text to correct
            context: Optional context for context-aware corrections
            commit_usage: Whether to update usage stats

        Returns:
            Tuple of (corrected_text, list of applied corrections)
        """
        if not text:
            return text, []

        # Get all enabled corrections, ordered by length (longest first)
        rows = self._db.query_all(
            """
            SELECT id, original_text, corrected_text, context, apply_count
            FROM user_corrections
            ORDER BY LENGTH(original_text) DESC, apply_count DESC
            """
        )

        if not rows:
            return text, []

        corrected = text
        applied: list[dict[str, Any]] = []

        for row in rows:
            original = row["original_text"]
            replacement = row["corrected_text"]

            # Match with word boundaries
            pattern = re.compile(rf"(?<!\w){re.escape(original)}(?!\w)", re.IGNORECASE)

            if pattern.search(corrected):
                corrected = pattern.sub(replacement, corrected)
                applied.append(
                    {
                        "correction_id": row["id"],
                        "original": original,
                        "corrected": replacement,
                        "context": row["context"],
                    }
                )

                if commit_usage:
                    self._db.execute(
                        """
                        UPDATE user_corrections
                        SET apply_count = apply_count + 1,
                            last_applied_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                        WHERE id = ?
                        """,
                        (row["id"],),
                    )

        return corrected, applied

    def list_corrections(
        self,
        *,
        search: str | None = None,
        correction_type: str | None = None,
        limit: int = 100,
    ) -> list[CorrectionRecord]:
        """List user corrections with optional filtering."""
        params: list[Any] = []
        filters: list[str] = []

        if search:
            filters.append("(original_text LIKE ? OR corrected_text LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        if correction_type:
            filters.append("correction_type = ?")
            params.append(correction_type)

        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        rows = self._db.query_all(
            f"""
            SELECT id, original_text, corrected_text, context, correction_type,
                   confidence, apply_count, last_applied_at, created_at, updated_at
            FROM user_corrections
            {where_sql}
            ORDER BY apply_count DESC, updated_at DESC
            LIMIT ?
            """,
            tuple(params),
        )

        return [
            CorrectionRecord(
                id=row["id"],
                original_text=row["original_text"],
                corrected_text=row["corrected_text"],
                context=row["context"],
                correction_type=row["correction_type"],
                confidence=row["confidence"],
                apply_count=int(row["apply_count"] or 0),
                last_applied_at=row["last_applied_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def delete_correction(self, correction_id: str) -> bool:
        """Delete a correction."""
        cursor = self._db.execute(
            "DELETE FROM user_corrections WHERE id = ?",
            (correction_id,),
        )
        return bool(cursor.rowcount)

    def clear_all_corrections(self) -> int:
        """Clear all learned corrections (manual only)."""
        cursor = self._db.execute("DELETE FROM user_corrections WHERE correction_type = 'manual'")
        return cursor.rowcount

    def export_corrections(self) -> str:
        """Export corrections as JSON."""
        import json

        corrections = self.list_corrections(limit=10000)
        return json.dumps(
            [
                {
                    "original": c.original_text,
                    "corrected": c.corrected_text,
                    "context": c.context,
                    "apply_count": c.apply_count,
                }
                for c in corrections
            ],
            ensure_ascii=False,
            indent=2,
        )

    def import_corrections(self, json_data: str) -> dict[str, int]:
        """Import corrections from JSON."""
        import json

        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        inserted = 0
        for item in data:
            original = item.get("original", "").strip()
            corrected = item.get("corrected", "").strip()
            context = item.get("context")

            if not original or not corrected:
                continue

            try:
                self.record_correction(
                    original_text=original,
                    corrected_text=corrected,
                    context=context,
                    correction_type="learned",
                )
                inserted += 1
            except Exception as e:
                logger.warning("Failed to import correction: %s", e)

        return {"inserted": inserted}
