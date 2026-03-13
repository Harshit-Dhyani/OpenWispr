"""System Mode Session Handler - Full-featured session management for PC audio capture.

This module provides comprehensive session handling for system audio transcription,
optimized for hours-long recordings with automatic segmentation, STEM processing,
and multiple export formats.

Features:
- Continuous audio streaming to disk with rotation
- Real-time transcription with segment building
- Automatic chapter detection on long silences (>2 seconds)
- STEM processing for formulas/equations
- Contextual notes with document attachments
- Export to txt, json, srt, md formats
- Session resume capability
- Progress reporting for long operations
- Background export tasks
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import wave
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from app.audio.capture import LoopbackAudioSource, MeterSmoother
from app.audio.devices import list_audio_devices
from app.core.logging_utils import configure_logging
from app.core.models import (
    AudioDeviceInfo,
    SessionDocument,
    SessionHealth,
    SessionState,
    TranscriptSegment,
    utc_now,
)
from app.core.session.formatters import ExportFormat, MarkdownFormatter, SrtFormatter
from app.core.settings.config import AppSettings, resolve_live_profile
from app.stem.postprocess import NotesBundle, StemNoteProcessor
from app.storage.document_store import ContextProvider, DocumentStore
from app.storage.session_store import SessionWriter
from app.stt.fast_chunker import FastChunker
from app.stt.fast_engine import FastTranscriber

logger = logging.getLogger(__name__)

WhisperTranscriber = FastTranscriber


# Re-export for backward compatibility


class MarkdownFormatter:
    """Formatter for Markdown export."""

    @classmethod
    def format_session(
        cls,
        session: SessionState,
        notes_bundle: NotesBundle,
        chapters: list[Chapter],
    ) -> str:
        """Format complete session as Markdown."""
        lines = [
            f"# {session.title}",
            "",
            "## Metadata",
            "",
            f"- **Session ID:** `{session.session_id}`",
            f"- **Started:** {session.started_at.isoformat()}",
            f"- **Model:** {session.model_name}",
            f"- **Language:** {session.language_mode}",
            f"- **Segments:** {len([s for s in session.segments if not s.suppressed])}",
            f"- **Formulas:** {len(session.formulas)}",
            f"- **Needs Review:** {len(session.needs_review)}",
            "",
        ]

        # Add chapters if available
        if chapters:
            lines.extend(["## Chapters", ""])
            for chapter in chapters:
                lines.append(f"### {cls._format_timestamp(chapter.start_time)} - {chapter.title}")
                if chapter.description:
                    lines.append(chapter.description)
                lines.append("")

        # Add notes
        if notes_bundle.notes_markdown:
            lines.extend(["## Notes", ""])
            lines.append(notes_bundle.notes_markdown)
            lines.append("")

        # Add formulas section
        if session.formulas:
            lines.extend(["## Extracted Formulas", ""])
            for formula in session.formulas:
                status = "✅" if not formula.review_flag else "⚠️"
                lines.append(
                    f"{status} `{formula.expression}` "
                    f"({cls._format_timestamp(formula.timestamp_start)}-"
                    f"{cls._format_timestamp(formula.timestamp_end)})"
                )
            lines.append("")

        # Add full transcript
        lines.extend(["## Full Transcript", ""])
        for segment in session.segments:
            if not segment.suppressed:
                lines.append(f"**[{cls._format_timestamp(segment.start)}]** {segment.display_text}")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format seconds as MM:SS."""
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"


# =============================================================================
# Session Components
# =============================================================================


@dataclass(slots=True)
class Chapter:
    """Represents a chapter/segment boundary in a long session."""

    start_time: float
    end_time: float
    title: str
    description: str = ""
    segment_indices: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "title": self.title,
            "description": self.description,
            "segment_indices": self.segment_indices,
        }


@dataclass(slots=True)
class SessionNote:
    """A contextual note attached to a specific timestamp."""

    id: str
    timestamp: float
    text: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "text": self.text,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class SessionMetadata:
    """Extended session metadata."""

    title: str
    tags: list[str] = field(default_factory=list)
    description: str = ""
    source_type: str = "system_audio"  # system_audio, microphone, file
    custom_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "tags": self.tags,
            "description": self.description,
            "source_type": self.source_type,
            "custom_fields": self.custom_fields,
        }


@dataclass
class SystemSessionConfig:
    """Configuration for system mode session."""

    # Export options
    export_formats: list[str] = field(default_factory=lambda: ["txt", "json", "srt", "md"])

    # Segmentation
    auto_segment: bool = True
    silence_threshold_db: float = -40.0
    min_silence_duration_ms: float = 2000.0  # 2 seconds for chapter detection

    # Audio saving
    save_audio: bool = True
    audio_rotation_size_mb: float = 100.0  # Rotate audio files at 100MB
    audio_compression: bool = False  # Future: enable compression

    # STEM processing
    enable_stem: bool = True

    # Progress reporting
    progress_report_interval_seconds: float = 30.0

    # Session limits
    max_session_duration_hours: float = 8.0
    max_disk_usage_gb: float = 50.0

    def validate(self) -> list[str]:
        """Validate configuration and return list of warnings."""
        warnings = []

        # Validate export formats
        valid_formats = {"txt", "json", "srt", "md"}
        invalid = set(self.export_formats) - valid_formats
        if invalid:
            warnings.append(f"Invalid export formats: {invalid}")

        # Validate durations
        if self.max_session_duration_hours > 24:
            warnings.append("Session duration exceeds 24 hours, may impact performance")

        if self.max_disk_usage_gb > 100:
            warnings.append("Disk usage limit > 100GB, ensure sufficient storage")

        return warnings


# =============================================================================
# Audio Recording Manager
# =============================================================================


