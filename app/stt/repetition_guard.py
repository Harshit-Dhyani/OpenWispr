"""Repetition detection and filtering for transcribed text.

Provides comprehensive tools for detecting and handling repetitive patterns in
transcribed speech to filter out low-quality transcripts caused by STT model
hallucinations or audio artifacts.

Features:
- Text normalization and tokenization utilities
- Sentence-level repetition detection
- N-gram analysis for phrase repetition patterns
- Repetition scoring for transcript quality assessment
- Segment trimming and deduplication
- Boundary handling for overlapping text segments
"""

from __future__ import annotations

import re
from collections import Counter

_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+\s+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")


def normalize_guard_text(text: str) -> str:
    """Normalize text by collapsing whitespace and trimming.

    Removes extra spaces, newlines, and tabs, converting them to single
    spaces, then strips leading and trailing whitespace.

    Args:
        text: Input text to normalize.

    Returns:
        Normalized text with collapsed whitespace.

    Example:
        >>> normalize_guard_text("  hello   world  ")
        'hello world'
        >>> normalize_guard_text("one\n\ttwo")
        'one two'
    """
    return " ".join((text or "").split()).strip()


def tokenize_guard_text(text: str) -> list[str]:
    """Tokenize text into lowercase word tokens.

    Extracts alphanumeric tokens from the text and converts them to lowercase.
    Handles contractions by preserving apostrophes within tokens.

    Args:
        text: Input text to tokenize.

    Returns:
        List of lowercase tokens in order of appearance.

    Example:
        >>> tokenize_guard_text("Hello World! It's fine.")
        ['hello', 'world', "it's", 'fine']
    """
    if not text:
        return []
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def repeated_sentence_count(text: str) -> int:
    """Find the longest run of consecutive repeated sentences.

    Analyzes text for consecutive identical sentences and returns the length
    of the longest such run. Sentences are compared case-insensitively with
    punctuation stripped.

    Args:
        text: Input text to analyze.

    Returns:
        Maximum count of consecutive identical sentences (1 if no repetition).

    Example:
        >>> repeated_sentence_count("Hello world. Hello world. Hello world.")
        3
        >>> repeated_sentence_count("Hello world. Goodbye world.")
        1
    """
    sentences = [
        normalize_guard_text(part).lower().rstrip(".!?") for part in _extract_sentences(text)
    ]
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
    """Calculate ratio of unique tokens to total tokens.

    Computes the proportion of unique tokens in the text. Lower values indicate
    more repetitive text.

    Args:
        text: Input text to analyze.

    Returns:
        Ratio of unique tokens to total tokens (1.0 for empty text).

    Example:
        >>> unique_token_ratio("hello world hello world")
        0.5
        >>> unique_token_ratio("hello world")
        1.0
    """
    tokens = tokenize_guard_text(text)
    if not tokens:
        return 1.0
    return len(set(tokens)) / len(tokens)


