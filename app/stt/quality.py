from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)

COMMON_FILLERS = {
    "hmm",
    "uh",
    "um",
    "ah",
    "uhh",
    "ahh",
    "er",
    "erm",
}


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
    logger.debug("=" * 60)
    logger.debug("assess_segment_quality START")
    logger.debug("  Input text (raw): %r", text[:200] + "..." if len(text) > 200 else text)
    logger.debug("  confidence: %.4f", confidence)
    logger.debug("  language_mode: %r", language_mode)
    logger.debug("  detected_language: %r", detected_language)
    logger.debug("  avg_logprob: %s", f"{avg_logprob:.4f}" if avg_logprob is not None else "None")
    logger.debug(
        "  no_speech_prob: %s", f"{no_speech_prob:.4f}" if no_speech_prob is not None else "None"
    )
    logger.debug(
        "  compression_ratio: %s",
        f"{compression_ratio:.4f}" if compression_ratio is not None else "None",
    )

    cleaned = " ".join(text.split()).strip()
    logger.debug("  Cleaned text: %r", cleaned[:200] + "..." if len(cleaned) > 200 else cleaned)
    logger.debug("  Cleaned text length: %d chars", len(cleaned))

    reasons: list[str] = []
    script_mismatch = _script_mismatch(cleaned, language_mode, detected_language)
    logger.debug("  script_mismatch result: %s", script_mismatch)

    if not cleaned:
        reasons.append("empty")
        logger.debug("  [CHECK] empty: TRUE (text is empty after cleaning)")
    else:
        logger.debug("  [CHECK] empty: FALSE")

    punct_ratio = _punctuation_ratio(cleaned)
    logger.debug("  [CHECK] punctuation_ratio: %.4f (threshold: 0.45)", punct_ratio)
    if punct_ratio > 0.45:
        reasons.append("punctuation-heavy")
        logger.debug("  [CHECK] punctuation-heavy: TRUE")
    else:
        logger.debug("  [CHECK] punctuation-heavy: FALSE")

    char_run = _max_repeated_char_run(cleaned)
    logger.debug("  [CHECK] max_repeated_char_run: %d (threshold: 12)", char_run)
    if char_run >= 12:
        reasons.append("repeated-character-run")
        logger.debug("  [CHECK] repeated-character-run: TRUE")
    else:
        logger.debug("  [CHECK] repeated-character-run: FALSE")

    low_ent = _low_entropy(cleaned)
    logger.debug("  [CHECK] low_entropy: %s", low_ent)
    if low_ent:
        reasons.append("low-entropy")
        logger.debug("  [CHECK] low-entropy: TRUE")
    else:
        logger.debug("  [CHECK] low-entropy: FALSE")

    is_filler = _looks_like_filler(cleaned, confidence)
    logger.debug("  [CHECK] looks_like_filler: %s", is_filler)
    if is_filler:
        reasons.append("low-value-filler")
        logger.debug("  [CHECK] low-value-filler: TRUE")
    else:
        logger.debug("  [CHECK] low-value-filler: FALSE")

    # Check for common hallucination phrases
    if _is_likely_hallucination(cleaned, confidence):
        reasons.append("likely-hallucination")
        logger.debug("  [CHECK] likely-hallucination: TRUE")

    if no_speech_prob is not None and no_speech_prob > 0.6 and confidence < 0.7:
        reasons.append("likely-no-speech")
        logger.debug(
            "  [CHECK] likely-no-speech: TRUE (no_speech_prob=%.4f > 0.6, confidence=%.4f < 0.7)",
            no_speech_prob,
            confidence,
        )
    else:
        logger.debug(
            "  [CHECK] likely-no-speech: FALSE (no_speech_prob=%s)",
            f"{no_speech_prob:.4f}" if no_speech_prob is not None else "None",
        )

    if avg_logprob is not None and avg_logprob < -1.0 and confidence < 0.7:
        reasons.append("low-logprob")
        logger.debug(
            "  [CHECK] low-logprob: TRUE (avg_logprob=%.4f < -1.0, confidence=%.4f < 0.7)",
            avg_logprob,
            confidence,
        )
    else:
        logger.debug(
            "  [CHECK] low-logprob: FALSE (avg_logprob=%s)",
            f"{avg_logprob:.4f}" if avg_logprob is not None else "None",
        )

    if compression_ratio is not None and compression_ratio > 2.4 and confidence < 0.7:
        reasons.append("compression-anomaly")
        logger.debug(
            "  [CHECK] compression-anomaly: TRUE (compression_ratio=%.4f > 2.4, confidence=%.4f < 0.7)",
            compression_ratio,
            confidence,
        )
    else:
        logger.debug(
            "  [CHECK] compression-anomaly: FALSE (compression_ratio=%s)",
            f"{compression_ratio:.4f}" if compression_ratio is not None else "None",
        )

    if script_mismatch and confidence < 0.7:
        reasons.append("script-mismatch")
        logger.debug(
            "  [CHECK] script-mismatch suppression: TRUE (confidence=%.4f < 0.7)", confidence
        )
    else:
        logger.debug("  [CHECK] script-mismatch suppression: FALSE")

    logger.debug("  All suppression reasons collected: %r", reasons)

    if reasons and confidence < 0.70:
        quality_label = "junk"
        logger.debug(
            "  Quality label decision: 'junk' (reasons exist and confidence=%.4f < 0.70)",
            confidence,
        )
    elif reasons and confidence < 0.85:
        quality_label = "weak"
        logger.debug(
            "  Quality label decision: 'weak' (reasons exist but confidence=%.4f < 0.85)",
            confidence,
        )
    else:
        quality_label = "ok"
        logger.debug("  Quality label decision: 'ok' (no reasons found)")

    suppressed = quality_label == "junk"
    logger.debug("  Final suppressed: %s", suppressed)
    logger.debug("  Final quality_label: %r", quality_label)
    logger.debug("  Final script_mismatch: %s", script_mismatch)
    logger.debug("assess_segment_quality END")
    logger.debug("=" * 60)

    return SegmentQuality(
        display_text=cleaned,
        suppressed=suppressed,
        suppression_reasons=reasons,
        quality_label=quality_label,
        script_mismatch=script_mismatch,
    )


