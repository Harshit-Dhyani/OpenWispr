"""Transcription mode definitions and configurations.

This module defines the two primary transcription modes (Hotkey and System)
along with their mode-specific default configurations.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import (
    AudioConstants,
    ModelConstants,
    VADConstants,
)

logger = logging.getLogger(__name__)

__all__ = [
    "TranscriptionMode",
    "ModeSettings",
    "WisprModeDefaults",
    "SystemModeDefaults",
    "ModeConfiguration",
    "get_mode_defaults",
    "get_mode_from_string",
]


class TranscriptionMode(str, Enum):
    """Enumeration of supported transcription modes."""

    WISPR = "wispr"
    SYSTEM = "system"

    def __repr__(self) -> str:
        return f"TranscriptionMode.{self.name}"

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        names = {
            TranscriptionMode.WISPR: "Hotkey Mode",
            TranscriptionMode.SYSTEM: "System Mode",
        }
        return names.get(self, self.value)

    @property
    def description(self) -> str:
        """Get mode description."""
        descriptions = {
            TranscriptionMode.WISPR: "Hotkey-triggered microphone dictation with low latency",
            TranscriptionMode.SYSTEM: "Full system audio capture for PC audio and videos",
        }
        return descriptions.get(self, "")


class ModeSettings(BaseModel):
    """Mode-specific transcription settings with validation.

    Attributes:
        model_name: Whisper model size (tiny, base, small, medium, large-v3)
        beam_size: Beam search width for decoding
        vad_threshold: Voice Activity Detection energy threshold
        chunk_duration: Audio chunk duration in seconds
        overlap_ratio: Overlap between consecutive chunks
        compute_type: Computation precision (float16, int8, int8_float16)
        vad_enabled: Whether Voice Activity Detection is enabled
        vad_min_silence_ms: Minimum silence to consider end of speech
        vad_speech_pad_ms: Padding added to speech segments
        confidence_threshold: Minimum confidence for transcript segments
        enable_filler_filter: Remove filler words (um, uh)
        enable_hallucination_filter: Remove likely incorrect segments
        best_of: Number of candidates to consider during decoding
        temperature: Sampling temperature for generation
        hotkey_optimized: Optimize for quick hotkey-triggered sessions
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "model_name": "tiny",
                    "beam_size": 1,
                    "vad_threshold": -40.0,
                    "chunk_duration": 0.5,
                }
            ]
        },
    )

    model_name: str = Field(
        default="medium",
        description="Whisper model size",
        pattern="^(tiny|base|small|medium|large-v3|turbo)$",
    )
    beam_size: int = Field(
        default=ModelConstants.DEFAULT_BEAM_SIZE,
        ge=1,
        le=20,
        description="Beam search width",
    )
    vad_threshold: float = Field(
        default=VADConstants.DEFAULT_THRESHOLD_DB,
        ge=-60.0,
        le=-20.0,
        description="VAD energy threshold in dB",
    )
    chunk_duration: float = Field(
        default=AudioConstants.DEFAULT_CHUNK_SECONDS,
        ge=0.1,
        le=5.0,
        description="Audio chunk duration in seconds",
    )
    overlap_ratio: float = Field(
        default=AudioConstants.DEFAULT_OVERLAP_SECONDS / AudioConstants.DEFAULT_CHUNK_SECONDS,
        ge=0.0,
        le=0.5,
        description="Overlap between chunks as ratio",
    )
    compute_type: str = Field(
        default=ModelConstants.DEFAULT_COMPUTE_TYPE,
        description="Computation precision type",
        pattern="^(float16|int8|int8_float16)$",
    )
    vad_enabled: bool = Field(
        default=VADConstants.DEFAULT_FILTER_ENABLED,
        description="Enable Voice Activity Detection",
    )
    vad_min_silence_ms: int = Field(
        default=VADConstants.DEFAULT_MIN_SILENCE_MS,
        ge=0,
        le=5000,
        description="Minimum silence duration in ms",
    )
    vad_speech_pad_ms: int = Field(
        default=VADConstants.DEFAULT_SPEECH_PAD_MS,
        ge=0,
        le=1000,
        description="Speech padding in ms",
    )
    confidence_threshold: float = Field(
        default=ModelConstants.DEFAULT_CONFIDENCE_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    )
    enable_filler_filter: bool = Field(
        default=True,
        description="Filter filler words (um, uh)",
    )
    enable_hallucination_filter: bool = Field(
        default=True,
        description="Filter hallucinated segments",
    )
    best_of: int = Field(
        default=ModelConstants.DEFAULT_BEST_OF,
        ge=1,
        le=20,
        description="Number of candidates to consider",
    )
    temperature: float = Field(
        default=ModelConstants.DEFAULT_TEMPERATURE,
        ge=0.0,
        le=1.0,
        description="Sampling temperature",
    )
    hotkey_optimized: bool = Field(
        default=False,
        description="Optimize for hotkey-triggered sessions",
    )

    @field_validator("chunk_duration")
    @classmethod
    def validate_chunk_duration(cls, v: float) -> float:
        """Validate chunk duration is reasonable for the model."""
        if v < 0.1:
            logger.warning("Chunk duration %.2fs may be too short for accurate transcription", v)
        elif v > 3.0:
            logger.warning("Chunk duration %.2fs may introduce noticeable latency", v)
        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModeSettings:
        """Create from dictionary with validation."""
        return cls(**data)


