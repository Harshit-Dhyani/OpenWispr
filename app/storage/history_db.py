"""SQLite-based persistence for history, dictionary, snippets, and styles.

Provides HistoryDatabase class - a thread-safe SQLite wrapper using WAL mode
for concurrent reads/writes. Handles schema migrations automatically on connect.

Tables:
    - transcript_sessions: Completed transcription sessions with metadata
    - transcript_revisions: Version history for session transcripts
    - dictionary_entries: User dictionary entries for correction
    - snippets: Reusable text snippets with trigger expansion
    - style_profiles: Named text style profiles
    - user_corrections: Learned user corrections

Key collaborators: app.storage.migrations for schema evolution.
"""

from __future__ import annotations

import logging
import sqlite3
import threading

from pathlib import Path
from contextlib import contextmanager
from typing import Any, Generator

from app.storage.migrations import run_migrations

logger = logging.getLogger(__name__)


class HistoryDatabase:
    """Thread-safe SQLite wrapper for history, dictionary, snippets, and styles."""

    def _cleanup_stale_wal_files(self) -> None:
        wal_path = self.db_path.with_suffix(".db-wal")
        shm_path = self.db_path.with_suffix(".db-shm")
        for path in (wal_path, shm_path):
            if path.exists():
                try:
                    path.unlink()
                except OSError as e:
                    logger.warning(f"Failed to clean up stale WAL file {path}: {e}")

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._cleanup_stale_wal_files()
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,  # Enable autocommit for single-statement writes
            timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA busy_timeout=30000;")  # Wait 30 seconds for locks
        run_migrations(self._conn)

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                yield self._conn
                self._conn.commit()
            except Exception as e:
                self._conn.rollback()
                logger.warning(f"Transaction failed: {e}")
                raise

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql: str, seq_of_params: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, seq_of_params)

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def set_meta(self, key: str, value: str) -> None:
        self.execute(
            """
            INSERT INTO app_meta(key, value, updated_at)
            VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value),
        )

    def get_meta(self, key: str) -> str | None:
        row = self.query_one("SELECT value FROM app_meta WHERE key = ?", (key,))
        if not row:
            return None
        return str(row["value"])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
