from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRANSCRIPTA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Transcripta"
    host: str = "127.0.0.1"
    port: int = 8765
    sample_rate: int = 16_000
    channels: int = 1
    chunk_seconds: float = 3.2
    overlap_seconds: float = 0.6
    capture_block_seconds: float = 0.03
    meter_decay: float = 0.85
    export_root: Path = Field(default_factory=lambda: Path.cwd() / "sessions")
    log_level: str = "INFO"
    default_model: str = "small"
    device: str = "auto"
    compute_type: str = "int8"
    default_language: str = "auto"
    default_live_mode: str = "balanced"
    default_execution_mode: str = "auto"

    # Auto-optimization settings
    auto_optimize: bool = True
    optimization_mode: str = "balanced"  # maximum, balanced, speed, low_memory

    # Advanced audio settings (auto-populated)
    chunk_duration: float = 1.0
    overlap_ratio: float = 0.2
    vad_threshold: float = -40.0
    vad_min_silence_ms: int = 200

    # Advanced quality settings
    confidence_threshold: float = 0.70
    enable_filler_filter: bool = True
    enable_hallucination_filter: bool = True
    min_segment_length: int = 3

    # Ultra-low latency settings
    vad_filter: bool = True
    condition_on_previous_text: bool = True  # Disabled for speed in ultra mode
    compression_ratio_threshold: float | None = None  # Disabled for speed
    vad_threshold: float = 0.5
    vad_min_silence_ms: int = 200
    vad_speech_pad_ms: int = 200
    beam_size: int = 1
    best_of: int = 1
    temperature: float = 0.0
    download_root: Path = Field(default_factory=lambda: Path.cwd() / "models")
    max_queue_items: int = 16
    output_refresh_seconds: float = 0.5
    capture_device_id: str | None = None


LIVE_MODE_PROFILES: dict[str, dict[str, float]] = {
    "ultra": {"chunk_seconds": 0.1, "overlap_seconds": 0.02},  # 100ms - fastest
    "realtime": {"chunk_seconds": 0.2, "overlap_seconds": 0.04},  # 200ms - fast
    "low_latency": {"chunk_seconds": 0.5, "overlap_seconds": 0.1},  # 500ms
    "balanced": {"chunk_seconds": 1.0, "overlap_seconds": 0.2},  # 1s - default
    "high_accuracy": {"chunk_seconds": 2.0, "overlap_seconds": 0.4},  # 2s
}


def resolve_live_profile(mode: str, settings: AppSettings) -> dict[str, float]:
    profile = LIVE_MODE_PROFILES.get(mode)
    if profile is None:
        return {
            "chunk_seconds": settings.chunk_seconds,
            "overlap_seconds": settings.overlap_seconds,
        }
    return dict(profile)
