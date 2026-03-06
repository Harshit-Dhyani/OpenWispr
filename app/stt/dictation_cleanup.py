from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.stt.repetition_guard import dedupe_boundary, trim_repetitive_segment


_WHITESPACE_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
_TOKEN_PUNCT_RE = re.compile(r"(^[^\w]+|[^\w]+$)")
_FILLER_ONLY_RE = re.compile(
    r"^(?:uh|um|erm|hmm|mm|ah|oh|okay|ok|right|you know|like)$",
    flags=re.IGNORECASE,
)
_HALLUCINATION_ONLY_RE = re.compile(
    r"^(?:thank you|thanks|thanks a lot|thank you very much|bye|goodbye|thanks for watching|thank you for watching|see you next time|please subscribe|like and subscribe)$",
    flags=re.IGNORECASE,
)


@dataclass(slots=True)
class DictationTexts:
    raw_partial_text: str
    display_partial_text: str
    raw_final_text: str
    clean_final_text: str


@dataclass(slots=True)
class TranscriptComposer:
    composed_text: str = ""
    max_overlap_words: int = 30
    duplicate_threshold: float = 0.92

    def add_final_segment(
        self,
        text: str,
        *,
        start: float | None = None,
        end: float | None = None,
        confidence: float | None = None,
    ) -> str:
        del start, end, confidence
        self.composed_text = compose_transcript_text(
            self.composed_text,
            text,
            max_overlap_words=self.max_overlap_words,
            duplicate_threshold=self.duplicate_threshold,
        )
        return self.composed_text

    def get_text(self) -> str:
        return self.composed_text

    def reset(self) -> None:
        self.composed_text = ""


def normalize_dictation_text(text: str) -> str:
    normalized = _WHITESPACE_RE.sub(" ", (text or "").strip())
    normalized = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", normalized)
    return normalized.strip()


def stabilize_partial_text(previous_display: str, candidate_raw: str) -> str:
    candidate = _format_partial(normalize_dictation_text(candidate_raw))
    previous = (previous_display or "").strip()

    if not candidate:
        return previous
    if not previous:
        return candidate

    prev_lower = previous.lower()
    cand_lower = candidate.lower()

    if prev_lower == cand_lower:
        return previous
    if prev_lower.startswith(cand_lower) and len(previous) - len(candidate) <= 6:
        return previous
    if cand_lower.startswith(prev_lower) and len(candidate) - len(previous) <= 2:
        return previous

    similarity = SequenceMatcher(None, prev_lower, cand_lower).ratio()
    if similarity >= 0.92 and len(candidate) <= len(previous) + 2:
        return previous

    return candidate


def clean_final_text_from_segments(segments: list[str]) -> DictationTexts:
    normalized_segments = [normalize_dictation_text(segment) for segment in segments if segment]
    normalized_segments = [segment for segment in normalized_segments if segment]

    raw_final = _collapse_adjacent_duplicates(normalized_segments)
    clean_final = clean_final_text(raw_final)
    display_partial = _format_partial(normalized_segments[-1]) if normalized_segments else ""

    return DictationTexts(
        raw_partial_text=normalized_segments[-1] if normalized_segments else "",
        display_partial_text=display_partial,
        raw_final_text=raw_final,
        clean_final_text=clean_final,
    )


def clean_final_text(text: str) -> str:
    normalized = normalize_dictation_text(trim_repetitive_segment(text))
    if not normalized:
        return ""

    if _FILLER_ONLY_RE.match(normalized):
        return ""
    if _HALLUCINATION_ONLY_RE.match(normalized):
        return ""

    cleaned = _capitalize_first(normalized)
    if cleaned and cleaned[-1].isalnum():
        cleaned = f"{cleaned}."
    return cleaned