def _punctuation_ratio(text: str) -> float:
    logger.debug("    _punctuation_ratio called (text length: %d)", len(text))
    if not text:
        logger.debug("    _punctuation_ratio: empty text, returning 0.0")
        return 0.0
    punctuation = sum(1 for char in text if not char.isalnum() and not char.isspace())
    ratio = punctuation / len(text)
    logger.debug(
        "    _punctuation_ratio: %d punctuation chars / %d total = %.4f",
        punctuation,
        len(text),
        ratio,
    )
    return ratio


def _max_repeated_char_run(text: str) -> int:
    logger.debug("    _max_repeated_char_run called (text length: %d)", len(text))
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
    logger.debug("    _max_repeated_char_run: max run = %d", longest)
    return longest


def _low_entropy(text: str) -> bool:
    logger.debug("    _low_entropy called (text length: %d)", len(text))
    compact = re.sub(r"\s+", "", text)
    logger.debug("    _low_entropy: compact text length = %d", len(compact))
    if len(compact) < 12:
        logger.debug("    _low_entropy: FALSE (compact length %d < 12)", len(compact))
        return False
    unique_ratio = len(set(compact)) / max(len(compact), 1)
    tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    repeated_token = _repeated_token(text)
    logger.debug("    _low_entropy: unique_ratio = %.4f (threshold 0.12)", unique_ratio)
    logger.debug("    _low_entropy: repeated_token = %d (threshold 6)", repeated_token)
    logger.debug("    _low_entropy: token count = %d", len(tokens))
    result = unique_ratio < 0.12 or repeated_token >= 6 or (len(tokens) <= 2 and unique_ratio < 0.2)
    logger.debug("    _low_entropy: result = %s", result)
    return result


def _repeated_token(text: str) -> int:
    logger.debug("      _repeated_token called (text length: %d)", len(text))
    tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    logger.debug("      _repeated_token: found %d tokens", len(tokens))
    if not tokens:
        logger.debug("      _repeated_token: no tokens, returning 0")
        return 0
    if len(tokens) <= 10:
        logger.debug("      _repeated_token: tokens = %r", tokens)
    longest = 1
    current = 1
    for index in range(1, len(tokens)):
        if tokens[index] == tokens[index - 1]:
            current += 1
        else:
            longest = max(longest, current)
            current = 1
    result = max(longest, current)
    logger.debug("      _repeated_token: longest run = %d", result)
    return result


# Common phrases Whisper hallucinates
HALLUCINATION_PHRASES = {
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "like and subscribe",
    "click the link",
    "check the description",
    "see you next time",
    "don't forget to like",
}


def _is_likely_hallucination(text: str, confidence: float) -> bool:
    """Check if text matches common hallucination patterns."""
    normalized = text.lower().strip()
    for phrase in HALLUCINATION_PHRASES:
        if phrase in normalized and confidence < 0.80:
            return True
    return False


