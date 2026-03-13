"""Regression tests for Electron security audit findings.

Tests for security issues found in the Electron audit:
- CSP headers in all HTML files
- nodeIntegration disabled
- contextIsolation enabled
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
ELECTRON_DIR = PROJECT_ROOT / "app" / "electron"


class TestCSPHeaders:
    """Tests for Content Security Policy headers in HTML files."""

    def _get_html_files(self) -> list[Path]:
        """Get all HTML files in the Electron directory (excluding node_modules and dist)."""
        html_files = []
        for pattern in ["**/*.html"]:
            for f in ELECTRON_DIR.rglob(pattern):
                if f.is_file():
                    path_str = str(f)
                    if "node_modules" not in path_str and "dist" not in path_str:
                        html_files.append(f)
        return html_files

    def _extract_head_content(self, html_path: Path) -> str:
        """Extract content from the <head> tag."""
        content = html_path.read_text(encoding="utf-8")
        head_match = re.search(r"<head[^>]*>(.*?)</head>", content, re.DOTALL | re.IGNORECASE)
        if head_match:
            return head_match.group(1)
        return ""

    def test_csp_headers_present(self) -> None:
        """All HTML files should have CSP meta tag."""
        html_files = self._get_html_files()

        assert len(html_files) > 0, "No HTML files found in Electron directory"

        missing_csp = []
        for html_file in html_files:
            head_content = self._extract_head_content(html_file)
            has_csp = bool(
                re.search(
                    r'<meta[^>]+http-equiv=["\']?Content-Security-Policy',
                    head_content,
                    re.IGNORECASE,
                )
            )

            if not has_csp:
                missing_csp.append(str(html_file.relative_to(PROJECT_ROOT)))

        assert not missing_csp, f"The following HTML files are missing CSP meta tags: {missing_csp}"

    def test_csp_allows_minimal_sources(self) -> None:
        """CSP should be minimal - default-src 'self'."""
        html_files = self._get_html_files()

        for html_file in html_files:
            head_content = self._extract_head_content(html_file)
            csp_match = re.search(
                r'<meta[^>]+http-equiv=["\']?Content-Security-Policy["\']?\s+content=["\']([^"\']+)["\']',
                head_content,
                re.IGNORECASE,
            )

            if csp_match:
                csp_value = csp_match.group(1)
                assert "default-src" in csp_value, (
                    f"{html_file.name}: CSP should specify default-src"
                )


class TestNodeIntegration:
    """Tests for nodeIntegration security setting."""

    def _find_browser_window_configs(self) -> list[tuple[str, dict]]:
        """Find all BrowserWindow configurations."""
        configs = []

        window_files = [
            ELECTRON_DIR / "main" / "windows" / "mainWindow.js",
            ELECTRON_DIR / "main" / "windows" / "floatingWindow.js",
            ELECTRON_DIR / "main" / "windows" / "quickSettingsWindow.js",
            ELECTRON_DIR / "main" / "services" / "windowManager.js",
        ]

        for window_file in window_files:
            if window_file.exists():
                content = window_file.read_text(encoding="utf-8")
                configs.append(
                    (
                        str(window_file.relative_to(PROJECT_ROOT)),
                        {
                            "content": content,
                        },
                    )
                )

        return configs

    def test_no_node_integration(self) -> None:
        """nodeIntegration should be false for all windows."""
        configs = self._find_browser_window_configs()

        assert len(configs) > 0, "No window configuration files found"

        violations = []
        for file_path, config in configs:
            content = config["content"]

            if "nodeIntegration" in content:
                if re.search(r"nodeIntegration:\s*true", content):
                    violations.append(f"{file_path}: nodeIntegration is true")
                elif "nodeIntegration" not in content:
                    violations.append(f"{file_path}: nodeIntegration not specified")

        assert not violations, f"nodeIntegration violations found:\n" + "\n".join(violations)

    def test_context_isolation(self) -> None:
        """contextIsolation should be true for all windows."""
        configs = self._find_browser_window_configs()

        assert len(configs) > 0, "No window configuration files found"

        violations = []
        for file_path, config in configs:
            content = config["content"]

            if "contextIsolation" in content:
                if re.search(r"contextIsolation:\s*false", content):
                    violations.append(f"{file_path}: contextIsolation is false")
            else:
                violations.append(f"{file_path}: contextIsolation not specified")

        assert not violations, f"contextIsolation violations found:\n" + "\n".join(violations)


class TestElectronSecurityBestPractices:
    """Tests for Electron security best practices."""

    def test_no_remote_module(self) -> None:
        """Should not use deprecated remote module."""
        js_files = list(ELECTRON_DIR.rglob("*.js"))

        violations = []
        for js_file in js_files:
            if "node_modules" in str(js_file):
                continue
            content = js_file.read_text(encoding="utf-8")
            if "require('remote')" in content or 'require("remote")' in content:
                violations.append(str(js_file.relative_to(PROJECT_ROOT)))

        assert not violations, f"Found deprecated remote module usage in: {violations}"

    def test_preload_script_exists(self) -> None:
        """Windows that need IPC should have preload scripts."""
        window_files = [
            ELECTRON_DIR / "main" / "windows" / "mainWindow.js",
            ELECTRON_DIR / "main" / "windows" / "floatingWindow.js",
            ELECTRON_DIR / "main" / "windows" / "quickSettingsWindow.js",
        ]

        for window_file in window_files:
            if not window_file.exists():
                continue

            content = window_file.read_text(encoding="utf-8")

            if "BrowserWindow" in content:
                assert "preload" in content, (
                    f"{window_file.name}: BrowserWindow should have preload script"
                )
