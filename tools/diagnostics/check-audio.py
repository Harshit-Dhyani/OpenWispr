#!/usr/bin/env python3
"""
Audio Diagnostics for Transcripta
Tests microphone, loopback devices, and audio capture

Usage:
    python tools/diagnostics/check-audio.py [--json] [--verbose] [--test DEVICE_ID]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DeviceInfo:
    """Information about an audio device."""

    id: str
    name: str
    channels: int | None
    is_loopback: bool = False
    kind: str = "unknown"


@dataclass
class CheckResult:
    """Result of an audio check."""

    name: str
    passed: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class AudioDiagnostics:
    """Audio diagnostics for Transcripta."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: list[CheckResult] = []
        self.devices: list[DeviceInfo] = []

    def _print_header(self, text: str) -> None:
        if self.verbose:
            print(f"\n{'=' * 60}")
            print(f"  {text}")
            print(f"{'=' * 60}")

    def _print_section(self, title: str) -> None:
        if self.verbose:
            print(f"\n{'─' * 60}")
            print(f"  {title}")
            print(f"{'─' * 60}")

    def check_soundcard(self) -> CheckResult:
        """Check if soundcard module is available."""
        self._print_header("Audio Diagnostics for Transcripta")

        try:
            import soundcard as sc

            result = CheckResult(
                name="soundcard_module",
                passed=True,
                message="soundcard module available",
                details={"module": "soundcard"},
            )
            if self.verbose:
                print("  ✓ soundcard module installed")
            self.results.append(result)
            return result
        except ImportError:
            result = CheckResult(
                name="soundcard_module",
                passed=False,
                message="soundcard module not installed - pip install soundcard",
            )
            if self.verbose:
                print("  ✗ soundcard module not found")
                print("  Run: pip install soundcard")
            self.results.append(result)
            return result

    def list_devices(self) -> list[DeviceInfo]:
        """List all audio devices."""
        self._print_section("Audio Devices")

        try:
            import soundcard as sc
        except ImportError:
            return []

        devices = []

        # List microphones
        try:
            mics = sc.all_microphones(include_loopback=True)
            for i, mic in enumerate(mics):
                device = DeviceInfo(
                    id=getattr(mic, "id", str(i)),
                    name=getattr(mic, "name", f"Mic {i}"),
                    channels=getattr(mic, "channels", None),
                    is_loopback=getattr(mic, "isloopback", False),
                    kind="microphone",
                )
                devices.append(device)

                if self.verbose:
                    loopback_marker = " [LOOPBACK]" if device.is_loopback else ""
                    print(f"  [{i}] {device.name}{loopback_marker}")
                    print(f"      ID: {device.id}, Channels: {device.channels}")
        except Exception as e:
            if self.verbose:
                print(f"  Error listing microphones: {e}")

        # List speakers
        try:
            speakers = sc.all_speakers()
            for i, speaker in enumerate(speakers):
                device = DeviceInfo(
                    id=getattr(speaker, "id", str(i)),
                    name=getattr(speaker, "name", f"Speaker {i}"),
                    channels=getattr(speaker, "channels", None),
                    kind="speaker",
                )
                devices.append(device)

                if self.verbose:
                    print(f"  [S{i}] {device.name}")
                    print(f"      ID: {device.id}, Channels: {device.channels}")
        except Exception as e:
            if self.verbose:
                print(f"  Error listing speakers: {e}")

        self.devices = devices

        result = CheckResult(
            name="device_list",
            passed=len(devices) > 0,
            message=f"Found {len(devices)} audio device(s)",
            details={
                "device_count": len(devices),
                "loopback_count": sum(1 for d in devices if d.is_loopback),
            },
        )
        self.results.append(result)
        return devices

    def check_default_microphone(self) -> CheckResult:
        """Check default microphone."""
        self._print_section("Default Microphone")

        try:
            import soundcard as sc

            default = sc.default_microphone()

            result = CheckResult(
                name="default_microphone",
                passed=True,
                message=f"Default: {default.name}",
                details={
                    "name": default.name,
                    "id": getattr(default, "id", "unknown"),
                    "channels": getattr(default, "channels", None),
                },
            )

            if self.verbose:
                print(f"  ✓ Default: {default.name}")
                print(f"    ID: {result.details['id']}")
                print(f"    Channels: {result.details['channels']}")

            self.results.append(result)
            return result

        except Exception as e:
            result = CheckResult(
                name="default_microphone",
                passed=False,
                message=f"Could not get default microphone: {e}",
            )
            if self.verbose:
                print(f"  ✗ Error: {e}")
            self.results.append(result)
            return result

    def test_capture(self, device_id: str | None = None, duration: float = 3.0) -> CheckResult:
        """Test audio capture from a device."""
        self._print_section("Capture Test")

        try:
            import numpy as np
            import soundcard as sc
        except ImportError as e:
            result = CheckResult(
                name="capture_test", passed=False, message=f"Missing dependency: {e}"
            )
            self.results.append(result)
            return result

        try:
            # Get device
            if device_id:
                # Find device by ID
                device = None
                for mic in sc.all_microphones(include_loopback=True):
                    if getattr(mic, "id", "") == device_id:
                        device = mic
                        break
                if device is None:
                    raise ValueError(f"Device {device_id} not found")
            else:
                device = sc.default_microphone()

            if self.verbose:
                print(f"  Testing: {device.name}")
                print(f"  Duration: {duration} seconds")
                print("  Please speak or play audio...")

            # Record
            samplerate = 16000
            with device.recorder(samplerate=samplerate) as mic:
                time.sleep(0.2)  # Initialize
                data = mic.record(numframes=int(samplerate * duration))

            # Analyze
            if data is None or len(data) == 0:
                result = CheckResult(
                    name="capture_test", passed=False, message="No audio data captured"
                )
                if self.verbose:
                    print("  ✗ No audio data captured")
                self.results.append(result)
                return result

            # Calculate metrics
            mono = data[:, 0] if len(data.shape) > 1 else data
            rms = float(np.sqrt(np.mean(mono**2)))
            peak = float(np.max(np.abs(mono)))
            db = 20 * np.log10(rms + 1e-10)

            has_signal = db > -50

            result = CheckResult(
                name="capture_test",
                passed=has_signal,
                message="Audio captured" if has_signal else "Audio level too low",
                details={
                    "samples": len(mono),
                    "rms": round(rms, 6),
                    "peak": round(peak, 6),
                    "db": round(db, 2),
                    "device": device.name,
                },
            )

            if self.verbose:
                print(f"  ✓ Captured {len(mono)} samples")
                print(f"  RMS: {rms:.4f}")
                print(f"  Peak: {peak:.4f}")
                print(f"  dB: {db:.1f}")
                if has_signal:
                    print("  ✓ Audio level good")
                else:
                    print("  ⚠ Audio level very low")
                    print("    - Check if microphone is muted")
                    print("    - Check Windows sound settings")

            self.results.append(result)
            return result

        except Exception as e:
            result = CheckResult(name="capture_test", passed=False, message=f"Capture failed: {e}")
            if self.verbose:
                print(f"  ✗ Error: {e}")
            self.results.append(result)
            return result

    def check_loopback_support(self) -> CheckResult:
        """Check for loopback device support."""
        self._print_section("Loopback Support")

        try:
            import soundcard as sc
        except ImportError:
            result = CheckResult(
                name="loopback_support", passed=False, message="soundcard not installed"
            )
            self.results.append(result)
            return result

        try:
            loopbacks = [d for d in self.devices if d.is_loopback]

            if loopbacks:
                result = CheckResult(
                    name="loopback_support",
                    passed=True,
                    message=f"Found {len(loopbacks)} loopback device(s)",
                    details={"loopback_devices": len(loopbacks)},
                )
                if self.verbose:
                    print(f"  ✓ Found {len(loopbacks)} loopback device(s)")
                    for d in loopbacks:
                        print(f"    - {d.name}")
            else:
                result = CheckResult(
                    name="loopback_support",
                    passed=False,
                    message="No loopback devices found - WASAPI may not be available",
                )
                if self.verbose:
                    print("  ⚠ No loopback devices found")
                    print("    WASAPI loopback may not be available")

            self.results.append(result)
            return result

        except Exception as e:
            result = CheckResult(
                name="loopback_support", passed=False, message=f"Error checking loopback: {e}"
            )
            self.results.append(result)
            return result

    def run_all(self, test_device: str | None = None) -> list[CheckResult]:
        """Run all audio diagnostics."""
        self.check_soundcard()
        self.list_devices()
        self.check_default_microphone()
        self.check_loopback_support()

        # Only run capture test if explicitly requested or verbose
        if test_device or self.verbose:
            self.test_capture(device_id=test_device)

        return self.results

    def print_summary(self) -> bool:
        """Print summary."""
        critical = ["soundcard_module", "device_list"]
        critical_results = [r for r in self.results if r.name in critical]
        passed = sum(1 for r in critical_results if r.passed)

        if self.verbose:
            print(f"\n{'=' * 60}")
            print("SUMMARY")
            print(f"{'=' * 60}")

            for result in self.results:
                status = "✓" if result.passed else "✗"
                print(f"  [{status}] {result.name}: {result.message}")

            print(f"\n  Critical: {passed}/{len(critical_results)} passed")

        return passed == len(critical_results)

    def to_json(self) -> dict:
        """Export results as JSON."""
        return {
            "success": all(
                r.passed for r in self.results if r.name in ["soundcard_module", "device_list"]
            ),
            "checks": [
                {"name": r.name, "passed": r.passed, "message": r.message, "details": r.details}
                for r in self.results
            ],
            "devices": [
                {
                    "id": d.id,
                    "name": d.name,
                    "channels": d.channels,
                    "is_loopback": d.is_loopback,
                    "kind": d.kind,
                }
                for d in self.devices
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audio diagnostics for Transcripta",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/diagnostics/check-audio.py           # Basic check
  python tools/diagnostics/check-audio.py --verbose # Detailed info
  python tools/diagnostics/check-audio.py --test <device_id>
        """,
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--test", metavar="DEVICE_ID", help="Test specific device")

    args = parser.parse_args()

    # Default to verbose if not JSON
    verbose = args.verbose or not args.json

    diagnostics = AudioDiagnostics(verbose=verbose)
    diagnostics.run_all(test_device=args.test)
    success = diagnostics.print_summary()

    if args.json:
        print(json.dumps(diagnostics.to_json(), indent=2))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
