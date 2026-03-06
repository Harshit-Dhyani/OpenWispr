#!/usr/bin/env python3
"""Generate TypeScript constants from Python configuration.

This script reads the Python configuration files and generates
TypeScript equivalents for the frontend to use.

Run this script whenever you modify app/config/:
    python app/config/generate_ts.py
"""

import json
from pathlib import Path
from typing import Any

# Import Python constants from authoritative source
from app.config.constants import (
    AppConstants,
    SAMPLE_RATES,
    COMMON_FILLER_WORDS,
    HALLUCINATION_PHRASES,
    HALLUCINATION_CONFIDENCE_THRESHOLD,
    GPU_FALLBACK_KEYWORDS,
    LIVE_MODE_PROFILES,
    AudioConstants,
    VADConstants,
    ModelConstants,
    PerformanceConstants,
    SessionConstants,
    UIConstants,
    QualityConstants,
    ServerConstants,
    FastChunkerConstants,
    AudioCaptureConstants,
    HealthConstants,
    AutoOptimizationConstants,
    RefinerConstants,
)
from app.config.text import (
    MODEL_NAMES,
    MODEL_NAMES_SHORT,
    LIVE_MODE_LABELS,
    LIVE_MODE_DESCRIPTIONS,
    SETTING_LABELS,
    SETTING_DESCRIPTIONS,
    BUTTON_LABELS,
    STATUS_LABELS,
    ERROR_MESSAGES,
    TOOLTIPS,
    CATEGORY_LABELS,
    THEME_LABELS,
    COMPUTE_TYPE_LABELS,
    CAPTURE_MODE_LABELS,
    AUDIO_BACKEND_LABELS,
    SAMPLE_RATE_LABELS,
    FINISH_ACTION_LABELS,
    FLOATING_POSITION_LABELS,
    LOG_LEVEL_LABELS,
    OPTIMIZATION_PRESET_LABELS,
    PRESET_DESCRIPTIONS,
    REFINEMENT_MODE_LABELS,
    REFINEMENT_PROFILE_LABELS,
    REFINER_ENGINE_LABELS,
    TAB_LABELS,
    SECTION_HEADERS,
    UNIT_LABELS,
    HARDWARE_LABELS,
    METRIC_LABELS,
    SETTINGS_SECTION_TEXT,
)
from app.config.settings import FAKE_SETTINGS, SETTINGS_REGISTRY


def to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.capitalize() for x in components[1:])


def ts_literal(value: Any) -> str:
    """Render a Python value as a valid TypeScript literal."""
    return json.dumps(value, ensure_ascii=False)


