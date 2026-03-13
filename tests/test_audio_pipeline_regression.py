"""Regression tests for audio pipeline audit findings.

Tests for issues found in the audio pipeline audit:
- VAD threshold consistency across pipelines
- Quality suppression thresholds
- Context word carryover for proper transcription
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

if "faster_whisper" not in sys.modules:
    fake = SimpleNamespace(WhisperModel=object)
    sys.modules["faster_whisper"] = fake

from app.config.constants import VADConstants


class TestVADThresholdConsistency:
    """Tests for VAD threshold consistency across pipelines."""

    def test_vad_threshold_consistency(self) -> None:
        """All VAD implementations should use same threshold from constants."""
        from app.audio.pipelines.wispr_pipeline import WisprPipelineConfig
        from app.audio.pipelines.system_pipeline import SystemPipelineConfig

        wispr_config = WisprPipelineConfig(
            vad_threshold_db=VADConstants.DEFAULT_THRESHOLD_DB,
        )

        assert wispr_config.vad_threshold_db == VADConstants.DEFAULT_THRESHOLD_DB

        system_config = SystemPipelineConfig(
            vad_threshold_db=VADConstants.DEFAULT_THRESHOLD_DB,
        )

        assert system_config.vad_threshold_db == VADConstants.DEFAULT_THRESHOLD_DB

        assert wispr_config.vad_threshold_db == system_config.vad_threshold_db

    def test_wispr_pipeline_uses_constant_threshold(self) -> None:
        """Wispr pipeline should use VADConstants for threshold."""
        from app.audio.pipelines.wispr_pipeline import WisprPipelineConfig

        config = WisprPipelineConfig()
        assert config.vad_threshold_db == VADConstants.DEFAULT_THRESHOLD_DB

    def test_system_pipeline_uses_explicit_threshold(self) -> None:
        """System pipeline should accept configurable threshold but default to constant."""
        from app.audio.pipelines.system_pipeline import SystemPipelineConfig

        config = SystemPipelineConfig()
        assert config.vad_threshold_db == -40.0


class TestQualitySuppression:
    """Tests for quality suppression threshold behavior."""

    def test_quality_suppression_not_aggressive(self) -> None:
        """JUNK threshold should not suppress valid speech (confidence >= 0.45)."""
        from app.config.constants import QualityConstants
        from app.stt.quality import assess_segment_quality

        result = assess_segment_quality(
            "This is a clear sentence with normal speech patterns.",
            confidence=0.85,
            language_mode="en",
            detected_language="en",
            avg_logprob=-0.2,
            no_speech_prob=0.05,
            compression_ratio=1.15,
        )

        assert result.quality_label != QualityConstants.QUALITY_LABEL_JUNK, (
            f"Valid speech with confidence should not be marked as junk. Got label: {result.quality_label}"
        )

    def test_junk_threshold_above_valid_speech(self) -> None:
        """JUNK threshold should be higher than valid speech threshold."""
        from app.config.constants import QualityConstants

        assert QualityConstants.JUNK_CONFIDENCE_THRESHOLD > 0.45, (
            "JUNK threshold should be > 0.45 to avoid suppressing valid speech"
        )

    def test_low_confidence_speech_not_suppressed(self) -> None:
        """Speech with moderate confidence should not be suppressed."""
        from app.config.constants import QualityConstants
        from app.stt.quality import assess_segment_quality

        result = assess_segment_quality(
            "Testing the microphone",
            confidence=0.50,
            language_mode="en",
            detected_language="en",
            avg_logprob=-0.5,
            no_speech_prob=0.1,
            compression_ratio=1.1,
        )

        assert result.quality_label != QualityConstants.QUALITY_LABEL_JUNK


class TestContextCarryover:
    """Tests for context word carryover sufficiency."""

    def test_context_carryover_sufficient(self) -> None:
        """Should have enough context words for proper transcription."""
        from app.stt.streaming_engine import ContextCarryoverManager, StreamingConfig

        config = StreamingConfig()
        manager = ContextCarryoverManager(config)

        sample_words = ["hello", "world", "this", "is", "a", "test", "sentence", "for", "context"]

        for word in sample_words:
            manager.push_word(word)

        context = manager.get_context()
        context_words = context.split() if context else []

        assert len(context_words) >= 3, (
            f"Context should have at least 3 words for proper transcription. "
            f"Got: {len(context_words)} words"
        )

    def test_default_context_words_config(self) -> None:
        """Default configuration should have reasonable context word count."""
        from app.stt.streaming_engine import StreamingConfig

        config = StreamingConfig()

        assert hasattr(config, "max_prefix_words")
        assert config.max_prefix_words >= 3, (
            "Should have at least 3 context words for transcription quality"
        )
