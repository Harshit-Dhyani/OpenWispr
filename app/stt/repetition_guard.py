from __future__ import annotations

import re
from collections import Counter

_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+\s+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")


def normalize_guard_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def tokenize_guard_text(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(normalize_guard_text(text))]


def repeated_sentence_count(text: str) -> int:
    sentences = [normalize_guard_text(part).lower().rstrip(".!?") for part in _extract_sentences(text)]
    if not sentences:
        return 0

    longest = 1
    current = 1
    for index in range(1, len(sentences)):
        if sentences[index] == sentences[index - 1]:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def unique_token_ratio(text: str) -> float:
    tokens = tokenize_guard_text(text)
    if not tokens:
        return 1.0
    return len(set(tokens)) / len(tokens)


def repeated_ngram_run(text: str, *, min_size: int = 2, max_size: int = 5) -> int:
    tokens = tokenize_guard_text(text)
    if len(tokens) < min_size * 2:
        return 0

    longest = 1
    for size in range(min_size, min(max_size, len(tokens) // 2) + 1):
        current = 1
        previous: tuple[str, ...] | None = None
        for index in range(0, len(tokens) - size + 1, size):
            ngram = tuple(tokens[index : index + size])
            if len(ngram) != size:
                break
            if previous is not None and ngram == previous:
                current += 1
                longest = max(longest, current)
            else:
                current = 1
            previous = ngram
    return longest


def repetition_score(text: str) -> float:
    tokens = tokenize_guard_text(text)
    if len(tokens) < 4:
        return 0.0

    ratio = 1.0 - unique_token_ratio(text)
    tail = tokens[-min(8, len(tokens)) :]
    half = len(tail) // 2
    if half >= 2 and tail[:half] == tail[half : half * 2]:
        ratio = max(ratio, 0.9)
    return ratio


def is_repetitive_segment(
    text: str,
    *,
    compression_ratio: float | None = None,
    avg_logprob: float | None = None,
) -> bool:
    normalized = normalize_guard_text(text)
    if not normalized:
        return False

    sentence_runs = repeated_sentence_count(normalized)
    ngram_runs = repeated_ngram_run(normalized)
    token_ratio = unique_token_ratio(normalized)
    score = repetition_score(normalized)
    token_count = len(tokenize_guard_text(normalized))

    if sentence_runs >= 3 or ngram_runs >= 3:
        return True
    if token_count >= 10 and token_ratio <= 0.35:
        return True
    if score >= 0.82:
        return True
    if compression_ratio is not None and compression_ratio > 2.4:
        if sentence_runs >= 2 or ngram_runs >= 2 or score >= 0.7:
            return True
        if avg_logprob is not None and avg_logprob < -0.9:
            return True
    return False


def trim_repetitive_segment(text: str) -> str:
    normalized = normalize_guard_text(text)
    if not normalized:
        return ""

    sentences = _extract_sentences(normalized)
    if len(sentences) >= 2:
        deduped: list[str] = []
        for sentence in sentences:
            current = normalize_guard_text(sentence)
            if deduped and deduped[-1].lower().rstrip(".!?") == current.lower().rstrip(".!?"):
                continue
            deduped.append(current)
        normalized = " ".join(deduped).strip()

    tokens = tokenize_guard_text(normalized)
    if not tokens:
        return ""

    counts = Counter(tokens)
    if len(tokens) >= 8 and counts.most_common(1)[0][1] >= max(4, len(tokens) // 2):
        # Keep the first short span rather than passing obvious loop spam through cleanup.
        kept = normalize_guard_text(" ".join(tokens[: min(6, len(tokens))]))
        return kept

    return normalize_guard_text(normalized)


def dedupe_boundary(
    existing_text: str,
    new_text: str,
    *,
    min_overlap_words: int = 2,
    max_overlap_words: int = 12,
) -> str:
    existing = normalize_guard_text(existing_text)
    candidate = normalize_guard_text(new_text)
    if not candidate:
        return existing
    if not existing:
        return candidate

    existing_tokens = tokenize_guard_text(existing)
    candidate_tokens = tokenize_guard_text(candidate)
    max_words = min(len(existing_tokens), len(candidate_tokens), max_overlap_words)

    overlap = 0
    for size in range(max_words, min_overlap_words - 1, -1):
        if existing_tokens[-size:] == candidate_tokens[:size]:
            overlap = size
            break

    if overlap <= 0:
        return normalize_guard_text(f"{existing} {candidate}")

    original_candidate_tokens = candidate.split()
    tail = original_candidate_tokens[overlap:]
    if not tail:
        return existing
    joiner = "" if existing.endswith("-") else " "
    return normalize_guard_text(f"{existing}{joiner}{' '.join(tail)}")


def _extract_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for match in _SENTENCE_RE.findall(normalize_guard_text(text)):
        sentence = normalize_guard_text(match)
        if sentence:
            sentences.append(sentence)
    return sentences
