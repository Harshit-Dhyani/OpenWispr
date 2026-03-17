from __future__ import annotations

from app.core.model_catalog import (
    MODEL_CATALOG,
    get_default_model_id,
    get_model_catalog_entry,
    list_model_catalog,
    runtime_name_for_model,
)


def test_model_catalog_entries_have_required_runtime_fields() -> None:
    assert MODEL_CATALOG
    for entry in MODEL_CATALOG:
        assert entry.id
        assert entry.display_name
        assert entry.category in {"asr", "refiner"}
        assert entry.family in {"whisper", "qwen", "mistral", "phi"}
        assert entry.engine in {"faster-whisper", "llamacpp", "ollama"}
        assert entry.size_gb_estimate > 0
        assert entry.recommended_vram_gb >= 0
        assert entry.speed_tier in {"fast", "balanced", "quality"}
        assert entry.license_note
        assert entry.description_short
        assert entry.why_choose_this
        assert entry.download_artifacts
        for artifact in entry.download_artifacts:
            assert artifact.filename
            assert artifact.url.startswith("https://")
            assert artifact.min_size_bytes > 0


def test_asr_catalog_entries_have_runtime_mapping() -> None:
    asr_entries = [entry for entry in MODEL_CATALOG if entry.category == "asr"]
    assert {entry.id for entry in asr_entries} == {
        "whisper-tiny",
        "whisper-small",
        "whisper-medium",
        "whisper-large-v3",
        "whisper-turbo",
    }
    for entry in asr_entries:
        assert entry.runtime_model_name


def test_model_catalog_default_and_runtime_mapping() -> None:
    assert get_default_model_id("asr") == "whisper-medium"
    assert get_default_model_id("refiner") == "qwen2.5-3b-instruct"
    assert any(entry.id == "qwen2.5-3b-instruct" for entry in MODEL_CATALOG)
    assert runtime_name_for_model("whisper-medium") == "medium"
    assert runtime_name_for_model("qwen2.5-7b-instruct") is None
    assert runtime_name_for_model("qwen2.5-3b-instruct") is None


def test_whisper_turbo_catalog_only_requests_existing_repo_artifacts() -> None:
    entry = get_model_catalog_entry("whisper-turbo")

    assert entry is not None
    assert [artifact.filename for artifact in entry.download_artifacts] == [
        "model.bin",
        "config.json",
        "tokenizer.json",
    ]


def test_model_catalog_loading() -> None:
    """Test that model catalog loads correctly."""
    assert MODEL_CATALOG is not None
    assert len(MODEL_CATALOG) > 0
    catalog_list = list_model_catalog()
    assert len(catalog_list) == len(MODEL_CATALOG)
    for entry in catalog_list:
        assert "id" in entry
        assert "display_name" in entry
        assert "category" in entry
        assert "enabled_runtime" in entry


def test_enabled_models_filter() -> None:
    """Test that only enabled models are returned when filtering by enabled_runtime."""
    enabled_models = [entry for entry in MODEL_CATALOG if entry.enabled_runtime]
    assert len(enabled_models) > 0
    for model in enabled_models:
        assert model.enabled_runtime is True

    disabled_models = [entry for entry in MODEL_CATALOG if not entry.enabled_runtime]
    assert len(disabled_models) > 0
    for model in disabled_models:
        assert model.enabled_runtime is False


def test_model_selection_respects_enabled_runtime() -> None:
    """Test that model selection considers enabled_runtime flag."""
    asr_models = [entry for entry in MODEL_CATALOG if entry.category == "asr"]
    enabled_asr = [m for m in asr_models if m.enabled_runtime]
    disabled_asr = [m for m in asr_models if not m.enabled_runtime]

    # All ASR models are currently enabled
    assert len(enabled_asr) > 0
    assert len(enabled_asr) == len(asr_models)

    refiner_models = [entry for entry in MODEL_CATALOG if entry.category == "refiner"]
    enabled_refiners = [m for m in refiner_models if m.enabled_runtime]
    # Refiners are disabled by default (require local LLM setup)
    assert len(enabled_refiners) == 0
    disabled_refiners = [m for m in refiner_models if not m.enabled_runtime]
    assert len(disabled_refiners) == len(refiner_models)
