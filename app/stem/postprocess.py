from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.models import FormulaFinding, TranscriptSegment
from app.stem.formula_extractor import extract_formula_findings, extract_step_markers
from app.stem.unit_checker import check_units_in_segment

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _CachedSegmentData:
    formulas: list[FormulaFinding]
    review_reasons: list[str]
    review_flag: bool


@dataclass(slots=True)
class NotesBundle:
    notes_markdown: str
    highlights_text: str
    formulas: list[FormulaFinding]
    needs_review: list[TranscriptSegment]


class StemNoteProcessor:
    def __init__(self) -> None:
        self._segment_cache: dict[int, _CachedSegmentData] = {}
        logger.debug("StemNoteProcessor initialized with empty segment cache")

    def build(self, segments: list[TranscriptSegment]) -> NotesBundle:
        segment_count = len(segments)
        logger.debug(f"Starting build process with segment_count={segment_count}")

        formulas = extract_formula_findings(segments)
        logger.debug(f"Formula extraction complete: found {len(formulas)} formulas")
        if formulas:
            formula_types = {}
            for f in formulas:
                key = (
                    "assignment"
                    if "=" in f.expression
                    else "function"
                    if any(fn in f.expression for fn in ["sin", "cos", "tan", "log", "ln"])
                    else "other"
                )
                formula_types[key] = formula_types.get(key, 0) + 1
            logger.debug(f"Formula types breakdown: {formula_types}")
            logger.debug(f"Formulas found: {[f.expression for f in formulas]}")

        contradictions = collect_variable_contradictions(formulas)
        contradiction_count = len(contradictions)
        if contradictions:
            logger.debug(f"Detected {contradiction_count} contradictions: {contradictions}")
        else:
            logger.debug("No contradictions detected")

        needs_review: list[TranscriptSegment] = []

        suppressed_count = 0
        review_reasons_breakdown: dict[str, int] = {}

        for segment in segments:
            reasons = list(segment.review_reasons)
            if segment.confidence < 0.45:
                reasons.append("low-confidence-transcript")
            if "??" in segment.text or "___" in segment.text:
                reasons.append("garbled-audio-text")
                suppressed_count += 1
            unit_check = check_units_in_segment(segment)
            if unit_check.reasons:
                logger.debug(f"Unit check for segment [{segment.start:.2f}s]: {unit_check.reasons}")
            reasons.extend(unit_check.reasons)
            for variable, timestamps in contradictions.items():
                if segment.start in timestamps:
                    reasons.append(f"contradictory-definition:{variable}")
            segment.review_reasons = sorted(set(reasons))
            segment.review_flag = bool(segment.review_reasons)
            if segment.review_flag:
                needs_review.append(segment)
                for reason in segment.review_reasons:
                    review_reasons_breakdown[reason] = review_reasons_breakdown.get(reason, 0) + 1

        formulas_needing_review = [f for f in formulas if f.review_flag]
        logger.debug(
            f"Processing complete: segment_count={segment_count}, formulas_found={len(formulas)}, formulas_needing_review={len(formulas_needing_review)}"
        )
        if formulas_needing_review:
            logger.debug(
                f"Formulas needing review details: {[(f.expression, f.reasons) for f in formulas_needing_review]}"
            )
        if review_reasons_breakdown:
            logger.debug(f"Review reasons breakdown: {review_reasons_breakdown}")
        logger.debug(f"Contradiction count: {contradiction_count}")
        if suppressed_count > 0:
            logger.debug(f"Suppressed segments (garbled markers): {suppressed_count}")

        bundle = NotesBundle(
            notes_markdown=self._build_notes_markdown(segments, formulas, needs_review),
            highlights_text=self._build_highlights(segments, formulas),
            formulas=formulas,
            needs_review=needs_review,
        )
        notes_preview = bundle.notes_markdown[:200].replace("\n", " ")
        logger.debug(
            f"NotesBundle created: notes_preview='{notes_preview}...', total_formulas={len(formulas)}, needs_review_count={len(needs_review)}"
        )
        return bundle

    def build_incremental(
        self,
        existing_segments: list[TranscriptSegment],
        new_segments: list[TranscriptSegment],
        existing_formulas: list[FormulaFinding],
        existing_needs_review: list[TranscriptSegment],
    ) -> NotesBundle:
        all_segments = existing_segments + new_segments

        new_formulas = extract_formula_findings(new_segments)
        formulas = list(existing_formulas) + new_formulas

        contradictions = collect_variable_contradictions(formulas)
        needs_review = list(existing_needs_review)
        existing_needs_review_ids = {id(s) for s in existing_needs_review}

        for segment in new_segments:
            reasons = list(segment.review_reasons)
            if segment.confidence < 0.45:
                reasons.append("low-confidence-transcript")
            if "??" in segment.text or "___" in segment.text:
                reasons.append("garbled-audio-text")
            unit_check = check_units_in_segment(segment)
            reasons.extend(unit_check.reasons)
            for variable, timestamps in contradictions.items():
                if segment.start in timestamps:
                    reasons.append(f"contradictory-definition:{variable}")
            segment.review_reasons = sorted(set(reasons))
            segment.review_flag = bool(segment.review_reasons)
            if segment.review_flag and id(segment) not in existing_needs_review_ids:
                needs_review.append(segment)

            self._segment_cache[id(segment)] = _CachedSegmentData(
                formulas=[f for f in new_formulas if f.timestamp_start == segment.start],
                review_reasons=list(segment.review_reasons),
                review_flag=segment.review_flag,
            )

        for segment in existing_segments:
            for variable, timestamps in contradictions.items():
                if segment.start in timestamps:
                    new_reason = f"contradictory-definition:{variable}"
                    if new_reason not in segment.review_reasons:
                        segment.review_reasons = sorted(
                            set([*segment.review_reasons, new_reason])
                        )
                        segment.review_flag = True
                        if segment not in needs_review:
                            needs_review.append(segment)

        return NotesBundle(
            notes_markdown=self._build_notes_markdown(all_segments, formulas, needs_review),
            highlights_text=self._build_highlights(all_segments, formulas),
            formulas=formulas,
            needs_review=needs_review,
        )

    def _build_notes_markdown(
        self,
        segments: list[TranscriptSegment],
        formulas: list[FormulaFinding],
        needs_review: list[TranscriptSegment],
    ) -> str:
        lines = [
            "# Session Notes",
            "",
            "> Derived from local transcript audio. Review flagged items before using formulas or steps as final notes.",
            "",
            "## Clean Notes",
            "",
        ]
        for segment in segments:
            markers = extract_step_markers(segment.text)
            if markers:
                lines.append(f"- {segment.text}  `step:{', '.join(markers)}`")
            else:
                lines.append(segment.text)
        lines.extend(["", "## Extracted Formulas", ""])
        if formulas:
            for formula in formulas:
                status = "needs review" if formula.review_flag else "ok"
                lines.append(
                    f"- `{formula.expression}` [{formula.timestamp_start:.2f}s - {formula.timestamp_end:.2f}s] ({status}, confidence={formula.confidence:.2f})"
                )
        else:
            lines.append("- No formula-like expressions detected.")
        lines.extend(["", "## Needs Review", ""])
        if needs_review:
            for segment in needs_review:
                lines.append(
                    f"- [{segment.start:.2f}s - {segment.end:.2f}s] {segment.text} :: {', '.join(segment.review_reasons)}"
                )
        else:
            lines.append("- No flagged segments.")
        return "\n".join(lines) + "\n"

    def _build_highlights(
        self,
        segments: list[TranscriptSegment],
        formulas: list[FormulaFinding],
    ) -> str:
        lines: list[str] = []
        for segment in segments[-10:]:
            if segment.confidence >= 0.55:
                lines.append(f"[{segment.start:.2f}s] {segment.text}")
        for formula in formulas[-10:]:
            lines.append(f"[formula {formula.timestamp_start:.2f}s] {formula.expression}")
        return "\n".join(lines) + ("\n" if lines else "")


def collect_variable_contradictions(formulas: list[FormulaFinding]) -> dict[str, set[float]]:
    seen: dict[str, tuple[str, float]] = {}
    contradictions: dict[str, set[float]] = {}
    for formula in formulas:
        if "=" not in formula.expression:
            continue
        left, right = [part.strip() for part in formula.expression.split("=", 1)]
        existing = seen.get(left)
        if existing and existing[0] != right:
            contradiction_timestamps = contradictions.setdefault(left, set())
            contradiction_timestamps.add(existing[1])
            contradiction_timestamps.add(formula.timestamp_start)
        else:
            seen[left] = (right, formula.timestamp_start)
    return contradictions
