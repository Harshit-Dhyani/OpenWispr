"""Core data models for the OpenWispr application.

Provides shared dataclasses for audio devices, transcripts, session state,
health monitoring, and device probing. These models are used throughout
the application backend and exposed via API endpoints.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(tz=UTC)


@dataclass(slots=True)
class AudioDeviceInfo:
    """Audio device descriptor for input/output devices.

    Attributes:
        id: Unique device identifier (platform-specific)
        name: Human-readable device name
        kind: Device category (e.g., 'audioinput', 'audiooutput')
        is_loopback: Whether this is a loopback/secondary sound device
        channels: Number of audio channels (None if unknown)
        sample_rate: Sample rate in Hz (None if unknown)
        backend_candidates: List of audio backends that might work with this device
        is_input: Whether device supports audio input
        is_output: Whether device supports audio output
        supports_loopback: Whether device supports loopback capture (None if unknown)
        driver: Audio driver name (e.g., 'WASAPI', 'DirectSound', None if unknown)
    """

    id: str
    name: str
    kind: str
    is_loopback: bool
    channels: int | None = None
    sample_rate: int | None = None
    backend_candidates: list[str] = field(default_factory=list)
    is_input: bool = False
    is_output: bool = False
    supports_loopback: bool | None = None
    driver: str | None = None


@dataclass(slots=True)
class TranscriptSegment:
    """Single transcribed segment with metadata.

    Attributes:
        id: Unique segment identifier
        start: Segment start time in seconds (relative to session start)
        end: Segment end time in seconds
        text: Raw transcribed text
        display_text: Text formatted for display (with formatting markers)
        language: Detected/transcribed language code (e.g., 'en', 'de')
        avg_logprob: Average log probability from STT model (None if unavailable)
        no_speech_prob: Probability that segment contains no speech (None if unavailable)
        compression_ratio: Audio compression ratio indicator (None if unavailable)
        confidence: Confidence score from 0.0 to 1.0
        review_flag: Whether segment is flagged for user review
        review_reasons: List of reasons why segment was flagged for review
        suppressed: Whether segment was suppressed from final output
        suppression_reasons: List of reasons why segment was suppressed
        quality_label: Quality classification ('ok', 'low', 'very_low')
        script_mismatch: Whether display_text differs significantly from text
        source_chunk_started_at: Original source chunk timestamp (None if unavailable)
    """

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
        """Convert segment to dictionary representation."""
        return asdict(self)


@dataclass(slots=True)
class FormulaFinding:
    """Detected mathematical formula within a transcript.

    Attributes:
        expression: The detected formula expression as string
        timestamp_start: Start time of formula in transcript (seconds)
        timestamp_end: End time of formula in transcript (seconds)
        context: Surrounding transcript text for context
        confidence: Detection confidence from 0.0 to 1.0
        parseable: Whether the expression was successfully parsed
        review_flag: Whether this finding needs user review
        reasons: List of detection/processing reasons
        variables: List of variable names detected in formula
        units: List of units detected in formula
    """

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
        """Convert finding to dictionary representation."""
        return asdict(self)


@dataclass(slots=True)
class SessionDocument:
    """Document attached to a recording session.

    Attributes:
        path: Path to the document file
        name: Document display name
        added_at: Timestamp when document was added to session
    """

    path: Path
    name: str
    added_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert document to dictionary representation."""
        payload = asdict(self)
        payload["path"] = str(self.path)
        payload["added_at"] = self.added_at.isoformat()
        return payload


@dataclass(slots=True)
class SessionHealth:
    """Runtime health and performance metrics for a session.

    Attributes:
        audio_stream_active: Whether audio stream is currently flowing
        gpu_mode: GPU acceleration mode ('cuda', 'cpu', 'unknown')
        execution_mode: Model execution mode ('auto', 'gpu', 'cpu')
        model_runtime_device: Actual device model runs on ('cuda', 'cpu', 'unknown')
        last_transcript_at: Timestamp of most recent transcript (None if none yet)
        dropped_frames: Number of dropped audio frames
        queue_depth: Current depth of audio processing queue
        dropped_stt_chunks: Number of dropped STT processing chunks
        stt_backpressure_state: STT processing backpressure state ('normal', 'high', 'critical')
        estimated_backlog_seconds: Estimated audio backlog in seconds
        last_error: Last error message (None if no recent errors)
        last_warning: Last warning message (None if no recent warnings)
        audio_backend: Currently active audio backend name
        audio_backend_fallbacks: List of fallback backends attempted
        audio_device_error: Audio device error message (None if no error)
    """

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
    audio_backend: str | None = None
    audio_backend_fallbacks: list[str] = field(default_factory=list)
    audio_device_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert health metrics to dictionary representation."""
        payload = asdict(self)
        payload["last_transcript_at"] = (
            self.last_transcript_at.isoformat() if self.last_transcript_at else None
        )
        return payload


@dataclass(slots=True)
class DeviceProbeResult:
    """Result of probing an audio device for signal quality.

    Attributes:
        backend: Audio backend used for probing
        sample_rate: Sample rate in Hz used during probe
        channels: Number of channels probed
        duration: Probe duration in seconds
        rms_mean: Mean RMS energy level
        rms_peak: Peak RMS energy level
        has_signal: Whether a valid audio signal was detected
        dominant_channels: List of channel indices with strongest signal
        dropped_frames: Number of frames dropped during probe
        wav_path: Path to recorded WAV file from probe
    """

    backend: str
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
        """Convert probe result to dictionary representation."""
        payload = asdict(self)
        payload["wav_path"] = str(self.wav_path)
        return payload


@dataclass(slots=True)
class SessionState:
    """Complete state for a recording session.

    Attributes:
        session_id: Unique session identifier
        title: User-defined session title
        output_dir: Directory for session output files
        model_name: STT model name in use
        language_mode: Language mode or code
        device_id: Selected audio device ID
        live_mode: Live transcription mode ('balanced', 'fast', 'accurate')
        execution_mode: Model execution mode ('auto', 'gpu', 'cpu')
        started_at: Session start timestamp
        status: Current session status ('idle', 'starting', 'recording', 'stopped')
        segments: List of transcribed segments
        formulas: List of detected formula findings
        needs_review: Segments flagged for review
        suppressed_segments: Segments that were suppressed
        documents: Documents attached to session
        health: Current session health metrics
    """

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
    ) -> SessionState:
        """Create a new session with generated ID and default values."""
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
        """Convert session to metadata dictionary for export."""
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
