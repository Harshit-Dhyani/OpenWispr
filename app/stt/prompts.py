"""Prompt text exports for STT transcription and refinement.

This module re-exports prompt constants from app.stt.refiner_prompts.
Canonical prompt source is refiner_prompts.py.
"""

from __future__ import annotations

from app.stt.refiner_prompts import (
    DEFAULT_PROFILE_INSTRUCTION,
    POLISHED_INTENSITY_INSTRUCTION,
    PROFILE_INSTRUCTIONS,
    PROMPT_PREFIX,
    STRICT_INTENSITY_INSTRUCTION,
    build_refiner_prompt,
)

__all__ = [
    "PROFILE_INSTRUCTIONS",
    "DEFAULT_PROFILE_INSTRUCTION",
    "STRICT_INTENSITY_INSTRUCTION",
    "POLISHED_INTENSITY_INSTRUCTION",
    "PROMPT_PREFIX",
    "build_refiner_prompt",
]