def generate_constants_ts() -> str:
    """Generate TypeScript constants file."""
    lines = [
        "// Auto-generated from app/config/constants.py",
        "// Do not edit manually - run `python app/config/generate_ts.py` to regenerate",
        "",
        "// ============================================",
        "// App Constants",
        "// ============================================",
        "export const AppConstants = {",
        f"  APP_NAME: '{AppConstants.APP_NAME}' as const,",
        f"  APP_SLUG: '{AppConstants.APP_SLUG}' as const,",
        f"  LOCAL_API_TITLE_SUFFIX: '{AppConstants.LOCAL_API_TITLE_SUFFIX}' as const,",
        f"  DOWNLOAD_USER_AGENT: '{AppConstants.DOWNLOAD_USER_AGENT}' as const,",
        "} as const;",
        "",
        "// ============================================",
        "// Audio Constants",
        "// ============================================",
        "export const AudioConstants = {",
        f"  DEFAULT_SAMPLE_RATE: {AudioConstants.DEFAULT_SAMPLE_RATE},",
        f"  DEFAULT_CHANNELS: {AudioConstants.DEFAULT_CHANNELS},",
        f"  DEFAULT_CHUNK_SECONDS: {AudioConstants.DEFAULT_CHUNK_SECONDS},",
        f"  DEFAULT_OVERLAP_SECONDS: {AudioConstants.DEFAULT_OVERLAP_SECONDS},",
        f"  MIN_CHUNK_SECONDS: {AudioConstants.MIN_CHUNK_SECONDS},",
        f"  MAX_CHUNK_SECONDS: {AudioConstants.MAX_CHUNK_SECONDS},",
        f"  DEFAULT_BLOCK_SECONDS: {AudioConstants.DEFAULT_BLOCK_SECONDS},",
        f"  DEFAULT_METER_DECAY: {AudioConstants.DEFAULT_METER_DECAY},",
        f"  MAX_QUEUE_ITEMS: {AudioConstants.MAX_QUEUE_ITEMS},",
        f"  CAPTURE_TIMEOUT_SECONDS: {AudioConstants.CAPTURE_TIMEOUT_SECONDS},",
        f"  DEFAULT_BACKEND: '{AudioConstants.DEFAULT_BACKEND}' as const,",
        f"  DEFAULT_CAPTURE_DEVICE_ID: '{AudioConstants.DEFAULT_CAPTURE_DEVICE_ID}' as const,",
        f"  DEFAULT_CAPTURE_MODE: '{AudioConstants.DEFAULT_CAPTURE_MODE}' as const,",
        f"  DEFAULT_PROBE_DURATION: {AudioConstants.DEFAULT_PROBE_DURATION},",
        f"  DEFAULT_PROBE_BLOCK_SIZE: {AudioConstants.DEFAULT_PROBE_BLOCK_SIZE},",
        "} as const;",
        "",
        "export const VALID_SAMPLE_RATES = " + json.dumps(SAMPLE_RATES) + " as const;",
        "",
        "// ============================================",
        "// VAD Constants",
        "// ============================================",
        "export const VADConstants = {",
        f"  DEFAULT_THRESHOLD_DB: {VADConstants.DEFAULT_THRESHOLD_DB},",
        f"  DEFAULT_MIN_SILENCE_MS: {VADConstants.DEFAULT_MIN_SILENCE_MS},",
        f"  DEFAULT_SPEECH_PAD_MS: {VADConstants.DEFAULT_SPEECH_PAD_MS},",
        f"  DEFAULT_FILTER_ENABLED: {str(VADConstants.DEFAULT_FILTER_ENABLED).lower()},",
        f"  DEFAULT_HYSTERESIS_MS: {VADConstants.DEFAULT_HYSTERESIS_MS},",
        f"  MIN_THRESHOLD_DB: {VADConstants.MIN_THRESHOLD_DB},",
        f"  MAX_THRESHOLD_DB: {VADConstants.MAX_THRESHOLD_DB},",
        "} as const;",
        "",
        "// ============================================",
        "// Model Constants",
        "// ============================================",
        "export const ModelConstants = {",
        f"  DEFAULT_MODEL_NAME: '{ModelConstants.DEFAULT_MODEL_NAME}' as const,",
        f"  DEFAULT_COMPUTE_TYPE: '{ModelConstants.DEFAULT_COMPUTE_TYPE}' as const,",
        f"  DEFAULT_BEAM_SIZE: {ModelConstants.DEFAULT_BEAM_SIZE},",
        f"  DEFAULT_BEST_OF: {ModelConstants.DEFAULT_BEST_OF},",
        f"  DEFAULT_PATIENCE: {ModelConstants.DEFAULT_PATIENCE},",
        f"  DEFAULT_TEMPERATURE: {ModelConstants.DEFAULT_TEMPERATURE},",
        f"  DEFAULT_CONFIDENCE_THRESHOLD: {ModelConstants.DEFAULT_CONFIDENCE_THRESHOLD},",
        f"  MIN_SEGMENT_LENGTH: {ModelConstants.MIN_SEGMENT_LENGTH},",
        "} as const;",
        "",
        "export const VALID_MODEL_NAMES = "
        + json.dumps(list(ModelConstants.VALID_MODELS))
        + " as const;",
        "export const VALID_COMPUTE_TYPES = ['float16', 'int8', 'int8_float16'] as const;",
        "",
        "export const MODEL_CATALOG_MAPPING = "
        + json.dumps(ModelConstants.MODEL_CATALOG_MAPPING)
        + " as const;",
        "",
        "// ============================================",
        "// Performance Constants",
        "// ============================================",
        "export const PerformanceConstants = {",
        f"  DEFAULT_LIVE_MODE: '{PerformanceConstants.DEFAULT_LIVE_MODE}' as const,",
        f"  DEFAULT_EXECUTION_MODE: '{PerformanceConstants.DEFAULT_EXECUTION_MODE}' as const,",
        f"  DEFAULT_MAX_WORKERS: {PerformanceConstants.DEFAULT_MAX_WORKERS},",
        f"  OUTPUT_REFRESH_SECONDS: {PerformanceConstants.OUTPUT_REFRESH_SECONDS},",
        f"  TARGET_LATENCY_MS: {PerformanceConstants.TARGET_LATENCY_MS},",
        f"  DEFAULT_THREAD_POOL_WORKERS: {PerformanceConstants.DEFAULT_THREAD_POOL_WORKERS},",
        f"  MAX_THREAD_POOL_WORKERS: {PerformanceConstants.MAX_THREAD_POOL_WORKERS},",
        f"  DEFAULT_CHUNK_DURATION_MS: {PerformanceConstants.DEFAULT_CHUNK_DURATION_MS},",
        f"  MAX_QUEUE_SIZE: {PerformanceConstants.MAX_QUEUE_SIZE},",
        "} as const;",
        "",
        "export const VALID_LIVE_MODES = ['ultra', 'realtime', 'low_latency', 'balanced', 'high_accuracy'] as const;",
        "export const VALID_EXECUTION_MODES = ['auto', 'cpu_only', 'gpu_only'] as const;",
        "",
        "// ============================================",
        "// Session Constants",
        "// ============================================",
        "export const SessionConstants = {",
        f"  DEFAULT_SESSION_TITLE: '{SessionConstants.DEFAULT_SESSION_TITLE}',",
        f"  DEFAULT_EXPORT_ROOT: '{SessionConstants.DEFAULT_EXPORT_ROOT}',",
        f"  MAX_TRANSCRIPT_SEGMENTS: {SessionConstants.MAX_TRANSCRIPT_SEGMENTS},",
        f"  MAX_SUPPRESSED_SEGMENTS: {SessionConstants.MAX_SUPPRESSED_SEGMENTS},",
        f"  MAX_FORMULAS: {SessionConstants.MAX_FORMULAS},",
        f"  MAX_REVIEW_ITEMS: {SessionConstants.MAX_REVIEW_ITEMS},",
        f"  THREAD_JOIN_TIMEOUT: {SessionConstants.THREAD_JOIN_TIMEOUT},",
        f"  STOP_TIMEOUT: {SessionConstants.STOP_TIMEOUT},",
        f"  CAPTURE_THREAD_JOIN_TIMEOUT: {SessionConstants.CAPTURE_THREAD_JOIN_TIMEOUT},",
        "} as const;",
        "",
        "// ============================================",
        "// UI Constants",
        "// ============================================",
        "export const UIConstants = {",
        f"  DEFAULT_THEME: '{UIConstants.DEFAULT_THEME}' as const,",
        f"  DEFAULT_LANGUAGE: '{UIConstants.DEFAULT_LANGUAGE}' as const,",
        f"  SETTINGS_VERSION: {UIConstants.SETTINGS_VERSION},",
        f"  AUTO_SAVE_INTERVAL_SECONDS: {UIConstants.AUTO_SAVE_INTERVAL_SECONDS},",
        f"  MAX_LOG_FILES: {UIConstants.MAX_LOG_FILES},",
        f"  DEFAULT_HOTKEY: '{UIConstants.DEFAULT_HOTKEY}',",
        "} as const;",
        "",
        "export const VALID_THEMES = " + json.dumps(sorted(UIConstants.VALID_THEMES)) + " as const;",
        "export const VALID_LOG_LEVELS = ['DEBUG', 'INFO', 'WARN', 'ERROR'] as const;",
        "",
        "// ============================================",
        "// Quality Constants",
        "// ============================================",
        "export const QualityConstants = {",
        f"  MAX_PUNCTUATION_RATIO: {QualityConstants.MAX_PUNCTUATION_RATIO},",
        f"  MAX_REPEATED_CHAR_RUN: {QualityConstants.MAX_REPEATED_CHAR_RUN},",
        f"  LOW_ENTROPY_UNIQUE_RATIO_THRESHOLD: {QualityConstants.LOW_ENTROPY_UNIQUE_RATIO_THRESHOLD},",
        f"  LOW_ENTROPY_TOKEN_REPEAT_THRESHOLD: {QualityConstants.LOW_ENTROPY_TOKEN_REPEAT_THRESHOLD},",
        f"  LOW_ENTROPY_SHORT_TOKEN_THRESHOLD: {QualityConstants.LOW_ENTROPY_SHORT_TOKEN_THRESHOLD},",
        f"  LOW_ENTROPY_SHORT_UNIQUE_RATIO: {QualityConstants.LOW_ENTROPY_SHORT_UNIQUE_RATIO},",
        f"  FILLER_CONFIDENCE_THRESHOLD: {QualityConstants.FILLER_CONFIDENCE_THRESHOLD},",
        f"  SHORT_TEXT_CONFIDENCE_THRESHOLD: {QualityConstants.SHORT_TEXT_CONFIDENCE_THRESHOLD},",
        f"  SHORT_TEXT_MAX_LENGTH: {QualityConstants.SHORT_TEXT_MAX_LENGTH},",
        f"  QUALITY_LABEL_JUNK: '{QualityConstants.QUALITY_LABEL_JUNK}',",
        f"  QUALITY_LABEL_WEAK: '{QualityConstants.QUALITY_LABEL_WEAK}',",
        f"  QUALITY_LABEL_OK: '{QualityConstants.QUALITY_LABEL_OK}',",
        f"  JUNK_CONFIDENCE_THRESHOLD: {QualityConstants.JUNK_CONFIDENCE_THRESHOLD},",
        f"  WEAK_CONFIDENCE_THRESHOLD: {QualityConstants.WEAK_CONFIDENCE_THRESHOLD},",
        f"  DUPLICATE_CONFIDENCE_THRESHOLD: {QualityConstants.DUPLICATE_CONFIDENCE_THRESHOLD},",
        f"  NO_SPEECH_PROB_THRESHOLD: {QualityConstants.NO_SPEECH_PROB_THRESHOLD},",
        f"  NO_SPEECH_CONFIDENCE_THRESHOLD: {QualityConstants.NO_SPEECH_CONFIDENCE_THRESHOLD},",
        f"  LOW_LOGPROB_THRESHOLD: {QualityConstants.LOW_LOGPROB_THRESHOLD},",
        f"  LOW_LOGPROB_CONFIDENCE_THRESHOLD: {QualityConstants.LOW_LOGPROB_CONFIDENCE_THRESHOLD},",
        f"  COMPRESSION_RATIO_THRESHOLD: {QualityConstants.COMPRESSION_RATIO_THRESHOLD},",
        f"  COMPRESSION_CONFIDENCE_THRESHOLD: {QualityConstants.COMPRESSION_CONFIDENCE_THRESHOLD},",
        f"  OVERLAP_DEDUP_TIME_WINDOW_SECONDS: {QualityConstants.OVERLAP_DEDUP_TIME_WINDOW_SECONDS},",
        f"  OVERLAP_DEDUP_MAX_DUPLICATES: {QualityConstants.OVERLAP_DEDUP_MAX_DUPLICATES},",
        f"  CONFIDENCE_PROXY_BASE: {QualityConstants.CONFIDENCE_PROXY_BASE},",
        f"  CONFIDENCE_PROXY_AVG_LOGPROB_OFFSET: {QualityConstants.CONFIDENCE_PROXY_AVG_LOGPROB_OFFSET},",
        f"  CONFIDENCE_PROXY_AVG_LOGPROB_SCALE: {QualityConstants.CONFIDENCE_PROXY_AVG_LOGPROB_SCALE},",
        f"  CONFIDENCE_PROXY_MAX_BONUS: {QualityConstants.CONFIDENCE_PROXY_MAX_BONUS},",
        f"  CONFIDENCE_PROXY_MAX_PENALTY: {QualityConstants.CONFIDENCE_PROXY_MAX_PENALTY},",
        f"  CONFIDENCE_PROXY_NO_SPEECH_SCALE: {QualityConstants.CONFIDENCE_PROXY_NO_SPEECH_SCALE},",
        f"  CONFIDENCE_PROXY_COMPRESSION_THRESHOLD: {QualityConstants.CONFIDENCE_PROXY_COMPRESSION_THRESHOLD},",
        f"  CONFIDENCE_PROXY_COMPRESSION_PENALTY_SCALE: {QualityConstants.CONFIDENCE_PROXY_COMPRESSION_PENALTY_SCALE},",
        f"  CONFIDENCE_PROXY_COMPRESSION_MAX_PENALTY: {QualityConstants.CONFIDENCE_PROXY_COMPRESSION_MAX_PENALTY},",
        f"  CONFIDENCE_PROXY_MAX_SCORE: {QualityConstants.CONFIDENCE_PROXY_MAX_SCORE},",
        "} as const;",
        "",
        "// ============================================",
        "// Filler Words",
        "// ============================================",
        "export const COMMON_FILLER_WORDS = "
        + json.dumps(sorted(COMMON_FILLER_WORDS))
        + " as const;",
        "",
        "// ============================================",
        "// Hallucination Detection",
        "// ============================================",
        "export const HALLUCINATION_PHRASES = "
        + json.dumps(sorted(HALLUCINATION_PHRASES))
        + " as const;",
        f"export const HALLUCINATION_CONFIDENCE_THRESHOLD = {HALLUCINATION_CONFIDENCE_THRESHOLD};",
        "",
        "// ============================================",
        "// Server/API Constants",
        "// ============================================",
        "export const ServerConstants = {",
        f"  DEFAULT_HOST: '{ServerConstants.DEFAULT_HOST}',",
        f"  DEFAULT_PORT: {ServerConstants.DEFAULT_PORT},",
        f"  DEFAULT_LOG_LEVEL: '{ServerConstants.DEFAULT_LOG_LEVEL}' as const,",
        "} as const;",
        "",
        "// ============================================",
        "// Live Mode Profiles",
        "// ============================================",
        "export const LIVE_MODE_PROFILES = " + json.dumps(LIVE_MODE_PROFILES) + " as const;",
        "export type LiveModeProfile = keyof typeof LIVE_MODE_PROFILES;",
        "",
        "// ============================================",
        "// Fast Chunker Constants",
        "// ============================================",
        "export const FastChunkerConstants = {",
        f"  DEFAULT_BASE_CHUNK_MS: {FastChunkerConstants.DEFAULT_BASE_CHUNK_MS},",
        f"  DEFAULT_OVERLAP_MS: {FastChunkerConstants.DEFAULT_OVERLAP_MS},",
        f"  DEFAULT_MIN_CHUNK_MS: {FastChunkerConstants.DEFAULT_MIN_CHUNK_MS},",
        f"  DEFAULT_MAX_CHUNK_MS: {FastChunkerConstants.DEFAULT_MAX_CHUNK_MS},",
        f"  DEFAULT_VAD_THRESHOLD_DB: {FastChunkerConstants.DEFAULT_VAD_THRESHOLD_DB},",
        f"  DEFAULT_VAD_HYSTERESIS_MS: {FastChunkerConstants.DEFAULT_VAD_HYSTERESIS_MS},",
        f"  HIGH_SPEECH_DENSITY_THRESHOLD: {FastChunkerConstants.HIGH_SPEECH_DENSITY_THRESHOLD},",
        f"  LOW_SPEECH_DENSITY_THRESHOLD: {FastChunkerConstants.LOW_SPEECH_DENSITY_THRESHOLD},",
        f"  ADAPTIVE_SIZE_HIGH_MULTIPLIER: {FastChunkerConstants.ADAPTIVE_SIZE_HIGH_MULTIPLIER},",
        f"  ADAPTIVE_SIZE_LOW_MULTIPLIER: {FastChunkerConstants.ADAPTIVE_SIZE_LOW_MULTIPLIER},",
        f"  BUFFER_CAPACITY_SECONDS: {FastChunkerConstants.BUFFER_CAPACITY_SECONDS},",
        f"  SPEECH_DENSITY_WINDOW_SIZE: {FastChunkerConstants.SPEECH_DENSITY_WINDOW_SIZE},",
        f"  SPEECH_DENSITY_MIN_SAMPLES: {FastChunkerConstants.SPEECH_DENSITY_MIN_SAMPLES},",
        f"  DEFAULT_MAX_QUEUE_SIZE: {FastChunkerConstants.DEFAULT_MAX_QUEUE_SIZE},",
        "} as const;",
        "",
        "// ============================================",
        "// Audio Capture Constants",
        "// ============================================",
        "export const AudioCaptureConstants = {",
        f"  MAX_CONSECUTIVE_ERRORS: {AudioCaptureConstants.MAX_CONSECUTIVE_ERRORS},",
        f"  STATS_LOG_INTERVAL_SECONDS: {AudioCaptureConstants.STATS_LOG_INTERVAL_SECONDS},",
        f"  QUEUE_PUT_TIMEOUT_SECONDS: {AudioCaptureConstants.QUEUE_PUT_TIMEOUT_SECONDS},",
        f"  READ_TIMEOUT_SECONDS: {AudioCaptureConstants.READ_TIMEOUT_SECONDS},",
        f"  SLOW_CHUNK_PROCESSING_THRESHOLD_MS: {AudioCaptureConstants.SLOW_CHUNK_PROCESSING_THRESHOLD_MS},",
        "} as const;",
        "",
        "// ============================================",
        "// Health Monitoring Constants",
        "// ============================================",
        "export const HealthConstants = {",
        f"  LOOP_STATS_INTERVAL_SECONDS: {HealthConstants.LOOP_STATS_INTERVAL_SECONDS},",
        f"  HEALTH_EMIT_INTERVAL_SECONDS: {HealthConstants.HEALTH_EMIT_INTERVAL_SECONDS},",
        f"  LOOP_LOG_INTERVAL_SECONDS: {HealthConstants.LOOP_LOG_INTERVAL_SECONDS},",
        "} as const;",
        "",
        "// ============================================",
        "// Auto-optimization Constants",
        "// ============================================",
        "export const AutoOptimizationConstants = {",
        f"  DEFAULT_ENABLED: {str(AutoOptimizationConstants.DEFAULT_ENABLED).lower()},",
        f"  DEFAULT_MODE: '{AutoOptimizationConstants.DEFAULT_MODE}' as const,",
        "} as const;",
        "",
        "export const VALID_OPTIMIZATION_MODES = ['maximum', 'balanced', 'speed', 'low_memory'] as const;",
        "",
        "// ============================================",
        "// Refiner Constants",
        "// ============================================",
        "export const RefinerConstants = {",
        f"  DEFAULT_MODEL_ID: '{RefinerConstants.DEFAULT_MODEL_ID}',",
        f"  DEFAULT_ENGINE_PREFERENCE: '{RefinerConstants.DEFAULT_ENGINE_PREFERENCE}' as const,",
        f"  DEFAULT_REFINEMENT_MODE: '{RefinerConstants.DEFAULT_REFINEMENT_MODE}' as const,",
        "} as const;",
        "",
        "export const VALID_REFINER_ENGINES = ['llamacpp', 'ollama'] as const;",
        "export const VALID_REFINEMENT_MODES = ['off', 'strict', 'polished'] as const;",
        "",
        "// ============================================",
        "// GPU Fallback Keywords",
        "// ============================================",
        "export const GPU_FALLBACK_KEYWORDS = " + json.dumps(GPU_FALLBACK_KEYWORDS) + " as const;",
        "",
        "// ============================================",
        "// Settings Validation Bounds",
        "// ============================================",
        "export const SettingsBounds = {",
        "  SESSION_TITLE_MIN_LENGTH: 1,",
        "  SESSION_TITLE_MAX_LENGTH: 100,",
        "  AUTO_SAVE_INTERVAL_MIN: 10,",
        "  AUTO_SAVE_INTERVAL_MAX: 300,",
        "  CHUNK_DURATION_MIN: 0.5,",
        "  CHUNK_DURATION_MAX: 5.0,",
        "  OVERLAP_RATIO_MIN: 0,",
        "  OVERLAP_RATIO_MAX: 0.5,",
        "  CONFIDENCE_THRESHOLD_MIN: 0,",
        "  CONFIDENCE_THRESHOLD_MAX: 1,",
        "  MIN_SEGMENT_LENGTH_MIN: 0.1,",
        "  MIN_SEGMENT_LENGTH_MAX: 2.0,",
        "  MAX_WORKERS_MIN: 1,",
        "  MAX_WORKERS_MAX: 16,",
        "  BEAM_SIZE_MIN: 1,",
        "  BEAM_SIZE_MAX: 20,",
        "  BEST_OF_MIN: 1,",
        "  BEST_OF_MAX: 20,",
        "  PATIENCE_MIN: 0.1,",
        "  PATIENCE_MAX: 5.0,",
        "  TEMPERATURE_MIN: 0,",
        "  TEMPERATURE_MAX: 1,",
        "  VAD_THRESHOLD_MIN: -60,",
        "  VAD_THRESHOLD_MAX: -20,",
        "  MAX_LOG_FILES_MIN: 1,",
        "  MAX_LOG_FILES_MAX: 100,",
        "} as const;",
        "",
        "// ============================================",
        "// Fake/Not Implemented Settings",
        "// ============================================",
        "export const FAKE_SETTINGS = new Set([",
    ]

    for setting in sorted(FAKE_SETTINGS):
        lines.append(f"  '{setting}',")

    lines.extend(
        [
            "]);",
            "",
        ]
    )

    return "\n".join(lines)