class AudioRecordingManager:
    """Manages continuous audio recording to disk with rotation."""

    def __init__(
        self,
        output_dir: Path,
        sample_rate: int = 16000,
        channels: int = 1,
        rotation_size_mb: float = 100.0,
    ) -> None:
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        self.channels = channels
        self.rotation_size_bytes = int(rotation_size_mb * 1024 * 1024)
        self.rotation_size_mb = rotation_size_mb

        self._current_file_index = 0
        self._current_writer: wave.Wave_write | None = None
        self._current_file_path: Path | None = None
        self._current_file_size = 0
        self._total_bytes_written = 0
        self._audio_files: list[Path] = []
        self._lock = threading.Lock()
        self._is_recording = False
        self._start_time: datetime | None = None

    def start(self) -> None:
        """Start audio recording."""
        with self._lock:
            if self._is_recording:
                return

            self._start_time = utc_now()
            self._is_recording = True
            self._create_new_file()

            logger.debug(
                "audio_recording_started",
                extra={
                    "output_dir": str(self.output_dir),
                    "sample_rate": self.sample_rate,
                    "channels": self.channels,
                    "rotation_mb": self.rotation_size_mb,
                },
            )

    def stop(self) -> list[Path]:
        """Stop recording and return list of recorded files."""
        with self._lock:
            if not self._is_recording:
                return list(self._audio_files)

            self._is_recording = False

            if self._current_writer:
                try:
                    self._current_writer.close()
                    logger.debug(
                        "audio_file_closed",
                        extra={
                            "file": str(self._current_file_path),
                            "size_mb": self._current_file_size / (1024 * 1024),
                        },
                    )
                except Exception as e:
                    logger.error(f"Error closing audio file: {e}")
                finally:
                    self._current_writer = None

            self._start_time = None
            return list(self._audio_files)

    def write(self, audio: np.ndarray) -> None:
        """Write audio data to the current file."""
        with self._lock:
            if not self._is_recording or self._current_writer is None:
                return

            # Convert to int16 for WAV format
            if audio.dtype == np.float32 or audio.dtype == np.float64:
                audio_int16 = (audio * 32767).astype(np.int16)
            else:
                audio_int16 = audio.astype(np.int16)

            # Check if we need to rotate
            data_size = len(audio_int16) * 2  # 2 bytes per int16 sample
            if self._current_file_size + data_size > self.rotation_size_bytes:
                self._rotate_file()

            # Write data
            try:
                self._current_writer.writeframes(audio_int16.tobytes())
                self._current_file_size += data_size
                self._total_bytes_written += data_size
            except Exception as e:
                logger.error(f"Error writing audio data: {e}")
                raise

    def _create_new_file(self) -> None:
        """Create a new audio file."""
        self._current_file_index += 1
        self._current_file_path = self.output_dir / f"audio_{self._current_file_index:04d}.wav"
        self._audio_files.append(self._current_file_path)

        try:
            self._current_writer = wave.open(str(self._current_file_path), "wb")
            self._current_writer.setnchannels(self.channels)
            self._current_writer.setsampwidth(2)  # 16-bit
            self._current_writer.setframerate(self.sample_rate)
            self._current_file_size = 44  # WAV header size

            logger.debug(
                "audio_file_created",
                extra={
                    "file": str(self._current_file_path),
                    "index": self._current_file_index,
                },
            )
        except Exception as e:
            logger.error(f"Error creating audio file: {e}")
            raise

    def _rotate_file(self) -> None:
        """Rotate to a new audio file."""
        if self._current_writer:
            try:
                self._current_writer.close()
                logger.debug(
                    "audio_file_rotated",
                    extra={
                        "file": str(self._current_file_path),
                        "final_size_mb": self._current_file_size / (1024 * 1024),
                    },
                )
            except Exception as e:
                logger.error(f"Error closing file for rotation: {e}")
            finally:
                self._current_writer = None

        self._create_new_file()

    def get_stats(self) -> dict[str, Any]:
        """Get recording statistics."""
        with self._lock:
            duration_seconds = 0.0
            if self._start_time:
                duration_seconds = (utc_now() - self._start_time).total_seconds()

            return {
                "is_recording": self._is_recording,
                "total_bytes_written": self._total_bytes_written,
                "total_mb": self._total_bytes_written / (1024 * 1024),
                "duration_seconds": duration_seconds,
                "duration_formatted": self._format_duration(duration_seconds),
                "file_count": len(self._audio_files),
                "current_file": str(self._current_file_path) if self._current_file_path else None,
            }

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration as HH:MM:SS."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# =============================================================================
# Export Manager
# =============================================================================


