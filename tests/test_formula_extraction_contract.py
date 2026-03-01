from __future__ import annotations

from tests._contracts import filtered_call, formula_text, resolve_symbol


FORMULA_MODULES = [
    "app.core.formulas",
    "app.core.formula_extraction",
    "app.stt.formulas",
]

FORMULA_SYMBOLS = [
    "extract_formulas",
    "extract_formulae",
    "find_formulas",
]


def test_formula_extraction_finds_equations_and_ignores_plain_versions():
    extractor = resolve_symbol(FORMULA_MODULES, FORMULA_SYMBOLS)
    transcript = (
        "We confirmed E = mc^2 in the lecture. "
        "Then we restated a^2 + b^2 = c^2 for the triangle example. "
        "Version 2.0.1 of the local app is unrelated."
    )

    results = filtered_call(
        extractor,
        transcript,
        text=transcript,
        transcript=transcript,
        source_text=transcript,
    )
    extracted = [formula_text(item) for item in results]

    assert any("E = mc^2" in item for item in extracted)
    assert any("a^2 + b^2 = c^2" in item for item in extracted)
    assert all("2.0.1" not in item for item in extracted)
