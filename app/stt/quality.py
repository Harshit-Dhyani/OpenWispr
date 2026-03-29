"""Transcript segment quality assessment with multi-stage filtering.

Provides comprehensive quality control for transcribed speech segments with:
- Confidence-based filtering using Whisper confidence scores
- Hallucination detection for common false positive patterns
- Repetition detection for repetitive/low-information content
- Script mismatch detection for Hindi/English language boundaries
- Low-entropy content filtering for garbled output
- Punctuation ratio checks for stuttering/garbage detection
- Filler word suppression for low-value utterances
- No-speech and logprob-based uncertainty detection
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache

from app.config.constants import (
    COMMON_FILLER_WORDS,
    HALLUCINATION_CONFIDENCE_THRESHOLD,
    HALLUCINATION_PHRASES,
    QualityConstants,
)

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for performance
_COMPILED_FILLER_SET = frozenset(f.lower() for f in COMMON_FILLER_WORDS) | frozenset(
    {"thanks", "thank you", "bye", "goodbye"}
)
_COMPILED_HALLUCINATION_SET = frozenset(p.lower() for p in HALLUCINATION_PHRASES)
_NON_LATIN_PATTERN = re.compile(r".*[\u0250-\uffff]")
_LATIN_LETTER_PATTERN = re.compile(r"[a-zA-Z]")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]")


@dataclass(slots=True)
class SegmentQuality:
    """Quality assessment result for a transcript segment.

    Attributes:
        display_text: Cleaned and normalized text for display
        suppressed: Whether the segment should be suppressed from output
        suppression_reasons: List of reasons why the segment was suppressed
        quality_label: Quality classification (JUNK, WEAK, or OK)
        script_mismatch: Whether script mismatch was detected
    """

    display_text: str
    suppressed: bool
    suppression_reasons: list[str]
    quality_label: str
    script_mismatch: bool


def assess_segment_quality(
    text: str,
    *,
    confidence: float,
    language_mode: str,
    detected_language: str,
    avg_logprob: float | None = None,
    no_speech_prob: float | None = None,
    compression_ratio: float | None = None,
) -> SegmentQuality:
    """Assess the quality of a transcript segment using multiple heuristics.

    Performs multi-stage quality assessment combining confidence scoring with
    pattern-based detection for hallucinations, repetitions, fillers, and
    script mismatches. Returns a structured quality assessment with suppression
    decision and detailed reasons.

    Args:
        text: Raw transcript text to assess
        confidence: Whisper confidence score (0.0 to 1.0)
        language_mode: Expected language mode ("en", "hi", "auto")
        detected_language: Language detected by Whisper
        avg_logprob: Average log probability from Whisper (optional)
        no_speech_prob: Probability that segment contains no speech (optional)
        compression_ratio: Compression ratio from Whisper (optional)

    Returns:
        SegmentQuality object containing assessment results

    Example:
        >>> quality = assess_segment_quality(
        ...     text="Hello world this is a test",
        ...     confidence=0.95,
        ...     language_mode="en",
        ...     detected_language="en"
        ... )
        >>> print(quality.quality_label)
        'OK'
        >>> print(quality.suppressed)
        False
    """
    # Single structured debug log instead of verbose per-check logging
    logger.debug(
        "Quality assessment: text_len=%d, confidence=%.3f, lang_mode=%s, detected=%s",
        len(text),
        confidence,
        language_mode,
        detected_language,
    )

    cleaned = " ".join(text.split()).strip()
    reasons: list[str] = []
    script_mismatch = _script_mismatch(cleaned, language_mode, detected_language)

    if not cleaned:
        reasons.append("empty")

    # Punctuation ratio check - prevents garbled output with excessive punctuation
    # Threshold 0.45: More than 45% punctuation indicates likely garbage/stuttering
    punct_ratio = _punctuation_ratio(cleaned)
    if punct_ratio > QualityConstants.MAX_PUNCTUATION_RATIO:
        reasons.append("punctuation-heavy")

    # Repeated character check - catches hallucinations like "aaaaaa..."
    # Threshold 12: Legitimate words rarely have 12+ repeated characters
    char_run = _max_repeated_char_run(cleaned)
    if char_run >= QualityConstants.MAX_REPEATED_CHAR_RUN:
        reasons.append("repeated-character-run")

    # Entropy check - catches repetitive or low-information content
    # Threshold 0.12: Unique char ratio below 12% indicates repetitive text
    low_ent = _low_entropy(cleaned)
    if low_ent:
        reasons.append("low-entropy")

    # Filler word detection
    is_filler = _looks_like_filler(cleaned, confidence)
    if is_filler:
        reasons.append("low-value-filler")

    # Check for common hallucination phrases
    if _is_likely_hallucination(cleaned, confidence):
        reasons.append("likely-hallucination")

    # No-speech detection based on model's no_speech_prob
    if (
        no_speech_prob is not None
        and no_speech_prob > QualityConstants.NO_SPEECH_PROB_THRESHOLD
        and confidence < QualityConstants.NO_SPEECH_CONFIDENCE_THRESHOLD
    ):
        reasons.append("likely-no-speech")

    # Low logprob indicates model uncertainty
    if (
        avg_logprob is not None
        and avg_logprob < QualityConstants.LOW_LOGPROB_THRESHOLD
        and confidence < QualityConstants.LOW_LOGPROB_CONFIDENCE_THRESHOLD
    ):
        reasons.append("low-logprob")

    # Compression ratio anomaly detection
    if (
        compression_ratio is not None
        and compression_ratio > QualityConstants.COMPRESSION_RATIO_THRESHOLD
        and confidence < QualityConstants.COMPRESSION_CONFIDENCE_THRESHOLD
    ):
        reasons.append("compression-anomaly")

    # Script mismatch suppression (e.g., Hindi text when English expected)
    if script_mismatch and confidence < QualityConstants.NO_SPEECH_CONFIDENCE_THRESHOLD:
        reasons.append("script-mismatch")

    # Determine quality label based on confidence and reasons
    if reasons and confidence < QualityConstants.JUNK_CONFIDENCE_THRESHOLD:
        quality_label = QualityConstants.QUALITY_LABEL_JUNK
    elif reasons and confidence < QualityConstants.WEAK_CONFIDENCE_THRESHOLD:
        quality_label = QualityConstants.QUALITY_LABEL_WEAK
    else:
        quality_label = QualityConstants.QUALITY_LABEL_OK

    suppressed = quality_label == QualityConstants.QUALITY_LABEL_JUNK

    # Log result if suppressed
    if suppressed:
        logger.debug(
            "Segment suppressed: reasons=%s, confidence=%.3f, label=%s",
            reasons,
            confidence,
            quality_label,
        )

    return SegmentQuality(
        display_text=cleaned,
        suppressed=suppressed,
        suppression_reasons=reasons,
        quality_label=quality_label,
        script_mismatch=script_mismatch,
    )


def _punctuation_ratio(text: str) -> float:
    """Calculate the ratio of punctuation characters to total text length.

    Args:
        text: Input text to analyze

    Returns:
        Ratio of punctuation to total characters (0.0 to 1.0)

    Example:
        >>> _punctuation_ratio("Hello, world!")
        0.14285714285714285
    """
    if not text:
        return 0.0
    punctuation = len(_PUNCTUATION_PATTERN.findall(text))
    return punctuation / len(text)


def _max_repeated_char_run(text: str) -> int:
    """Find the longest run of repeated characters in the text.

    Detects hallucinations and speech artifacts like "aaaaaa" or "ummmmm".

    Args:
        text: Input text to analyze

    Returns:
        Length of the longest consecutive repeated character sequence

    Example:
        >>> _max_repeated_char_run("hellooooo")
        5
    """
    longest = 0
    current = 0
    previous = ""
    for char in text:
        if char == previous:
            current += 1
        else:
            current = 1
            previous = char
        longest = max(longest, current)
    return longest


def _low_entropy(text: str) -> bool:
    """Detect low-entropy content indicating repetitive or garbled text.

    Uses multiple heuristics:
    - Character uniqueness ratio (unique chars / total chars)
    - Token repetition count
    - Short text with low uniqueness

    Args:
        text: Input text to analyze

    Returns:
        True if text appears to be low-entropy/repetitive

    Example:
        >>> _low_entropy("the the the the the")
        True
    """
    compact = _WHITESPACE_PATTERN.sub("", text)
    compact_len = len(compact)
    if compact_len < 12:
        return False
    unique_ratio = len(set(compact)) / compact_len
    tokens = _TOKEN_PATTERN.findall(text)
    repeated_token = _repeated_token_fast(tokens)
    return (
        unique_ratio < QualityConstants.LOW_ENTROPY_UNIQUE_RATIO_THRESHOLD
        or repeated_token >= QualityConstants.LOW_ENTROPY_TOKEN_REPEAT_THRESHOLD
        or (
            len(tokens) <= QualityConstants.LOW_ENTROPY_SHORT_TOKEN_THRESHOLD
            and unique_ratio < QualityConstants.LOW_ENTROPY_SHORT_UNIQUE_RATIO
        )
    )


def _repeated_token_fast(tokens: list[str]) -> int:
    """Find the maximum count of consecutive identical tokens (optimized).

    Args:
        tokens: Pre-split tokens from text

    Returns:
        Maximum count of consecutive repeated tokens

    Example:
        >>> _repeated_token_fast(["yes", "yes", "yes", "okay"])
        3
    """
    if not tokens:
        return 0
    longest = 1
    current = 1
    prev = tokens[0]
    for i in range(1, len(tokens)):
        if tokens[i] == prev:
            current += 1
        else:
            if current > longest:
                longest = current
            current = 1
            prev = tokens[i]
    return max(longest, current)


# Common phrases Whisper hallucinates - use constants from app.core.constants
HALLUCINATION_PHRASES = HALLUCINATION_PHRASES


@lru_cache(maxsize=256)
def _is_likely_hallucination_cached(text_lower: str) -> bool:
    """Cached version of hallucination check."""
    return any(phrase in text_lower for phrase in _COMPILED_HALLUCINATION_SET)


def _is_likely_hallucination(text: str, confidence: float) -> bool:
    """Check if text matches common hallucination patterns from Whisper.

    Compares normalized text against known hallucination phrases and
    considers confidence threshold for suppression decision.

    Args:
        text: Normalized text to check
        confidence: Whisper confidence score

    Returns:
        True if text appears to be a hallucination
    """
    if confidence >= HALLUCINATION_CONFIDENCE_THRESHOLD:
        return False
    normalized = text.lower().strip()
    return _is_likely_hallucination_cached(normalized)


def _looks_like_filler(text: str, confidence: float) -> bool:
    """Detect filler words and low-value utterances.

    Checks for known filler words and short uncertain utterances that
    provide minimal value to the transcript.

    Args:
        text: Input text to analyze
        confidence: Whisper confidence score

    Returns:
        True if text appears to be a filler or low-value utterance

    Example:
        >>> _looks_like_filler("um", 0.5)
        True
    """
    normalized = text.lower().strip(" .,!?:;-'")

    # Check if the text is a known filler word with low confidence
    # Threshold 0.72: Only suppress fillers if confidence is below this level
    if normalized in _COMPILED_FILLER_SET:
        if confidence < QualityConstants.FILLER_CONFIDENCE_THRESHOLD:
            return True

    # Check for very short text with low confidence
    # Threshold 5 chars, 0.65 confidence: Short uncertain utterances are likely noise
    if (
        len(normalized) <= QualityConstants.SHORT_TEXT_MAX_LENGTH
        and confidence < QualityConstants.SHORT_TEXT_CONFIDENCE_THRESHOLD
    ):
        return True

    return False


def _script_mismatch(text: str, language_mode: str, detected_language: str) -> bool:
    """Detect script mismatch between expected and detected language.

    For English mode: detects presence of non-Latin scripts
    For Hindi mode: detects English text when Hindi is expected

    Args:
        text: Input text to analyze
        language_mode: Expected language mode ("en", "hi", "auto")
        detected_language: Language detected by Whisper

    Returns:
        True if there's a script mismatch

    Example:
        >>> _script_mismatch("हिंदी टेक्स्ट", "en", "hi")
        True
    """
    if language_mode == "auto":
        return False
    if not text:
        return False
    if language_mode == "en":
        return bool(_NON_LATIN_PATTERN.match(text))
    if language_mode == "hi":
        latin_ratio = _latin_letter_ratio(text)
        is_detected_en = detected_language == "en"
        return is_detected_en and latin_ratio > 0.95
    return False


def _contains_non_latin_letters(text: str) -> bool:
    """Check if text contains non-Latin alphabetic characters.

    Args:
        text: Input text to check

    Returns:
        True if text contains non-Latin letters

    Example:
        >>> _contains_non_latin_letters("hello")
        False
        >>> _contains_non_latin_letters("नमस्ते")
        True
    """
    return bool(_NON_LATIN_PATTERN.match(text))


def _latin_letter_ratio(text: str) -> float:
    """Calculate the ratio of Latin letters to total letters in text.

    Args:
        text: Input text to analyze

    Returns:
        Ratio of Latin letters to total letters (0.0 to 1.0)

    Example:
        >>> _latin_letter_ratio("hello world")
        1.0
        >>> _latin_letter_ratio("hello दुनिया")
        0.5384615384615384
    """
    letters = _LATIN_LETTER_PATTERN.findall(text)
    if not letters:
        return 0.0
    latin = sum(1 for char in letters if ord(char) <= 0x024F)
    return latin / len(letters)
