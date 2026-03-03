#!/usr/bin/env python3
"""Generate TypeScript constants from Python configuration.

This script reads the Python configuration files and generates
TypeScript equivalents for the frontend to use.

Run this script whenever you modify config/python/:
    python config/generate_ts.py
"""

import json
from pathlib import Path
from typing import Any

# Import Python constants
from config.python.constants import (
    SAMPLE_RATES,
    COMMON_FILLER_WORDS,
    HALLUCINATION_PHRASES,
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
)
from config.python.text import (
    MODEL_NAMES,
    LIVE_MODE_LABELS,
    LIVE_MODE_DESCRIPTIONS,
    SETTING_LABELS,
    SETTING_DESCRIPTIONS,
    BUTTON_LABELS,
    STATUS_LABELS,
    ERROR_MESSAGES,
    TOOLTIPS,
)


def to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.capitalize() for x in components[1:])


def generate_constants_ts() -> str:
    """Generate TypeScript constants file."""
    lines = [
        "// Auto-generated from config/python/constants.py",
        "// Do not edit manually - run `python config/generate_ts.py` to regenerate",
        "",
        "export const SampleRates = " + json.dumps(SAMPLE_RATES) + " as const;",
        "",
        "export const CommonFillerWords = "
        + json.dumps(sorted(COMMON_FILLER_WORDS))
        + " as const;",
        "",
        "export const HallucinationPhrases = " + json.dumps(HALLUCINATION_PHRASES) + " as const;",
        "",
        "export const GpuFallbackKeywords = " + json.dumps(GPU_FALLBACK_KEYWORDS) + " as const;",
        "",
        "export const LiveModeProfiles = " + json.dumps(LIVE_MODE_PROFILES) + " as const;",
        "",
        "export type LiveModeProfile = keyof typeof LiveModeProfiles;",
        "",
        "export const AudioConstants = {",
        f"  defaultSampleRate: {AudioConstants.DEFAULT_SAMPLE_RATE},",
        f"  defaultChannels: {AudioConstants.DEFAULT_CHANNELS},",
        f"  defaultChunkSeconds: {AudioConstants.DEFAULT_CHUNK_SECONDS},",
        f"  defaultOverlapSeconds: {AudioConstants.DEFAULT_OVERLAP_SECONDS},",
        f"  defaultBlockSeconds: {AudioConstants.DEFAULT_BLOCK_SECONDS},",
        f"  defaultMeterDecay: {AudioConstants.DEFAULT_METER_DECAY},",
        f"  maxQueueItems: {AudioConstants.MAX_QUEUE_ITEMS},",
        "} as const;",
        "",
        "export const VadConstants = {",
        f"  defaultThresholdDb: {VADConstants.DEFAULT_THRESHOLD_DB},",
        f"  defaultMinSilenceMs: {VADConstants.DEFAULT_MIN_SILENCE_MS},",
        f"  defaultSpeechPadMs: {VADConstants.DEFAULT_SPEECH_PAD_MS},",
        f"  defaultFilterEnabled: {str(VADConstants.DEFAULT_FILTER_ENABLED).lower()},",
        "} as const;",
        "",
        "export const ModelConstants = {",
        f"  defaultModelName: '{ModelConstants.DEFAULT_MODEL_NAME}',",
        f"  defaultComputeType: '{ModelConstants.DEFAULT_COMPUTE_TYPE}',",
        f"  defaultConfidenceThreshold: {ModelConstants.DEFAULT_CONFIDENCE_THRESHOLD},",
        f"  defaultBeamSize: {ModelConstants.DEFAULT_BEAM_SIZE},",
        f"  defaultBestOf: {ModelConstants.DEFAULT_BEST_OF},",
        f"  defaultTemperature: {ModelConstants.DEFAULT_TEMPERATURE},",
        f"  minSegmentLength: {ModelConstants.MIN_SEGMENT_LENGTH},",
        "} as const;",
        "",
        "export const ServerConstants = {",
        f"  defaultHost: '{ServerConstants.DEFAULT_HOST}',",
        f"  defaultPort: {ServerConstants.DEFAULT_PORT},",
        f"  defaultLogLevel: '{ServerConstants.DEFAULT_LOG_LEVEL}',",
        "} as const;",
        "",
    ]
    return "\n".join(lines)


def generate_text_ts() -> str:
    """Generate TypeScript text constants file."""
    lines = [
        "// Auto-generated from config/python/text.py",
        "// Do not edit manually - run `python config/generate_ts.py` to regenerate",
        "",
        "export const ModelNames: Record<string, string> = "
        + json.dumps(MODEL_NAMES, indent=2)
        + ";",
        "",
        "export const LiveModeLabels: Record<string, string> = "
        + json.dumps(LIVE_MODE_LABELS, indent=2)
        + ";",
        "",
        "export const LiveModeDescriptions: Record<string, string> = "
        + json.dumps(LIVE_MODE_DESCRIPTIONS, indent=2)
        + ";",
        "",
        "export const SettingLabels: Record<string, string> = "
        + json.dumps(SETTING_LABELS, indent=2)
        + ";",
        "",
        "export const SettingDescriptions: Record<string, string> = "
        + json.dumps(SETTING_DESCRIPTIONS, indent=2)
        + ";",
        "",
        "export const ButtonLabels: Record<string, string> = "
        + json.dumps(BUTTON_LABELS, indent=2)
        + ";",
        "",
        "export const StatusLabels: Record<string, string> = "
        + json.dumps(STATUS_LABELS, indent=2)
        + ";",
        "",
        "export const ErrorMessages: Record<string, string> = "
        + json.dumps(ERROR_MESSAGES, indent=2)
        + ";",
        "",
        "export const Tooltips: Record<string, string> = " + json.dumps(TOOLTIPS, indent=2) + ";",
        "",
    ]
    return "\n".join(lines)


def main():
    """Generate TypeScript configuration files."""
    config_dir = Path(__file__).parent
    ts_dir = config_dir / "typescript"
    ts_dir.mkdir(exist_ok=True)

    # Generate constants.ts
    constants_ts = ts_dir / "constants.ts"
    constants_ts.write_text(generate_constants_ts(), encoding="utf-8")
    print(f"Generated: {constants_ts}")

    # Generate text.ts
    text_ts = ts_dir / "text.ts"
    text_ts.write_text(generate_text_ts(), encoding="utf-8")
    print(f"Generated: {text_ts}")

    # Create shared/exports.ts for easy importing
    shared_dir = config_dir / "shared"
    shared_dir.mkdir(exist_ok=True)
    exports_ts = shared_dir / "index.ts"
    exports_ts.write_text(
        "// Shared configuration exports\n"
        "export * from '../typescript/constants';\n"
        "export * from '../typescript/text';\n",
        encoding="utf-8",
    )
    print(f"Generated: {exports_ts}")

    print("\nTypeScript configuration files updated successfully!")


if __name__ == "__main__":
    main()
