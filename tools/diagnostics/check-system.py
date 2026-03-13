#!/usr/bin/env python3
"""
System Diagnostics for OpenWispr
Checks CUDA availability across all transcription dependencies

Usage:
    python tools/diagnostics/check-system.py [--json] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    """Result of a system check."""

    name: str
    passed: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


class SystemDiagnostics:
    """System diagnostics for OpenWispr."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: list[CheckResult] = []
        self.warnings: list[str] = []

    def _print_header(self, text: str) -> None:
        """Print section header."""
        if self.verbose:
            print(f"\n{'=' * 50}")
            print(f"  {text}")
            print(f"{'=' * 50}")

    def _print_section(self, title: str) -> None:
        """Print subsection."""
        if self.verbose:
            print(f"\n{'─' * 50}")
            print(f"  {title}")
            print(f"{'─' * 50}")

    def _print_result(self, label: str, value: str, status: str | None = None) -> None:
        """Print a result line."""
        if not self.verbose:
            return
        symbols = {"ok": "[✓] ", "warn": "[!] ", "error": "[✗] "}
        symbol = symbols.get(status, "")
        print(f"  {symbol}{label:<30} {value}")

    def check_pytorch(self) -> CheckResult:
        """Check PyTorch CUDA availability."""
        self._print_section("PyTorch")

        try:
            import torch

            cuda_available = torch.cuda.is_available()
            result = CheckResult(
                name="pytorch_cuda",
                passed=cuda_available,
                message="CUDA available" if cuda_available else "CUDA not available",
                details={
                    "pytorch_version": torch.__version__,
                    "cuda_available": cuda_available,
                },
            )

            if cuda_available:
                result.details["cuda_version"] = torch.version.cuda or "Unknown"
                result.details["device_count"] = torch.cuda.device_count()
                result.details["device_name"] = (
                    torch.cuda.get_device_name(0) if result.details["device_count"] > 0 else "N/A"
                )

                self._print_result("CUDA available", "Yes", "ok")
                self._print_result("CUDA version", result.details["cuda_version"], "ok")
                self._print_result("GPU count", str(result.details["device_count"]), "ok")
                self._print_result("Primary GPU", result.details["device_name"], "ok")

                # Memory info
                try:
                    mem_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    result.details["gpu_memory_gb"] = round(mem_total, 2)
                    self._print_result("GPU Memory", f"{mem_total:.2f} GB", "ok")
                except Exception as e:
                    if self.verbose:
                        print(f"  Could not get memory info: {e}")
            else:
                self._print_result("CUDA available", "No", "error")
                result.message = "PyTorch CUDA not available - may have CPU-only version"

            self.results.append(result)
            return result

        except ImportError:
            result = CheckResult(name="pytorch_cuda", passed=False, message="PyTorch not installed")
            self._print_result("PyTorch", "Not installed", "error")
            self.results.append(result)
            return result

    def check_ctranslate2(self) -> CheckResult:
        """Check CTranslate2 CUDA support."""
        self._print_section("CTRANSLATE2")

        try:
            import ctranslate2

            version = getattr(ctranslate2, "__version__", "Unknown")

            try:
                devices = ctranslate2.get_cuda_device_count()
                passed = devices > 0

                result = CheckResult(
                    name="ctranslate2_cuda",
                    passed=passed,
                    message=f"{devices} CUDA device(s) detected",
                    details={"version": version, "cuda_devices": devices},
                )

                self._print_result("Version", version)
                self._print_result("CUDA devices", str(devices), "ok" if passed else "warn")

            except Exception as e:
                result = CheckResult(
                    name="ctranslate2_cuda",
                    passed=False,
                    message=f"CUDA check failed: {e}",
                    details={"version": version, "error": str(e)},
                )
                self._print_result("CUDA check", f"Error: {e}", "error")

            self.results.append(result)
            return result

        except ImportError:
            result = CheckResult(
                name="ctranslate2_cuda", passed=False, message="CTRANSLATE2 not installed"
            )
            self._print_result("CTRANSLATE2", "Not installed", "error")
            self.results.append(result)
            return result

    def check_faster_whisper(self) -> CheckResult:
        """Check faster-whisper installation."""
        self._print_section("Faster-Whisper")

        try:
            from faster_whisper import WhisperModel

            result = CheckResult(
                name="faster_whisper",
                passed=True,
                message="Faster-Whisper installed",
                details={"installed": True},
            )
            self._print_result("Installed", "Yes", "ok")

            # Check compute types
            try:
                import ctranslate2

                if ctranslate2.get_cuda_device_count() > 0:
                    supported = ctranslate2.get_supported_compute_types("cuda")
                    result.details["compute_types"] = list(supported)
                    self._print_result("CUDA compute types", ", ".join(sorted(supported)), "ok")
            except Exception as e:
                logging.warning("Failed to check CUDA compute types for faster-whisper: %s", e)

            self.results.append(result)
            return result

        except ImportError:
            result = CheckResult(
                name="faster_whisper",
                passed=True,  # Warning only
                message="Faster-Whisper not installed (optional)",
            )
            self._print_result("Faster-Whisper", "Not installed (optional)", "warn")
            self.warnings.append(
                "Faster-Whisper not installed (only needed for faster-whisper backend)"
            )
            self.results.append(result)
            return result

    def check_nvidia_smi(self) -> CheckResult:
        """Check NVIDIA driver status."""
        self._print_section("NVIDIA Drivers")

        try:
            result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                driver_info = {}

                for line in lines:
                    if "Driver Version" in line:
                        driver_info["driver_version"] = line.strip()
                        self._print_result("Driver", line.strip(), "ok")
                    if "CUDA Version" in line:
                        driver_info["cuda_version"] = line.strip()
                        self._print_result("CUDA", line.strip(), "ok")

                check_result = CheckResult(
                    name="nvidia_driver",
                    passed=True,
                    message="NVIDIA drivers installed",
                    details=driver_info,
                )
            else:
                check_result = CheckResult(
                    name="nvidia_driver", passed=False, message="nvidia-smi returned error"
                )
                self._print_result("nvidia-smi", "Error", "error")

            self.results.append(check_result)
            return check_result

        except FileNotFoundError:
            result = CheckResult(
                name="nvidia_driver",
                passed=False,
                message="nvidia-smi not found - NVIDIA drivers may not be installed",
            )
            self._print_result("nvidia-smi", "Not found", "error")
            self.results.append(result)
            return result
        except subprocess.TimeoutExpired:
            result = CheckResult(name="nvidia_driver", passed=False, message="nvidia-smi timeout")
            self._print_result("nvidia-smi", "Timeout", "error")
            self.results.append(result)
            return result

    def check_environment(self) -> CheckResult:
        """Check environment variables."""
        self._print_section("Environment Variables")

        env_vars = ["CUDA_PATH", "CUDA_HOME", "PATH"]
        found = []

        for var in env_vars:
            value = os.environ.get(var)
            if value:
                found.append(var)
                if var == "PATH":
                    cuda_paths = [p for p in value.split(os.pathsep) if "cuda" in p.lower()]
                    if cuda_paths:
                        self._print_result(var, f"{len(cuda_paths)} CUDA paths", "ok")
                    else:
                        self._print_result(var, "Set (no CUDA paths)", "warn")
                else:
                    display = value if len(value) < 50 else value[:47] + "..."
                    self._print_result(var, display, "ok")
            else:
                if var in ("CUDA_PATH", "CUDA_HOME"):
                    self._print_result(var, "Not set", "warn")

        result = CheckResult(
            name="environment",
            passed=True,
            message=f"Found {len(found)} relevant env vars",
            details={"found_vars": found},
        )
        self.results.append(result)
        return result

    def run_all(self) -> list[CheckResult]:
        """Run all system diagnostics."""
        self._print_header("System Diagnostics for OpenWispr")

        if self.verbose:
            print(f"  Platform: {sys.platform}")
            print(f"  Python: {sys.version.split()[0]}")
            print(f"  Executable: {sys.executable}")

        self.check_pytorch()
        self.check_ctranslate2()
        self.check_faster_whisper()
        self.check_nvidia_smi()
        self.check_environment()

        return self.results

    def print_summary(self) -> bool:
        """Print summary of results."""
        critical_checks = ["pytorch_cuda", "ctranslate2_cuda", "nvidia_driver"]
        critical_results = [r for r in self.results if r.name in critical_checks]

        passed = sum(1 for r in critical_results if r.passed)
        total = len(critical_results)

        if self.verbose:
            print(f"\n{'=' * 50}")
            print("SUMMARY")
            print(f"{'=' * 50}")

            for result in self.results:
                status = "ok" if result.passed else "error"
                self._print_result(result.name, "PASS" if result.passed else "FAIL", status)

            print(f"\n  Critical: {passed}/{total} passed")

            if self.warnings:
                print("\n  Warnings:")
                for warning in self.warnings:
                    print(f"    ! {warning}")

        return passed == total

    def to_json(self) -> dict:
        """Export results as JSON-serializable dict."""
        return {
            "success": all(
                r.passed for r in self.results if r.name in ["pytorch_cuda", "ctranslate2_cuda"]
            ),
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "checks": [
                {"name": r.name, "passed": r.passed, "message": r.message, "details": r.details}
                for r in self.results
            ],
            "warnings": self.warnings,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="System diagnostics for OpenWispr",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Default to verbose if not JSON
    verbose = args.verbose or not args.json

    diagnostics = SystemDiagnostics(verbose=verbose)
    diagnostics.run_all()
    success = diagnostics.print_summary()

    if args.json:
        print(json.dumps(diagnostics.to_json(), indent=2))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