class WisprModeDefaults:
    """Default settings optimized for Hotkey Mode (hotkey/microphone).

    Optimized for:
    - Low latency transcription
    - Quick dictation sessions
    - Microphone input
    - Fast response times
    """

    MODEL_NAME: Literal["tiny", "base"] = "tiny"
    BEAM_SIZE: int = 1
    BEST_OF: int = 1
    VAD_THRESHOLD: float = -40.0
    CHUNK_DURATION: float = 0.5
    OVERLAP_RATIO: float = 0.1
    COMPUTE_TYPE: str = "int8"
    VAD_ENABLED: bool = True
    VAD_MIN_SILENCE_MS: int = 300
    VAD_SPEECH_PAD_MS: int = 100
    CONFIDENCE_THRESHOLD: float = 0.6
    ENABLE_FILLER_FILTER: bool = True
    ENABLE_HALLUCINATION_FILTER: bool = True
    TEMPERATURE: float = 0.0
    HOTKEY_OPTIMIZED: bool = True

    @classmethod
    def to_settings(cls) -> ModeSettings:
        """Create ModeSettings instance with hotkey defaults."""
        return ModeSettings(
            model_name=cls.MODEL_NAME,
            beam_size=cls.BEAM_SIZE,
            best_of=cls.BEST_OF,
            vad_threshold=cls.VAD_THRESHOLD,
            chunk_duration=cls.CHUNK_DURATION,
            overlap_ratio=cls.OVERLAP_RATIO,
            compute_type=cls.COMPUTE_TYPE,
            vad_enabled=cls.VAD_ENABLED,
            vad_min_silence_ms=cls.VAD_MIN_SILENCE_MS,
            vad_speech_pad_ms=cls.VAD_SPEECH_PAD_MS,
            confidence_threshold=cls.CONFIDENCE_THRESHOLD,
            enable_filler_filter=cls.ENABLE_FILLER_FILTER,
            enable_hallucination_filter=cls.ENABLE_HALLUCINATION_FILTER,
            temperature=cls.TEMPERATURE,
            hotkey_optimized=cls.HOTKEY_OPTIMIZED,
        )

    @classmethod
    def to_dict(cls) -> dict[str, Any]:
        """Convert to dictionary."""
        return cls.to_settings().to_dict()


