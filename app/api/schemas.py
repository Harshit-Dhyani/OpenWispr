from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class StartSessionRequest(BaseModel):
    title: str
    output_root: str
    model_name: str
    language_mode: str
    capture_source: Literal["microphone", "system"] | None = None
    device_id: str | None = None
    live_mode: str = "balanced"
    execution_mode: str = "auto"
    vad_threshold: float | None = None
    vad_min_silence_ms: int | None = None
    vad_speech_pad_ms: int | None = None


class AttachPdfRequest(BaseModel):
    path: str


class PreloadModelRequest(BaseModel):
    model_name: str
    execution_mode: str = "auto"


class ModelSelectionRequest(BaseModel):
    category: str
    model_id: str


class RefinementModeRequest(BaseModel):
    mode: str
