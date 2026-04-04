"""Dictation text cleanup and normalization for speech-to-text processing.

Provides utilities for cleaning, normalizing, and composing dictation transcripts:
- Normalizing dictation text (fixing spacing, punctuation, capitalization)
- Cleaning filler words and hallucinations from final transcripts
- Composing final transcript from segments with duplicate detection
- Stabilizing partial text during live dictation

Example:
    >>> from app.stt.dictation_cleanup import clean_final_text_from_segments
    >>> result = clean_final_text_from_segments(["hello ", "  world  "])
    >>> print(result.clean_final_text)
    Hello world.
"""

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
    """Container for dictation text variants at different processing stages.

    Holds raw and cleaned versions of partial and final transcript text for
    use in display and storage.

    Attributes:
        raw_partial_text: Raw normalized text from current partial segment
        display_partial_text: Formatted text for live display during dictation
        raw_final_text: Concatenated final text with basic normalization
        clean_final_text: Fully cleaned text with filler/hallucination removal
    """

    raw_partial_text: str
    display_partial_text: str
    raw_final_text: str
    clean_final_text: str


@dataclass(slots=True)
class TranscriptComposer:
    """Composes final transcript from incoming dictation segments.

    Handles merging of new segments with existing composed text, including
    duplicate detection, overlap handling, and text normalization.

    Attributes:
        composed_text: Current composed transcript text
        max_overlap_words: Maximum words to consider for overlap detection (default: 30)
        duplicate_threshold: Similarity threshold for duplicate detection (default: 0.92)

    Example:
        >>> composer = TranscriptComposer()
        >>> composer.add_final_segment("Hello world")
        >>> composer.add_final_segment("world today")
        >>> print(composer.get_text())
        Hello world today
    """

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
        """Add a final transcript segment and return updated composed text.

        Args:
            text: New transcript segment to add
            start: Segment start time in seconds (unused, retained for API compatibility)
            end: Segment end time in seconds (unused, retained for API compatibility)
            confidence: Segment confidence score (unused, retained for API compatibility)

        Returns:
            Updated composed transcript text
        """
        del start, end, confidence
        self.composed_text = compose_transcript_text(
            self.composed_text,
            text,
            max_overlap_words=self.max_overlap_words,
            duplicate_threshold=self.duplicate_threshold,
        )
        return self.composed_text

    def get_text(self) -> str:
        """Get current composed transcript text.

        Returns:
            Current composed transcript
        """
        return self.composed_text

    def reset(self) -> None:
        """Reset composed text to empty string."""
        self.composed_text = ""


def normalize_dictation_text(text: str) -> str:
    """Normalize dictation text with consistent spacing and punctuation.

    Applies the following normalizations:
    - Collapses multiple whitespace characters to single space
    - Removes space before punctuation marks (.,;:!?)
    - Strips leading/trailing whitespace

    Args:
        text: Input text to normalize

    Returns:
        Normalized text with consistent formatting

    Example:
        >>> normalize_dictation_text("  hello  ,   world  ")
        'hello, world'
    """
    normalized = _WHITESPACE_RE.sub(" ", (text or "").strip())
    normalized = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", normalized)
    return normalized.strip()


