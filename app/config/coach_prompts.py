from __future__ import annotations

import json
from dataclasses import dataclass

DEFAULT_COACH_TEMPLATE_ID = "default_english_coach"


DEFAULT_COACH_SYSTEM_PROMPT = """You are an English writing coach for dictation transcripts.
You must preserve the speakers meaning and tone.
You must NOT add new facts.
Prefer minimal edits.
Output MUST be valid JSON only, matching the schema exactly."""


DEFAULT_COACH_USER_TEMPLATE = """Language mode: {language_mode}
Detail level: {detail_level}
Overrides JSON: {overrides_json}

Original transcript:
{original_text}

Task:
1) Produce "polished" that reads naturally (single paragraph unless clearly multiple).
2) Provide "diff" operations aligned to the original string indices where possible. If exact indices are hard, provide approximate ranges but keep them consistent.
3) Provide 2–5 short tips.
4) Provide up to 5 mistakes with fixes and short explanations.
5) Provide one short practice rewrite.

Return JSON with keys: original, polished, diff, tips, mistakes, practice, meta."""


@dataclass(slots=True)
class CoachPromptTemplate:
    id: str
    name: str
    version: int
    system: str
    user_template: str
    enabled: bool = True
    built_in: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "system": self.system,
            "user_template": self.user_template,
            "enabled": self.enabled,
            "built_in": self.built_in,
        }


DEFAULT_COACH_TEMPLATE = CoachPromptTemplate(
    id=DEFAULT_COACH_TEMPLATE_ID,
    name="Default English Coach",
    version=1,
    system=DEFAULT_COACH_SYSTEM_PROMPT,
    user_template=DEFAULT_COACH_USER_TEMPLATE,
    enabled=True,
    built_in=True,
)


def get_default_coach_templates() -> list[dict[str, object]]:
    return [DEFAULT_COACH_TEMPLATE.to_dict()]


def compile_coach_prompt(
    *,
    template: dict[str, object],
    original_text: str,
    language_mode: str,
    detail_level: str,
    overrides: dict[str, object],
    custom_user_template: str = "",
) -> dict[str, object]:
    resolved_user_template = (custom_user_template or str(template.get("user_template", ""))).strip()
    resolved_system = str(template.get("system", "")).strip() or DEFAULT_COACH_SYSTEM_PROMPT
    overrides_json = json.dumps(overrides, ensure_ascii=True, sort_keys=True)
    variables = {
        "original_text": original_text,
        "language_mode": language_mode,
        "detail_level": detail_level,
        "overrides_json": overrides_json,
    }
    return {
        "system_prompt": resolved_system,
        "user_prompt": resolved_user_template.format(**variables),
        "variables": variables,
        "resolved_template_id": template.get("id", DEFAULT_COACH_TEMPLATE_ID),
        "resolved_template_version": int(template.get("version", 1) or 1),
    }
