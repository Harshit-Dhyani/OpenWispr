"""Transcript segment aggregation and utterance building.

Provides real-time transcript assembly with:
- Aggregating multiple transcript segments into coherent utterances
- Merging overlapping segments with deduplication
- Tracking accepted, dropped, and merged segment counts
- Repetition detection and trimming
- Text normalization and cleanup
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.stt.dictation_cleanup import (
    clean_final_text,
    compose_transcript_text,
    normalize_dictation_text,
)
from app.stt.repetition_guard import is_repetitive_segment, trim_repetitive_segment


@dataclass(slots=True)
class AggregatedUtterance:
    """Final aggregated utterance with metadata.

    Attributes:
        aggregated_raw_text: Raw concatenated text from all accepted segments.
        aggregated_clean_text: Final cleaned and formatted transcript text.
        accepted_segments_count: Number of segments successfully added.
        dropped_segments_count: Number of segments dropped (duplicates, repetition, etc.).
        merged_segments_count: Number of segments merged with previous text.
        warnings: List of warning messages for suppressed or modified segments.
    """

    aggregated_raw_text: str
    aggregated_clean_text: str
    accepted_segments_count: int
    dropped_segments_count: int
    merged_segments_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _AcceptedSegment:
    """Internal storage for accepted transcript segments.

    Attributes:
        segment_id: Unique identifier for the segment.
        raw_text: Raw text content from the segment.
        clean_text: Cleaned/normalized text content.
        start: Start timestamp in seconds.
        end: End timestamp in seconds.
        confidence: Confidence score for the segment.
    """

    segment_id: str
    raw_text: str
    clean_text: str
    start: float
    end: float
    confidence: float


@dataclass(slots=True)
class UtteranceAggregator:
    """Aggregates transcript segments into coherent utterances.

    Processes incoming transcript segments through a pipeline that:
    1. Normalizes and cleans incoming text
    2. Detects and trims repetitive content
    3. Merges with previous text, avoiding duplicates
    4. Tracks statistics for accepted, dropped, and merged segments

    Example:
        >>> aggregator = UtteranceAggregator()
        >>> aggregator.add_segment(
        ...     segment_id="seg-1",
        ...     text="Hello world",
        ...     display_text="Hello world",
        ...     start=0.0,
        ...     end=1.5,
        ...     confidence=0.95,
        ... )
        >>> aggregator.add_segment(
        ...     segment_id="seg-2",
        ...     text="This is a test",
        ...     display_text="This is a test",
        ...     start=1.5,
        ...     end=3.0,
        ...     confidence=0.90,
        ... )
        >>> result = aggregator.finalize()
        >>> print(result.aggregated_clean_text)
        Hello world this is a test
    """

    _segments: list[_AcceptedSegment] = field(default_factory=list)
    _aggregated_text: str = ""
    dropped_segments_count: int = 0
    merged_segments_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def add_segment(
        self,
        *args,
        segment_id: str | None = None,
        text: str | None = None,
        display_text: str = "",
        start: float = 0.0,
        end: float = 0.0,
        confidence: float = 0.0,
        suppressed: bool = False,
        suppression_reasons: list[str] | None = None,
    ) -> None:
        """Add a transcript segment for aggregation.

        Processes the segment through normalization, repetition detection,
        and deduplication. Segments may be dropped if they are suppressed,
        empty after normalization, or duplicate previously added text.

        Args:
            *args: Optional positional args (segment_id, text, display_text).
                If more than 3 positional args are provided, raises TypeError.
            segment_id: Unique identifier for the segment (required).
            text: Raw text content to process.
            display_text: Display-formatted text (used for clean_text if provided).
            start: Segment start timestamp in seconds.
            end: Segment end timestamp in seconds.
            confidence: Confidence score for the segment (0.0 to 1.0).
            suppressed: Whether the segment was suppressed by upstream processing.
            suppression_reasons: List of reasons why segment was suppressed.

        Raises:
            TypeError: If segment_id is None or positional args exceed 3.

        Example:
            >>> aggregator = UtteranceAggregator()
            >>> aggregator.add_segment("seg-1", "Hello", "Hello", 0.0, 1.0, 0.95)
            >>> aggregator.add_segment(segment_id="seg-2", text="World")
        """
        if args:
            if len(args) > 3:
                raise TypeError(
                    "UtteranceAggregator.add_segment accepts at most 3 positional args: "
                    "(segment_id, text, display_text)"
                )
            if len(args) >= 1:
                segment_id = str(args[0])
            if len(args) >= 2:
                text = str(args[1])
            if len(args) == 3:
                display_text = str(args[2])

        if segment_id is None:
            raise TypeError("segment_id is required")

        if suppressed:
            self.dropped_segments_count += 1
            if suppression_reasons:
                self.warnings.extend(
                    f"suppressed:{reason}" for reason in suppression_reasons if reason
                )
            return

        source_text = (text or "") or display_text
        normalized = normalize_dictation_text(source_text)
        raw_text = normalize_dictation_text(trim_repetitive_segment(normalized))
        if not raw_text:
            self.dropped_segments_count += 1
            return
        if is_repetitive_segment(normalized):
            if not raw_text or is_repetitive_segment(raw_text):
                self.dropped_segments_count += 1
                self.warnings.append("dropped:repetition")
                return
            self.warnings.append("trimmed:repetition")

        previous = self._aggregated_text
        self._aggregated_text = compose_transcript_text(previous, raw_text)
        if self._aggregated_text == previous:
            self.dropped_segments_count += 1
            return
        if previous:
            self.merged_segments_count += 1

        self._segments.append(
            _AcceptedSegment(
                segment_id=segment_id,
                raw_text=raw_text,
                clean_text=normalize_dictation_text(display_text if display_text else source_text),
                start=float(start or 0.0),
                end=float(end or 0.0),
                confidence=float(confidence or 0.0),
            )
        )

    def finalize(self) -> AggregatedUtterance:
        """Finalize aggregation and return the completed utterance.

        Combines all accepted segments into final raw and clean text,
        resetting internal state after aggregation.

        Returns:
            AggregatedUtterance containing the final text and statistics.

        Example:
            >>> aggregator = UtteranceAggregator()
            >>> aggregator.add_segment("seg-1", "Hello", "Hello")
            >>> result = aggregator.finalize()
            >>> print(result.accepted_segments_count)
            1
        """
        raw_text = normalize_dictation_text(
            " ".join(segment.raw_text for segment in self._segments)
        )
        merged_text = normalize_dictation_text(self._aggregated_text or raw_text)
        return AggregatedUtterance(
            aggregated_raw_text=raw_text,
            aggregated_clean_text=clean_final_text(merged_text),
            accepted_segments_count=len(self._segments),
            dropped_segments_count=self.dropped_segments_count,
            merged_segments_count=self.merged_segments_count,
            warnings=list(self.warnings),
        )

    def get_current_text(self) -> str:
        """Get the current aggregated text without finalizing.

        Returns:
            Current normalized aggregated text.

        Example:
            >>> aggregator = UtteranceAggregator()
            >>> aggregator.add_segment("seg-1", "Hello", "Hello")
            >>> aggregator.get_current_text()
            'hello'
        """
        return normalize_dictation_text(self._aggregated_text)

    def reset(self) -> None:
        """Reset the aggregator to initial state.

        Clears all accepted segments, resets aggregated text, and zeroes
        out all statistics. Use this to start a new utterance without
        creating a new aggregator instance.

        Example:
            >>> aggregator = UtteranceAggregator()
            >>> aggregator.add_segment("seg-1", "Hello", "Hello")
            >>> aggregator.reset()
            >>> aggregator.get_current_text()
            ''
        """
        self._segments.clear()
        self._aggregated_text = ""
        self.dropped_segments_count = 0
        self.merged_segments_count = 0
        self.warnings.clear()
