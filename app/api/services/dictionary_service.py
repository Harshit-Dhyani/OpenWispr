"""Dictionary service for phrase-to-replacement text transformations.

Provides DictionaryService for managing user-defined phrase replacements
with scope support (personal/shared/team). Supports CRUD operations,
text application with usage tracking, and cache management.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.storage.history_db import HistoryDatabase

_ALLOWED_SCOPES = {"personal", "shared", "team"}

# In-memory cache for dictionary entries
_dictionary_cache: dict[str, tuple[list[dict], float]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL_SECONDS = 30.0  # Cache entries for 30 seconds


@dataclass(frozen=True)
class DictionaryApplyResult:
    text: str
    applied: list[dict[str, Any]]


def _get_cached_entries(db: HistoryDatabase, scope: str | None = None) -> list[dict[str, Any]]:
    """Get dictionary entries with caching."""
    cache_key = f"dict:{scope or 'all'}"
    current_time = time.time()

    with _cache_lock:
        if cache_key in _dictionary_cache:
            entries, cache_time = _dictionary_cache[cache_key]
            if current_time - cache_time < _CACHE_TTL_SECONDS:
                return entries

    # Cache miss - load from DB
    params: list[Any] = []
    filters: list[str] = []

    normalized_scope = scope.strip().lower() if scope else None
    if normalized_scope and normalized_scope in _ALLOWED_SCOPES:
        filters.append("scope = ?")
        params.append(normalized_scope)

    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db.query_all(
        f"""
        SELECT id, phrase, replacement, scope, enabled, usage_count, created_at, updated_at
        FROM dictionary_entries
        {where_sql}
        ORDER BY phrase COLLATE NOCASE ASC
        """,
        tuple(params),
    )
    for row in rows:
        row["enabled"] = bool(row["enabled"])
        row["usage_count"] = int(row["usage_count"] or 0)

    # Update cache
    with _cache_lock:
        _dictionary_cache[cache_key] = (rows, current_time)

    return rows


def invalidate_dictionary_cache() -> None:
    """Clear the dictionary cache."""
    with _cache_lock:
        _dictionary_cache.clear()


class DictionaryService:
    """Service for managing phrase-to-replacement dictionary entries.

    Provides CRUD operations for user-defined phrase replacements with scope
    support (personal/shared/team). Supports text application with usage tracking
    and cache management for performance.

    Key collaborators: HistoryDatabase for persistence.
    """

    def __init__(self, db: HistoryDatabase) -> None:
        self._db = db

    @staticmethod
    def _normalize_scope(scope: str | None) -> str:
        value = (scope or "personal").strip().lower()
        if value not in _ALLOWED_SCOPES:
            return "personal"
        return value

    @staticmethod
    def _normalize_phrase(phrase: str) -> str:
        return " ".join(phrase.strip().split()).lower()

    def list_entries(
        self, *, scope: str | None = None, search: str | None = None
    ) -> list[dict[str, Any]]:
        """List dictionary entries with optional scope filtering and search.

        Args:
            scope: Filter by scope (personal, shared, team)
            search: Search term for phrase or replacement

        Returns:
            List of dictionary entry records
        """
        params: list[Any] = []
        filters: list[str] = []

        normalized_scope = self._normalize_scope(scope) if scope else None
        if normalized_scope:
            filters.append("scope = ?")
            params.append(normalized_scope)

        if search:
            filters.append("(phrase LIKE ? OR replacement LIKE ?)")
            token = f"%{search.strip()}%"
            params.extend([token, token])

        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self._db.query_all(
            f"""
            SELECT id, phrase, replacement, scope, enabled, usage_count, created_at, updated_at
            FROM dictionary_entries
            {where_sql}
            ORDER BY phrase COLLATE NOCASE ASC
            """,
            tuple(params),
        )
        for row in rows:
            row["enabled"] = bool(row["enabled"])
            row["usage_count"] = int(row["usage_count"] or 0)
        return rows

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        """Get a dictionary entry by ID.

        Returns:
            Entry dict if found, None otherwise.
        """
        row = self._db.query_one(
            """
            SELECT id, phrase, replacement, scope, enabled, usage_count, created_at, updated_at
            FROM dictionary_entries
            WHERE id = ?
            """,
            (entry_id,),
        )
        if row is None:
            return None
        row["enabled"] = bool(row["enabled"])
        row["usage_count"] = int(row["usage_count"] or 0)
        return row

    def create_entry(
        self,
        *,
        phrase: str,
        replacement: str,
        scope: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Create a new dictionary entry.

        Args:
            phrase: The phrase to replace
            replacement: The replacement text
            scope: Scope (personal, shared, team)
            enabled: Whether entry is enabled

        Returns:
            The created entry record

        Raises:
            ValueError: If phrase is empty
        """
        normalized_phrase = self._normalize_phrase(phrase)
        if not normalized_phrase:
            raise ValueError("Dictionary phrase cannot be empty")
        entry_id = uuid.uuid4().hex
        normalized_scope = self._normalize_scope(scope)

        self._db.execute(
            """
            INSERT INTO dictionary_entries(
                id, phrase, phrase_normalized, replacement, scope, enabled, usage_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            """,
            (
                entry_id,
                phrase.strip(),
                normalized_phrase,
                replacement,
                normalized_scope,
                1 if enabled else 0,
            ),
        )
        created = self.get_entry(entry_id)
        if created is None:
            raise RuntimeError("Failed to create dictionary entry")
        return created

    def update_entry(self, entry_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update an existing dictionary entry.

        Args:
            entry_id: ID of entry to update
            updates: Dict with fields to update (phrase, replacement, scope, enabled)

        Returns:
            The updated entry record

        Raises:
            KeyError: If entry not found
            ValueError: If phrase is empty
        """
        existing = self.get_entry(entry_id)
        if existing is None:
            raise KeyError(entry_id)

        phrase = str(updates.get("phrase", existing["phrase"]))
        replacement = str(updates.get("replacement", existing["replacement"]))
        scope = self._normalize_scope(str(updates.get("scope", existing["scope"])))
        enabled = bool(updates.get("enabled", existing["enabled"]))
        normalized_phrase = self._normalize_phrase(phrase)
        if not normalized_phrase:
            raise ValueError("Dictionary phrase cannot be empty")

        self._db.execute(
            """
            UPDATE dictionary_entries
            SET phrase = ?,
                phrase_normalized = ?,
                replacement = ?,
                scope = ?,
                enabled = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (phrase.strip(), normalized_phrase, replacement, scope, 1 if enabled else 0, entry_id),
        )
        updated = self.get_entry(entry_id)
        if updated is None:
            raise RuntimeError("Failed to update dictionary entry")
        return updated

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a dictionary entry.

        Returns:
            True if entry was deleted, False if not found.
        """
        cursor = self._db.execute("DELETE FROM dictionary_entries WHERE id = ?", (entry_id,))
        return bool(cursor.rowcount)

    def apply_to_text(self, text: str, *, commit_usage: bool = False) -> DictionaryApplyResult:
        """Apply dictionary replacements to text.

        Replaces phrases with their configured replacements using word-boundary
        matching. Longer phrases are matched first to prevent partial replacements.

        Args:
            text: Input text to transform
            commit_usage: Whether to increment usage counts

        Returns:
            DictionaryApplyResult with transformed text and list of applied replacements
        """
        if not text:
            return DictionaryApplyResult(text=text, applied=[])

        rows = self._db.query_all(
            """
            SELECT id, phrase, replacement
            FROM dictionary_entries
            WHERE enabled = 1
            ORDER BY LENGTH(phrase) DESC, phrase COLLATE NOCASE ASC
            """
        )
        if not rows:
            return DictionaryApplyResult(text=text, applied=[])

        updated_text = text
        applied: list[dict[str, Any]] = []

        for row in rows:
            phrase = str(row["phrase"])
            replacement = str(row["replacement"])
            pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", flags=re.IGNORECASE)
            updated_text, count = pattern.subn(replacement, updated_text)
            if count:
                applied.append(
                    {
                        "entry_id": row["id"],
                        "phrase": phrase,
                        "replacement": replacement,
                        "count": count,
                    }
                )
                if commit_usage:
                    self._db.execute(
                        "UPDATE dictionary_entries SET usage_count = usage_count + ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
                        (count, row["id"]),
                    )

        return DictionaryApplyResult(text=updated_text, applied=applied)

    def preview_apply(self, text: str) -> dict[str, Any]:
        result = self.apply_to_text(text, commit_usage=False)
        return {
            "input_text": text,
            "output_text": result.text,
            "applied": result.applied,
        }
