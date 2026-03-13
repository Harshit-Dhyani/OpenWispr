from __future__ import annotations

from typing import Final

PROFILE_INSTRUCTIONS: Final[dict[str, str]] = {
    "clean_dictation": (
        "Keep the speaker's meaning intact, smooth dictation artifacts, and produce clean prose."
    ),
    "professional": (
        "Make the final text read like polished professional writing while preserving every fact."
    ),
    "student_notes": (
        "Make the final text clean and easy to review as study notes, but keep every fact and ordering intact."
    ),
    "code_logs": (
        "Preserve code tokens, commands, ids, filenames, versions, percentages, decimals, hotkeys, and uppercase technical tokens exactly."
    ),
}

DEFAULT_PROFILE_INSTRUCTION: Final[str] = (
    "Preserve numbers, units, formulas, code tokens, identifiers, filenames, product names, and technical terms exactly."
)

STRICT_INTENSITY_INSTRUCTION: Final[str] = (
    "Correct punctuation, capitalization, spacing, and paragraphing only."
)
POLISHED_INTENSITY_INSTRUCTION: Final[str] = (
    "Polish the transcript for readability while preserving meaning exactly."
)
PROMPT_PREFIX: Final[str] = (
    "You are a transcript refiner.\n"
    "Return only the refined transcript text.\n"
    "If the transcript already looks correct, return it unchanged.\n"
    "Preserve placeholders like [[KEEP_TOKEN_0001]] exactly and do not rename, split, or remove them.\n"
)


def build_refiner_prompt(
    text: str,
    *,
    mode: str,
    profile: str,
    language_hint: str,
    cleanup_instructions: str = "",
) -> str:
    intensity_instruction = (
        STRICT_INTENSITY_INSTRUCTION if mode == "strict" else POLISHED_INTENSITY_INSTRUCTION
    )
    profile_instruction = PROFILE_INSTRUCTIONS.get(profile, DEFAULT_PROFILE_INSTRUCTION)
    extra_instructions = cleanup_instructions.strip()

    prompt = (
        PROMPT_PREFIX
        + f"Language hint: {language_hint}.\n"
        + f"Task: {intensity_instruction} {profile_instruction}\n"
    )
    if extra_instructions:
        prompt += (
            "Additional cleanup instructions for final text only:\n"
            f"{extra_instructions}\n"
        )
    prompt += (
        "<TRANSCRIPT>\n"
        f"{text}\n"
        "</TRANSCRIPT>\n"
        "<REFINED_TEXT>\n"
    )
    return prompt