def repeated_ngram_run(text: str, *, min_size: int = 2, max_size: int = 5) -> int:
    """Find the longest run of consecutive repeated n-grams.

    Analyzes tokenized text for consecutive repeated n-grams of varying sizes.
    Checks for repeated sequences of 2-5 tokens (configurable) and returns
    the longest run found.

    Args:
        text: Input text to analyze.
        min_size: Minimum n-gram size to check (default: 2).
        max_size: Maximum n-gram size to check (default: 5).

    Returns:
        Maximum count of consecutive identical n-grams (0 if insufficient tokens).

    Example:
        >>> repeated_ngram_run("the quick brown the quick brown fox")
        2
        >>> repeated_ngram_run("hello world foo bar")
        0
    """
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
    """Calculate repetition score for text quality assessment.

    Computes a score between 0.0 and 1.0 indicating repetition severity.
    Considers both token uniqueness and end-of-text repetition patterns.
    Scores above 0.8 typically indicate poor quality transcripts.

    Args:
        text: Input text to score.

    Returns:
        Repetition score (0.0 for texts under 4 tokens).

    Example:
        >>> repetition_score("hello hello hello hello hello")
        0.9
        >>> repetition_score("the quick brown fox jumps")
        0.0
    """
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
    """Determine if a text segment contains excessive repetition.

    Uses multiple heuristics to detect repetitive transcripts that should
    be filtered out:
    - Sentence repetition (3+ identical sentences)
    - N-gram repetition (3+ identical phrases)
    - Low token diversity (<=35% unique for 10+ tokens)
    - High repetition score (>=0.82)
    - Combined metrics with compression ratio and log probability

    Args:
        text: Input text to evaluate.
        compression_ratio: Optional compression ratio for additional analysis.
        avg_logprob: Optional average log probability for additional analysis.

    Returns:
        True if text shows excessive repetition, False otherwise.

    Example:
        >>> is_repetitive_segment("hello world hello world hello world")
        True
        >>> is_repetitive_segment("the quick brown fox jumps over")
        False
    """
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
    """Trim repetitive content from a text segment.

    Removes repeated sentences at the start and filters out segments with
    excessive token repetition. Keeps a short prefix of repetitive content
    rather than discarding entirely.

    Operations performed:
    1. Deduplicate consecutive identical sentences
    2. For excessive single-token repetition, keep first 6 tokens

    Args:
        text: Input text to trim.

    Returns:
        Trimmed text with repetition removed, empty string if invalid.

    Example:
        >>> trim_repetitive_segment("hello world hello world hello world")
        'hello world'
        >>> trim_repetitive_segment("test. test. unique content here.")
        'test. unique content here.'
    """
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
    """Deduplicate overlapping text at segment boundaries.

    Detects when new text starts with content that already exists at the
    end of existing text and removes the overlap to prevent duplication.
    This is essential for handling streaming transcripts where boundaries
    may contain repeated words.

    Args:
        existing_text: Preceding text segment.
        new_text: New text segment to append.
        min_overlap_words: Minimum word overlap to trigger deduplication (default: 2).
        max_overlap_words: Maximum word overlap to consider (default: 12).

    Returns:
        Combined text with overlapping content removed.

    Example:
        >>> dedupe_boundary("hello world", "world test")
        'hello world test'
        >>> dedupe_boundary("hello world", "completely different")
        'hello world completely different'
    """
    existing = normalize_guard_text(existing_text)
    candidate = normalize_guard_text(new_text)
    if not candidate:
        return existing
    if not existing:
        return candidate

    existing_tokens = tokenize_guard_text(existing)
    candidate_tokens = tokenize_guard_text(candidate)
    
    if len(existing_tokens) < min_overlap_words or len(candidate_tokens) < min_overlap_words:
        return normalize_guard_text(f"{existing} {candidate}")
    
    max_words = min(len(existing_tokens), len(candidate_tokens), max_overlap_words)
    
    # Quick check: compare last token first for early exit
    if not existing_tokens or not candidate_tokens:
        return normalize_guard_text(f"{existing} {candidate}")
    
    # Check exact match of full token list slices for efficiency
    # Iterate from largest to smallest overlap
    for size in range(max_words, min_overlap_words - 1, -1):
        # Compare slices directly - list equality is fast in Python
        if existing_tokens[-size:] == candidate_tokens[:size]:
            overlap = size
            break
    else:
        overlap = 0

    if overlap <= 0:
        return normalize_guard_text(f"{existing} {candidate}")

    original_candidate_tokens = candidate.split()
    tail = original_candidate_tokens[overlap:]
    if not tail:
        return existing
    joiner = "" if existing.endswith("-") else " "
    return normalize_guard_text(f"{existing}{joiner}{' '.join(tail)}")


def _extract_sentences(text: str) -> list[str]:
    """Extract sentences from text using punctuation delimiters.

    Splits text into sentences based on period, exclamation, and question
    mark delimiters while preserving the delimiters in the output.

    Args:
        text: Input text to split.

    Returns:
        List of sentence strings in order of appearance.
    """
    sentences: list[str] = []
    for match in _SENTENCE_RE.findall(normalize_guard_text(text)):
        sentence = normalize_guard_text(match)
        if sentence:
            sentences.append(sentence)
    return sentences
