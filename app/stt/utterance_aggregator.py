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
    aggregated_raw_text: str
    aggregated_clean_text: str
    accepted_segments_count: int
    dropped_segments_count: int
    merged_segments_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _AcceptedSegment:
    segment_id: str
    raw_text: str
    clean_text: str
    start: float
    end: float
    confidence: float


@dataclass(slots=True)
class UtteranceAggregator:
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

        original_text = normalize_dictation_text((text or "") or display_text)
        raw_text = normalize_dictation_text(trim_repetitive_segment(original_text))
        if not raw_text:
            self.dropped_segments_count += 1
            return
        if is_repetitive_segment(original_text):
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
                clean_text=normalize_dictation_text(display_text or text),
                start=float(start or 0.0),
                end=float(end or 0.0),
                confidence=float(confidence or 0.0),
            )
        )

    def finalize(self) -> AggregatedUtterance:
        raw_text = normalize_dictation_text(" ".join(segment.raw_text for segment in self._segments))
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
        return normalize_dictation_text(self._aggregated_text)

    def reset(self) -> None:
        self._segments.clear()
        self._aggregated_text = ""
        self.dropped_segments_count = 0
        self.merged_segments_count = 0
        self.warnings.clear()