def _looks_like_filler(text: str, confidence: float) -> bool:
    logger.debug(
        "    _looks_like_filler called (text: %r, confidence: %.4f)",
        text[:100] if len(text) > 100 else text,
        confidence,
    )
    normalized = text.lower().strip(" .,!?:;-'\"")
    logger.debug("    _looks_like_filler: normalized = %r", normalized)

    if normalized in COMMON_FILLERS:
        is_filler_word = True
        logger.debug("    _looks_like_filler: '%s' found in COMMON_FILLERS", normalized)
        if confidence < 0.72:
            logger.debug(
                "    _looks_like_filler: TRUE (filler word '%s' with confidence %.4f < 0.72)",
                normalized,
                confidence,
            )
            return True
        else:
            logger.debug(
                "    _looks_like_filler: FALSE (filler word but confidence %.4f >= 0.72)",
                confidence,
            )
    else:
        is_filler_word = False
        logger.debug("    _looks_like_filler: '%s' NOT in COMMON_FILLERS", normalized)

    if len(normalized) <= 5 and confidence < 0.65:
        logger.debug(
            "    _looks_like_filler: TRUE (short text len=%d <= 5, confidence %.4f < 0.65)",
            len(normalized),
            confidence,
        )
        return True

    logger.debug(
        "    _looks_like_filler: FALSE (not a filler, len=%d, confidence=%.4f)",
        len(normalized),
        confidence,
    )
    return False


def _script_mismatch(text: str, language_mode: str, detected_language: str) -> bool:
    logger.debug(
        "    _script_mismatch called (language_mode=%r, detected_language=%r, text_len=%d)",
        language_mode,
        detected_language,
        len(text),
    )
    if language_mode == "auto":
        logger.debug("    _script_mismatch: FALSE (language_mode is 'auto')")
        return False
    if not text:
        logger.debug("    _script_mismatch: FALSE (empty text)")
        return False
    if language_mode == "en":
        has_non_latin = _contains_non_latin_letters(text)
        logger.debug("    _script_mismatch: mode='en', has_non_latin=%s", has_non_latin)
        if has_non_latin:
            logger.debug("    _script_mismatch: TRUE (non-Latin chars in 'en' mode)")
        return has_non_latin
    if language_mode == "hi":
        latin_ratio = _latin_letter_ratio(text)
        is_detected_en = detected_language == "en"
        result = is_detected_en and latin_ratio > 0.95
        logger.debug(
            "    _script_mismatch: mode='hi', detected_language='%s', latin_ratio=%.4f",
            detected_language,
            latin_ratio,
        )
        logger.debug(
            "    _script_mismatch: is_detected_en=%s, latin_ratio > 0.95 = %s",
            is_detected_en,
            latin_ratio > 0.95,
        )
        if result:
            logger.debug(
                "    _script_mismatch: TRUE (detected as English with %.1f%% Latin chars in 'hi' mode)",
                latin_ratio * 100,
            )
        return result
    logger.debug("    _script_mismatch: FALSE (unknown language_mode=%r)", language_mode)
    return False


def _contains_non_latin_letters(text: str) -> bool:
    logger.debug("      _contains_non_latin_letters called (text length: %d)", len(text))
    non_latin_chars = [
        (char, hex(ord(char))) for char in text if char.isalpha() and ord(char) > 0x024F
    ]
    result = len(non_latin_chars) > 0
    if result and len(non_latin_chars) <= 5:
        logger.debug(
            "      _contains_non_latin_letters: found %d non-Latin chars: %r",
            len(non_latin_chars),
            non_latin_chars,
        )
    else:
        logger.debug(
            "      _contains_non_latin_letters: found %d non-Latin chars", len(non_latin_chars)
        )
    logger.debug("      _contains_non_latin_letters: result = %s", result)
    return result


def _latin_letter_ratio(text: str) -> float:
    logger.debug("      _latin_letter_ratio called (text length: %d)", len(text))
    letters = [char for char in text if char.isalpha()]
    logger.debug("      _latin_letter_ratio: found %d alphabetic characters", len(letters))
    if not letters:
        logger.debug("      _latin_letter_ratio: no letters, returning 0.0")
        return 0.0
    latin = sum(1 for char in letters if ord(char) <= 0x024F)
    ratio = latin / len(letters)
    logger.debug(
        "      _latin_letter_ratio: %d Latin / %d total = %.4f (%.1f%%)",
        latin,
        len(letters),
        ratio,
        ratio * 100,
    )
    return ratio
