from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.api.services.dictionary_service import DictionaryService
from app.api.services.snippet_service import SnippetService
from app.api.services.style_service import StyleService
from app.storage.history_db import HistoryDatabase


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _word_count(text: str | None) -> int:
    if not text:
        return 0
    return len([token for token in text.split() if token.strip()])


@dataclass(frozen=True)
class DownloadAsset:
    kind: str
    filename: str
    content_type: str
    path: Path | None = None
    text: str | None = None


class TranscriptHistoryService:
    def __init__(
        self,
        db: HistoryDatabase,
        *,
        dictionary_service: DictionaryService | None = None,
        snippet_service: SnippetService | None = None,
        style_service: StyleService | None = None,
    ) -> None:
        self._db = db
        self._dictionary_service = dictionary_service
        self._snippet_service = snippet_service
        self._style_service = style_service
        self._retry_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="history-retry")

    def close(self) -> None:
        self._retry_executor.shutdown(wait=False, cancel_futures=True)

    def ingest_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = str(payload.get("session_id", "")).strip()
        if not session_id:
            raise ValueError("session_id is required")

        source_workflow = str(payload.get("source_workflow") or "session")
        capture_source = str(payload.get("capture_source") or "microphone")
        started_at = str(payload.get("started_at") or _utc_now_iso())
        ended_at = str(payload.get("ended_at") or _utc_now_iso())
        duration_ms = int(payload.get("duration_ms") or 0)
        settings_snapshot_json = json.dumps(payload.get("settings_snapshot") or {})

        values = {
            "session_id": session_id,
            "source_workflow": source_workflow,
            "capture_source": capture_source,
            "title": payload.get("title"),
            "transcription_mode": payload.get("transcription_mode"),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "model_name": payload.get("model_name"),
            "model_id": payload.get("model_id"),
            "language_mode": payload.get("language_mode"),
            "execution_mode": payload.get("execution_mode"),
            "device_id": payload.get("device_id"),
            "status": payload.get("status") or "completed",
            "raw_text": payload.get("raw_text"),
            "aggregated_clean_text": payload.get("aggregated_clean_text"),
            "postprocessed_text": payload.get("postprocessed_text"),
            "coach_polished_text": payload.get("coach_polished_text"),
            "active_text": payload.get("active_text"),
            "active_text_source": payload.get("active_text_source") or "unknown",
            "audio_path": payload.get("audio_path"),
            "session_artifacts_path": payload.get("session_artifacts_path"),
            "settings_snapshot_json": settings_snapshot_json,
            "retry_status": payload.get("retry_status") or "idle",
        }

        with self._db.transaction():
            self._db.execute(
                """
                INSERT INTO transcript_sessions(
                    session_id, source_workflow, capture_source, title, transcription_mode, started_at, ended_at, duration_ms,
                    model_name, model_id, language_mode, execution_mode, device_id, status, raw_text, aggregated_clean_text,
                    postprocessed_text, coach_polished_text, active_text, active_text_source, audio_path, session_artifacts_path,
                    settings_snapshot_json, retry_status, created_at, updated_at
                ) VALUES (
                    :session_id, :source_workflow, :capture_source, :title, :transcription_mode, :started_at, :ended_at, :duration_ms,
                    :model_name, :model_id, :language_mode, :execution_mode, :device_id, :status, :raw_text, :aggregated_clean_text,
                    :postprocessed_text, :coach_polished_text, :active_text, :active_text_source, :audio_path, :session_artifacts_path,
                    :settings_snapshot_json, :retry_status, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                )
                ON CONFLICT(session_id) DO UPDATE SET
                    source_workflow = excluded.source_workflow,
                    capture_source = excluded.capture_source,
                    title = excluded.title,
                    transcription_mode = excluded.transcription_mode,
                    started_at = excluded.started_at,
                    ended_at = excluded.ended_at,
                    duration_ms = excluded.duration_ms,
                    model_name = excluded.model_name,
                    model_id = excluded.model_id,
                    language_mode = excluded.language_mode,
                    execution_mode = excluded.execution_mode,
                    device_id = excluded.device_id,
                    status = excluded.status,
                    raw_text = excluded.raw_text,
                    aggregated_clean_text = excluded.aggregated_clean_text,
                    postprocessed_text = excluded.postprocessed_text,
                    coach_polished_text = excluded.coach_polished_text,
                    active_text = excluded.active_text,
                    active_text_source = excluded.active_text_source,
                    audio_path = excluded.audio_path,
                    session_artifacts_path = excluded.session_artifacts_path,
                    settings_snapshot_json = excluded.settings_snapshot_json,
                    retry_status = excluded.retry_status,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                values,
            )
            self._sync_revisions(session_id, values)

        session = self.get_session(session_id)
        if session is None:
            raise RuntimeError("failed to persist transcript session")
        return session

    def ingest_hotkey_result(
        self, result: Any, *, settings_snapshot: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        session_id = getattr(result, "session_id", None) or ""
        composed_text = getattr(result, "composed_text", None) or getattr(
            result, "final_transcription", ""
        )
        active_text = getattr(result, "paste_text", None) or composed_text or ""
        coach_result = getattr(result, "coach_result", None)
        if isinstance(coach_result, dict):
            coach_polished = coach_result.get("polished")
        else:
            coach_polished = getattr(coach_result, "polished", None)

        # Get capture_source from settings snapshot, defaulting to microphone
        capture_source = "microphone"
        if settings_snapshot:
            capture_source = settings_snapshot.get("hotkey", {}).get("capture_source", "microphone")
            if capture_source not in ("microphone", "system"):
                capture_source = settings_snapshot.get("audio", {}).get(
                    "default_capture_source", "microphone"
                )

        payload = {
            "session_id": session_id,
            "source_workflow": "dictation",
            "capture_source": capture_source,
            "title": "Dictation",
            "transcription_mode": getattr(result, "transcription_mode", "dictation"),
            "started_at": _utc_now_iso(),
            "ended_at": _utc_now_iso(),
            "duration_ms": getattr(result, "duration_ms", 0),
            "model_name": getattr(result, "source_backend", None),
            "language_mode": getattr(result, "language_used", None),
            "execution_mode": None,
            "device_id": None,
            "status": "completed",
            "raw_text": getattr(result, "raw_transcription", None) or composed_text,
            "aggregated_clean_text": getattr(result, "aggregated_clean_text", None)
            or composed_text,
            "postprocessed_text": getattr(result, "postprocessed_text", None) or composed_text,
            "coach_polished_text": coach_polished,
            "active_text": active_text,
            "active_text_source": "paste_text",
            "audio_path": getattr(result, "debug_wav_path", None),
            "settings_snapshot": settings_snapshot or {},
        }
        if not payload["session_id"]:
            payload["session_id"] = f"hotkey-{int(datetime.now(tz=UTC).timestamp() * 1000)}"
        return self.ingest_session(payload)

    def _sync_revisions(self, session_id: str, values: dict[str, Any]) -> None:
        existing_rows = self._db.query_all(
            "SELECT revision_index, text_source, text_value FROM transcript_revisions WHERE session_id = ? ORDER BY revision_index ASC",
            (session_id,),
        )
        existing_values = {(row["text_source"], row["text_value"]) for row in existing_rows}
        revision_index = len(existing_rows)
        candidate_sources = [
            ("raw_text", values.get("raw_text")),
            ("aggregated_clean_text", values.get("aggregated_clean_text")),
            ("postprocessed_text", values.get("postprocessed_text")),
            ("coach_polished_text", values.get("coach_polished_text")),
            (str(values.get("active_text_source") or "active_text"), values.get("active_text")),
        ]
        for source, text in candidate_sources:
            text_value = str(text or "").strip()
            if not text_value:
                continue
            if (source, text_value) in existing_values:
                continue
            self._db.execute(
                """
                INSERT INTO transcript_revisions(session_id, revision_index, text_source, text_value, metadata_json, created_at)
                VALUES (?, ?, ?, ?, '{}', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                """,
                (session_id, revision_index, source, text_value),
            )
            revision_index += 1

    def list_sessions(
        self,
        *,
        range_days: int | None = None,
        capture_source: str | None = None,
        workflow: str | None = None,
        include_deleted: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []
        if not include_deleted:
            filters.append("deleted_at IS NULL")
        if capture_source:
            filters.append("capture_source = ?")
            params.append(capture_source)
        if workflow:
            filters.append("source_workflow = ?")
            params.append(workflow)
        if range_days and range_days > 0:
            cutoff = datetime.now(tz=UTC) - timedelta(days=range_days)
            filters.append("started_at >= ?")
            params.append(cutoff.isoformat().replace("+00:00", "Z"))
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.extend([max(limit, 1), max(offset, 0)])
        rows = self._db.query_all(
            f"""
            SELECT session_id, source_workflow, capture_source, title, transcription_mode, started_at, ended_at,
                   duration_ms, model_name, model_id, language_mode, execution_mode, device_id, status, raw_text,
                   aggregated_clean_text, postprocessed_text, coach_polished_text, active_text, active_text_source,
                   audio_path, retry_status, retry_error, retry_attempt_count, deleted_at, created_at, updated_at
            FROM transcript_sessions
            {where_sql}
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )
        return [self._serialize_session_row(row) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self._db.query_one(
            """
            SELECT session_id, source_workflow, capture_source, title, transcription_mode, started_at, ended_at,
                   duration_ms, model_name, model_id, language_mode, execution_mode, device_id, status, raw_text,
                   aggregated_clean_text, postprocessed_text, coach_polished_text, active_text, active_text_source,
                   audio_path, session_artifacts_path, settings_snapshot_json, retry_status, retry_error,
                   retry_attempt_count, deleted_at, created_at, updated_at
            FROM transcript_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        )
        if row is None:
            return None
        payload = self._serialize_session_row(row)
        payload["revisions"] = self._db.query_all(
            """
            SELECT revision_index, text_source, text_value, metadata_json, created_at
            FROM transcript_revisions
            WHERE session_id = ?
            ORDER BY revision_index ASC
            """,
            (session_id,),
        )
        try:
            payload["settings_snapshot"] = json.loads(payload.get("settings_snapshot_json") or "{}")
        except json.JSONDecodeError:
            payload["settings_snapshot"] = {}
        return payload

    def _serialize_session_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload["duration_ms"] = int(payload.get("duration_ms") or 0)
        payload["retry_attempt_count"] = int(payload.get("retry_attempt_count") or 0)
        payload["word_count"] = _word_count(str(payload.get("active_text") or ""))
        payload["audio_available"] = bool(payload.get("audio_path"))
        return payload

    def analytics(self, *, range_days: int | None = None, tz: str = "UTC") -> dict[str, Any]:
        sessions = self.list_sessions(
            range_days=range_days, include_deleted=False, limit=5000, offset=0
        )
        if not sessions:
            return {
                "range_days": range_days or "all",
                "timezone": tz,
                "summary": {
                    "days_used": 0,
                    "total_words": 0,
                    "avg_wpm": 0,
                    "peak_usage_hour": None,
                },
                "daily": [],
                "hourly": [],
            }

        day_counter: Counter[str] = Counter()
        hour_counter: Counter[int] = Counter()
        total_words = 0
        total_duration_minutes = 0.0

        for session in sessions:
            started = _parse_iso(session.get("started_at"))
            if started is None:
                continue
            local_started = started.astimezone()
            day_counter[local_started.strftime("%Y-%m-%d")] += 1
            hour_counter[local_started.hour] += 1
            total_words += int(session.get("word_count") or 0)
            total_duration_minutes += max(float(session.get("duration_ms") or 0), 0.0) / 60000.0

        peak_hour = None
        if hour_counter:
            peak_hour = max(hour_counter.items(), key=lambda item: item[1])[0]
        avg_wpm = 0
        if total_duration_minutes > 0:
            avg_wpm = int(round(total_words / total_duration_minutes))

        daily = [
            {"day": day, "count": count}
            for day, count in sorted(day_counter.items(), key=lambda item: item[0])
        ]
        hourly = [{"hour": hour, "count": hour_counter.get(hour, 0)} for hour in range(24)]

        return {
            "range_days": range_days or "all",
            "timezone": tz,
            "summary": {
                "days_used": len(day_counter),
                "total_words": total_words,
                "avg_wpm": avg_wpm,
                "peak_usage_hour": peak_hour,
            },
            "daily": daily,
            "hourly": hourly,
        }

    def undo_ai_edit(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)

        fallback_order = [
            ("postprocessed_text", session.get("postprocessed_text")),
            ("aggregated_clean_text", session.get("aggregated_clean_text")),
            ("raw_text", session.get("raw_text")),
        ]
        target_source = None
        target_text = None
        for source, value in fallback_order:
            if str(value or "").strip():
                target_source = source
                target_text = str(value)
                break
        if target_text is None:
            target_source = "active_text"
            target_text = str(session.get("active_text") or "")

        self._db.execute(
            """
            UPDATE transcript_sessions
            SET active_text = ?,
                active_text_source = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE session_id = ?
            """,
            (target_text, target_source, session_id),
        )
        self._sync_revisions(
            session_id,
            {
                "raw_text": session.get("raw_text"),
                "aggregated_clean_text": session.get("aggregated_clean_text"),
                "postprocessed_text": session.get("postprocessed_text"),
                "coach_polished_text": session.get("coach_polished_text"),
                "active_text_source": "undo_ai_edit",
                "active_text": target_text,
            },
        )
        updated = self.get_session(session_id)
        if updated is None:
            raise RuntimeError("undo update failed")
        return updated

    def retry_transcript(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        self._db.execute(
            """
            UPDATE transcript_sessions
            SET retry_status = 'queued',
                retry_error = NULL,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE session_id = ?
            """,
            (session_id,),
        )
        self._retry_executor.submit(self._run_retry, session_id)
        updated = self.get_session(session_id)
        if updated is None:
            raise RuntimeError("retry update failed")
        return updated

    def _run_retry(self, session_id: str) -> None:
        self._db.execute(
            "UPDATE transcript_sessions SET retry_status = 'running', updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE session_id = ?",
            (session_id,),
        )
        try:
            session = self.get_session(session_id)
            if session is None:
                raise RuntimeError("session missing")

            text = (
                str(session.get("raw_text") or "")
                or str(session.get("aggregated_clean_text") or "")
                or str(session.get("active_text") or "")
            )
            if self._dictionary_service is not None:
                text = self._dictionary_service.apply_to_text(text, commit_usage=True).text
            if self._snippet_service is not None:
                text = self._snippet_service.expand_text(text, commit_usage=True).text
            if self._style_service is not None:
                context = "personal" if session.get("source_workflow") == "dictation" else "work"
                text = self._style_service.apply_style(text, context=context).text

            self._db.execute(
                """
                UPDATE transcript_sessions
                SET active_text = ?,
                    active_text_source = 'retry_pipeline',
                    retry_status = 'completed',
                    retry_attempt_count = retry_attempt_count + 1,
                    retry_error = NULL,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE session_id = ?
                """,
                (text, session_id),
            )
            self._sync_revisions(
                session_id,
                {
                    "raw_text": session.get("raw_text"),
                    "aggregated_clean_text": session.get("aggregated_clean_text"),
                    "postprocessed_text": session.get("postprocessed_text"),
                    "coach_polished_text": session.get("coach_polished_text"),
                    "active_text_source": "retry_pipeline",
                    "active_text": text,
                },
            )
        except Exception as exc:
            self._db.execute(
                """
                UPDATE transcript_sessions
                SET retry_status = 'failed',
                    retry_error = ?,
                    retry_attempt_count = retry_attempt_count + 1,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE session_id = ?
                """,
                (str(exc), session_id),
            )

    def delete_session(self, session_id: str) -> bool:
        cursor = self._db.execute(
            """
            UPDATE transcript_sessions
            SET deleted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE session_id = ? AND deleted_at IS NULL
            """,
            (session_id,),
        )
        return bool(cursor.rowcount)

    def build_download_asset(self, session_id: str, asset: str) -> DownloadAsset:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)

        if asset == "audio":
            audio_path = Path(str(session.get("audio_path") or ""))
            if not audio_path.exists():
                raise FileNotFoundError("audio file is not available")
            return DownloadAsset(
                kind="audio",
                filename=f"{session_id}.wav",
                content_type="audio/wav",
                path=audio_path,
            )

        if asset == "transcript":
            text = str(session.get("active_text") or "")
            return DownloadAsset(
                kind="transcript",
                filename=f"{session_id}.txt",
                content_type="text/plain; charset=utf-8",
                text=text,
            )

        if asset == "bundle":
            bundle = {
                "session": session,
                "exported_at": _utc_now_iso(),
            }
            return DownloadAsset(
                kind="bundle",
                filename=f"{session_id}.json",
                content_type="application/json; charset=utf-8",
                text=json.dumps(bundle, ensure_ascii=False, indent=2),
            )

        raise ValueError("asset must be one of: audio, transcript, bundle")

    def cleanup_retention(self, retention_days: int) -> int:
        if retention_days <= 0:
            return 0
        cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)
        cursor = self._db.execute(
            """
            DELETE FROM transcript_sessions
            WHERE deleted_at IS NOT NULL
              AND deleted_at < ?
            """,
            (cutoff.isoformat().replace("+00:00", "Z"),),
        )
        return int(cursor.rowcount or 0)
