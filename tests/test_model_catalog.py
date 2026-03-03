from __future__ import annotations

from app.core.model_catalog import MODEL_CATALOG, get_default_model_id, runtime_name_for_model


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
    assert get_default_model_id("refiner") == "qwen2.5-7b-instruct"
    assert runtime_name_for_model("whisper-medium") == "medium"
    assert runtime_name_for_model("qwen2.5-7b-instruct") is None
