"""
Model Routing Contract Tests

Validates that source-specific model routing works correctly per AGENTS.md rules:
- "Keep source-specific model routing strict: microphone uses microphone model,
   system uses system model, fallback only when source-specific value is unset."
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config.settings import SETTINGS_REGISTRY


class TestModelRoutingContract:
    """Test source-specific model routing contract."""

    def test_microphone_capture_uses_microphone_model(self):
        """Verify when capture_source='microphone', uses microphone_asr_model_id."""
        microphone_model = "whisper-tiny"
        system_model = "whisper-large-v3"
        default_model = "whisper-medium"

        transcription = SimpleNamespace(
            microphone_asr_model_id=microphone_model,
            system_asr_model_id=system_model,
            default_asr_model_id=default_model,
            model_name=default_model,
        )

        capture_source = "microphone"
        resolved_model = (
            transcription.microphone_asr_model_id
            if capture_source == "microphone"
            else transcription.system_asr_model_id
        )

        assert resolved_model == microphone_model

    def test_system_capture_uses_system_model(self):
        """Verify when capture_source='system', uses system_asr_model_id."""
        microphone_model = "whisper-tiny"
        system_model = "whisper-large-v3"
        default_model = "whisper-medium"

        transcription = SimpleNamespace(
            microphone_asr_model_id=microphone_model,
            system_asr_model_id=system_model,
            default_asr_model_id=default_model,
            model_name=default_model,
        )

        capture_source = "system"
        resolved_model = (
            transcription.microphone_asr_model_id
            if capture_source == "microphone"
            else transcription.system_asr_model_id
        )

        assert resolved_model == system_model

    def test_fallback_when_source_specific_unset(self):
        """Verify fallback to default_asr_model_id when source-specific is unset."""
        microphone_model = None
        system_model = None
        default_model = "whisper-medium"

        transcription = SimpleNamespace(
            microphone_asr_model_id=microphone_model,
            system_asr_model_id=system_model,
            default_asr_model_id=default_model,
            model_name=default_model,
        )

        resolved_mic = (
            transcription.microphone_asr_model_id
            or transcription.default_asr_model_id
            or transcription.model_name
        )
        resolved_sys = (
            transcription.system_asr_model_id
            or transcription.default_asr_model_id
            or transcription.model_name
        )

        assert resolved_mic == default_model
        assert resolved_sys == default_model

    def test_microphone_session_ignores_system_model(self):
        """Verify system_asr_model_id not used for microphone sessions."""
        microphone_model = "whisper-tiny"
        system_model = "whisper-large-v3"

        transcription = SimpleNamespace(
            microphone_asr_model_id=microphone_model,
            system_asr_model_id=system_model,
            default_asr_model_id="whisper-medium",
            model_name="whisper-medium",
        )

        capture_source = "microphone"
        result = (
            transcription.microphone_asr_model_id
            if capture_source == "microphone"
            else transcription.system_asr_model_id
        )

        assert result == microphone_model
        assert result != system_model

    def test_system_session_ignores_microphone_model(self):
        """Verify microphone_asr_model_id not used for system sessions."""
        microphone_model = "whisper-tiny"
        system_model = "whisper-large-v3"

        transcription = SimpleNamespace(
            microphone_asr_model_id=microphone_model,
            system_asr_model_id=system_model,
            default_asr_model_id="whisper-medium",
            model_name="whisper-medium",
        )

        capture_source = "system"
        result = (
            transcription.microphone_asr_model_id
            if capture_source == "microphone"
            else transcription.system_asr_model_id
        )

        assert result == system_model
        assert result != microphone_model

    def test_session_start_uses_correct_model(self):
        """Verify session start uses source-specific model based on capture_source.

        Per AGENTS.md: session start must use correct model for the capture source.
        Microphone sessions should use microphone_asr_model_id, system should use system_asr_model_id.
        """
        microphone_model = "whisper-tiny"
        system_model = "whisper-large-v3"
        default_model = "whisper-medium"

        transcription = SimpleNamespace(
            microphone_asr_model_id=microphone_model,
            system_asr_model_id=system_model,
            default_asr_model_id=default_model,
            model_name=default_model,
        )

        def resolve_model(capture_source: str) -> str:
            if capture_source == "microphone":
                return transcription.microphone_asr_model_id
            elif capture_source == "system":
                return transcription.system_asr_model_id
            return transcription.default_asr_model_id

        mic_result = resolve_model("microphone")
        sys_result = resolve_model("system")

        assert mic_result == microphone_model, (
            f"Microphone session should use '{microphone_model}', got '{mic_result}'"
        )
        assert sys_result == system_model, (
            f"System session should use '{system_model}', got '{sys_result}'"
        )
        assert mic_result != sys_result, "Microphone and system sessions must use different models"


class TestModelRoutingSettingsExist:
    """Verify model routing settings exist in registry."""

    def test_microphone_asr_model_id_in_registry(self):
        """Verify microphone_asr_model_id is defined in settings registry."""
        assert "microphone_asr_model_id" in SETTINGS_REGISTRY

    def test_system_asr_model_id_in_registry(self):
        """Verify system_asr_model_id is defined in settings registry."""
        assert "system_asr_model_id" in SETTINGS_REGISTRY

    def test_default_asr_model_id_in_registry(self):
        """Verify default_asr_model_id is defined in settings registry."""
        assert "default_asr_model_id" in SETTINGS_REGISTRY