def generate_text_ts() -> str:
    """Generate TypeScript text constants file."""
    lines = [
        "// Auto-generated from app/config/text.py",
        "// Do not edit manually - run `python app/config/generate_ts.py` to regenerate",
        "",
        "// ============================================",
        "// Model Names",
        "// ============================================",
        "export const MODEL_NAMES = " + json.dumps(MODEL_NAMES, indent=2) + " as const;",
        "",
        "export const MODEL_NAMES_SHORT = "
        + json.dumps(MODEL_NAMES_SHORT, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Live Mode Labels",
        "// ============================================",
        "export const LIVE_MODE_LABELS = " + json.dumps(LIVE_MODE_LABELS, indent=2) + " as const;",
        "",
        "export const LIVE_MODE_DESCRIPTIONS = "
        + json.dumps(LIVE_MODE_DESCRIPTIONS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Setting Category Labels",
        "// ============================================",
        "export const CATEGORY_LABELS = " + json.dumps(CATEGORY_LABELS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Setting Labels",
        "// ============================================",
        "export const SETTING_LABELS = " + json.dumps(SETTING_LABELS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Setting Descriptions",
        "// ============================================",
        "export const SETTING_DESCRIPTIONS = "
        + json.dumps(SETTING_DESCRIPTIONS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Theme Labels",
        "// ============================================",
        "export const THEME_LABELS = " + json.dumps(THEME_LABELS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Compute Type Labels",
        "// ============================================",
        "export const COMPUTE_TYPE_LABELS = "
        + json.dumps(COMPUTE_TYPE_LABELS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Capture Mode Labels",
        "// ============================================",
        "export const CAPTURE_MODE_LABELS = "
        + json.dumps(CAPTURE_MODE_LABELS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Audio Backend Labels",
        "// ============================================",
        "export const AUDIO_BACKEND_LABELS = "
        + json.dumps(AUDIO_BACKEND_LABELS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Sample Rate Labels",
        "// ============================================",
        "export const SAMPLE_RATE_LABELS: Record<string, string> = "
        + json.dumps(SAMPLE_RATE_LABELS, indent=2)
        + ";",
        "",
        "// ============================================",
        "// Finish Action Labels",
        "// ============================================",
        "export const FINISH_ACTION_LABELS = "
        + json.dumps(FINISH_ACTION_LABELS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Floating Window Position Labels",
        "// ============================================",
        "export const FLOATING_POSITION_LABELS = "
        + json.dumps(FLOATING_POSITION_LABELS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Log Level Labels",
        "// ============================================",
        "export const LOG_LEVEL_LABELS = " + json.dumps(LOG_LEVEL_LABELS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Optimization Preset Labels",
        "// ============================================",
        "export const OPTIMIZATION_PRESET_LABELS = "
        + json.dumps(OPTIMIZATION_PRESET_LABELS, indent=2)
        + " as const;",
        "",
        "export const PRESET_DESCRIPTIONS = "
        + json.dumps(PRESET_DESCRIPTIONS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Refinement Mode Labels",
        "// ============================================",
        "export const REFINEMENT_MODE_LABELS = "
        + json.dumps(REFINEMENT_MODE_LABELS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Refinement Profile Labels",
        "// ============================================",
        "export const REFINEMENT_PROFILE_LABELS = "
        + json.dumps(REFINEMENT_PROFILE_LABELS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Refiner Engine Labels",
        "// ============================================",
        "export const REFINER_ENGINE_LABELS = "
        + json.dumps(REFINER_ENGINE_LABELS, indent=2)
        + " as const;",
        "",
        "// ============================================",
        "// Tab Labels",
        "// ============================================",
        "export const TAB_LABELS = " + json.dumps(TAB_LABELS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Button Labels",
        "// ============================================",
        "export const BUTTON_LABELS = " + json.dumps(BUTTON_LABELS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Status Labels",
        "// ============================================",
        "export const STATUS_LABELS = " + json.dumps(STATUS_LABELS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Section Headers",
        "// ============================================",
        "export const SECTION_HEADERS = " + json.dumps(SECTION_HEADERS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Error Messages",
        "// ============================================",
        "export const ERROR_MESSAGES = " + json.dumps(ERROR_MESSAGES, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Tooltips",
        "// ============================================",
        "export const TOOLTIPS = " + json.dumps(TOOLTIPS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Unit Labels",
        "// ============================================",
        "export const UNIT_LABELS = " + json.dumps(UNIT_LABELS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Hardware Labels",
        "// ============================================",
        "export const HARDWARE_LABELS = " + json.dumps(HARDWARE_LABELS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Metric Labels",
        "// ============================================",
        "export const METRIC_LABELS = " + json.dumps(METRIC_LABELS, indent=2) + " as const;",
        "",
        "// ============================================",
        "// Settings Section UI Copy",
        "// ============================================",
        "export const SETTINGS_SECTION_TEXT = "
        + json.dumps(SETTINGS_SECTION_TEXT, indent=2)
        + " as const;",
        "",
    ]

    return "\n".join(lines)


def generate_settings_ts() -> str:
    """Generate TypeScript settings registry file."""
    lines = [
        "// Auto-generated from app/config/settings.py",
        "// Do not edit manually - run `python app/config/generate_ts.py` to regenerate",
        "",
        "// ============================================",
        "// Setting Definition Types",
        "// ============================================",
        "export type SettingType = 'string' | 'number' | 'boolean' | 'enum' | 'range' | 'object' | 'array';",
        "",
        "export interface SettingDefinition {",
        "  name: string;",
        "  category: string;",
        "  type: SettingType;",
        "  default: unknown;",
        "  label: string;",
        "  description: string;",
        "  options?: (string | number)[];",
        "  min?: number;",
        "  max?: number;",
        "  step?: number;",
        "  suffix?: string;",
        "  isFake: boolean;",
        "  isAdvanced: boolean;",
        "}",
        "",
        "// ============================================",
        "// Settings Registry - Single Source of Truth",
        "// ============================================",
        "export const SETTINGS_REGISTRY: Record<string, SettingDefinition> = {",
    ]

    for name, defn in sorted(SETTINGS_REGISTRY.items()):
        options_str = ""
        if defn.options:
            options_str = f"\n    options: {ts_literal(defn.options)},"

        min_str = f"\n    min: {defn.min}," if defn.min is not None else ""
        max_str = f"\n    max: {defn.max}," if defn.max is not None else ""
        step_str = f"\n    step: {defn.step}," if defn.step is not None else ""
        suffix_str = f"\n    suffix: {ts_literal(defn.suffix)}," if defn.suffix else ""
        default_str = ts_literal(defn.default)

        lines.extend(
            [
                f"  {name}: {{",
                f"    name: {ts_literal(defn.name)},",
                f"    category: {ts_literal(defn.category)},",
                f"    type: {ts_literal(defn.type)},",
                f"    default: {default_str},",
                f"    label: {ts_literal(defn.label)},",
                f"    description: {ts_literal(defn.description)},{options_str}{min_str}{max_str}{step_str}{suffix_str}",
                f"    isFake: {str(defn.is_fake).lower()},",
                f"    isAdvanced: {str(defn.is_advanced).lower()},",
                "  },",
            ]
        )

    lines.extend(
        [
            "};",
            "",
            "// ============================================",
            "// Registry Access Functions",
            "// ============================================",
            "",
            "export function getSetting(name: string): SettingDefinition {",
            "  const defn = SETTINGS_REGISTRY[name];",
            "  if (!defn) {",
            "    throw new Error(`Unknown setting: ${name}`);",
            "  }",
            "  return defn;",
            "}",
            "",
            "export function getSettingsByCategory(category: string): Record<string, SettingDefinition> {",
            "  return Object.fromEntries(",
            "    Object.entries(SETTINGS_REGISTRY).filter(([_, defn]) => defn.category === category)",
            "  );",
            "}",
            "",
            "export function getAllCategories(): string[] {",
            "  return [...new Set(Object.values(SETTINGS_REGISTRY).map(d => d.category))];",
            "}",
            "",
            "export function getSettingDefault(name: string): unknown {",
            "  return getSetting(name).default;",
            "}",
            "",
            "export function getCategoryDefaults(category: string): Record<string, unknown> {",
            "  const settings = getSettingsByCategory(category);",
            "  return Object.fromEntries(",
            "    Object.entries(settings).map(([name, defn]) => [name, defn.default])",
            "  );",
            "}",
            "",
            "export function isFakeSetting(name: string): boolean;",
            "export function isFakeSetting(_category: string | null, name: string): boolean;",
            "export function isFakeSetting(arg1: string | null, arg2?: string): boolean {",
            "  const name = arg2 ?? arg1 as string;",
            "  const defn = SETTINGS_REGISTRY[name];",
            "  return defn?.isFake ?? false;",
            "}",
            "",
            "export function getFakeSettings(): Record<string, string[]> {",
            "  const result: Record<string, string[]> = {};",
            "  Object.values(SETTINGS_REGISTRY).forEach(defn => {",
            "    if (defn.isFake) {",
            "      if (!result[defn.category]) {",
            "        result[defn.category] = [];",
            "      }",
            "      result[defn.category].push(defn.name);",
            "    }",
            "  });",
            "  return result;",
            "}",
            "",
            "// ============================================",
            "// Validation Functions",
            "// ============================================",
            "",
            "export interface ValidationResult {",
            "  isValid: boolean;",
            "  error?: string;",
            "}",
            "",
            "export function validateSetting(name: string, value: unknown): ValidationResult {",
            "  const defn = SETTINGS_REGISTRY[name];",
            "  if (!defn) {",
            "    return { isValid: false, error: `Unknown setting: ${name}` };",
            "  }",
            "",
            "  switch (defn.type) {",
            "    case 'boolean':",
            "      if (typeof value !== 'boolean') {",
            "        return { isValid: false, error: `Expected boolean, got ${typeof value}` };",
            "      }",
            "      break;",
            "    case 'string':",
            "      if (typeof value !== 'string') {",
            "        return { isValid: false, error: `Expected string, got ${typeof value}` };",
            "      }",
            "      break;",
            "    case 'number':",
            "    case 'range':",
            "      if (typeof value !== 'number') {",
            "        return { isValid: false, error: `Expected number, got ${typeof value}` };",
            "      }",
            "      if (defn.min !== undefined && value < defn.min) {",
            "        return { isValid: false, error: `Value must be >= ${defn.min}` };",
            "      }",
            "      if (defn.max !== undefined && value > defn.max) {",
            "        return { isValid: false, error: `Value must be <= ${defn.max}` };",
            "      }",
            "      break;",
            "    case 'enum':",
            "      if (defn.options && !defn.options.includes(value as string | number)) {",
            "        return { isValid: false, error: `Invalid value. Must be one of: ${defn.options.join(', ')}` };",
            "      }",
            "      break;",
            "    case 'object':",
            "      if (typeof value !== 'object' || value === null || Array.isArray(value)) {",
            "        return { isValid: false, error: `Expected object, got ${Array.isArray(value) ? 'array' : typeof value}` };",
            "      }",
            "      break;",
            "    case 'array':",
            "      if (!Array.isArray(value)) {",
            "        return { isValid: false, error: `Expected array, got ${typeof value}` };",
            "      }",
            "      break;",
            "  }",
            "",
            "  return { isValid: true };",
            "}",
            "",
            "// ============================================",
            "// Settings Version",
            "// ============================================",
            f"export const CURRENT_SETTINGS_VERSION = {UIConstants.SETTINGS_VERSION};",
            "",
            "export function getSettingsVersion(): number {",
            "  return CURRENT_SETTINGS_VERSION;",
            "}",
            "",
        ]
    )

    return "\n".join(lines)


def generate_index_ts() -> str:
    """Generate index.ts barrel file."""
    return """// Auto-generated barrel file
// Do not edit manually - run `python app/config/generate_ts.py` to regenerate

export * from './constants';
export * from './text';
export * from './settings';
"""


def generate_electron_app_meta_js() -> str:
    """Generate Electron main app metadata file."""
    return f"""// Auto-generated from app/config/constants.py
// Do not edit manually - run `python app/config/generate_ts.py` to regenerate

module.exports = {{
  APP_NAME: "{AppConstants.APP_NAME}",
  APP_SLUG: "{AppConstants.APP_SLUG}",
  LOCAL_API_TITLE_SUFFIX: "{AppConstants.LOCAL_API_TITLE_SUFFIX}",
  DOWNLOAD_USER_AGENT: "{AppConstants.DOWNLOAD_USER_AGENT}",
}};
"""


def main():
    """Generate TypeScript configuration files."""
    # Determine output directory
    config_dir = Path(__file__).parent
    output_dir = config_dir.parent / "electron" / "frontend" / "src" / "config" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate constants.ts
    constants_ts = output_dir / "constants.ts"
    constants_ts.write_text(generate_constants_ts(), encoding="utf-8")
    print(f"Generated: {constants_ts}")

    # Generate text.ts
    text_ts = output_dir / "text.ts"
    text_ts.write_text(generate_text_ts(), encoding="utf-8")
    print(f"Generated: {text_ts}")

    # Generate settings.ts
    settings_ts = output_dir / "settings.ts"
    settings_ts.write_text(generate_settings_ts(), encoding="utf-8")
    print(f"Generated: {settings_ts}")

    # Generate index.ts
    index_ts = output_dir / "index.ts"
    index_ts.write_text(generate_index_ts(), encoding="utf-8")
    print(f"Generated: {index_ts}")

    # Generate Electron main app metadata
    electron_meta_dir = config_dir.parent / "electron" / "main" / "shared" / "generated"
    electron_meta_dir.mkdir(parents=True, exist_ok=True)
    electron_meta_js = electron_meta_dir / "appMeta.js"
    electron_meta_js.write_text(generate_electron_app_meta_js(), encoding="utf-8")
    print(f"Generated: {electron_meta_js}")

    print("\nTypeScript configuration files generated successfully!")


if __name__ == "__main__":
    main()