class SystemModeDefaults:
    """Default settings optimized for System Mode (PC audio/video).

    Optimized for:
    - High accuracy transcription
    - Long-form content (videos, meetings)
    - System audio capture
    - Quality over speed
    """

    MODEL_NAME: Literal["small", "medium", "large-v3"] = "medium"
    BEAM_SIZE: int = 5
    BEST_OF: int = 5
    VAD_THRESHOLD: float = -35.0
    CHUNK_DURATION: float = 2.0
    OVERLAP_RATIO: float = 0.2
    COMPUTE_TYPE: str = "float16"
    VAD_ENABLED: bool = True
    VAD_MIN_SILENCE_MS: int = 500
    VAD_SPEECH_PAD_MS: int = 200
    CONFIDENCE_THRESHOLD: float = 0.7
    ENABLE_FILLER_FILTER: bool = True
    ENABLE_HALLUCINATION_FILTER: bool = True
    TEMPERATURE: float = 0.0
    HOTKEY_OPTIMIZED: bool = False

    @classmethod
    def to_settings(cls) -> ModeSettings:
        """Create ModeSettings instance with System defaults."""
        return ModeSettings(
            model_name=cls.MODEL_NAME,
            beam_size=cls.BEAM_SIZE,
            best_of=cls.BEST_OF,
            vad_threshold=cls.VAD_THRESHOLD,
            chunk_duration=cls.CHUNK_DURATION,
            overlap_ratio=cls.OVERLAP_RATIO,
            compute_type=cls.COMPUTE_TYPE,
            vad_enabled=cls.VAD_ENABLED,
            vad_min_silence_ms=cls.VAD_MIN_SILENCE_MS,
            vad_speech_pad_ms=cls.VAD_SPEECH_PAD_MS,
            confidence_threshold=cls.CONFIDENCE_THRESHOLD,
            enable_filler_filter=cls.ENABLE_FILLER_FILTER,
            enable_hallucination_filter=cls.ENABLE_HALLUCINATION_FILTER,
            temperature=cls.TEMPERATURE,
            hotkey_optimized=cls.HOTKEY_OPTIMIZED,
        )

    @classmethod
    def to_dict(cls) -> dict[str, Any]:
        """Convert to dictionary."""
        return cls.to_settings().to_dict()


class ModeConfiguration(BaseModel):
    """Complete mode configuration including metadata.

    This class encapsulates all configuration for a transcription mode,
    including the settings and runtime metadata.
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
    )

    mode: TranscriptionMode
    settings: ModeSettings
    is_active: bool = False
    display_name: str = ""
    description: str = ""

    def model_post_init(self, __context: Any) -> None:
        """Set computed fields after initialization."""
        if not self.display_name:
            self.display_name = self.mode.display_name
        if not self.description:
            self.description = self.mode.description

    def activate(self) -> None:
        """Mark this mode as active."""
        self.is_active = True
        logger.debug("%s activated", self.mode.value)

    def deactivate(self) -> None:
        """Mark this mode as inactive."""
        self.is_active = False
        logger.debug("%s deactivated", self.mode.value)


# ============================================
# Factory Functions
# ============================================
def get_mode_defaults(mode: TranscriptionMode | str) -> ModeSettings:
    """Get default settings for a specific mode.

    Args:
        mode: The transcription mode (enum or string)

    Returns:
        ModeSettings with mode-specific defaults

    Raises:
        ValueError: If mode is not recognized
    """
    mode_enum = get_mode_from_string(mode) if isinstance(mode, str) else mode

    if mode_enum == TranscriptionMode.WISPR:
        return WisprModeDefaults.to_settings()
    elif mode_enum == TranscriptionMode.SYSTEM:
        return SystemModeDefaults.to_settings()
    else:
        raise ValueError(f"Unknown transcription mode: {mode}")


def get_mode_from_string(value: str) -> TranscriptionMode:
    """Convert string to TranscriptionMode enum.

    Args:
        value: Mode string (case-insensitive)

    Returns:
        TranscriptionMode enum value

    Raises:
        ValueError: If string doesn't match any mode
    """
    try:
        return TranscriptionMode(value.lower())
    except ValueError as exc:
        valid_modes = [m.value for m in TranscriptionMode]
        raise ValueError(f"Invalid mode '{value}'. Valid modes: {valid_modes}") from exc


def get_mode_configuration(mode: TranscriptionMode | str) -> ModeConfiguration:
    """Get complete mode configuration.

    Args:
        mode: The transcription mode

    Returns:
        ModeConfiguration with settings and metadata
    """
    mode_enum = get_mode_from_string(mode) if isinstance(mode, str) else mode
    settings = get_mode_defaults(mode_enum)

    return ModeConfiguration(
        mode=mode_enum,
        settings=settings,
        display_name=mode_enum.display_name,
        description=mode_enum.description,
    )