def compose_transcript_text(
    existing_text: str,
    candidate_text: str,
    *,
    max_overlap_words: int = 30,
    duplicate_threshold: float = 0.92,
) -> str:
    existing = normalize_dictation_text(existing_text)
    candidate = normalize_dictation_text(candidate_text)

    if not candidate:
        return existing
    if not existing:
        return candidate

    refined_replacement = _replace_refined_tail(existing, candidate)
    if refined_replacement is not None:
        return refined_replacement

    existing_tail = _tail_text(existing, max_overlap_words)
    similarity = SequenceMatcher(None, existing_tail.lower(), candidate.lower()).ratio()
    if similarity >= duplicate_threshold:
        return existing

    overlap = _find_word_overlap(existing, candidate, max_overlap_words=max_overlap_words)
    if overlap > 0:
        return dedupe_boundary(
            existing,
            candidate,
            min_overlap_words=1,
            max_overlap_words=max_overlap_words,
        )

    joiner = "" if existing.endswith("-") else " "
    return normalize_dictation_text(f"{existing}{joiner}{candidate}")


def merge_segment_texts(existing_segments: list[dict], candidate_text: str) -> bool:
    candidate = normalize_dictation_text(candidate_text)
    if not candidate:
        return False
    if not existing_segments:
        return False

    last = existing_segments[-1]
    last_text = normalize_dictation_text(last.get("raw_text") or last.get("text") or "")
    if not last_text:
        return False

    last_lower = last_text.lower()
    candidate_lower = candidate.lower()
    similarity = SequenceMatcher(None, last_lower, candidate_lower).ratio()

    if candidate_lower == last_lower:
        return True

    if candidate_lower.startswith(last_lower):
        last["raw_text"] = candidate
        last["text"] = _format_partial(candidate)
        return True

    if similarity >= 0.95:
        last["raw_text"] = candidate if len(candidate) >= len(last_text) else last_text
        last["text"] = _format_partial(last["raw_text"])
        return True

    return False


def _collapse_adjacent_duplicates(segments: list[str]) -> str:
    collapsed: list[str] = []
    for segment in segments:
        if collapsed and SequenceMatcher(None, collapsed[-1].lower(), segment.lower()).ratio() >= 0.97:
            if len(segment) > len(collapsed[-1]):
                collapsed[-1] = segment
            continue
        collapsed.append(segment)
    return normalize_dictation_text(" ".join(collapsed))


def _format_partial(text: str) -> str:
    if not text:
        return ""
    return _capitalize_first(text)


def _find_word_overlap(existing: str, candidate: str, *, max_overlap_words: int) -> int:
    existing_tokens = _match_tokens(existing.split())
    candidate_tokens = _match_tokens(candidate.split())
    max_k = min(len(existing_tokens), len(candidate_tokens), max_overlap_words)

    for overlap in range(max_k, 0, -1):
        if existing_tokens[-overlap:] == candidate_tokens[:overlap]:
            return overlap

    return 0


def _replace_refined_tail(existing: str, candidate: str) -> str | None:
    existing_tokens = existing.split()
    candidate_tokens = candidate.split()
    if not existing_tokens or not candidate_tokens:
        return None

    tail_length = min(len(existing_tokens), len(candidate_tokens))
    tail_text = " ".join(existing_tokens[-tail_length:])
    similarity = SequenceMatcher(None, tail_text.lower(), candidate.lower()).ratio()
    if similarity < 0.95:
        return None
    if len(candidate) < len(tail_text):
        return existing

    prefix_tokens = existing_tokens[:-tail_length]
    prefix = " ".join(prefix_tokens)
    joiner = "" if not prefix or prefix.endswith("-") else " "
    return normalize_dictation_text(f"{prefix}{joiner}{candidate}")


def _match_tokens(tokens: list[str]) -> list[str]:
    matched: list[str] = []
    for token in tokens:
        normalized = _TOKEN_PUNCT_RE.sub("", token).lower()
        if normalized:
            matched.append(normalized)
    return matched


def _tail_text(text: str, max_words: int) -> str:
    tokens = normalize_dictation_text(text).split()
    if not tokens:
        return ""
    return " ".join(tokens[-max_words:])


def _capitalize_first(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.upper() + text[index + 1 :]
    return text
