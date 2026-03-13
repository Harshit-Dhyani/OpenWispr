"""
Regression test for settings naming consistency between backend and frontend.

This test verifies that the backend settings registry (app.config.settings) and
the generated frontend settings (app/electron/frontend/src/config/generated/settings.ts)
have consistent setting names and default values.

This catches settings drift early, specifically the bug where a setting was named
mute_transcripta_audio_during_dictation instead of mute_openwispr_audio_during_dictation.
"""

import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from app.config.settings import SETTINGS_REGISTRY as BACKEND_REGISTRY


@pytest.fixture(autouse=True)
def reset_singletons() -> Any:
    """Override the conftest's reset_singletons fixture to avoid errors."""
    with patch("app.core.settings.manager._settings_manager", None, create=True):
        with patch("app.core.error_handler._default_handler", None, create=True):
            yield


FRONTEND_SETTINGS_PATH = (
    Path(__file__).parent.parent
    / "app"
    / "electron"
    / "frontend"
    / "src"
    / "config"
    / "generated"
    / "settings.ts"
)


def parse_frontend_settings() -> dict[str, dict[str, Any]]:
    """Parse the generated frontend settings.ts file using regex."""
    if not FRONTEND_SETTINGS_PATH.exists():
        pytest.fail(f"Frontend settings file not found: {FRONTEND_SETTINGS_PATH}")

    content = FRONTEND_SETTINGS_PATH.read_text(encoding="utf-8")

    pattern = re.compile(
        r"^\s*(\w+):\s*\{\s*$",
        re.MULTILINE,
    )

    settings: dict[str, dict[str, Any]] = {}
    current_name: str | None = None
    brace_count = 0
    current_entry_lines: list[str] = []

    for line in content.split("\n"):
        match = pattern.match(line)
        if match:
            if current_name is not None:
                settings[current_name] = _parse_entry("\n".join(current_entry_lines))
            current_name = match.group(1)
            brace_count = 0
            current_entry_lines = [line]
        elif current_name is not None:
            current_entry_lines.append(line)
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0 and "}" in line:
                settings[current_name] = _parse_entry("\n".join(current_entry_lines))
                current_name = None
                current_entry_lines = []

    if current_name is not None:
        settings[current_name] = _parse_entry("\n".join(current_entry_lines))

    return settings


def _parse_entry(entry_text: str) -> dict[str, Any]:
    """Parse a single settings entry."""
    result: dict[str, Any] = {}

    for line in entry_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("name:"):
            match = re.match(r'name:\s*"([^"]+)"', stripped)
            if match:
                result["name"] = match.group(1)
        elif stripped.startswith("category:"):
            match = re.match(r'category:\s*"([^"]+)"', stripped)
            if match:
                result["category"] = match.group(1)
        elif stripped.startswith("type:"):
            match = re.match(r'type:\s*"([^"]+)"', stripped)
            if match:
                result["type"] = match.group(1)
        elif stripped.startswith("default:"):
            default_str = stripped.replace("default:", "").strip().rstrip(",")
            result["default"] = _parse_value(default_str)

    return result


def _parse_value(value_str: str) -> Any:
    """Parse a TypeScript value string to Python."""
    value_str = value_str.strip()

    if value_str == "true":
        return True
    if value_str == "false":
        return False

    if value_str == "null":
        return None

    if re.match(r"^-?\d+\.\d+$", value_str):
        return float(value_str)

    if re.match(r"^-?\d+$", value_str):
        return int(value_str)

    if value_str.startswith('"') and value_str.endswith('"'):
        return value_str[1:-1]

    if value_str.startswith("["):
        return value_str

    if value_str.startswith("{"):
        return value_str

    return value_str


