from __future__ import annotations

import re
from typing import Literal

from app.stt.repetition_guard import trim_repetitive_segment

TranscriptionMode = Literal["dictation", "literal", "session_paragraph"]
RefinementProfile = Literal[
    "raw", "clean_dictation", "professional", "student_notes", "code_log", "code_logs"
]

_WHITESPACE_RE = re.compile(r"\s+")
_DECIMAL_WORD_RE = re.compile(
    r"\b(?P<int>\d+|zero|one|two|three|four|five|six|seven|eight|nine)\s+point\s+(?P<frac>(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine)(?:\s+(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine))*)\b",
    flags=re.IGNORECASE,
)
_PERCENT_RE = re.compile(
    r"\b(?P<num>\d+(?:\.\d+)?)\s+percent\b",
    flags=re.IGNORECASE,
)
_PERCENT_WORD_RE = re.compile(
    r"\b(?P<num>(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)(?:\s+(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred))*)\s+percent\b",
    flags=re.IGNORECASE,
)
_DIGIT_WORD_RUN_RE = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|\d)(?:\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|\d)){1,}\b",
    flags=re.IGNORECASE,
)
_DOTTED_TOKEN_RE = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|\d)(?:\s+dot\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|\d))+\b",
    flags=re.IGNORECASE,
)
_SINGLE_LETTER_ACRONYM_RE = re.compile(
    r"\b(?:[A-Za-z]\s+){2,}[A-Za-z]\b",
)
_KNOWN_TOKEN_PREFIXES = ("HTTP", "HTTPS", "API", "SDK", "URL", "UUID", "JSON", "XML")
_NUMERIC_DOT_RE = re.compile(r"(?<=\d)\.(?=\d)")
_NUMERIC_DOT_PLACEHOLDER = "__OPENWISPR_NUMERIC_DOT__"

_DIGIT_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}

_NUMBER_WORD_VALUES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def normalize_postprocess_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "").strip()).strip()


def postprocess_live_text(text: str, *, mode: TranscriptionMode) -> str:
    del mode
    return normalize_postprocess_text(text)


def postprocess_final_text(
    text: str,
    *,
    mode: TranscriptionMode,
    profile: RefinementProfile = "clean_dictation",
) -> str:
    normalized = normalize_postprocess_text(text)
    if not normalized:
        return ""

    # Normalize numeric and literal tokens before repetition trimming so decimal
    # runs, dotted versions, and hotkey-like phrases are preserved.
    normalized = spoken_numbers_to_symbols(normalized, mode=mode)
    normalized = normalize_acronyms_and_tokens(normalized, mode=mode)
    has_numeric_dots = bool(_NUMERIC_DOT_RE.search(normalized))
    if has_numeric_dots:
        normalized = normalize_postprocess_text(normalized)
    else:
        normalized = normalize_postprocess_text(trim_repetitive_segment(normalized))
        normalized = _collapse_repeated_sentences(normalized)
        normalized = normalize_postprocess_text(normalized)

    if not normalized:
        return ""

    conservative_profile = profile in {"clean_dictation", "professional", "student_notes"}
    if mode != "literal" and profile not in {"code_log", "code_logs"}:
        normalized = _capitalize_first(normalized)
        if (
            normalized
            and (normalized[-1].isalnum() or normalized[-1] == "%")
            and conservative_profile
        ):
            normalized = f"{normalized}."
    return normalized


def spoken_numbers_to_symbols(text: str, *, mode: TranscriptionMode) -> str:
    normalized = normalize_postprocess_text(text)
    if not normalized:
        return ""

    normalized = _DECIMAL_WORD_RE.sub(_convert_decimal_match, normalized)
    normalized = _PERCENT_RE.sub(lambda match: f"{match.group('num')}%", normalized)
    normalized = _PERCENT_WORD_RE.sub(_convert_percent_word_match, normalized)

    if mode == "literal":
        normalized = _DOTTED_TOKEN_RE.sub(_convert_dotted_match, normalized)
        normalized = _DIGIT_WORD_RUN_RE.sub(_convert_digit_run_match, normalized)
        normalized = _replace_literal_symbol_words(normalized)

    return normalize_postprocess_text(normalized)


