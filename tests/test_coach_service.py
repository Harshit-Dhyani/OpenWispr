from __future__ import annotations

import json
from pathlib import Path

from app.api.services.coach_service import CoachRequestContext, CoachService


def _context(**overrides: object) -> CoachRequestContext:
    payload = {
        "text": "i want to improve my english writing",
        "language_mode": "en",
        "detail_level": "compact",
        "capture_source": "microphone",
        "template_id": "default_english_coach",
        "overrides": {
            "tone": "friendly",
            "aggressiveness": "light",
            "filler_removal": True,
            "keep_slang": False,
            "target_style": "simple",
        },
        "privacy_mode": "local_only",
        "runtime_enabled": False,
        "model_id": None,
        "custom_user_template": "",
        "templates": None,
    }
    payload.update(overrides)
    return CoachRequestContext(**payload)


def test_coach_service_returns_local_only_fallback_and_caches_it(tmp_path: Path) -> None:
    cache_path = tmp_path / "coach_cache.json"
    service = CoachService(tmp_path, cache_path)
    context = _context()

    first = service.generate(context, fallback_text="I want to improve my English writing.")
    second = service.generate(context, fallback_text="I want to improve my English writing.")

    assert first.polished == "I want to improve my English writing."
    assert first.meta.provider == "disabled_local_only"
    assert first.meta.cache_hit is False
    assert second.meta.provider == "cache"
    assert second.meta.cache_hit is True
    cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert len(cache_payload) > 0


def test_coach_service_falls_back_when_runtime_is_unavailable(tmp_path: Path) -> None:
    service = CoachService(tmp_path, tmp_path / "coach_cache.json")
    context = _context(
        privacy_mode="allow_llm",
        runtime_enabled=False,
        model_id="qwen2.5-3b-instruct",
    )

    result = service.generate(context, fallback_text="I want to improve my English writing.")

    assert result.polished == "I want to improve my English writing."
    assert result.meta.provider == "fallback_runtime_unavailable"
    assert result.diff


def test_coach_service_prompt_preview_uses_custom_user_template(tmp_path: Path) -> None:
    service = CoachService(tmp_path, tmp_path / "coach_cache.json")
    context = _context(
        custom_user_template="Original transcript:\n{original_text}\nOverrides: {overrides_json}",
        templates=[
            {
                "id": "default_english_coach",
                "name": "Default English Coach",
                "version": 3,
                "system": "SYSTEM",
                "user_template": "USER {original_text}",
                "enabled": True,
                "built_in": True,
            }
        ],
    )

    preview = service.prompt_preview(context)

    assert preview["resolved_template_id"] == "default_english_coach"
    assert preview["resolved_template_version"] == 3
    assert "Original transcript:" in preview["user_prompt"]
    assert '"target_style": "simple"' in preview["variables"]["overrides_json"]
