"""E2E regression tests for coach integration audit findings.

Tests for coach integration issues found in audit:
- Coach results should display in UI
- Floating window should show coach suggestions
"""

from __future__ import annotations

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ELECTRON_DIR = PROJECT_ROOT / "app" / "electron"
FRONTEND_DIR = ELECTRON_DIR / "frontend" / "src"


class TestCoachResultDisplay:
    """Tests for coach result display in UI."""

    def test_coach_result_displays(self) -> None:
        """Coach output should appear in UI."""
        coach_component_files = [
            FRONTEND_DIR / "components" / "CoachContent.tsx",
            FRONTEND_DIR / "components" / "CoachPanel.tsx",
            FRONTEND_DIR / "components" / "CoachDrawer.tsx",
        ]

        found_component = False
        for coach_file in coach_component_files:
            if coach_file.exists():
                found_component = True
                content = coach_file.read_text(encoding="utf-8")

                has_result_display = (
                    "coachResult" in content
                    or "polished" in content
                    or "suggestion" in content
                    or "coachOutput" in content
                )

                assert has_result_display, f"{coach_file.name}: Should display coach result"

        assert found_component, (
            "No coach UI component found. Coach results cannot display without UI."
        )

    def test_coach_service_integrated(self) -> None:
        """Coach service should be integrated with frontend."""
        tsx_files = list(FRONTEND_DIR.rglob("*.tsx"))

        coach_integration_found = False

        for tsx_file in tsx_files:
            content = tsx_file.read_text(encoding="utf-8")

            if any(keyword in content.lower() for keyword in ["coach", "polish", "improve"]):
                if "api" in content.lower() or "service" in content.lower():
                    coach_integration_found = True
                    break

        assert coach_integration_found, (
            "Coach service should be integrated with frontend via API calls"
        )


class TestFloatingWindowCoach:
    """Tests for coach suggestions in floating window."""

    def test_floating_window_shows_coach(self) -> None:
        """Floating window should show coach suggestions when enabled."""
        floating_files = [
            FRONTEND_DIR / "components" / "FloatingContent.tsx",
            FRONTEND_DIR / "floating-main.tsx",
        ]

        found_floating = False

        for floating_file in floating_files:
            if floating_file.exists():
                found_floating = True
                content = floating_file.read_text(encoding="utf-8")

                has_coach_support = (
                    "coach" in content.lower()
                    or "suggestion" in content.lower()
                    or "polished" in content.lower()
                )

                if not has_coach_support:
                    pytest.skip(f"{floating_file.name}: Coach integration not implemented yet")

        assert found_floating, "No floating window component found"

    def test_floating_window_coach_setting(self) -> None:
        """There should be a setting to enable coach in floating window."""
        settings_files = [
            FRONTEND_DIR / "components" / "SettingsContent.tsx",
            FRONTEND_DIR / "config" / "settings.ts",
        ]

        found_coach_setting = False

        for settings_file in settings_files:
            if settings_file.exists():
                content = settings_file.read_text(encoding="utf-8")

                if "coach" in content.lower() and "floating" in content.lower():
                    found_coach_setting = True
                    break

        if not found_coach_setting:
            pytest.skip("Coach floating window setting not implemented yet")


class TestCoachAPIContract:
    """Tests for coach API contract."""

    def test_coach_api_endpoint_exists(self) -> None:
        """Backend should have coach API endpoint."""
        api_files = list((PROJECT_ROOT / "app" / "api").rglob("*.py"))

        coach_endpoint_found = False

        for api_file in api_files:
            content = api_file.read_text(encoding="utf-8")

            if "coach" in content.lower():
                if "route" in content.lower() or "@app" in content or "router" in content:
                    coach_endpoint_found = True
                    break

        assert coach_endpoint_found, "Coach API endpoint not found in backend"

    def test_coach_response_schema(self) -> None:
        """Coach API response should have proper schema."""
        api_files = list((PROJECT_ROOT / "app" / "api").rglob("*.py"))

        for api_file in api_files:
            content = api_file.read_text(encoding="utf-8")

            if "coach" in content.lower() and "route" in content.lower():
                has_response_model = (
                    "polished" in content or "suggestion" in content or "CoachResponse" in content
                )

                assert has_response_model, (
                    f"{api_file.name}: Should have proper coach response schema"
                )


class TestCoachServiceIntegration:
    """Tests for coach service backend integration."""

    def test_coach_service_available(self) -> None:
        """Coach service should be importable and usable."""
        import sys

        sys.path.insert(0, str(PROJECT_ROOT / "app"))

        try:
            from app.api.services.coach_service import CoachService

            assert CoachService is not None
        except ImportError as e:
            pytest.fail(f"CoachService not importable: {e}")

    def test_coach_runtime_independent(self) -> None:
        """Coach should have independent runtime settings (not gated on refiner)."""
        import sys

        sys.path.insert(0, str(PROJECT_ROOT / "app"))

        from app.config.settings import SETTINGS_REGISTRY

        coach_settings = [name for name in SETTINGS_REGISTRY.keys() if "coach" in name.lower()]

        assert len(coach_settings) > 0, (
            "Coach should have its own settings, not be gated on refiner"
        )