def normalize_acronyms_and_tokens(text: str, *, mode: TranscriptionMode) -> str:
    normalized = normalize_postprocess_text(text)
    if not normalized or mode != "literal":
        return normalized

    normalized = _SINGLE_LETTER_ACRONYM_RE.sub(
        lambda match: match.group(0).replace(" ", "").upper(),
        normalized,
    )

    for prefix in _KNOWN_TOKEN_PREFIXES:
        normalized = re.sub(
            rf"\b{prefix}\s+([A-Za-z])\b",
            lambda match: f"{prefix}{match.group(1).upper()}",
            normalized,
            flags=re.IGNORECASE,
        )

    return normalize_postprocess_text(normalized)


def _collapse_repeated_sentences(text: str) -> str:
    parts = re.findall(r"[^.!?]+[.!?]?", text)
    seen: list[str] = []
    for part in parts:
        sentence = normalize_postprocess_text(part)
        if not sentence:
            continue
        if seen and seen[-1].rstrip(".!?").lower() == sentence.rstrip(".!?").lower():
            continue
        seen.append(sentence)
    return " ".join(seen).strip() or text


def _convert_decimal_match(match: re.Match[str]) -> str:
    integer = _normalize_digit_token(match.group("int"))
    fraction_tokens = [
        _normalize_digit_token(token)
        for token in match.group("frac").split()
        if _normalize_digit_token(token) is not None
    ]
    if integer is None or not fraction_tokens:
        return match.group(0)
    return f"{integer}.{''.join(fraction_tokens)}"


def _convert_digit_run_match(match: re.Match[str]) -> str:
    tokens = match.group(0).split()
    converted = [_normalize_digit_token(token) for token in tokens]
    if any(token is None for token in converted):
        return match.group(0)
    return "".join(token for token in converted if token is not None)


def _convert_dotted_match(match: re.Match[str]) -> str:
    tokens = [token for token in match.group(0).split() if token.lower() != "dot"]
    delimiters = [token.lower() == "dot" for token in match.group(0).split()]
    del delimiters
    pieces = match.group(0).split()
    rendered: list[str] = []
    for token in pieces:
        if token.lower() == "dot":
            rendered.append(".")
            continue
        normalized = _normalize_digit_token(token)
        rendered.append(normalized if normalized is not None else token)
    return "".join(rendered)


def _convert_percent_word_match(match: re.Match[str]) -> str:
    parsed = _parse_small_number_phrase(match.group("num"))
    if parsed is None:
        return match.group(0)
    return f"{parsed}%"


def _replace_literal_symbol_words(text: str) -> str:
    replacements = {
        " dot ": ".",
        " underscore ": "_",
        " slash ": "/",
        " dash ": "-",
        " hyphen ": "-",
    }

    padded = f" {text} "
    for needle, replacement in replacements.items():
        padded = padded.replace(needle, replacement)
    return padded.strip()


def _normalize_digit_token(token: str) -> str | None:
    lowered = token.lower()
    if lowered.isdigit():
        return lowered
    return _DIGIT_WORDS.get(lowered)


def _parse_small_number_phrase(value: str) -> str | None:
    tokens = [token.lower() for token in value.split() if token.strip()]
    if not tokens:
        return None
    if all(token.isdigit() for token in tokens):
        return "".join(tokens)

    total = 0
    current = 0
    for token in tokens:
        if token.isdigit():
            current += int(token)
            continue
        if token == "hundred":
            if current == 0:
                current = 1
            current *= 100
            continue
        number = _NUMBER_WORD_VALUES.get(token)
        if number is None:
            return None
        if number >= 20 and number % 10 == 0:
            current += number
        else:
            current += number
    total += current
    return str(total) if total > 0 or "zero" in tokens else None


def _capitalize_first(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return f"{text[:index]}{char.upper()}{text[index + 1 :]}"
    return text


def _protect_numeric_dots(text: str) -> str:
    return _NUMERIC_DOT_RE.sub(_NUMERIC_DOT_PLACEHOLDER, text)


def _restore_numeric_dots(text: str) -> str:
    return text.replace(_NUMERIC_DOT_PLACEHOLDER, ".")
