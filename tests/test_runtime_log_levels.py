import logging

from app.api.server import _apply_runtime_log_levels, _resolve_runtime_log_level


def test_debug_setting_is_honored_without_env(monkeypatch):
    monkeypatch.delenv("OPENWISPR_LOG_LEVEL", raising=False)

    resolved = _resolve_runtime_log_level({"advanced": {"logLevel": "DEBUG"}})

    assert resolved == "DEBUG"


def test_env_debug_overrides_settings(monkeypatch):
    monkeypatch.setenv("OPENWISPR_LOG_LEVEL", "DEBUG")

    resolved = _resolve_runtime_log_level({"advanced": {"logLevel": "ERROR"}})

    assert resolved == "DEBUG"


def test_debug_runtime_enables_noisy_library_loggers():
    _apply_runtime_log_levels("DEBUG")

    assert logging.getLogger("httpx").level == logging.DEBUG
    assert logging.getLogger("httpcore").level == logging.DEBUG
    assert logging.getLogger("faster_whisper").level == logging.DEBUG


def test_info_runtime_quiets_noisy_library_loggers():
    _apply_runtime_log_levels("INFO")

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("faster_whisper").level == logging.WARNING
