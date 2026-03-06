from __future__ import annotations

from app.stt.deterministic_postprocess import (
    postprocess_final_text,
    postprocess_live_text,
    spoken_numbers_to_symbols,
)


def test_dictation_mode_converts_decimals_and_percentages() -> None:
    text = "set threshold to zero point two three and success rate is 100 percent"
    result = postprocess_final_text(text, mode="dictation")

    assert result == "Set threshold to 0.23 and success rate is 100%."


def test_dictation_mode_converts_word_percentages() -> None:
    text = "success rate is one hundred percent"
    result = postprocess_final_text(text, mode="dictation")

    assert result == "Success rate is 100%."


def test_dictation_mode_handles_long_decimal_runs() -> None:
    text = "set epsilon to zero point zero zero zero one"
    result = postprocess_final_text(text, mode="dictation")

    assert result == "Set epsilon to 0.0001."


def test_literal_mode_preserves_digit_runs() -> None:
    text = "token zero one zero zero zero"
    result = postprocess_final_text(text, mode="literal")

    assert result == "token 01000"


def test_literal_mode_builds_dotted_versions() -> None:
    text = "version zero dot zero dot one dot zero zero zero"
    result = postprocess_final_text(text, mode="literal")

    assert result == "version 0.0.1.000"


def test_literal_mode_normalizes_acronym_runs() -> None:
    text = "library H T T P X client"
    result = postprocess_final_text(text, mode="literal")

    assert result == "library HTTPX client"


def test_literal_mode_converts_underscore_tokens() -> None:
    text = "config underscore path"
    result = spoken_numbers_to_symbols(text, mode="literal")

    assert result == "config_path"


def test_live_postprocess_stays_lightweight() -> None:
    text = "set threshold to zero point two three"
    result = postprocess_live_text(text, mode="dictation")

    assert result == "set threshold to zero point two three"
