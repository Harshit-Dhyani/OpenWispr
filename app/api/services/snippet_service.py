from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from app.storage.history_db import HistoryDatabase


_ALLOWED_SCOPES = {"personal", "shared", "team"}


@dataclass(frozen=True)
class SnippetApplyResult:
    text: str
    applied: list[dict[str, Any]]


class SnippetService:
    def __init__(self, db: HistoryDatabase) -> None:
        self._db = db

    @staticmethod
    def _normalize_scope(scope: str | None) -> str:
        value = (scope or "personal").strip().lower()
        if value not in _ALLOWED_SCOPES:
            return "personal"
        return value

    @staticmethod
    def _normalize_trigger(trigger: str) -> str:
        return " ".join(trigger.strip().split()).lower()

    def list_entries(self, *, scope: str | None = None, search: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        filters: list[str] = []
        normalized_scope = self._normalize_scope(scope) if scope else None
        if normalized_scope:
            filters.append("scope = ?")
            params.append(normalized_scope)

        if search:
            token = f"%{search.strip()}%"
            filters.append("(trigger LIKE ? OR expansion LIKE ?)")
            params.extend([token, token])

        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self._db.query_all(
            f"""
            SELECT id, trigger, expansion, scope, enabled, usage_count, created_at, updated_at
            FROM snippets
            {where_sql}
            ORDER BY trigger COLLATE NOCASE ASC
            """,
            tuple(params),
        )
        for row in rows:
            row["enabled"] = bool(row["enabled"])
            row["usage_count"] = int(row["usage_count"] or 0)
        return rows

    def get_entry(self, snippet_id: str) -> dict[str, Any] | None:
        row = self._db.query_one(
            """
            SELECT id, trigger, expansion, scope, enabled, usage_count, created_at, updated_at
            FROM snippets
            WHERE id = ?
            """,
            (snippet_id,),
        )
        if row is None:
            return None
        row["enabled"] = bool(row["enabled"])
        row["usage_count"] = int(row["usage_count"] or 0)
        return row

    def create_entry(
        self,
        *,
        trigger: str,
        expansion: str,
        scope: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        normalized_trigger = self._normalize_trigger(trigger)
        if not normalized_trigger:
            raise ValueError("Snippet trigger cannot be empty")
        snippet_id = uuid.uuid4().hex
        normalized_scope = self._normalize_scope(scope)

        self._db.execute(
            """
            INSERT INTO snippets(
                id, trigger, trigger_normalized, expansion, scope, enabled, usage_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            """,
            (snippet_id, trigger.strip(), normalized_trigger, expansion, normalized_scope, 1 if enabled else 0),
        )
        created = self.get_entry(snippet_id)
        if created is None:
            raise RuntimeError("Failed to create snippet entry")
        return created

    def update_entry(self, snippet_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_entry(snippet_id)
        if existing is None:
            raise KeyError(snippet_id)

        trigger = str(updates.get("trigger", existing["trigger"]))
        expansion = str(updates.get("expansion", existing["expansion"]))
        scope = self._normalize_scope(str(updates.get("scope", existing["scope"])))
        enabled = bool(updates.get("enabled", existing["enabled"]))
        normalized_trigger = self._normalize_trigger(trigger)
        if not normalized_trigger:
            raise ValueError("Snippet trigger cannot be empty")

        self._db.execute(
            """
            UPDATE snippets
            SET trigger = ?,
                trigger_normalized = ?,
                expansion = ?,
                scope = ?,
                enabled = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (trigger.strip(), normalized_trigger, expansion, scope, 1 if enabled else 0, snippet_id),
        )
        updated = self.get_entry(snippet_id)
        if updated is None:
            raise RuntimeError("Failed to update snippet entry")
        return updated

    def delete_entry(self, snippet_id: str) -> bool:
        cursor = self._db.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
        return bool(cursor.rowcount)

    def expand_text(self, text: str, *, commit_usage: bool = False) -> SnippetApplyResult:
        if not text:
            return SnippetApplyResult(text=text, applied=[])

        rows = self._db.query_all(
            """
            SELECT id, trigger, expansion
            FROM snippets
            WHERE enabled = 1
            ORDER BY LENGTH(trigger) DESC, trigger COLLATE NOCASE ASC
            """
        )
        if not rows:
            return SnippetApplyResult(text=text, applied=[])

        output = text
        applied: list[dict[str, Any]] = []

        for row in rows:
            trigger = str(row["trigger"])
            pattern = re.compile(rf"(?<!\w){re.escape(trigger)}(?!\w)", flags=re.IGNORECASE)
            output, count = pattern.subn(str(row["expansion"]), output)
            if count:
                applied.append(
                    {
                        "snippet_id": row["id"],
                        "trigger": trigger,
                        "expansion": row["expansion"],
                        "count": count,
                    }
                )
                if commit_usage:
                    self._db.execute(
                        "UPDATE snippets SET usage_count = usage_count + ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
                        (count, row["id"]),
                    )

        return SnippetApplyResult(text=output, applied=applied)

    def preview_expand(self, text: str) -> dict[str, Any]:
        result = self.expand_text(text, commit_usage=False)
        return {
            "input_text": text,
            "output_text": result.text,
            "applied": result.applied,
        }

    def import_entries(self, payload: list[dict[str, Any]], *, replace_existing: bool = False) -> dict[str, int]:
        inserted = 0
        updated = 0

        for item in payload:
            trigger = str(item.get("trigger", "")).strip()
            expansion = str(item.get("expansion", ""))
            if not trigger:
                continue
            scope = self._normalize_scope(str(item.get("scope", "personal")))
            enabled = bool(item.get("enabled", True))

            existing = self._db.query_one(
                "SELECT id FROM snippets WHERE trigger_normalized = ? AND scope = ?",
                (self._normalize_trigger(trigger), scope),
            )
            if existing and replace_existing:
                self.update_entry(
                    existing["id"],
                    {
                        "trigger": trigger,
                        "expansion": expansion,
                        "scope": scope,
                        "enabled": enabled,
                    },
                )
                updated += 1
            elif not existing:
                self.create_entry(
                    trigger=trigger,
                    expansion=expansion,
                    scope=scope,
                    enabled=enabled,
                )
                inserted += 1

        return {"inserted": inserted, "updated": updated}

    def export_entries(self) -> str:
        entries = self.list_entries()
        return json.dumps(entries, ensure_ascii=False, indent=2)
