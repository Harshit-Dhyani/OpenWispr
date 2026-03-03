#!/usr/bin/env python3
"""
Transcripta Tools Runner - Unified interface for all development tools.

Usage:
    python tools/runner.py --all              # Run all checks
    python tools/runner.py --system          # Run system diagnostics
    python tools/runner.py --audio           # Run audio diagnostics
    python tools/runner.py --ci              # Run CI verification
    python tools/runner.py --setup           # Run setup checks

Options:
    --json      Output results as JSON
    --verbose   Show detailed output
    --fix       Attempt to fix issues automatically (where supported)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolResult:
    """Result of running a tool."""

    name: str
    passed: bool
    exit_code: int
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0


class ToolRunner:
    """Runner for Transcripta development tools."""

    TOOLS_DIR = Path(__file__).parent

    # Tool definitions: (name, script_path, description)
    TOOLS = {
        "system": ("diagnostics/check-system.py", "System diagnostics (CUDA, dependencies)"),
        "audio": ("diagnostics/check-audio.py", "Audio device diagnostics"),
        "ci": ("ci/verify-fixes.py", "CI verification (pre-commit checks)"),
        "cleanup": ("maintenance/cleanup-logs.py", "Log file cleanup"),
    }

    def __init__(self, verbose: bool = False, json_output: bool = False):
        self.verbose = verbose
        self.json_output = json_output
        self.results: list[ToolResult] = []

    def _run_script(self, name: str, script_path: str, args: list[str] | None = None) -> ToolResult:
        """Run a Python script and capture results."""
        import time

        full_path = self.TOOLS_DIR / script_path

        if not full_path.exists():
            return ToolResult(
                name=name, passed=False, exit_code=1, error=f"Script not found: {full_path}"
            )

        cmd = [sys.executable, str(full_path)]
        if args:
            cmd.extend(args)
        if self.json_output:
            cmd.append("--json")

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            duration_ms = (time.time() - start_time) * 1000

            return ToolResult(
                name=name,
                passed=result.returncode == 0,
                exit_code=result.returncode,
                output=result.stdout,
                error=result.stderr,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                name=name, passed=False, exit_code=124, error="Timeout after 5 minutes"
            )
        except Exception as e:
            return ToolResult(name=name, passed=False, exit_code=1, error=str(e))

    def run_system(self) -> ToolResult:
        """Run system diagnostics."""
        self._print_header("System Diagnostics")
        result = self._run_script("system", self.TOOLS["system"][0])
        self.results.append(result)
        if not self.json_output:
            self._print_result(result)
        return result

    def run_audio(self) -> ToolResult:
        """Run audio diagnostics."""
        self._print_header("Audio Diagnostics")
        result = self._run_script("audio", self.TOOLS["audio"][0])
        self.results.append(result)
        if not self.json_output:
            self._print_result(result)
        return result

    def run_ci(self) -> ToolResult:
        """Run CI verification."""
        self._print_header("CI Verification")
        result = self._run_script("ci", self.TOOLS["ci"][0])
        self.results.append(result)
        if not self.json_output:
            self._print_result(result)
        return result

    def run_cleanup(self) -> ToolResult:
        """Run log cleanup."""
        self._print_header("Log Cleanup")
        result = self._run_script("cleanup", self.TOOLS["cleanup"][0])
        self.results.append(result)
        if not self.json_output:
            self._print_result(result)
        return result

    def run_all(self) -> list[ToolResult]:
        """Run all diagnostic tools."""
        self.run_system()
        self.run_audio()
        self.run_ci()
        return self.results

    def _print_header(self, text: str) -> None:
        """Print a section header."""
        if not self.json_output:
            print(f"\n{'=' * 60}")
            print(f"  {text}")
            print(f"{'=' * 60}")

    def _print_result(self, result: ToolResult) -> None:
        """Print tool result."""
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"\n[{status}] {result.name} (exit: {result.exit_code})")

        if self.verbose or not result.passed:
            if result.output:
                print(result.output)
            if result.error:
                print(f"Errors: {result.error}")

    def print_summary(self) -> bool:
        """Print summary of all results."""
        if self.json_output:
            output = {
                "success": all(r.passed for r in self.results),
                "results": [
                    {
                        "name": r.name,
                        "passed": r.passed,
                        "exit_code": r.exit_code,
                        "duration_ms": r.duration_ms,
                        "output": r.output if self.verbose else None,
                        "error": r.error if not r.passed else None,
                    }
                    for r in self.results
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"\n{'=' * 60}")
            print("SUMMARY")
            print(f"{'=' * 60}")

            for result in self.results:
                status = "✓" if result.passed else "✗"
                print(f"  [{status}] {result.name}")

            passed = sum(1 for r in self.results if r.passed)
            total = len(self.results)
            print(f"\nTotal: {passed}/{total} passed")

        return all(r.passed for r in self.results)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transcripta Tools Runner - Unified tool interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/runner.py --all              # Run all diagnostics
  python tools/runner.py --system --json    # System check, JSON output
  python tools/runner.py --audio --verbose  # Audio check with details
  python tools/runner.py --ci               # Run CI verification only
        """,
    )

    parser.add_argument("--all", action="store_true", help="Run all checks")
    parser.add_argument("--system", action="store_true", help="Run system diagnostics")
    parser.add_argument("--audio", action="store_true", help="Run audio diagnostics")
    parser.add_argument("--ci", action="store_true", help="Run CI verification")
    parser.add_argument("--cleanup", action="store_true", help="Run log cleanup")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--list", action="store_true", help="List available tools")

    args = parser.parse_args()

    # List mode
    if args.list:
        print("Available tools:")
        for name, (_, description) in ToolRunner.TOOLS.items():
            print(f"  --{name:<10} {description}")
        return 0

    # Default to --all if no specific tool selected
    if not any([args.all, args.system, args.audio, args.ci, args.cleanup]):
        args.all = True

    runner = ToolRunner(verbose=args.verbose, json_output=args.json)

    if args.all:
        runner.run_all()
    else:
        if args.system:
            runner.run_system()
        if args.audio:
            runner.run_audio()
        if args.ci:
            runner.run_ci()
        if args.cleanup:
            runner.run_cleanup()

    success = runner.print_summary()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
