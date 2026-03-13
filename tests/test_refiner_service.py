from __future__ import annotations

from pathlib import Path

from app.api.services.refiner_service import RefinerService


def test_refiner_service_uses_installed_gguf_path(tmp_path: Path) -> None:
    model_dir = tmp_path / "refiner" / "qwen2.5-7b-instruct"
    model_dir.mkdir(parents=True)
    model_file = model_dir / "qwen2.5-7b-instruct-q4_k_m.gguf"
    model_file.write_bytes(b"gguf")

    service = RefinerService(tmp_path)

    assert service.is_available("qwen2.5-7b-instruct") is True
    assert service._resolve_model_path("qwen2.5-7b-instruct") == model_file


def test_refiner_service_returns_original_text_when_runtime_disabled(tmp_path: Path) -> None:
    service = RefinerService(tmp_path)

    result = service.refine_text(
        "project status update",
        mode="strict",
        profile="clean_dictation",
        model_id="qwen2.5-7b-instruct",
        runtime_enabled=False,
        language_hint="en",
    )

    assert result.text == "project status update"
    assert result.used_runtime is False
    assert "disabled" in (result.error or "")


def test_refiner_service_uses_runtime_when_available(tmp_path: Path) -> None:
    model_dir = tmp_path / "refiner" / "phi-3-mini-4k-instruct"
    model_dir.mkdir(parents=True)
    (model_dir / "Phi-3-mini-4k-instruct-q4.gguf").write_bytes(b"gguf")

    class FakeLlama:
        def create_completion(self, **_: object) -> dict[str, object]:
            return {"choices": [{"text": "Project status update."}]}

    service = RefinerService(tmp_path)
    service._ensure_model = lambda model_id: FakeLlama()  # type: ignore[method-assign]

    result = service.refine_text(
        "project status update",
        mode="strict",
        profile="clean_dictation",
        model_id="phi-3-mini-4k-instruct",
        runtime_enabled=True,
        language_hint="en",
    )

    assert result.text == "Project status update."
    assert result.used_runtime is True
    assert result.model_id == "phi-3-mini-4k-instruct"


def test_refiner_service_preserves_technical_tokens_in_strict_mode(tmp_path: Path) -> None:
    model_dir = tmp_path / "refiner" / "phi-3-mini-4k-instruct"
    model_dir.mkdir(parents=True)
    (model_dir / "Phi-3-mini-4k-instruct-q4.gguf").write_bytes(b"gguf")

    class FakeLlama:
        def create_completion(self, **_: object) -> dict[str, object]:
            return {"choices": [{"text": "Set max_tokens to 128ms in app.api.server."}]}

    service = RefinerService(tmp_path)
    service._ensure_model = lambda model_id: FakeLlama()  # type: ignore[method-assign]

    result = service.refine_text(
        "set max_tokens to 128ms in app.api.server",
        mode="strict",
        profile="code_logs",
        model_id="phi-3-mini-4k-instruct",
        runtime_enabled=True,
        language_hint="en",
    )

    assert result.text == "Set max_tokens to 128ms in app.api.server."
    assert result.used_runtime is True


def test_refiner_service_falls_back_when_runtime_rewrites_protected_tokens(tmp_path: Path) -> None:
    model_dir = tmp_path / "refiner" / "phi-3-mini-4k-instruct"
    model_dir.mkdir(parents=True)
    (model_dir / "Phi-3-mini-4k-instruct-q4.gguf").write_bytes(b"gguf")

    class FakeLlama:
        def create_completion(self, **_: object) -> dict[str, object]:
            return {"choices": [{"text": "Set maximum tokens to 256 milliseconds in server.py."}]}

    service = RefinerService(tmp_path)
    service._ensure_model = lambda model_id: FakeLlama()  # type: ignore[method-assign]

    result = service.refine_text(
        "set max_tokens to 128ms in app.api.server",
        mode="strict",
        profile="code_logs",
        model_id="phi-3-mini-4k-instruct",
        runtime_enabled=True,
        language_hint="en",
    )

    assert result.text == "set max_tokens to 128ms in app.api.server"
    assert result.used_runtime is False
    assert "protected tokens" in (result.error or "")


def test_refiner_prompt_includes_cleanup_instructions(tmp_path: Path) -> None:
    service = RefinerService(tmp_path)

    prompt = service._build_prompt(
        "project status update",
        mode="strict",
        profile="clean_dictation",
        language_hint="en",
        cleanup_instructions="Keep proper nouns unchanged.",
    )

    assert "Additional cleanup instructions for final text only" in prompt
    assert "Keep proper nouns unchanged." in prompt


def test_refiner_service_preserves_placeholders_in_code_logs_profile(tmp_path: Path) -> None:
    service = RefinerService(tmp_path)

    protected = service._protect_sensitive_tokens(
        "keep HTTPX at 100% and version 0.0.1.000 plus Ctrl+Shift+T"
    )

    assert "[[KEEP_TOKEN_" in protected.protected_text
    assert service._placeholders_intact(protected.protected_text, protected.placeholders) is True
    restored = service._restore_sensitive_tokens(protected.protected_text, protected.placeholders)
    assert restored == "keep HTTPX at 100% and version 0.0.1.000 plus Ctrl+Shift+T"
