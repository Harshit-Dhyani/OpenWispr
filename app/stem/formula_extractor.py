"""STEM formula extraction from transcripts.

Provides detection and parsing of mathematical expressions, assignment formulas,
trigonometric/logarithmic functions, and unit-valued expressions from transcript segments.
"""

from __future__ import annotations

import ast
import logging
import re

from app.core.models import FormulaFinding, TranscriptSegment

logger = logging.getLogger(__name__)

FORMULA_PATTERN = re.compile(
    r"([A-Za-z0-9Ωπ+\-*/^() ]{1,40}\s*=\s*[A-Za-z0-9Ωπ+\-*/^() ]{1,40}|(?:sin|cos|tan|log|ln)\s*\([^)]{1,40}\)|\b\d+(?:\.\d+)?\s*(?:m|s|kg|N|J|W|Pa|C|V|A|Ω|Hz|ohm)\b)",
    re.IGNORECASE,
)
VARIABLE_PATTERN = re.compile(r"\b[a-zA-ZΩπ]\w*\b")
UNIT_PATTERN = re.compile(r"\b(?:m|s|kg|N|J|W|Pa|C|V|A|Hz|ohm|Ω)\b", re.IGNORECASE)
STEP_WORDS = {"therefore", "hence", "assume", "let", "substitute", "differentiate", "integrate"}
GARBLED_MARKERS = {"??", "___", "...", "um", "uh"}


def normalize_formula_text(text: str) -> str:
    replacements = {
        " into ": " * ",
        " x ": " * ",
        " plus ": " + ",
        " minus ": " - ",
        "pi": "π",
        "omega": "Ω",
    }
    normalized = f" {text} "
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
        normalized = normalized.replace(source.title(), target)
    return " ".join(normalized.split())


def is_expression_parseable(expression: str) -> bool:
    candidate = expression.replace("^", "**")
    if "=" in candidate:
        left, right = candidate.split("=", 1)
        candidate = f"({left}) - ({right})"
    candidate = candidate.replace("π", "3.1415926535").replace("Ω", "1")
    candidate = re.sub(r"\b(sin|cos|tan|log|ln)\b", "1", candidate)
    candidate = re.sub(r"\b[a-zA-Z_]\w*\b", "1", candidate)
    try:
        parsed = ast.parse(candidate, mode="eval")
    except SyntaxError:
        return False
    return all(isinstance(node, ALLOWED_AST_NODES) for node in ast.walk(parsed))


ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Constant,
    ast.Load,
    ast.Mod,
    ast.FloorDiv,
)


def extract_formula_findings(segments: list[TranscriptSegment]) -> list[FormulaFinding]:
    segment_count = len(segments)
    logger.debug(f"Starting formula extraction for {segment_count} segments")
    findings: list[FormulaFinding] = []
    formulas_by_type: dict[str, int] = {}

    for segment in segments:
        source_text = segment.display_text or segment.text
        matches = FORMULA_PATTERN.findall(normalize_formula_text(source_text))
        if matches:
            logger.debug(
                f"Segment [{segment.start:.2f}s - {segment.end:.2f}s]: found {len(matches)} potential formulas"
            )

        for match in matches:
            expression = str(match).strip(" ,.")
            parseable = is_expression_parseable(expression)
            reasons: list[str] = []
            review_flag = False

            formula_type = (
                "assignment"
                if "=" in expression
                else "function"
                if any(fn in expression for fn in ["sin", "cos", "tan", "log", "ln"])
                else "unit_value"
                if UNIT_PATTERN.search(expression)
                else "expression"
            )
            formulas_by_type[formula_type] = formulas_by_type.get(formula_type, 0) + 1

            if "=" in expression and not parseable:
                review_flag = True
                reasons.append("formula-not-parseable")
                logger.debug(f"Formula flagged: not parseable - '{expression}'")
            if any(marker in expression.lower() for marker in GARBLED_MARKERS):
                review_flag = True
                reasons.append("garbled-formula-tokens")
                logger.debug(f"Formula flagged: garbled tokens - '{expression}'")

            variables = sorted(set(VARIABLE_PATTERN.findall(expression)))
            units = sorted(set(UNIT_PATTERN.findall(expression)))

            finding = FormulaFinding(
                expression=expression,
                timestamp_start=segment.start,
                timestamp_end=segment.end,
                context=source_text,
                confidence=max(0.15, segment.confidence - (0.2 if review_flag else 0.0)),
                parseable=parseable,
                review_flag=review_flag,
                reasons=reasons,
                variables=variables,
                units=units,
            )
            findings.append(finding)
            logger.debug(
                f"Formula extracted: '{expression}' type={formula_type} parseable={parseable} review_flag={review_flag} variables={variables} units={units}"
            )

    logger.debug(f"Formula extraction complete: {len(findings)} total formulas found")
    logger.debug(f"Formula types breakdown: {formulas_by_type}")
    if findings:
        all_expressions = [f.expression for f in findings]
        needing_review = [f.expression for f in findings if f.review_flag]
        logger.debug(f"All formulas: {all_expressions}")
        if needing_review:
            logger.debug(f"Formulas needing review ({len(needing_review)}): {needing_review}")

    return findings


def extract_step_markers(text: str) -> list[str]:
    lowered = text.lower()
    return [word for word in STEP_WORDS if word in lowered]


def extract_formulas(
    source_text: str | None = None,
    /,
    *,
    text: str | None = None,
    transcript: str | None = None,
    source: str | None = None,
) -> list[dict[str, str]]:
    material = source_text or text or transcript or source or ""
    segment = TranscriptSegment(
        id="adhoc",
        start=0.0,
        end=0.0,
        text=material,
        display_text=material,
        language="auto",
        confidence=0.75,
    )
    return [{"expression": finding.expression} for finding in extract_formula_findings([segment])]