class ExportManager:
    """Manages background export tasks."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="export-")
        self._pending_tasks: dict[str, asyncio.Future] = {}
        self._export_history: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def export_async(
        self,
        session: SessionState,
        notes_bundle: NotesBundle,
        chapters: list[Chapter],
        formats: list[ExportFormat],
        callback: Callable[[str, bool, str], None] | None = None,
    ) -> str:
        """Queue an async export task."""
        task_id = uuid4().hex[:8]

        future = self._executor.submit(
            self._do_export,
            session,
            notes_bundle,
            chapters,
            formats,
            task_id,
            callback,
        )

        with self._lock:
            self._pending_tasks[task_id] = future

        return task_id

    def _do_export(
        self,
        session: SessionState,
        notes_bundle: NotesBundle,
        chapters: list[Chapter],
        formats: list[ExportFormat],
        task_id: str,
        callback: Callable[[str, bool, str], None] | None,
    ) -> None:
        """Perform the actual export."""
        try:
            results = []
            for fmt in formats:
                path = self._export_single(session, notes_bundle, chapters, fmt)
                results.append(f"{fmt.value}:{path.name}")

            message = f"Exported {len(results)} formats"
            success = True

            with self._lock:
                self._export_history.append(
                    {
                        "task_id": task_id,
                        "timestamp": utc_now().isoformat(),
                        "formats": [f.value for f in formats],
                        "results": results,
                        "success": True,
                    }
                )

        except Exception as e:
            message = f"Export failed: {e}"
            success = False
            logger.error(f"Export task {task_id} failed: {e}")

            with self._lock:
                self._export_history.append(
                    {
                        "task_id": task_id,
                        "timestamp": utc_now().isoformat(),
                        "formats": [f.value for f in formats],
                        "error": str(e),
                        "success": False,
                    }
                )

        finally:
            with self._lock:
                self._pending_tasks.pop(task_id, None)

        if callback:
            try:
                callback(task_id, success, message)
            except Exception as e:
                logger.error(f"Export callback error: {e}")

    def _export_single(
        self,
        session: SessionState,
        notes_bundle: NotesBundle,
        chapters: list[Chapter],
        fmt: ExportFormat,
    ) -> Path:
        """Export to a single format."""
        output_path = self.output_dir / f"export.{fmt.value}"

        if fmt == ExportFormat.TXT:
            content = self._format_txt(session)
        elif fmt == ExportFormat.JSON:
            content = self._format_json(session, notes_bundle, chapters)
        elif fmt == ExportFormat.SRT:
            content = SrtFormatter.format_segments(session.segments)
        elif fmt == ExportFormat.MD:
            content = MarkdownFormatter.format_session(session, notes_bundle, chapters)
        else:
            raise ValueError(f"Unknown format: {fmt}")

        # Atomic write
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(output_path)

        logger.debug(
            "export_complete",
            extra={"format": fmt.value, "path": str(output_path), "size": len(content)},
        )

        return output_path

    def _format_txt(self, session: SessionState) -> str:
        """Format as plain text."""
        lines = [f"Session: {session.title}", f"Started: {session.started_at.isoformat()}", ""]

        for segment in session.segments:
            if not segment.suppressed:
                lines.append(segment.display_text)

        return "\n".join(lines)

    def _format_json(
        self,
        session: SessionState,
        notes_bundle: NotesBundle,
        chapters: list[Chapter],
    ) -> str:
        """Format as JSON."""
        data = {
            "session": session.to_metadata_dict(),
            "segments": [s.to_dict() for s in session.segments],
            "formulas": [f.to_dict() for f in session.formulas],
            "needs_review": [s.to_dict() for s in session.needs_review],
            "chapters": [c.to_dict() for c in chapters],
            "export_metadata": {
                "exported_at": utc_now().isoformat(),
                "notes_preview": notes_bundle.notes_markdown[:500] if notes_bundle else "",
            },
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def get_pending_tasks(self) -> list[str]:
        """Get list of pending task IDs."""
        with self._lock:
            return list(self._pending_tasks.keys())

    def get_history(self) -> list[dict[str, Any]]:
        """Get export history."""
        with self._lock:
            return list(self._export_history)

    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> None:
        """Shutdown the export manager."""
        logger.debug("export_manager_shutdown", extra={"wait": wait, "timeout": timeout})
        self._executor.shutdown(wait=wait)


# =============================================================================
# Silence-Based Chapter Detection
# =============================================================================


class ChapterDetector:
    """Detects chapters based on long periods of silence."""

    def __init__(
        self,
        threshold_db: float = -40.0,
        min_silence_duration_ms: float = 2000.0,
        sample_rate: int = 16000,
    ) -> None:
        self.threshold_linear = 10 ** (threshold_db / 20.0)
        self.min_silence_samples = int(min_silence_duration_ms * sample_rate / 1000)
        self.sample_rate = sample_rate

        self._silence_counter = 0
        self._in_silence = False
        self._chapters: list[Chapter] = []
        self._current_chapter_start = 0.0
        self._total_samples = 0
        self._chapter_counter = 0

    def process(self, audio: np.ndarray, timestamp: float) -> Chapter | None:
        """Process audio and detect chapter boundaries."""
        frame_energy = np.sqrt(np.mean(np.square(audio)) + 1e-12)
        is_silent = frame_energy < self.threshold_linear

        if is_silent:
            if not self._in_silence:
                self._in_silence = True
            self._silence_counter += len(audio)
        else:
            if self._in_silence:
                # End of silence period
                silence_duration = self._silence_counter / self.sample_rate

                if self._silence_counter >= self.min_silence_samples:
                    # This is a chapter boundary
                    self._chapter_counter += 1
                    chapter = Chapter(
                        start_time=self._current_chapter_start,
                        end_time=timestamp - silence_duration,
                        title=f"Chapter {self._chapter_counter}",
                        description=f"Auto-detected chapter after {silence_duration:.1f}s silence",
                    )
                    self._chapters.append(chapter)
                    self._current_chapter_start = timestamp
                    return chapter

            self._in_silence = False
            self._silence_counter = 0

        self._total_samples += len(audio)
        return None

    def get_chapters(self) -> list[Chapter]:
        """Get all detected chapters."""
        return list(self._chapters)

    def finalize(self, end_time: float) -> list[Chapter]:
        """Finalize and return chapters, including the last one."""
        if self._current_chapter_start < end_time:
            final_chapter = Chapter(
                start_time=self._current_chapter_start,
                end_time=end_time,
                title=f"Chapter {self._chapter_counter + 1}",
                description="Final chapter",
            )
            self._chapters.append(final_chapter)

        return list(self._chapters)


# =============================================================================
# Main System Session Handler
# =============================================================================


class SystemSessionHandler:
    """Full-featured session handler for system audio transcription.

    This class provides comprehensive session management including:
    - Hours-long recording with audio rotation
    - Automatic segmentation on silence
    - STEM processing for formulas
    - Multiple export formats
    - Session resume capability
    - Progress reporting
    """

    CHUNK_DURATION_MS = 200
    TARGET_LATENCY_MS = 500
    MAX_WORKERS = 2

    def __init__(
        self,
        settings: AppSettings,
        session_config: SystemSessionConfig | None = None,
    ) -> None:
        self.settings = settings
        self.session_config = session_config or SystemSessionConfig()

        # Core components
        self.session: SessionState | None = None
        self.extended_metadata: SessionMetadata | None = None
        self.writer: SessionWriter | None = None
        self.document_store = DocumentStore()
        self.context_provider = ContextProvider(self.document_store)
        self.note_processor = StemNoteProcessor()

        # Audio components
        self.audio_source: LoopbackAudioSource | None = None
        self.chunker: FastChunker | None = None
        self.transcriber: FastTranscriber | None = None
        self.meter = MeterSmoother(decay=settings.meter_decay)

        # Extended features
        self.audio_recorder: AudioRecordingManager | None = None
        self.export_manager: ExportManager | None = None
        self.chapter_detector: ChapterDetector | None = None

        # Threading
        self._audio_thread: threading.Thread | None = None
        self._processing_executor: ThreadPoolExecutor | None = None
        self._export_executor: ThreadPoolExecutor | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()

        # State tracking
        self._last_rebuild_at = 0.0
        self._outputs_dirty = False
        self._last_processed_segment_index = -1
        self._pending_chunks = 0
        self._pending_lock = threading.Lock()
        self._session_lock = threading.Lock()
        self._chunks_processed = 0

        # Session tracking
        self._chapters: list[Chapter] = []
        self._session_notes: list[SessionNote] = []
        self._stream_time = 0.0
        self._start_time: datetime | None = None
        self._last_progress_report = 0.0

        # Preloading
        self._preloaded_model: Any = None
        self._preload_lock = threading.Lock()

        # Logging
        self.logger: logging.Logger | None = None
        self._loop_counter = 0
        self._last_loop_log = 0.0

        # Callbacks
        self._on_segment: Callable[[TranscriptSegment], None] | None = None
        self._on_partial: Callable[[str, float, float], None] | None = None
        self._on_health: Callable[[SessionHealth, float], None] | None = None
        self._on_state: Callable[[SessionState], None] | None = None
        self._on_chapter: Callable[[Chapter], None] | None = None
        self._on_progress: Callable[[dict[str, Any]], None] | None = None
        self._callback_lock = threading.Lock()

        # Notes bundle cache
        self._last_notes_bundle: NotesBundle | None = None

        # Validate config
        warnings = self.session_config.validate()
        if warnings:
            for warning in warnings:
                logger.warning(f"Session config warning: {warning}")

    def set_callbacks(
        self,
        *,
        on_segment: Callable[[TranscriptSegment], None] | None = None,
        on_partial: Callable[[str, float, float], None] | None = None,
        on_health: Callable[[SessionHealth, float], None] | None = None,
        on_state: Callable[[SessionState], None] | None = None,
        on_chapter: Callable[[Chapter], None] | None = None,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Register callback functions."""
        registered = []
        with self._callback_lock:
            if on_segment:
                self._on_segment = on_segment
                registered.append("on_segment")
            if on_partial:
                self._on_partial = on_partial
                registered.append("on_partial")
            if on_health:
                self._on_health = on_health
                registered.append("on_health")
            if on_state:
                self._on_state = on_state
                registered.append("on_state")
            if on_chapter:
                self._on_chapter = on_chapter
                registered.append("on_chapter")
            if on_progress:
                self._on_progress = on_progress
                registered.append("on_progress")

        if self.logger:
            self.logger.debug(
                "callbacks_registered",
                extra={
                    "registered": registered,
                    "session_id": self.session.session_id if self.session else None,
                },
            )

    def preload_model(
        self,
        model_name: str,
        language_mode: str,
        execution_mode: str,
    ) -> dict[str, Any]:
        """Preload a model for faster session start."""
        session_slug = self.session.session_id if self.session else None

        if self.logger:
            self.logger.debug(
                "preload_model_start",
                extra={
                    "model_name": model_name,
                    "language_mode": language_mode,
                    "execution_mode": execution_mode,
                    "session_id": session_slug,
                },
            )

        with self._preload_lock:
            if self._preloaded_model is not None:
                return {
                    "status": "already_loaded",
                    "device": self._preloaded_model.get("device", "unknown"),
                }

            transcriber = WhisperTranscriber(
                model_name=model_name,
                download_root=str(self.settings.download_root),
                device=self.settings.device,
                compute_type=self.settings.compute_type,
                beam_size=self.settings.beam_size,
                best_of=self.settings.best_of,
                temperature=self.settings.temperature,
                vad_filter=self.settings.vad_filter,
                language_mode=language_mode,
                execution_mode=execution_mode,
                max_queue_items=self.settings.max_queue_items,
            )

            start_time = time.perf_counter()
            model = transcriber.load_model()
            load_time_ms = (time.perf_counter() - start_time) * 1000

            self._preloaded_model = {
                "transcriber": transcriber,
                "model": model,
                "device": transcriber._gpu_mode,
                "load_time_ms": load_time_ms,
            }

            return {
                "status": "loaded",
                "device": transcriber._gpu_mode,
                "load_time_ms": load_time_ms,
            }

    def create_session(
        self,
        *,
        title: str,
        output_root: Path,
        description: str = "",
        tags: list[str] | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> SessionState:
        """Create a new session without starting recording."""
        self.document_store = DocumentStore()
        self.context_provider = ContextProvider(self.document_store)

        output_dir = output_root / self._slugify(title)

        # Create session state
        self.session = SessionState.create(
            title=title,
            output_dir=output_dir,
            model_name=self.settings.default_model,
            language_mode=self.settings.default_language,
            device_id="default",
            live_mode=self.settings.default_live_mode,
            execution_mode=self.settings.default_execution_mode,
        )
        self.session.status = "created"

        # Create extended metadata
        self.extended_metadata = SessionMetadata(
            title=title,
            tags=tags or [],
            description=description,
            source_type="system_audio",
            custom_fields=custom_fields or {},
        )

        # Initialize components
        self.writer = SessionWriter(self.session)
        self.logger = configure_logging(output_dir / "logs", self.settings.log_level)
        self.export_manager = ExportManager(output_dir)

        # Initialize audio recorder if enabled
        if self.session_config.save_audio:
            self.audio_recorder = AudioRecordingManager(
                output_dir=output_dir / "audio",
                sample_rate=self.settings.sample_rate,
                channels=self.settings.channels,
                rotation_size_mb=self.session_config.audio_rotation_size_mb,
            )

        # Initialize chapter detector if auto-segment enabled
        if self.session_config.auto_segment:
            self.chapter_detector = ChapterDetector(
                threshold_db=self.session_config.silence_threshold_db,
                min_silence_duration_ms=self.session_config.min_silence_duration_ms,
                sample_rate=self.settings.sample_rate,
            )

        # Write initial metadata
        self.writer.write_metadata()
        self._write_extended_metadata()

        self.logger.debug(
            "session_created",
            extra={
                "session_id": self.session.session_id,
                "title": title,
                "output_dir": str(output_dir),
                "save_audio": self.session_config.save_audio,
                "auto_segment": self.session_config.auto_segment,
            },
        )

        self._emit_state()
        return self.session

    def start_session(
        self,
        *,
        title: str,
        output_root: Path,
        model_name: str,
        language_mode: str,
        device_id: str | None,
        live_mode: str,
        execution_mode: str,
        vad_params: dict[str, Any] | None = None,
        enable_streaming: bool = True,
        description: str = "",
        tags: list[str] | None = None,
        resume_from: Path | None = None,
    ) -> SessionState:
        """Start a new recording session."""
        if self.session and self.session.status == "running":
            raise RuntimeError("Session already running")

        # Create or resume session
        if resume_from and resume_from.exists():
            return self._resume_session(
                resume_from=resume_from,
                model_name=model_name,
                language_mode=language_mode,
                device_id=device_id,
                live_mode=live_mode,
                execution_mode=execution_mode,
                vad_params=vad_params,
                enable_streaming=enable_streaming,
            )

        # Create new session
        self.create_session(
            title=title,
            output_root=output_root,
            description=description,
            tags=tags,
        )

        if self.session is None:
            raise RuntimeError("Failed to create session")

        # Update session parameters
        self.session.model_name = model_name
        self.session.language_mode = language_mode
        self.session.device_id = device_id or "default"
        self.session.live_mode = live_mode
        self.session.execution_mode = execution_mode

        # Ensure output directory exists
        self.session.output_dir.mkdir(parents=True, exist_ok=True)
        (self.session.output_dir / "logs").mkdir(exist_ok=True)

        self.logger.debug(
            "session_start_init",
            extra={
                "session_id": self.session.session_id,
                "title": title,
                "model_name": model_name,
                "language_mode": language_mode,
                "live_mode": live_mode,
                "execution_mode": execution_mode,
            },
        )

        # Initialize chunker
        live_profile = resolve_live_profile(live_mode, self.settings)
        chunk_duration = live_profile["chunk_seconds"]
        self.chunker = FastChunker(
            sample_rate=self.settings.sample_rate,
            chunk_duration=chunk_duration,
            overlap_ratio=max(0.05, min(live_profile["overlap_seconds"] / chunk_duration, 0.4)),
        )

        # Initialize audio source
        block_size = max(
            256,
            int(self.settings.sample_rate * self.settings.capture_block_seconds),
        )
        self.audio_source = LoopbackAudioSource(
            device_id=device_id,
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
            block_size=block_size,
            max_queue_items=self.settings.max_queue_items * 2,
            audio_backend=self.settings.audio_backend,
        )
        self.audio_source.on_error = self._handle_error

        # Initialize transcriber
        with self._preload_lock:
            if self._preloaded_model and self._preloaded_model.get("transcriber"):
                cached = self._preloaded_model
                self.transcriber = cached["transcriber"]
                if self.transcriber.model_name == model_name:
                    self.transcriber.set_language_mode(language_mode)
                    self.transcriber.set_execution_mode(execution_mode)
                    self.transcriber.set_streaming_profile(
                        streaming_window_ms=max(800, int(chunk_duration * 1000)),
                        streaming_overlap_ms=max(120, int(live_profile["overlap_seconds"] * 1000)),
                    )
                else:
                    self._preloaded_model = None
                    self.transcriber = None
            else:
                self.transcriber = None

        if self.transcriber is None:
            self.transcriber = WhisperTranscriber(
                model_name=model_name,
                download_root=str(self.settings.download_root),
                device=self.settings.device,
                compute_type=self.settings.compute_type,
                beam_size=self.settings.beam_size,
                best_of=self.settings.best_of,
                temperature=self.settings.temperature,
                vad_filter=False if live_mode == "ultra" else self.settings.vad_filter,
                language_mode=language_mode,
                execution_mode=execution_mode,
                max_queue_items=self.settings.max_queue_items,
                vad_params=vad_params,
                streaming_window_ms=max(800, int(chunk_duration * 1000)),
                streaming_overlap_ms=max(120, int(live_profile["overlap_seconds"] * 1000)),
            )

        # Register transcriber callbacks
        self.transcriber.add_segment_callback(self._handle_segment)
        self.transcriber.add_partial_callback(self._handle_partial)
        self.transcriber.add_error_callback(self._handle_error)
        self.transcriber.add_health_callback(self._handle_health)

        # Reset state
        self._stop_event.clear()
        self._pause_event.clear()
        self._last_rebuild_at = 0.0
        self._outputs_dirty = False
        self._last_processed_segment_index = -1
        self._pending_chunks = 0
        self._loop_counter = 0
        self._last_loop_log = 0.0
        self._chunks_processed = 0
        self._stream_time = 0.0
        self._start_time = utc_now()
        self._last_progress_report = time.monotonic()

        try:
            # Start components
            if self.audio_recorder:
                self.audio_recorder.start()

            self.transcriber.start()
            self.audio_source.start()

            # Create thread pools
            self._processing_executor = ThreadPoolExecutor(
                max_workers=self.MAX_WORKERS,
                thread_name_prefix="stt-worker",
            )

            # Start audio loop
            self._audio_thread = threading.Thread(
                target=self._audio_loop_parallel if enable_streaming else self._audio_loop,
                name="audio-loop",
                daemon=True,
            )
            self._audio_thread.start()

            # Update session status
            self.session.status = "running"
            self.session.health.execution_mode = execution_mode
            self.session.health.last_warning = self._get_language_warning(language_mode)

            if self.writer:
                self.writer.write_metadata()

            self._emit_state()

            self.logger.debug(
                "session_started",
                extra={
                    "session_id": self.session.session_id,
                    "status": "running",
                    "save_audio": self.session_config.save_audio,
                    "auto_segment": self.session_config.auto_segment,
                },
            )

            return self.session

        except Exception:
            self.logger.exception("session_start_failed")
            self._cleanup_on_error()
            raise

    def _resume_session(
        self,
        resume_from: Path,
        model_name: str,
        language_mode: str,
        device_id: str | None,
        live_mode: str,
        execution_mode: str,
        vad_params: dict[str, Any] | None,
        enable_streaming: bool,
    ) -> SessionState:
        """Resume a previously saved session."""
        self.logger.info(f"Resuming session from {resume_from}")

        # Load session metadata
        session_file = resume_from / "session.json"
        if not session_file.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")

        # Parse existing session data
        try:
            metadata = json.loads(session_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            self.logger.warning(f"Failed to parse session file: {e}")
            raise

        # Create new session with loaded data
        self.create_session(
            title=metadata.get("title", "Resumed Session"),
            output_root=resume_from.parent,
        )

        if self.session is None:
            raise RuntimeError("Failed to create session for resume")

        # Restore session ID and timestamps
        self.session.session_id = metadata.get("session_id", self.session.session_id)
        self.session.started_at = datetime.fromisoformat(metadata["started_at"])

        # Load existing segments
        transcript_file = resume_from / "transcript.jsonl"
        if transcript_file.exists():
            self._load_existing_segments(transcript_file)

        # Now start the session
        return self.start_session(
            title=self.session.title,
            output_root=resume_from.parent,
            model_name=model_name,
            language_mode=language_mode,
            device_id=device_id,
            live_mode=live_mode,
            execution_mode=execution_mode,
            vad_params=vad_params,
            enable_streaming=enable_streaming,
        )

    def _load_existing_segments(self, transcript_file: Path) -> None:
        """Load existing transcript segments from file."""
        if self.session is None:
            return

        count = 0
        with transcript_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    segment = TranscriptSegment(
                        id=data["id"],
                        start=data["start"],
                        end=data["end"],
                        text=data["text"],
                        display_text=data["display_text"],
                        language=data["language"],
                        avg_logprob=data.get("avg_logprob"),
                        no_speech_prob=data.get("no_speech_prob"),
                        compression_ratio=data.get("compression_ratio"),
                        confidence=data.get("confidence", 0.0),
                        review_flag=data.get("review_flag", False),
                        review_reasons=data.get("review_reasons", []),
                        suppressed=data.get("suppressed", False),
                        suppression_reasons=data.get("suppression_reasons", []),
                        quality_label=data.get("quality_label", "ok"),
                    )
                    self.session.segments.append(segment)
                    count += 1
                except (json.JSONDecodeError, KeyError) as e:
                    self.logger.warning(f"Failed to load segment: {e}")

        self.logger.info(f"Loaded {count} existing segments")

    def pause_session(self) -> None:
        """Pause the current session."""
        if self.session and self.session.status == "running":
            self._pause_event.set()
            self.session.status = "paused"

            if self.audio_recorder:
                self.audio_recorder.stop()

            self.logger.debug("session_paused", extra={"session_id": self.session.session_id})
            self._emit_state()

    def resume_session(self) -> None:
        """Resume a paused session."""
        if self.session and self.session.status == "paused":
            self._pause_event.clear()
            self.session.status = "running"

            if self.audio_recorder:
                self.audio_recorder.start()

            self.logger.debug("session_resumed", extra={"session_id": self.session.session_id})
            self._emit_state()

    def stop_session(self, export_formats: list[str] | None = None) -> dict[str, Any]:
        """Stop the current session and optionally export."""
        session_slug = self.session.session_id if self.session else None

        if self.logger:
            self.logger.debug("session_stop_init", extra={"session_id": session_slug})

        self._stop_event.set()

        # Stop audio components
        if self.audio_source:
            self.audio_source.stop()

        if self.transcriber:
            self.transcriber.stop()

        # Stop thread pool
        if self._processing_executor:
            self._processing_executor.shutdown(wait=True, cancel_futures=True)

        # Wait for audio thread
        if self._audio_thread:
            self._audio_thread.join(timeout=5)

        # Stop audio recorder
        audio_files: list[Path] = []
        if self.audio_recorder:
            audio_files = self.audio_recorder.stop()

        # Finalize chapters
        if self.chapter_detector and self._stream_time > 0:
            self._chapters = self.chapter_detector.finalize(self._stream_time)

        # Finalize outputs
        if self.session:
            self.session.status = "stopped"
            self._rebuild_outputs(force=True)

            if self.writer:
                self.writer.write_metadata()
                self._write_extended_metadata()

        # Export if formats specified
        export_task_id: str | None = None
        if export_formats and self.session and self.export_manager:
            formats = [ExportFormat.from_string(f) for f in export_formats]
            export_task_id = self.export_manager.export_async(
                session=self.session,
                notes_bundle=self._last_notes_bundle or NotesBundle("", "", [], []),
                chapters=self._chapters,
                formats=formats,
            )

        self._emit_state()

        if self.logger:
            self.logger.debug(
                "session_stopped",
                extra={
                    "session_id": session_slug,
                    "total_chunks": self._chunks_processed,
                    "total_segments": len(self.session.segments) if self.session else 0,
                    "audio_files": len(audio_files),
                    "chapters": len(self._chapters),
                },
            )

        # Return summary
        return {
            "session_id": session_slug,
            "status": "stopped",
            "duration_seconds": self._stream_time if self.session else 0,
            "total_segments": len(self.session.segments) if self.session else 0,
            "audio_files": [str(f) for f in audio_files],
            "chapters": len(self._chapters),
            "export_task_id": export_task_id,
        }

    def add_note(
        self, text: str, timestamp: float | None = None, tags: list[str] | None = None
    ) -> SessionNote:
        """Add a contextual note to the session."""
        note = SessionNote(
            id=uuid4().hex[:8],
            timestamp=timestamp or self._stream_time,
            text=text,
            tags=tags or [],
        )

        self._session_notes.append(note)

        # Write to session notes file
        if self.session:
            notes_file = self.session.output_dir / "session_notes.jsonl"
            with notes_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(note.to_dict(), ensure_ascii=False) + "\n")

        if self.logger:
            self.logger.debug(
                "note_added",
                extra={
                    "note_id": note.id,
                    "timestamp": note.timestamp,
                    "tags": note.tags,
                },
            )

        return note

    def attach_document(self, path: str | Path) -> SessionDocument:
        """Attach a document to the session."""
        if self.session is None:
            raise RuntimeError("No active session")

        document = self.document_store.add_pdf(path)
        self.session.documents.append(document)

        if self.writer:
            self.writer.write_metadata()

        self._emit_state()
        return document

    def export(
        self,
        formats: list[str] | None = None,
        wait: bool = False,
        callback: Callable[[str, bool, str], None] | None = None,
    ) -> str | None:
        """Export session to specified formats."""
        if self.session is None or self.export_manager is None:
            return None

        formats_to_export = formats or self.session_config.export_formats
        export_formats = [ExportFormat.from_string(f) for f in formats_to_export]

        task_id = self.export_manager.export_async(
            session=self.session,
            notes_bundle=self._last_notes_bundle or NotesBundle("", "", [], []),
            chapters=self._chapters,
            formats=export_formats,
            callback=callback,
        )

        if wait:
            # Wait for export to complete
            while task_id in self.export_manager.get_pending_tasks():
                time.sleep(0.1)

        return task_id

    def get_progress(self) -> dict[str, Any]:
        """Get current session progress."""
        if self.session is None:
            return {"status": "no_session"}

        duration_seconds = 0.0
        if self._start_time:
            duration_seconds = (utc_now() - self._start_time).total_seconds()

        audio_stats = {}
        if self.audio_recorder:
            audio_stats = self.audio_recorder.get_stats()

        visible_segments = len([s for s in self.session.segments if not s.suppressed])

        return {
            "status": self.session.status,
            "session_id": self.session.session_id,
            "duration_seconds": duration_seconds,
            "duration_formatted": self._format_duration(duration_seconds),
            "stream_time": self._stream_time,
            "total_segments": len(self.session.segments),
            "visible_segments": visible_segments,
            "suppressed_segments": len(self.session.suppressed_segments),
            "formulas": len(self.session.formulas),
            "needs_review": len(self.session.needs_review),
            "chapters": len(self._chapters),
            "pending_exports": len(self.export_manager.get_pending_tasks())
            if self.export_manager
            else 0,
            "audio": audio_stats,
            "health": self.session.health.to_dict() if self.session.health else {},
        }

    def list_devices(self) -> list[AudioDeviceInfo]:
        """List available audio devices."""
        return list_audio_devices()

    # =============================================================================
    # Internal Methods
    # =============================================================================

    def _audio_loop(self) -> None:
        """Sequential audio processing loop."""
        assert self.audio_source is not None
        assert self.chunker is not None

        stream_time = 0.0
        loop_count = 0
        last_log_time = time.monotonic()

        while not self._stop_event.is_set():
            # Check pause
            if self._pause_event.is_set():
                time.sleep(0.1)
                continue

            samples = self.audio_source.read(timeout=0.05)
            loop_count += 1

            if samples is None:
                continue

            stream_time += len(samples) / self.settings.sample_rate
            self._stream_time = stream_time

            chunks = self.chunker.push(samples, stream_time)
            chunk_count = len(chunks)
            self._chunks_processed += chunk_count

            if self.session:
                self.session.health.audio_stream_active = True
                self.session.health.dropped_frames = self.audio_source.dropped_frames

            # Record audio if enabled
            if self.audio_recorder:
                self.audio_recorder.write(samples)

            # Process chunks
            for chunk in chunks:
                if self.transcriber:
                    self.transcriber.submit(chunk)

            # Detect chapters
            if self.chapter_detector:
                chapter = self.chapter_detector.process(samples, stream_time)
                if chapter:
                    self._chapters.append(chapter)
                    self._emit_chapter(chapter)

            # Rebuild outputs
            self._maybe_rebuild_outputs()
            self._emit_health()
            self._maybe_report_progress()

            # Logging
            now = time.monotonic()
            if now - last_log_time >= 1.0:
                if self.logger:
                    self.logger.debug(
                        "audio_loop_stats",
                        extra={
                            "session_id": self.session.session_id if self.session else None,
                            "loops": loop_count,
                            "chunks": chunk_count,
                            "total_chunks": self._chunks_processed,
                            "stream_time": round(stream_time, 3),
                        },
                    )
                loop_count = 0
                last_log_time = now

    def _audio_loop_parallel(self) -> None:
        """Parallel audio processing loop."""
        assert self.audio_source is not None
        assert self.chunker is not None
        assert self._processing_executor is not None

        stream_time = 0.0
        last_health_emit = 0.0
        loop_count = 0
        last_log_time = time.monotonic()

        while not self._stop_event.is_set():
            # Check pause
            if self._pause_event.is_set():
                time.sleep(0.1)
                continue

            samples = self.audio_source.read(timeout=0.02)
            loop_count += 1

            if samples is None:
                continue

            stream_time += len(samples) / self.settings.sample_rate
            self._stream_time = stream_time

            chunks = self.chunker.push(samples, stream_time)
            chunk_count = len(chunks)
            self._chunks_processed += chunk_count

            if self.session:
                self.session.health.audio_stream_active = True
                self.session.health.dropped_frames = self.audio_source.dropped_frames

            # Record audio if enabled
            if self.audio_recorder:
                self.audio_recorder.write(samples)

            # Process chunks in parallel
            for chunk in chunks:
                with self._pending_lock:
                    self._pending_chunks += 1
                self._processing_executor.submit(self._process_chunk, chunk)

            # Detect chapters
            if self.chapter_detector:
                chapter = self.chapter_detector.process(samples, stream_time)
                if chapter:
                    self._chapters.append(chapter)
                    self._emit_chapter(chapter)

            # Health and progress
            now = time.monotonic()
            if now - last_health_emit > 0.1:
                self._maybe_rebuild_outputs()
                self._emit_health()
                last_health_emit = now

            self._maybe_report_progress()

            # Logging
            if now - last_log_time >= 1.0:
                with self._pending_lock:
                    pending = self._pending_chunks

                if self.logger:
                    self.logger.debug(
                        "audio_loop_stats",
                        extra={
                            "session_id": self.session.session_id if self.session else None,
                            "loops": loop_count,
                            "chunks": chunk_count,
                            "pending": pending,
                            "stream_time": round(stream_time, 3),
                        },
                    )
                loop_count = 0
                last_log_time = now

    def _process_chunk(self, chunk: Any) -> None:
        """Process a single chunk."""
        try:
            if self.transcriber and not self._stop_event.is_set():
                self.transcriber.submit(chunk)
        finally:
            with self._pending_lock:
                self._pending_chunks -= 1

    def _handle_segment(self, segment: TranscriptSegment) -> None:
        """Handle a new transcript segment."""
        if self.session is None or self.writer is None:
            return

        self.session.segments.append(segment)
        self._apply_overlap_dedupe(segment)

        if segment.suppressed:
            self.session.suppressed_segments.append(segment)

        self.session.health.last_transcript_at = utc_now()
        self.writer.append_segment(segment)

        # STEM processing
        if self.session_config.enable_stem:
            self._outputs_dirty = True
            self._rebuild_outputs_incremental()

        # Callbacks
        with self._callback_lock:
            callback = self._on_segment
        if callback:
            callback(segment)

        self._emit_health()
        self._emit_state()

        if self.logger:
            self.logger.debug(
                "segment_processed",
                extra={
                    "session_id": self.session.session_id,
                    "segment_index": len(self.session.segments) - 1,
                    "text": segment.display_text[:80] if segment.display_text else "",
                    "confidence": round(segment.confidence, 3),
                },
            )

    def _handle_partial(self, text: str, start: float, end: float) -> None:
        """Handle partial transcript."""
        with self._callback_lock:
            callback = self._on_partial
        if callback and not self._stop_event.is_set():
            callback(text, start, end)

    def _handle_health(self, health: SessionHealth) -> None:
        """Handle health update from transcriber."""
        with self._session_lock:
            session = self.session

        if session is None:
            with self._callback_lock:
                callback = self._on_health
            if callback:
                callback(health, 0.0)
            return

        # Update session health
        session.health.gpu_mode = health.gpu_mode
        session.health.execution_mode = health.execution_mode
        session.health.model_runtime_device = health.model_runtime_device
        session.health.last_transcript_at = health.last_transcript_at
        session.health.queue_depth = health.queue_depth
        session.health.dropped_stt_chunks = health.dropped_stt_chunks
        session.health.stt_backpressure_state = health.stt_backpressure_state
        session.health.estimated_backlog_seconds = health.estimated_backlog_seconds
        session.health.last_error = health.last_error
        session.health.last_warning = health.last_warning

        if self.audio_source:
            session.health.audio_backend = self.audio_source.backend_name
            session.health.audio_backend_fallbacks = list(self.audio_source.backend_fallbacks)

        self._emit_health()

    def _handle_error(self, exc: Exception) -> None:
        """Handle errors from audio/transcriber components."""
        error_message = str(exc)
        error_type = "runtime"

        if "audio" in error_message.lower() or "device" in error_message.lower():
            error_type = "audio_device"
        elif any(keyword in error_message.lower() for keyword in ["cuda", "gpu", "cublas"]):
            error_type = "gpu_runtime"

        if self.logger:
            self.logger.exception(
                "runtime_error",
                extra={
                    "session_id": self.session.session_id if self.session else None,
                    "error_type": error_type,
                    "error": error_message,
                },
            )

        if self.session:
            self.session.health.last_error = error_message
            self.session.status = "error"
            self.session.health.audio_stream_active = False

            if error_type == "audio_device":
                self.session.health.last_warning = (
                    f"Audio device error: {error_message}. "
                    "Session artifacts preserved. Reconnect the device to resume."
                )
            elif error_type == "gpu_runtime":
                self.session.health.last_warning = (
                    f"GPU runtime error: {error_message}. "
                    "Session artifacts preserved. Check CUDA installation or switch to CPU mode."
                )

            if self.writer:
                self.writer.write_metadata()
                self.writer.append_note(
                    f"\n\n[Runtime Error - {error_type.upper()}]\n{error_message}\n"
                )

            self._rebuild_outputs(force=True)
            self._emit_health()
            self._emit_state()

    def _apply_overlap_dedupe(self, segment: TranscriptSegment) -> None:
        """Apply overlap-based deduplication."""
        if self.session is None or segment.suppressed:
            return

        normalized = self._normalize_text(segment.display_text)
        if not normalized:
            return

        duplicates = 0
        for previous in reversed(self.session.segments[:-1]):
            if previous.suppressed:
                continue
            if (segment.start - previous.start) > 10.0:
                break
            if self._normalize_text(previous.display_text) == normalized:
                duplicates += 1
                if duplicates >= 1:
                    segment.suppressed = True
                    segment.quality_label = "junk" if segment.confidence < 0.55 else "weak"
                    segment.suppression_reasons.append("overlap-duplicate")
                    segment.review_flag = True
                    segment.review_reasons.append("overlap-duplicate")
                    return

    def _rebuild_outputs(self, *, force: bool = False) -> None:
        """Rebuild all output files."""
        if self.session is None or self.writer is None:
            return

        if not force and not self._outputs_dirty:
            return

        visible = [s for s in self.session.segments if not s.suppressed]
        bundle = self.note_processor.build(visible)

        self.session.formulas = bundle.formulas
        self.session.needs_review = bundle.needs_review
        self._last_notes_bundle = bundle

        self.writer.write_outputs(
            notes_markdown=bundle.notes_markdown,
            formulas=bundle.formulas,
            highlights_text=bundle.highlights_text,
        )

        self._last_rebuild_at = time.monotonic()
        self._outputs_dirty = False
        self._last_processed_segment_index = len(self.session.segments) - 1

    def _rebuild_outputs_incremental(self) -> None:
        """Incrementally rebuild outputs."""
        if self.session is None or self.writer is None:
            return

        if self._last_processed_segment_index < 0:
            self._rebuild_outputs(force=True)
            return

        new_segments = [
            s
            for i, s in enumerate(self.session.segments)
            if i > self._last_processed_segment_index and not s.suppressed
        ]

        if not new_segments:
            return

        existing = [
            s
            for s in self.session.segments[: self._last_processed_segment_index + 1]
            if not s.suppressed
        ]

        bundle = self.note_processor.build_incremental(
            existing_segments=existing,
            new_segments=new_segments,
            existing_formulas=self.session.formulas,
            existing_needs_review=self.session.needs_review,
        )

        self.session.formulas = bundle.formulas
        self.session.needs_review = bundle.needs_review
        self._last_notes_bundle = bundle

        self.writer.write_outputs(
            notes_markdown=bundle.notes_markdown,
            formulas=bundle.formulas,
            highlights_text=bundle.highlights_text,
        )

        self._last_rebuild_at = time.monotonic()
        self._outputs_dirty = False
        self._last_processed_segment_index = len(self.session.segments) - 1

    def _maybe_rebuild_outputs(self) -> None:
        """Maybe rebuild outputs based on time."""
        if not self._outputs_dirty:
            return
        if (time.monotonic() - self._last_rebuild_at) < self.settings.output_refresh_seconds:
            return
        self._rebuild_outputs(force=True)

    def _maybe_report_progress(self) -> None:
        """Maybe report progress based on interval."""
        if not self._on_progress:
            return

        now = time.monotonic()
        interval = self.session_config.progress_report_interval_seconds

        if now - self._last_progress_report >= interval:
            progress = self.get_progress()

            with self._callback_lock:
                callback = self._on_progress
            if callback:
                callback(progress)

            self._last_progress_report = now

    def _emit_health(self) -> None:
        """Emit health update."""
        with self._session_lock:
            session = self.session

        if session is None:
            return

        if self.audio_source:
            session.health.dropped_frames = self.audio_source.dropped_frames
            session.health.audio_backend = self.audio_source.backend_name
            meter_value = self.meter.update(self.audio_source.level_rms)
        else:
            meter_value = 0.0

        with self._pending_lock:
            pending = self._pending_chunks

        with self._callback_lock:
            callback = self._on_health

        if callback:
            callback(session.health, meter_value)

    def _emit_state(self) -> None:
        """Emit state update."""
        with self._session_lock:
            session = self.session

        if session:
            with self._callback_lock:
                callback = self._on_state
            if callback:
                callback(session)

    def _emit_chapter(self, chapter: Chapter) -> None:
        """Emit chapter detection."""
        with self._callback_lock:
            callback = self._on_chapter
        if callback:
            callback(chapter)

    def _cleanup_on_error(self) -> None:
        """Cleanup resources on error."""
        if self.session:
            self.session.status = "error"
            self.session.health.audio_stream_active = False

        self.audio_source = None
        self.transcriber = None
        self._audio_thread = None
        self._processing_executor = None

    def _write_extended_metadata(self) -> None:
        """Write extended session metadata to disk."""
        if self.session is None or self.extended_metadata is None:
            return

        metadata_path = self.session.output_dir / "metadata.json"
        data = {
            "session": self.session.to_metadata_dict(),
            "extended": self.extended_metadata.to_dict(),
            "config": {
                "export_formats": self.session_config.export_formats,
                "auto_segment": self.session_config.auto_segment,
                "save_audio": self.session_config.save_audio,
                "enable_stem": self.session_config.enable_stem,
            },
            "chapters": [c.to_dict() for c in self._chapters],
            "notes_count": len(self._session_notes),
        }

        temp_path = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(metadata_path)

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to slug format."""
        lowered = "".join(c.lower() if c.isalnum() else "-" for c in text)
        parts = [p for p in lowered.split("-") if p]
        return "-".join(parts) or f"session-{int(time.time())}"

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for deduplication."""
        return " ".join(
            "".join(c.lower() if c.isalnum() or c.isspace() else " " for c in text).split()
        )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration as HH:MM:SS."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @staticmethod
    def _get_language_warning(language_mode: str) -> str | None:
        """Get warning message for language mode."""
        if language_mode == "auto":
            return "Auto language detection may increase latency. Using optimized path for Hindi/English."
        if language_mode in ("hi", "hin"):
            return "Hindi mode active. Using optimized transcription parameters."
        return None

    def shutdown(self) -> None:
        """Shutdown the handler and cleanup resources."""
        if self.session and self.session.status == "running":
            self.stop_session()

        if self.export_manager:
            self.export_manager.shutdown(wait=True)

        if self.logger:
            self.logger.debug("system_session_handler_shutdown")


# =============================================================================
# Factory Functions
# =============================================================================


def create_system_session_handler(
    settings: AppSettings | None = None,
    **config_kwargs: Any,
) -> SystemSessionHandler:
    """Factory function to create a system session handler.

    Args:
        settings: Application settings (uses defaults if None)
        **config_kwargs: Session configuration options

    Returns:
        Configured SystemSessionHandler instance
    """
    if settings is None:
        settings = AppSettings()

    session_config = SystemSessionConfig(**config_kwargs)
    return SystemSessionHandler(settings, session_config)


def load_session_from_disk(session_dir: Path) -> dict[str, Any]:
    """Load a session from disk.

    Args:
        session_dir: Path to session directory

    Returns:
        Dictionary containing session data
    """
    metadata_path = session_dir / "metadata.json"
    session_path = session_dir / "session.json"

    result = {
        "session_dir": str(session_dir),
        "metadata": None,
        "segments": [],
        "formulas": [],
    }

    # Load metadata
    if metadata_path.exists():
        try:
            result["metadata"] = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to parse session metadata: {e}")
    elif session_path.exists():
        try:
            result["metadata"] = {"session": json.loads(session_path.read_text(encoding="utf-8"))}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to parse session data: {e}")

    # Load segments
    transcript_path = session_dir / "transcript.jsonl"
    if transcript_path.exists():
        with transcript_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        result["segments"].append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    # Load formulas
    formulas_path = session_dir / "formulas.json"
    if formulas_path.exists():
        try:
            result["formulas"] = json.loads(formulas_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to parse formulas data: {e}")

    return result
