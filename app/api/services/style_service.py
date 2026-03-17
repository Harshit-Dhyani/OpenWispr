"""Style service for text style profile management and application.

Provides StyleService for managing text style profiles (formal, casual, etc.)
with configurable rules for capitalization and punctuation. Supports profile
assignments to contexts (personal, work, email) and style application to text.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from app.storage.history_db import HistoryDatabase

STYLE_CONTEXTS = ("personal", "work", "email", "other")


@dataclass(frozen=True)
class StyleApplyResult:
    text: str
    profile: dict[str, Any] | None


class StyleService:
    """Text style profile management service.

    Manages style profiles for text transformation with configurable rules
    for capitalization and punctuation. Provides profile CRUD operations,
    context assignments (personal, work, email), and style application.

    State ownership:
    - Owns profile and assignment state in the database
    - Seed profiles (formal, casual, very_casual) created on init
    - Thread-safe via database transaction locking

    Dependencies:
    - HistoryDatabase for persistence
    """

    def __init__(self, db: HistoryDatabase) -> None:
        self._db = db
        self._ensure_seed_profiles()

    def _ensure_seed_profiles(self) -> None:
        profiles = [
            {
                "id": "formal",
                "name": "Formal",
                "style_key": "formal",
                "description": "Caps + punctuation for polished communication.",
                "rules_json": json.dumps({"caps": "sentence", "punctuation": "strong"}),
                "built_in": 1,
            },
            {
                "id": "casual",
                "name": "Casual",
                "style_key": "casual",
                "description": "Relaxed sentence casing with light punctuation.",
                "rules_json": json.dumps({"caps": "sentence", "punctuation": "light"}),
                "built_in": 1,
            },
            {
                "id": "very_casual",
                "name": "very casual",
                "style_key": "very_casual",
                "description": "No caps + less punctuation.",
                "rules_json": json.dumps({"caps": "none", "punctuation": "minimal"}),
                "built_in": 1,
            },
        ]
        for profile in profiles:
            self._db.execute(
                """
                INSERT INTO style_profiles(id, name, style_key, description, rules_json, enabled, built_in, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    profile["id"],
                    profile["name"],
                    profile["style_key"],
                    profile["description"],
                    profile["rules_json"],
                    profile["built_in"],
                ),
            )

        defaults = {
            "personal": "casual",
            "work": "formal",
            "email": "formal",
            "other": "casual",
        }
        for context, profile_id in defaults.items():
            self._db.execute(
                """
                INSERT INTO style_profile_assignments(context, profile_id, updated_at)
                VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                ON CONFLICT(context) DO NOTHING
                """,
                (context, profile_id),
            )

    def list_profiles(self) -> list[dict[str, Any]]:
        rows = self._db.query_all(
            """
            SELECT id, name, style_key, description, rules_json, enabled, built_in, created_at, updated_at
            FROM style_profiles
            ORDER BY built_in DESC, name COLLATE NOCASE ASC
            """
        )
        for row in rows:
            row["enabled"] = bool(row["enabled"])
            row["built_in"] = bool(row["built_in"])
            row["rules"] = json.loads(row.get("rules_json") or "{}")
            row.pop("rules_json", None)
        return rows

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        row = self._db.query_one(
            """
            SELECT id, name, style_key, description, rules_json, enabled, built_in, created_at, updated_at
            FROM style_profiles
            WHERE id = ?
            """,
            (profile_id,),
        )
        if row is None:
            return None
        row["enabled"] = bool(row["enabled"])
        row["built_in"] = bool(row["built_in"])
        row["rules"] = json.loads(row.get("rules_json") or "{}")
        row.pop("rules_json", None)
        return row

    def create_profile(
        self,
        *,
        name: str,
        style_key: str,
        description: str,
        rules: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        profile_id = uuid.uuid4().hex
        self._db.execute(
            """
            INSERT INTO style_profiles(id, name, style_key, description, rules_json, enabled, built_in, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            """,
            (
                profile_id,
                name.strip(),
                style_key.strip(),
                description,
                json.dumps(rules or {}),
                1 if enabled else 0,
            ),
        )
        created = self.get_profile(profile_id)
        if created is None:
            raise RuntimeError("Failed to create style profile")
        return created

    def update_profile(self, profile_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_profile(profile_id)
        if existing is None:
            raise KeyError(profile_id)

        self._db.execute(
            """
            UPDATE style_profiles
            SET name = ?,
                style_key = ?,
                description = ?,
                rules_json = ?,
                enabled = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (
                str(updates.get("name", existing["name"])).strip(),
                str(updates.get("style_key", existing["style_key"])).strip(),
                str(updates.get("description", existing["description"])),
                json.dumps(updates.get("rules", existing.get("rules", {}))),
                1 if bool(updates.get("enabled", existing["enabled"])) else 0,
                profile_id,
            ),
        )
        updated = self.get_profile(profile_id)
        if updated is None:
            raise RuntimeError("Failed to update style profile")
        return updated

    def delete_profile(self, profile_id: str) -> bool:
        row = self.get_profile(profile_id)
        if row is None:
            return False
        if row.get("built_in"):
            raise ValueError("Built-in style profiles cannot be deleted")

        cursor = self._db.execute("DELETE FROM style_profiles WHERE id = ?", (profile_id,))
        return bool(cursor.rowcount)

    def list_assignments(self) -> dict[str, str]:
        rows = self._db.query_all(
            "SELECT context, profile_id FROM style_profile_assignments ORDER BY context ASC"
        )
        return {str(row["context"]): str(row["profile_id"]) for row in rows}

    def set_assignment(self, context: str, profile_id: str) -> dict[str, str]:
        normalized_context = context.strip().lower()
        if normalized_context not in STYLE_CONTEXTS:
            raise ValueError("Invalid style context")
        if self.get_profile(profile_id) is None:
            raise KeyError(profile_id)

        self._db.execute(
            """
            INSERT INTO style_profile_assignments(context, profile_id, updated_at)
            VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            ON CONFLICT(context) DO UPDATE SET
                profile_id = excluded.profile_id,
                updated_at = excluded.updated_at
            """,
            (normalized_context, profile_id),
        )
        return self.list_assignments()

    def resolve_profile(
        self, *, context: str = "other", profile_id: str | None = None
    ) -> dict[str, Any] | None:
        if profile_id:
            return self.get_profile(profile_id)

        normalized_context = context.strip().lower()
        if normalized_context not in STYLE_CONTEXTS:
            normalized_context = "other"

        assignment = self._db.query_one(
            "SELECT profile_id FROM style_profile_assignments WHERE context = ?",
            (normalized_context,),
        )
        if assignment is None:
            return None
        return self.get_profile(str(assignment["profile_id"]))

    def apply_style(
        self,
        text: str,
        *,
        context: str = "other",
        profile_id: str | None = None,
    ) -> StyleApplyResult:
        profile = self.resolve_profile(context=context, profile_id=profile_id)
        if not text or not profile or not profile.get("enabled", True):
            return StyleApplyResult(text=text, profile=profile)

        style_key = str(profile.get("style_key", "")).strip().lower()
        if style_key == "formal":
            transformed = self._apply_formal(text)
        elif style_key == "very_casual":
            transformed = self._apply_very_casual(text)
        else:
            transformed = self._apply_casual(text)

        return StyleApplyResult(text=transformed, profile=profile)

    def preview(
        self, text: str, *, context: str = "other", profile_id: str | None = None
    ) -> dict[str, Any]:
        result = self.apply_style(text, context=context, profile_id=profile_id)
        return {
            "input_text": text,
            "output_text": result.text,
            "profile": result.profile,
        }

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _apply_formal(self, text: str) -> str:
        normalized = self._normalize_whitespace(text)
        if not normalized:
            return normalized
        normalized = normalized[0].upper() + normalized[1:]
        if normalized[-1] not in {".", "!", "?"}:
            normalized += "."
        return normalized

    def _apply_casual(self, text: str) -> str:
        normalized = self._normalize_whitespace(text)
        if not normalized:
            return normalized
        return normalized[0].upper() + normalized[1:]

    def _apply_very_casual(self, text: str) -> str:
        normalized = self._normalize_whitespace(text).lower()
        return re.sub(r"[.!]+$", "", normalized)
