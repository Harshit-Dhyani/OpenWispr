from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass(slots=True)
class AudioDeviceInfo:
    id: str
    name: str
    kind: str
    is_loopback: bool
    channels: int | None = None
    sample_rate: int | None = None


@dataclass(slots=True)
class TranscriptSegment:
    id: str
    start: float
    end: float
    text: str
    display_text: str
    language: str
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    compression_ratio: float | None = None
    confidence: float = 0.0
    review_flag: bool = False
    review_reasons: list[str] = field(default_factory=list)
    suppressed: bool = False
    suppression_reasons: list[str] = field(default_factory=list)
    quality_label: str = "ok"
    script_mismatch: bool = False
    source_chunk_started_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FormulaFinding:
    expression: str
    timestamp_start: float
    timestamp_end: float
    context: str
    confidence: float
    parseable: bool
    review_flag: bool
    reasons: list[str]
    variables: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SessionDocument:
    path: Path
    name: str
    added_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = str(self.path)
        payload["added_at"] = self.added_at.isoformat()
        return payload


@dataclass(slots=True)
class SessionHealth:
    audio_stream_active: bool = False
    gpu_mode: str = "unknown"
    execution_mode: str = "auto"
    model_runtime_device: str = "unknown"
    last_transcript_at: datetime | None = None
    dropped_frames: int = 0
    queue_depth: int = 0
    dropped_stt_chunks: int = 0
    stt_backpressure_state: str = "normal"
    estimated_backlog_seconds: float = 0.0
    last_error: str | None = None
    last_warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["last_transcript_at"] = (
            self.last_transcript_at.isoformat() if self.last_transcript_at else None
        )
        return payload


@dataclass(slots=True)
class DeviceProbeResult:
    sample_rate: int
    channels: int
    duration: float
    rms_mean: float
    rms_peak: float
    has_signal: bool
    dominant_channels: list[int]
    dropped_frames: int
    wav_path: Path

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["wav_path"] = str(self.wav_path)
        return payload


@dataclass(slots=True)
class SessionState:
    session_id: str
    title: str
    output_dir: Path
    model_name: str
    language_mode: str
    device_id: str
    live_mode: str = "balanced"
    execution_mode: str = "auto"
    started_at: datetime = field(default_factory=utc_now)
    status: str = "idle"
    segments: list[TranscriptSegment] = field(default_factory=list)
    formulas: list[FormulaFinding] = field(default_factory=list)
    needs_review: list[TranscriptSegment] = field(default_factory=list)
    suppressed_segments: list[TranscriptSegment] = field(default_factory=list)
    documents: list[SessionDocument] = field(default_factory=list)
    health: SessionHealth = field(default_factory=SessionHealth)

    @classmethod
    def create(
        cls,
        *,
        title: str,
        output_dir: Path,
        model_name: str,
        language_mode: str,
        device_id: str,
        live_mode: str,
        execution_mode: str,
    ) -> "SessionState":
        return cls(
            session_id=uuid4().hex,
            title=title,
            output_dir=output_dir,
            model_name=model_name,
            language_mode=language_mode,
            device_id=device_id,
            live_mode=live_mode,
            execution_mode=execution_mode,
            status="starting",
        )

    def to_metadata_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "output_dir": str(self.output_dir),
            "model_name": self.model_name,
            "language_mode": self.language_mode,
            "device_id": self.device_id,
            "live_mode": self.live_mode,
            "execution_mode": self.execution_mode,
            "started_at": self.started_at.isoformat(),
            "status": self.status,
            "documents": [document.to_dict() for document in self.documents],
            "segment_count": len([segment for segment in self.segments if not segment.suppressed]),
            "formula_count": len(self.formulas),
            "review_count": len(self.needs_review),
            "suppressed_count": len(self.suppressed_segments),
            "health": self.health.to_dict(),
        }
