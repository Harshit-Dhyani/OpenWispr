"""Regression tests for frontend audit findings.

Tests for issues found in the frontend audit:
- No placebo controls (settings marked is_fake should not be editable)
- No dead code imports (unused components should not be imported)
- Settings context usage in quick settings
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = PROJECT_ROOT / "app" / "electron" / "frontend" / "src"


class TestPlaceboControls:
    """Tests for placebo/unimplemented settings in UI."""

    def _get_fake_settings(self) -> set[str]:
        """Get set of fake settings from backend."""
        import sys

        sys.path.insert(0, str(PROJECT_ROOT / "app"))

        from app.config.settings import FAKE_SETTINGS

        return FAKE_SETTINGS

    def test_no_placebo_controls(self) -> None:
        """Settings marked is_fake should not have editable UI controls."""
        fake_settings = self._get_fake_settings()

        tsx_files = list(FRONTEND_DIR.rglob("*.tsx"))

        violations = []

        for tsx_file in tsx_files:
            content = tsx_file.read_text(encoding="utf-8")

            for fake_setting in fake_settings:
                setting_name = fake_setting

                if f'"{setting_name}"' in content or f"'{setting_name}'" in content:
                    camel_case = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), setting_name)

                    if camel_case in content:
                        if re.search(rf"(?:const|let|var)\s+{camel_case}\s*=.*useState", content):
                            violations.append(
                                f"{tsx_file.relative_to(PROJECT_ROOT)}: "
                                f"Fake setting '{setting_name}' has editable control"
                            )

        assert not violations, f"Found placebo controls for fake settings:\n" + "\n".join(
            violations
        )


class TestDeadCodeImports:
    """Tests for unused/dead code imports."""

    def _get_react_components(self) -> list[tuple[str, set[str]]]:
        """Get all React components and their imports."""
        components = []

        for tsx_file in FRONTEND_DIR.rglob("*.tsx"):
            content = tsx_file.read_text(encoding="utf-8")

            imports = set()
            import_pattern = r'import\s+(?:{[^}]+}|\w+)\s+from\s+["\']([^"\']+)["\']'

            for match in re.finditer(import_pattern, content):
                import_path = match.group(1)
                imports.add(import_path)

            components.append((str(tsx_file.relative_to(PROJECT_ROOT)), imports))

        return components

    def test_no_dead_code_imports(self) -> None:
        """Unused component imports should not exist."""
        components = self._get_react_components()

        all_imports = set()
        for _, imports in components:
            all_imports.update(imports)

        violations = []

        for file_path, imports in components:
            full_path = PROJECT_ROOT / file_path
            if not full_path.exists():
                continue

            content = full_path.read_text(encoding="utf-8")

            for imp in imports:
                if imp.startswith("."):
                    imp_path = (FRONTEND_DIR / file_path).parent / imp

                    resolved = None
                    if imp_path.exists():
                        resolved = imp_path
                    else:
                        for ext in [".tsx", ".ts"]:
                            test_path = imp_path.with_suffix(ext)
                            if test_path.exists():
                                resolved = test_path
                                break
                        if not resolved:
                            index_path = imp_path / "index.ts"
                            if index_path.exists():
                                resolved = index_path
                            else:
                                index_path_tsx = imp_path / "index.tsx"
                                if index_path_tsx.exists():
                                    resolved = index_path_tsx

                    if resolved:
                        resolved_name = resolved.stem
                        usage_pattern = rf"\b{resolved_name}\b"
                        if not re.search(usage_pattern, content):
                            violations.append(f"{file_path}: imports '{imp}' but doesn't use it")

        assert not violations, f"Found dead code imports:\n" + "\n".join(violations[:10])


class TestSettingsContextUsage:
    """Tests for SettingsContext usage."""

    def test_settings_context_used(self) -> None:
        """Quick settings should use SettingsContext or receive via props."""
        quick_settings_files = [
            FRONTEND_DIR / "components" / "QuickSettingsContent.tsx",
        ]

        for qs_file in quick_settings_files:
            if not qs_file.exists():
                continue

            content = qs_file.read_text(encoding="utf-8")

            has_settings_context = "useSettings" in content or "SettingsContext" in content

            has_settings_props = (
                "settingsHotkey" in content
                or "dictationLanguage" in content
                or "dictationModelId" in content
                or "sessionTitle" in content
            )

            if "settings" in qs_file.name.lower():
                assert has_settings_context or has_settings_props, (
                    f"{qs_file.name}: Should use SettingsContext or receive settings via props"
                )

            if "settings" in qs_file.name.lower():
                assert has_settings_context or has_settings_props, (
                    f"{qs_file.name}: Should use SettingsContext or receive settings via props"
                )

    def test_settings_imports_from_context(self) -> None:
        """Frontend should import settings from context, not directly."""
        tsx_files = list(FRONTEND_DIR.rglob("*.tsx"))

        violations = []

        for tsx_file in tsx_files:
            content = tsx_file.read_text(encoding="utf-8")

            if "settings" in tsx_file.name.lower():
                continue

            has_direct_import = re.search(r'import\s+.*from\s+["\']@/config/settings["\']', content)

            has_context_import = "useSettings" in content or "SettingsContext" in content

            if has_direct_import and not has_context_import:
                violations.append(
                    f"{tsx_file.relative_to(PROJECT_ROOT)}: Direct settings import without context"
                )

        assert not violations, f"Files with direct settings imports:\n" + "\n".join(violations[:5])


class TestFrontendCodeQuality:
    """Additional frontend code quality tests."""

    def test_no_console_log_in_production(self) -> None:
        """Avoid console.log statements that could leak info."""
        tsx_files = list(FRONTEND_DIR.rglob("*.tsx"))

        violations = []

        for tsx_file in tsx_files:
            content = tsx_file.read_text(encoding="utf-8")

            for i, line in enumerate(content.split("\n"), 1):
                if "console.log" in line and "import" not in line:
                    if not line.strip().startswith("//") and not line.strip().startswith("*"):
                        violations.append(f"{tsx_file.relative_to(PROJECT_ROOT)}:{i}")

        assert not violations, f"Found console.log statements in:\n" + "\n".join(violations[:5])

    def test_all_html_have_title(self) -> None:
        """All HTML files should have title tags."""
        html_files = list(FRONTEND_DIR.rglob("*.html"))

        violations = []

        for html_file in html_files:
            content = html_file.read_text(encoding="utf-8")

            if "<title>" not in content:
                violations.append(str(html_file.relative_to(PROJECT_ROOT)))

        assert not violations, f"HTML files missing title:\n" + "\n".join(violations)