class TestSettingsWiring:
    """Test settings naming consistency between backend and frontend."""

    def test_frontend_settings_file_exists(self):
        """Verify the frontend settings file exists."""
        assert FRONTEND_SETTINGS_PATH.exists(), f"Settings file not found: {FRONTEND_SETTINGS_PATH}"

    def test_mute_setting_name_consistency(self):
        """Verify mute setting is named correctly (not using old 'transcripta' name)."""
        frontend_settings = parse_frontend_settings()

        wrong_name = "mute_transcripta_audio_during_dictation"
        correct_name = "mute_openwispr_audio_during_dictation"

        assert wrong_name not in frontend_settings, (
            f"Found old setting name '{wrong_name}' in frontend - "
            "should be renamed to '{correct_name}'"
        )

        assert correct_name in frontend_settings, (
            f"Expected setting '{correct_name}' not found in frontend"
        )

        backend_def = BACKEND_REGISTRY[correct_name]
        frontend_def = frontend_settings[correct_name]

        assert backend_def.name == frontend_def["name"], (
            f"Backend and frontend setting name mismatch: "
            f"backend='{backend_def.name}', frontend='{frontend_def['name']}'"
        )

    def test_all_backend_settings_exist_in_frontend(self):
        """Verify all backend settings have corresponding entries in frontend."""
        frontend_settings = parse_frontend_settings()

        missing_settings = []
        for name in BACKEND_REGISTRY:
            if name not in frontend_settings:
                missing_settings.append(name)

        assert not missing_settings, f"Settings missing in frontend: {missing_settings}"

    def test_all_frontend_settings_exist_in_backend(self):
        """Verify all frontend settings have corresponding entries in backend."""
        frontend_settings = parse_frontend_settings()

        extra_settings = []
        for name in frontend_settings:
            if name not in BACKEND_REGISTRY:
                extra_settings.append(name)

        assert not extra_settings, f"Extra settings in frontend (not in backend): {extra_settings}"

    def test_setting_names_match(self):
        """Verify setting names are identical between backend and frontend."""
        frontend_settings = parse_frontend_settings()

        mismatches = []
        for name, backend_def in BACKEND_REGISTRY.items():
            if name not in frontend_settings:
                continue

            frontend_def = frontend_settings[name]
            if backend_def.name != frontend_def.get("name"):
                mismatches.append(
                    f"  - {name}: backend.name='{backend_def.name}', "
                    f"frontend.name='{frontend_def.get('name')}'"
                )

        assert not mismatches, "Setting name mismatches:\n" + "\n".join(mismatches)

    def test_setting_categories_match(self):
        """Verify setting categories are identical between backend and frontend."""
        frontend_settings = parse_frontend_settings()

        mismatches = []
        for name, backend_def in BACKEND_REGISTRY.items():
            if name not in frontend_settings:
                continue

            frontend_def = frontend_settings[name]
            if backend_def.category != frontend_def.get("category"):
                mismatches.append(
                    f"  - {name}: backend.category='{backend_def.category}', "
                    f"frontend.category='{frontend_def.get('category')}'"
                )

        assert not mismatches, "Setting category mismatches:\n" + "\n".join(mismatches)

    def test_setting_types_match(self):
        """Verify setting types are identical between backend and frontend."""
        frontend_settings = parse_frontend_settings()

        mismatches = []
        for name, backend_def in BACKEND_REGISTRY.items():
            if name not in frontend_settings:
                continue

            frontend_def = frontend_settings[name]
            if backend_def.type != frontend_def.get("type"):
                mismatches.append(
                    f"  - {name}: backend.type='{backend_def.type}', "
                    f"frontend.type='{frontend_def.get('type')}'"
                )

        assert not mismatches, "Setting type mismatches:\n" + "\n".join(mismatches)

    def test_setting_defaults_match(self):
        """Verify setting default values match between backend and frontend.

        Note: Complex types (object, array) are skipped as they use different
        serialization formats between Python and TypeScript but are generated
        from the same source.
        """
        frontend_settings = parse_frontend_settings()

        mismatches = []
        for name, backend_def in BACKEND_REGISTRY.items():
            if name not in frontend_settings:
                continue

            if backend_def.type in ("object", "array"):
                continue

            frontend_def = frontend_settings[name]
            backend_default = backend_def.default

            frontend_default = frontend_def.get("default")
            if frontend_default is None:
                continue

            if not _defaults_match(backend_default, frontend_default):
                mismatches.append(
                    f"  - {name}: backend.default={backend_default!r}, "
                    f"frontend.default={frontend_default!r}"
                )

        assert not mismatches, "Setting default value mismatches:\n" + "\n".join(mismatches)

        assert not mismatches, "Setting default value mismatches:\n" + "\n".join(mismatches)


def _defaults_match(backend_val: Any, frontend_val: Any) -> bool:
    """Check if backend and frontend default values are equivalent."""
    if isinstance(backend_val, bool):
        return str(backend_val).lower() == str(frontend_val).lower()

    if isinstance(backend_val, (int, float)):
        try:
            return float(backend_val) == float(frontend_val)
        except (ValueError, TypeError):
            return False

    if isinstance(backend_val, str):
        return backend_val == str(frontend_val).strip('"')

    if backend_val is None:
        return frontend_val is None or frontend_val == "null"

    if isinstance(backend_val, (list, tuple)):
        return str(backend_val) == frontend_val

    if isinstance(backend_val, dict):
        return str(backend_val) == frontend_val

    return str(backend_val) == str(frontend_val)
