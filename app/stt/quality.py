from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable

from app.core.constants import (
    COMMON_FILLER_WORDS,
    HALLUCINATION_PHRASES,
    HALLUCINATION_CONFIDENCE_THRESHOLD,
    QualityConstants,
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
COMMON_FILLERS = COMMON_FILLER_WORDS | {"thanks", "thank you", "bye", "goodbye"}


@dataclass(slots=True)
class SegmentQuality:
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
    if not text:
        return 0.0
    punctuation = sum(1 for char in text if not char.isalnum() and not char.isspace())
    return punctuation / len(text)


def _max_repeated_char_run(text: str) -> int:
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
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 12:
        return False
    unique_ratio = len(set(compact)) / max(len(compact), 1)
    tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    repeated_token = _repeated_token(text)
    return (
        unique_ratio < QualityConstants.LOW_ENTROPY_UNIQUE_RATIO_THRESHOLD
        or repeated_token >= QualityConstants.LOW_ENTROPY_TOKEN_REPEAT_THRESHOLD
        or (
            len(tokens) <= QualityConstants.LOW_ENTROPY_SHORT_TOKEN_THRESHOLD
            and unique_ratio < QualityConstants.LOW_ENTROPY_SHORT_UNIQUE_RATIO
        )
    )


def _repeated_token(text: str) -> int:
    tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    if not tokens:
        return 0
    longest = 1
    current = 1
    for index in range(1, len(tokens)):
        if tokens[index] == tokens[index - 1]:
            current += 1
        else:
            longest = max(longest, current)
            current = 1
    return max(longest, current)


# Common phrases Whisper hallucinates - use constants from app.core.constants
HALLUCINATION_PHRASES = HALLUCINATION_PHRASES


def _is_likely_hallucination(text: str, confidence: float) -> bool:
    """Check if text matches common hallucination patterns."""
    normalized = text.lower().strip()
    for phrase in HALLUCINATION_PHRASES:
        if phrase in normalized and confidence < HALLUCINATION_CONFIDENCE_THRESHOLD:
            return True
    return False


def _looks_like_filler(text: str, confidence: float) -> bool:
    normalized = text.lower().strip(" .,!?:;-'\"")

    # Check if the text is a known filler word with low confidence
    # Threshold 0.72: Only suppress fillers if confidence is below this level
    if normalized in COMMON_FILLERS:
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
    if language_mode == "auto":
        return False
    if not text:
        return False
    if language_mode == "en":
        return _contains_non_latin_letters(text)
    if language_mode == "hi":
        latin_ratio = _latin_letter_ratio(text)
        is_detected_en = detected_language == "en"
        return is_detected_en and latin_ratio > 0.95
    return False


def _contains_non_latin_letters(text: str) -> bool:
    return any(char.isalpha() and ord(char) > 0x024F for char in text)


def _latin_letter_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    latin = sum(1 for char in letters if ord(char) <= 0x024F)
    return latin / len(letters)
