from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def _create_v1_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS transcript_sessions (
            session_id TEXT PRIMARY KEY,
            source_workflow TEXT NOT NULL,
            capture_source TEXT NOT NULL,
            title TEXT,
            transcription_mode TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            model_name TEXT,
            model_id TEXT,
            language_mode TEXT,
            execution_mode TEXT,
            device_id TEXT,
            status TEXT NOT NULL DEFAULT 'completed',
            raw_text TEXT,
            aggregated_clean_text TEXT,
            postprocessed_text TEXT,
            coach_polished_text TEXT,
            active_text TEXT,
            active_text_source TEXT,
            audio_path TEXT,
            session_artifacts_path TEXT,
            settings_snapshot_json TEXT,
            retry_status TEXT NOT NULL DEFAULT 'idle',
            retry_error TEXT,
            retry_attempt_count INTEGER NOT NULL DEFAULT 0,
            deleted_at TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_transcript_sessions_started_at
            ON transcript_sessions(started_at DESC);
        CREATE INDEX IF NOT EXISTS idx_transcript_sessions_deleted_at
            ON transcript_sessions(deleted_at);
        CREATE INDEX IF NOT EXISTS idx_transcript_sessions_capture_source
            ON transcript_sessions(capture_source);

        CREATE TABLE IF NOT EXISTS transcript_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            revision_index INTEGER NOT NULL,
            text_source TEXT NOT NULL,
            text_value TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            FOREIGN KEY(session_id) REFERENCES transcript_sessions(session_id) ON DELETE CASCADE,
            UNIQUE(session_id, revision_index)
        );

        CREATE INDEX IF NOT EXISTS idx_transcript_revisions_session
            ON transcript_revisions(session_id, revision_index);

        CREATE TABLE IF NOT EXISTS dictionary_entries (
            id TEXT PRIMARY KEY,
            phrase TEXT NOT NULL,
            phrase_normalized TEXT NOT NULL,
            replacement TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'personal',
            enabled INTEGER NOT NULL DEFAULT 1,
            usage_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            UNIQUE(phrase_normalized, scope)
        );

        CREATE INDEX IF NOT EXISTS idx_dictionary_entries_scope
            ON dictionary_entries(scope, enabled);

        CREATE TABLE IF NOT EXISTS snippets (
            id TEXT PRIMARY KEY,
            trigger TEXT NOT NULL,
            trigger_normalized TEXT NOT NULL,
            expansion TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'personal',
            enabled INTEGER NOT NULL DEFAULT 1,
            usage_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            UNIQUE(trigger_normalized, scope)
        );

        CREATE INDEX IF NOT EXISTS idx_snippets_scope
            ON snippets(scope, enabled);

        CREATE TABLE IF NOT EXISTS style_profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            style_key TEXT NOT NULL,
            description TEXT NOT NULL,
            rules_json TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            built_in INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            UNIQUE(style_key)
        );

        CREATE TABLE IF NOT EXISTS style_profile_assignments (
            context TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            FOREIGN KEY(profile_id) REFERENCES style_profiles(id) ON DELETE CASCADE
        );
        """
    )


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))")

    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = ?",
        ("history_schema_version",),
    ).fetchone()
    current_version = int(row[0]) if row and row[0].isdigit() else 0

    if current_version < 1:
        _create_v1_schema(conn)
        conn.execute(
            """
            INSERT INTO app_meta(key, value, updated_at)
            VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            ("history_schema_version", str(SCHEMA_VERSION)),
        )
        conn.commit()
        logger.info("History storage schema migrated to v%s", SCHEMA_VERSION)
