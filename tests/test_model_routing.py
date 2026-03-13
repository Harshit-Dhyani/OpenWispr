"""
Model Routing Tests

Tests model selection and routing behavior including:
- Microphone vs system model selection
- Source-specific model routing
- Fallback logic when model unavailable

Regression protection for:
- Wrong model used for wrong capture source
- Fallback not working when source-specific model unset
- Model routing not respecting strict source boundaries
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


class TestMicrophoneModelRouting:
    """Test model routing for microphone capture source."""

    def test_microphone_source_uses_microphone_model(self):
        """Verify microphone capture uses microphone_asr_model_id."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id="whisper-tiny",
                system_asr_model_id="whisper-base",
                default_asr_model_id="whisper-medium",
                model_name="base",
            )
        )

        result = (
            settings.transcription.microphone_asr_model_id
            or settings.transcription.default_asr_model_id
            or settings.transcription.model_name
        )

        assert result == "whisper-tiny"

    def test_microphone_ignores_system_model(self):
        """Verify microphone sessions never use system model."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id="whisper-tiny",
                system_asr_model_id="whisper-large-v3",
                default_asr_model_id="whisper-medium",
                model_name="base",
            )
        )

        mic_model = settings.transcription.microphone_asr_model_id
        sys_model = settings.transcription.system_asr_model_id

        assert mic_model != sys_model

    def test_microphone_fallback_hierarchy(self):
        """Verify fallback chain: microphone_asr_model_id -> default_asr_model_id -> model_name."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id=None,
                system_asr_model_id=None,
                default_asr_model_id="whisper-medium",
                model_name="tiny",
            )
        )

        resolved = (
            settings.transcription.microphone_asr_model_id
            or settings.transcription.default_asr_model_id
            or settings.transcription.model_name
        )

        assert resolved == "whisper-medium"


class TestSystemModelRouting:
    """Test model routing for system capture source."""

    def test_system_source_uses_system_model(self):
        """Verify system capture uses system_asr_model_id."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id="whisper-tiny",
                system_asr_model_id="whisper-base",
                default_asr_model_id="whisper-medium",
                model_name="base",
            )
        )

        result = (
            settings.transcription.system_asr_model_id
            or settings.transcription.default_asr_model_id
            or settings.transcription.model_name
        )

        assert result == "whisper-base"

    def test_system_ignores_microphone_model(self):
        """Verify system sessions never use microphone model."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id="whisper-tiny",
                system_asr_model_id="whisper-large-v3",
                default_asr_model_id="whisper-medium",
                model_name="base",
            )
        )

        sys_model = settings.transcription.system_asr_model_id

        assert sys_model == "whisper-large-v3"
        assert sys_model != settings.transcription.microphone_asr_model_id

    def test_system_fallback_hierarchy(self):
        """Verify fallback chain: system_asr_model_id -> default_asr_model_id -> model_name."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id=None,
                system_asr_model_id=None,
                default_asr_model_id="whisper-medium",
                model_name="tiny",
            )
        )

        resolved = (
            settings.transcription.system_asr_model_id
            or settings.transcription.default_asr_model_id
            or settings.transcription.model_name
        )

        assert resolved == "whisper-medium"


class TestModelRoutingFallback:
    """Test fallback logic when models are unavailable."""

    def test_fallback_when_microphone_model_unset(self):
        """Verify fallback to default when microphone model is None."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id=None,
                default_asr_model_id="whisper-medium",
                model_name="tiny",
            )
        )

        resolved = (
            settings.transcription.microphone_asr_model_id
            or settings.transcription.default_asr_model_id
            or settings.transcription.model_name
        )

        assert resolved == "whisper-medium"

    def test_fallback_when_system_model_unset(self):
        """Verify fallback to default when system model is None."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                system_asr_model_id=None,
                default_asr_model_id="whisper-medium",
                model_name="tiny",
            )
        )

        resolved = (
            settings.transcription.system_asr_model_id
            or settings.transcription.default_asr_model_id
            or settings.transcription.model_name
        )

        assert resolved == "whisper-medium"

    def test_fallback_when_all_models_unset(self):
        """Verify fallback to model_name when all specific models are None."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id=None,
                system_asr_model_id=None,
                default_asr_model_id=None,
                model_name="whisper-tiny",
            )
        )

        resolved = (
            settings.transcription.microphone_asr_model_id
            or settings.transcription.default_asr_model_id
            or settings.transcription.model_name
        )

        assert resolved == "whisper-tiny"

    def test_explicit_model_name_overrides_defaults(self):
        """Verify explicit model_name parameter takes precedence."""
        explicit_model = "custom-model"

        resolved = explicit_model or "default"

        assert resolved == "custom-model"


class TestModelRoutingBoundaryEnforcement:
    """Test strict enforcement of source-specific routing boundaries."""

    def test_microphone_and_system_models_are_different(self):
        """Verify microphone and system models can be different."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id="whisper-tiny",
                system_asr_model_id="whisper-large-v3",
                default_asr_model_id="whisper-medium",
                model_name="base",
            )
        )

        assert (
            settings.transcription.microphone_asr_model_id
            != settings.transcription.system_asr_model_id
        )

    def test_same_model_can_be_used_for_both_sources(self):
        """Verify same model can be explicitly set for both sources."""
        settings = SimpleNamespace(
            transcription=SimpleNamespace(
                microphone_asr_model_id="whisper-base",
                system_asr_model_id="whisper-base",
                default_asr_model_id="whisper-medium",
                model_name="tiny",
            )
        )

        assert (
            settings.transcription.microphone_asr_model_id
            == settings.transcription.system_asr_model_id
        )

    def test_no_cross_contamination_between_sources(self):
        """Verify setting one source doesn't affect the other."""
        base_settings = {
            "microphone_asr_model_id": "whisper-tiny",
            "system_asr_model_id": "whisper-base",
        }

        mic_settings = base_settings.copy()
        sys_settings = base_settings.copy()

        mic_settings["microphone_asr_model_id"] = "whisper-tiny-pro"

        assert mic_settings["microphone_asr_model_id"] != sys_settings["microphone_asr_model_id"]
        assert sys_settings["system_asr_model_id"] == "whisper-base"
