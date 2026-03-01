from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final


@dataclass(slots=True, frozen=True)
class VADConfig:
    """Voice Activity Detection configuration per language."""

    threshold: float = 0.5
    min_silence_duration_ms: int = 200
    speech_pad_ms: int = 200


@dataclass(slots=True, frozen=True)
class ModelRecommendations:
    """Model size recommendations for a language."""

    tiny: str = "tiny"
    base: str = "base"
    small: str = "small"


@dataclass(slots=True, frozen=True)
class LanguageProfile:
    """Complete optimization profile for a specific language."""

    code: str
    name: str
    temperature: float
    precise_mode: bool
    phonetic_patience: bool
    vad: VADConfig
    models: ModelRecommendations
    script_patterns: tuple[str, ...] = field(default_factory=tuple)
    supports_code_switching: bool = False


# Hindi-specific profile
HINDI_PROFILE: Final[LanguageProfile] = LanguageProfile(
    code="hi",
    name="Hindi",
    temperature=0.2,
    precise_mode=False,
    phonetic_patience=True,
    vad=VADConfig(
        threshold=0.4,
        min_silence_duration_ms=250,
        speech_pad_ms=200,
    ),
    models=ModelRecommendations(
        tiny="tiny",
        base="base",
        small="small",
    ),
    script_patterns=(
        r"[\u0900-\u097F]",  # Devanagari range
    ),
    supports_code_switching=True,
)

# English-specific profile
ENGLISH_PROFILE: Final[LanguageProfile] = LanguageProfile(
    code="en",
    name="English",
    temperature=0.0,
    precise_mode=True,
    phonetic_patience=False,
    vad=VADConfig(
        threshold=0.5,
        min_silence_duration_ms=200,
        speech_pad_ms=200,
    ),
    models=ModelRecommendations(
        tiny="tiny.en",
        base="base.en",
        small="small.en",
    ),
    script_patterns=(
        r"[a-zA-Z]",  # Latin script
    ),
    supports_code_switching=True,
)

# Auto-detection profile
AUTO_PROFILE: Final[LanguageProfile] = LanguageProfile(
    code="auto",
    name="Auto-detect",
    temperature=0.1,
    precise_mode=False,
    phonetic_patience=False,
    vad=VADConfig(
        threshold=0.45,
        min_silence_duration_ms=225,
        speech_pad_ms=200,
    ),
    models=ModelRecommendations(
        tiny="tiny",
        base="base",
        small="small",
    ),
    script_patterns=(),
    supports_code_switching=True,
)

# Registry of all profiles
LANGUAGE_PROFILES: Final[dict[str, LanguageProfile]] = {
    "hi": HINDI_PROFILE,
    "en": ENGLISH_PROFILE,
    "auto": AUTO_PROFILE,
}

# Script detection patterns
DEVANAGARI_PATTERN: Final[re.Pattern[str]] = re.compile(r"[\u0900-\u097F]+")
LATIN_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-zA-Z]+")


class ScriptDetector:
    """Detect script types in text for mixed-language content."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[str, ...]] = {}
        self._cache_max_size = 1000

    def detect_scripts(self, text: str) -> tuple[str, ...]:
        """Detect which scripts are present in the text.

        Returns a tuple of script codes: 'devanagari', 'latin', or both.
        Uses LRU-style caching for repeated detection.
        """
        cache_key = text[:200]  # Cache based on first 200 chars
        if cache_key in self._cache:
            return self._cache[cache_key]

        scripts: list[str] = []

        if DEVANAGARI_PATTERN.search(text):
            scripts.append("devanagari")
        if LATIN_PATTERN.search(text):
            scripts.append("latin")

        result = tuple(scripts)

        # Simple cache management
        if len(self._cache) >= self._cache_max_size:
            self._cache.clear()
        self._cache[cache_key] = result

        return result

    def is_mixed_hindi_english(self, text: str) -> bool:
        """Check if text contains both Hindi (Devanagari) and English (Latin) scripts."""
        scripts = self.detect_scripts(text)
        return "devanagari" in scripts and "latin" in scripts

    def get_dominant_script(self, text: str) -> str | None:
        """Determine the dominant script in the text based on character count."""
        devanagari_count = len(DEVANAGARI_PATTERN.findall(text))
        latin_count = len(LATIN_PATTERN.findall(text))

        if devanagari_count == 0 and latin_count == 0:
            return None
        if devanagari_count > latin_count:
            return "devanagari"
        if latin_count > devanagari_count:
            return "latin"
        return "mixed"


def get_profile(language_code: str) -> LanguageProfile:
    """Get the language profile for a given language code.

    Args:
        language_code: ISO 639-1 language code (e.g., 'hi', 'en') or 'auto'

    Returns:
        LanguageProfile for the specified language, or AUTO_PROFILE if not found
    """
    return LANGUAGE_PROFILES.get(language_code.lower(), AUTO_PROFILE)


def get_vad_config(language_code: str) -> VADConfig:
    """Get VAD configuration optimized for the specified language."""
    return get_profile(language_code).vad


def get_recommended_model(language_code: str, quality_level: str = "balanced") -> str:
    """Get the recommended model for a language and quality level.

    Args:
        language_code: ISO 639-1 language code or 'auto'
        quality_level: One of 'fast' (tiny), 'balanced' (base), 'high' (small)

    Returns:
        Model name string suitable for WhisperModel
    """
    profile = get_profile(language_code)
    models = profile.models

    quality_map = {
        "fast": models.tiny,
        "balanced": models.base,
        "high": models.small,
        "tiny": models.tiny,
        "base": models.base,
        "small": models.small,
    }

    return quality_map.get(quality_level, models.base)


def get_transcription_params(language_code: str) -> dict[str, float | bool]:
    """Get transcription parameters optimized for the specified language.

    Returns a dictionary with keys:
        - temperature: float
        - precise_mode: bool
        - phonetic_patience: bool
    """
    profile = get_profile(language_code)
    return {
        "temperature": profile.temperature,
        "precise_mode": profile.precise_mode,
        "phonetic_patience": profile.phonetic_patience,
    }


# Global script detector instance
script_detector: Final[ScriptDetector] = ScriptDetector()


def detect_mixed_content(text: str) -> dict[str, bool | str | None]:
    """Analyze text for mixed Hindi-English content.

    Returns a dictionary with:
        - is_mixed: bool - True if both scripts present
        - scripts: tuple - Detected script codes
        - dominant_script: str | None - 'devanagari', 'latin', 'mixed', or None
    """
    scripts = script_detector.detect_scripts(text)
    return {
        "is_mixed": script_detector.is_mixed_hindi_english(text),
        "scripts": scripts,
        "dominant_script": script_detector.get_dominant_script(text),
    }
