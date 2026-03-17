"""Pydantic schemas for API request and response validation.

This module defines all request and response models used by the FastAPI
endpoints. Schemas are organized by feature area:

Session Schemas:
- StartSessionRequest: Parameters for starting a transcription session
- AttachPdfRequest: PDF attachment for context-aware transcription
- PreloadModelRequest: Model preloading parameters
- ModelSelectionRequest: Model selection by category and ID
- RefinementModeRequest: Refinement mode configuration

Hotkey Schemas:
- HotkeyStartRequest: Parameters for starting hotkey transcription
- HotkeyStartResponse: Response from hotkey start
- HotkeyStopRequest: Parameters for stopping hotkey transcription
- HotkeyStopResponse: Response from hotkey stop
- HotkeyStatusResponse: Current hotkey session status
- HotkeyInjectRequest: Text injection request
- HotkeyInjectResponse: Text injection response
- HotkeyConfig: Hotkey configuration
- CoachPromptPreviewRequest: Coach prompt preview parameters

Dictionary Schemas:
- DictionaryEntryCreateRequest: Create dictionary entry
- DictionaryEntryUpdateRequest: Update dictionary entry

Snippet Schemas:
- SnippetCreateRequest: Create text snippet
- SnippetUpdateRequest: Update text snippet
- SnippetImportRequest: Bulk import snippets
- PreviewExpandRequest: Preview snippet expansion

Style Schemas:
- StyleProfileCreateRequest: Create style profile
- StyleProfileUpdateRequest: Update style profile
- StyleAssignmentRequest: Assign profile to context
- StylePreviewRequest: Preview style application

Text Transform Schemas:
- PreviewApplyRequest: Preview transformations
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class StartSessionRequest(BaseModel):
    title: str = Field(..., min_length=1)
    output_root: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1)
    language_mode: str = Field(..., min_length=1)
    capture_source: Literal["microphone", "system"] | None = None
    device_id: str | None = None
    live_mode: str = "balanced"
    execution_mode: Literal["auto", "gpu_only", "cpu_only"] = "auto"
    vad_threshold: float | None = None
    vad_min_silence_ms: int | None = None
    vad_speech_pad_ms: int | None = None


class AttachPdfRequest(BaseModel):
    path: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        p = Path(v)
        if not p.is_file() or p.suffix.lower() != ".pdf":
            raise ValueError("Must be a valid PDF file path")
        return str(p.resolve())


class PreloadModelRequest(BaseModel):
    model_name: str
    execution_mode: str = "auto"


class ModelSelectionRequest(BaseModel):
    category: str
    model_id: str


class RefinementModeRequest(BaseModel):
    mode: str


class SnippetCreateRequest(BaseModel):
    trigger: str = Field(..., min_length=1)
    expansion: str = Field(..., min_length=1)
    scope: str | None = None
    enabled: bool = True


class SnippetUpdateRequest(BaseModel):
    trigger: str | None = None
    expansion: str | None = None
    scope: str | None = None
    enabled: bool | None = None


class SnippetImportRequest(BaseModel):
    entries: list[dict]
    replace_existing: bool = False


class PreviewExpandRequest(BaseModel):
    text: str = ""


class StyleProfileCreateRequest(BaseModel):
    name: str = ""
    style_key: str = "custom"
    description: str = ""
    rules: dict = {}
    enabled: bool = True


class StyleProfileUpdateRequest(BaseModel):
    name: str | None = None
    style_key: str | None = None
    description: str | None = None
    rules: dict | None = None
    enabled: bool | None = None


class StyleAssignmentRequest(BaseModel):
    context: str = "other"
    profile_id: str = ""


class StylePreviewRequest(BaseModel):
    text: str = ""
    context: str = "other"
    profile_id: str | None = None


class DictionaryEntryCreateRequest(BaseModel):
    phrase: str = Field(..., min_length=1)
    replacement: str = Field(..., min_length=1)
    scope: str | None = None
    enabled: bool = True


class DictionaryEntryUpdateRequest(BaseModel):
    phrase: str | None = None
    replacement: str | None = None
    scope: str | None = None
    enabled: bool | None = None


class PreviewApplyRequest(BaseModel):
    text: str = ""


# Hotkey Schemas


class HotkeyStartRequest(BaseModel):
    capture_source: Literal["microphone", "system"] | None = None
    device_id: str | None = None
    model_name: str | None = None
    language_mode: str = "auto"
    execution_mode: str = "auto"
    transcription_mode: Literal["dictation", "literal", "session_paragraph"] = "dictation"


class HotkeyStartResponse(BaseModel):
    session_id: str
    status: str
    message: str = ""


class HotkeyStopRequest(BaseModel):
    mode: Literal["finish", "finish_and_paste", "cancel"] = "finish_and_paste"


class HotkeyStopResponse(BaseModel):
    session_id: str | None = None
    status: str = "idle"
    transcription_mode: Literal["dictation", "literal", "session_paragraph"] = "dictation"
    composed_text: str = ""
    final_transcription: str
    aggregated_raw_text: str = ""
    aggregated_clean_text: str = ""
    postprocessed_text: str = ""
    paste_text: str = ""
    live_paste_text: str = ""
    final_cleanup_applied: bool = False
    raw_transcription: str = ""
    refined_transcription: str | None = None
    coach_result: Any = None
    coach_status: str = "disabled"
    coach_display_source: str = "faithful"
    coach_error: str | None = None
    coach_cache_hit: bool = False
    debug_wav_path: str | None = None
    duration_ms: int = 0
    segment_count: int = 0
    source_backend: str = "unknown"
    language_used: str = "auto"
    refinement_mode: str = "off"
    refiner_model_id: str | None = None


class HotkeyStatusResponse(BaseModel):
    state: str = "idle"
    is_recording: bool = False
    partial_text: str = ""
    raw_partial_text: str = ""
    display_partial_text: str = ""
    audio_level: float = 0.0
    session_id: str | None = None
    correlation_id: str | None = None
    duration_ms: int = 0
    levels: list[float] | None = None


class HotkeyInjectRequest(BaseModel):
    text: str


class HotkeyInjectResponse(BaseModel):
    success: bool
    message: str = ""


class HotkeyConfig(BaseModel):
    chunk_seconds: float = 2.4
    overlap_seconds: float = 0.48
    vad_threshold: float = 0.5
    model_name: str | None = None
    language_mode: str = "auto"
    execution_mode: str = "auto"


class HotkeyConfigRequest(BaseModel):
    chunk_seconds: float | None = Field(None, ge=0)
    overlap_seconds: float | None = Field(None, ge=0)
    vad_threshold_db: float | None = None
    vad_min_silence_ms: int | None = Field(None, ge=0)
    vad_speech_pad_ms: int | None = Field(None, ge=0)
    confidence_threshold: float | None = Field(None, ge=0)
    enable_filler_filter: bool | None = None


class HotkeyConfigResponse(BaseModel):
    success: bool
    config: "HotkeyConfig"
    message: str = ""


class CoachPromptPreviewRequest(BaseModel):
    capture_source: Literal["microphone", "system"] = "microphone"
    original_text: str = ""
    language_mode: str = "auto"
    detail_level: Literal["compact", "standard", "deep"] = "compact"
    template_id: str = "default_english_coach"
    custom_user_template: str = ""
    overrides: dict[str, Any] = Field(default_factory=dict)
    privacy_mode: Literal["local_only", "allow_llm"] = "local_only"
    templates: list[dict[str, Any]] = Field(default_factory=list)