def stabilize_partial_text(previous_display: str, candidate_raw: str) -> str:
    """Stabilize live partial text to reduce flickering during dictation.

    Compares the candidate text with the previous display text and returns
    the more stable option when they are similar. This prevents jittery
    display updates when small variations occur between recognition results.

    Args:
        previous_display: Previously displayed text
        candidate_raw: New candidate text from speech recognition

    Returns:
        Stabilized text for display (either previous or candidate)

    Example:
        >>> stabilize_partial_text("Hello wor", "Hello world")
        'Hello wor'
    """
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
    """Clean dictation text from a list of transcript segments.

    Processes a list of segments to produce both raw and cleaned final text,
    along with partial text for live display. Applies normalization, duplicate
    removal, and cleaning operations.

    Args:
        segments: List of transcript segment strings

    Returns:
        DictationTexts containing raw and cleaned text variants

    Example:
        >>> result = clean_final_text_from_segments(["hello", "hello", "world"])
        >>> result.clean_final_text
        'Hello world.'
    """
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
    """Clean final transcript text by removing filler words and hallucinations.

    Applies the following cleaning operations:
    - Normalizes text spacing and punctuation
    - Trims repetitive segments using repetition guard
    - Removes filler-only text (um, uh, ah, etc.)
    - Removes hallucination-only text (thank you, goodbye, etc.)
    - Capitalizes first letter and adds trailing period if needed

    Args:
        text: Input text to clean

    Returns:
        Cleaned text, or empty string if text is only filler/hallucination

    Example:
        >>> clean_final_text("um hello world")
        'Hello world.'
        >>> clean_final_text("uh")
        ''
    """
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
    """Compose transcript by merging candidate text with existing text.

    Handles merging new transcript segments with existing composed text using:
    - Refined tail replacement detection
    - Duplicate detection with configurable threshold
    - Word overlap detection for partial duplicates
    - Clean joining with appropriate spacing

    Args:
        existing_text: Current composed transcript text
        candidate_text: New transcript segment to add
        max_overlap_words: Maximum words to check for overlap (default: 30)
        duplicate_threshold: Similarity threshold for duplicate detection (default: 0.92)

    Returns:
        Composed transcript text with candidate merged

    Example:
        >>> compose_transcript_text("Hello world", "world today")
        'Hello world today'
    """
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
    """Attempt to merge candidate text with the last existing segment.

    Checks if the candidate text is similar enough to the last segment to
    be considered an update rather than a new segment. Updates the segment
    in-place if merge is successful.

    Args:
        existing_segments: List of segment dictionaries with 'raw_text' or 'text' keys
        candidate_text: New candidate text to potentially merge

    Returns:
        True if segments were merged, False if candidate is distinct

    Example:
        >>> segments = [{"raw_text": "hello", "text": "Hello"}]
        >>> merge_segment_texts(segments, "hello world")
        True
        >>> segments[0]["raw_text"]
        'hello world'
    """
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
    """Collapse adjacent duplicate segments, keeping the longer version.

    Merges consecutive segments that are nearly identical (97% similarity),
    preserving the longer version when sizes differ.

    Args:
        segments: List of normalized text segments

    Returns:
        Collapsed text with duplicates removed

    Example:
        >>> _collapse_adjacent_duplicates(["hello", "hello", "world"])
        'hello world'
    """
    collapsed: list[str] = []
    for segment in segments:
        if (
            collapsed
            and SequenceMatcher(None, collapsed[-1].lower(), segment.lower()).ratio() >= 0.97
        ):
            if len(segment) > len(collapsed[-1]):
                collapsed[-1] = segment
            continue
        collapsed.append(segment)
    return normalize_dictation_text(" ".join(collapsed))


def _format_partial(text: str) -> str:
    """Format text for partial/live display.

    Applies first-letter capitalization to text for display purposes.

    Args:
        text: Input text to format

    Returns:
        Text with first letter capitalized

    Example:
        >>> _format_partial("hello world")
        'Hello world'
    """
    if not text:
        return ""
    return _capitalize_first(text)


def _find_word_overlap(existing: str, candidate: str, *, max_overlap_words: int) -> int:
    """Find the number of trailing words in existing that match candidate prefix.

    Compares the end of existing text with the start of candidate text to
    find word-level overlap for merging purposes.

    Args:
        existing: Existing transcript text
        candidate: New candidate text
        max_overlap_words: Maximum words to check

    Returns:
        Number of overlapping words (0 if no overlap)

    Example:
        >>> _find_word_overlap("hello world", "world today", max_overlap_words=5)
        1
    """
    existing_tokens = _match_tokens(existing.split())
    candidate_tokens = _match_tokens(candidate.split())
    max_k = min(len(existing_tokens), len(candidate_tokens), max_overlap_words)

    for overlap in range(max_k, 0, -1):
        if existing_tokens[-overlap:] == candidate_tokens[:overlap]:
            return overlap

    return 0


def _replace_refined_tail(existing: str, candidate: str) -> str | None:
    """Check if candidate is a refined version of the existing tail.

    Detects when a new transcription is likely a refinement of the last
    few words of existing text (e.g., corrected recognition), and performs
    the replacement if valid.

    Args:
        existing: Existing transcript text
        candidate: New candidate text

    Returns:
        Replaced text if refinement detected, None otherwise
    """
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
    """Normalize tokens for matching by removing punctuation and lowercasing.

    Strips leading/trailing non-word characters (punctuation) from each token
    and converts to lowercase for comparison purposes.

    Args:
        tokens: List of text tokens

    Returns:
        List of normalized tokens

    Example:
        >>> _match_tokens(["Hello!", "world.", "test,"])
        ['hello', 'world', 'test']
    """
    matched: list[str] = []
    for token in tokens:
        normalized = _TOKEN_PUNCT_RE.sub("", token).lower()
        if normalized:
            matched.append(normalized)
    return matched


def _tail_text(text: str, max_words: int) -> str:
    """Extract the last N words from text.

    Retrieves the trailing portion of text up to max_words words.

    Args:
        text: Input text
        max_words: Maximum number of words to return

    Returns:
        Last N words of text, or empty string if text is empty

    Example:
        >>> _tail_text("hello world today is great", 2)
        'today is great'
    """
    tokens = normalize_dictation_text(text).split()
    if not tokens:
        return ""
    return " ".join(tokens[-max_words:])


def _capitalize_first(text: str) -> str:
    """Capitalize the first alphabetic character in text.

    Finds the first character that is alphabetic and capitalizes it,
    leaving the rest of the text unchanged.

    Args:
        text: Input text

    Returns:
        Text with first letter capitalized

    Example:
        >>> _capitalize_first("hello world")
        'Hello world'
        >>> _capitalize_first("  hello")
        '  Hello'
    """
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.upper() + text[index + 1 :]
    return text
