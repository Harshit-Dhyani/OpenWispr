"""STEM unit validation and dimension checking.

Provides detection and validation of physical units (m, s, kg, N, J, etc.) in transcript
segments with dimension contradiction detection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.models import TranscriptSegment

VALUE_UNIT_PATTERN = re.compile(
    r"\b(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>m|s|kg|N|J|W|Pa|C|V|A|Hz|Ω|ohm)\b",
    re.IGNORECASE,
)

UNIT_DIMENSIONS = {
    "m": "length",
    "s": "time",
    "kg": "mass",
    "n": "force",
    "j": "energy",
    "w": "power",
    "pa": "pressure",
    "c": "charge",
    "v": "voltage",
    "a": "current",
    "ω": "resistance",
    "ohm": "resistance",
    "hz": "frequency",
}


@dataclass(slots=True)
class UnitCheckResult:
    review_flag: bool
    reasons: list[str]
    values: list[tuple[float, str]]


def check_units_in_segment(segment: TranscriptSegment) -> UnitCheckResult:
    values: list[tuple[float, str]] = []
    reasons: list[str] = []
    for match in VALUE_UNIT_PATTERN.finditer(segment.text):
        value = float(match.group("value"))
        unit = match.group("unit")
        values.append((value, unit))
        lowered = unit.lower()
        if lowered == "kg" and value <= 0:
            reasons.append("non-positive-mass")
        if lowered == "s" and value < 0:
            reasons.append("negative-time")
        if lowered == "hz" and value < 0:
            reasons.append("negative-frequency")

    contradiction = detect_dimension_contradiction(segment.text)
    if contradiction:
        reasons.append(contradiction)

    return UnitCheckResult(review_flag=bool(reasons), reasons=sorted(set(reasons)), values=values)


def detect_dimension_contradiction(text: str) -> str | None:
    lowered = text.lower()
    if "=" not in lowered and "equal to" not in lowered:
        return None
    seen: set[str] = set()
    for match in VALUE_UNIT_PATTERN.finditer(text):
        dimension = UNIT_DIMENSIONS.get(match.group("unit").lower())
        if dimension:
            seen.add(dimension)
    if "force" in seen and "time" in seen:
        return "mixed-force-time-equality"
    return None
