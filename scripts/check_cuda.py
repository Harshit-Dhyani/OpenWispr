#!/usr/bin/env python3
"""
CUDA Diagnostic Script for Transcripta
Checks CUDA availability across all transcription dependencies
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(text):
    print(f"\n{'=' * 50}")
    print(f"  {text}")
    print(f"{'=' * 50}")


def print_section(title):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


def print_result(label, value, status=None):
    status_symbol = ""
    if status == "ok":
        status_symbol = "[✓] "
    elif status == "warn":
        status_symbol = "[!] "
    elif status == "error":
        status_symbol = "[✗] "
    print(f"  {status_symbol}{label:<30} {value}")


def check_pytorch_cuda():
    """Check PyTorch CUDA availability"""
    print_section("PyTorch CUDA")

    try:
        import torch

        cuda_available = torch.cuda.is_available()

        if cuda_available:
            cuda_version = torch.version.cuda or "Unknown"
            device_count = torch.cuda.device_count()
            device_name = torch.cuda.get_device_name(0) if device_count > 0 else "N/A"

            print_result("CUDA available", "Yes", "ok")
            print_result("CUDA version", cuda_version, "ok")
            print_result("GPU count", device_count, "ok")
            print_result("Primary GPU", device_name, "ok")

            # Get memory info for primary GPU
            if device_count > 0:
                try:
                    mem_allocated = torch.cuda.memory_allocated(0) / 1024**3
                    mem_reserved = torch.cuda.memory_reserved(0) / 1024**3
                    mem_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    print_result("GPU Memory (allocated)", f"{mem_allocated:.2f} GB")
                    print_result("GPU Memory (reserved)", f"{mem_reserved:.2f} GB")
                    print_result("GPU Memory (total)", f"{mem_total:.2f} GB", "ok")
                except Exception as e:
                    print_result("GPU Memory", f"Error: {e}", "warn")

            return True, cuda_version
        else:
            print_result("CUDA available", "No", "error")
            print_result("PyTorch version", torch.__version__, "warn")

            # Check if torch is CPU-only build
            if hasattr(torch, "_C") and not torch.cuda.is_available():
                print("\n  ⚠️  PyTorch is installed but CUDA is not available.")
                print("      You may have installed the CPU-only version of PyTorch.")

            return False, None

    except ImportError:
        print_result("PyTorch", "Not installed", "error")
        print("\n  ⚠️  PyTorch is not installed.")
        return False, None


def check_ctranslate2_cuda():
    """Check CTranslate2 CUDA support"""
    print_section("CTRANSLATE2")

    try:
        import ctranslate2

        # Get version
        version = getattr(ctranslate2, "__version__", "Unknown")
        print_result("Version", version)

        # Check CUDA devices
        try:
            devices = ctranslate2.get_cuda_device_count()
            if devices > 0:
                print_result("CUDA devices", devices, "ok")
                return True
            else:
                print_result("CUDA devices", "0 (CPU only)", "warn")
                return False
        except Exception as e:
            print_result("CUDA check", f"Error: {e}", "error")
            return False

    except ImportError:
        print_result("CTRANSLATE2", "Not installed", "error")
        print("\n  ⚠️  CTranslate2 is not installed.")
        return False


def check_faster_whisper():
    """Check faster-whisper CUDA support"""
    print_section("Faster-Whisper")

    try:
        from faster_whisper import WhisperModel

        print_result("Installed", "Yes", "ok")

        # Try to detect compute type support
        try:
            import ctranslate2

            supported = (
                ctranslate2.get_supported_compute_types("cuda")
                if ctranslate2.get_cuda_device_count() > 0
                else set()
            )
            if supported:
                print_result("CUDA compute types", ", ".join(sorted(supported)), "ok")
        except Exception:
            pass

        return True

    except ImportError:
        print_result("Faster-Whisper", "Not installed", "warn")
        print("\n  ℹ️  Faster-Whisper is not installed.")
        print("     This is only needed if you plan to use faster-whisper backend.")
        return False


def check_environment_variables():
    """Check relevant environment variables"""
    print_section("Environment Variables")

    env_vars = [
        "CUDA_PATH",
        "CUDA_HOME",
        "CUDA_ROOT",
        "PATH",
        "LD_LIBRARY_PATH",
        "CTRANSLATE2_ROOT",
    ]

    found_any = False
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            found_any = True
            if var == "PATH":
                # Show PATH entries that contain CUDA
                cuda_paths = [p for p in value.split(os.pathsep) if "cuda" in p.lower()]
                if cuda_paths:
                    print_result(var, f"{len(cuda_paths)} CUDA-related paths", "ok")
                    for p in cuda_paths[:3]:  # Show first 3
                        print(f"    → {p}")
                    if len(cuda_paths) > 3:
                        print(f"    ... and {len(cuda_paths) - 3} more")
                else:
                    print_result(var, "Set (no CUDA paths found)", "warn")
            else:
                # Truncate long values
                display_value = value if len(value) < 50 else value[:47] + "..."
                print_result(var, display_value, "ok")
        else:
            if var in ("CUDA_PATH", "CUDA_HOME"):
                print_result(var, "Not set", "warn")
            else:
                print_result(var, "Not set", None)

    if not found_any:
        print("  ⚠️  No CUDA-related environment variables found.")


def check_nvidia_smi():
    """Check nvidia-smi output"""
    print_section("NVIDIA System Management")

    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            print_result("nvidia-smi", "Available", "ok")

            # Extract driver version
            for line in lines:
                if "Driver Version" in line:
                    print(f"  {line.strip()}")
                if "CUDA Version" in line:
                    print(f"  {line.strip()}")

            # Show GPU summary
            print("\n  GPU Summary:")
            for i, line in enumerate(lines):
                if line.strip().startswith("|") and "%" in line:
                    print(f"    {line}")
                    if i + 1 < len(lines) and lines[i + 1].strip().startswith("|"):
                        print(f"    {lines[i + 1]}")
        else:
            print_result("nvidia-smi", "Error", "error")
            print(f"  stderr: {result.stderr[:200]}")

    except FileNotFoundError:
        print_result("nvidia-smi", "Not found in PATH", "error")
        print("\n  ⚠️  nvidia-smi not found. NVIDIA drivers may not be installed.")
    except subprocess.TimeoutExpired:
        print_result("nvidia-smi", "Timeout", "error")
    except Exception as e:
        print_result("nvidia-smi", f"Error: {e}", "error")


def check_cuda_installation():
    """Check for CUDA toolkit installation"""
    print_section("CUDA Toolkit")

    cuda_paths = []

    # Common CUDA installation paths on Windows
    windows_paths = [
        Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"),
        Path(r"C:\CUDA"),
    ]

    # Check environment paths
    for env_var in ["CUDA_PATH", "CUDA_HOME", "CUDA_ROOT"]:
        path = os.environ.get(env_var)
        if path:
            cuda_paths.append(Path(path))

    # Check common paths
    cuda_paths.extend(windows_paths)

    found_cuda = False
    for cuda_path in cuda_paths:
        if cuda_path.exists():
            found_cuda = True
            print_result("CUDA Toolkit path", str(cuda_path), "ok")

            # List versions found
            if cuda_path.name == "CUDA":
                versions = [d for d in cuda_path.iterdir() if d.is_dir()]
                if versions:
                    print(f"  Installed versions: {', '.join(v.name for v in versions)}")

            # Check for nvcc
            nvcc_paths = [
                cuda_path / "bin" / "nvcc.exe",
                cuda_path / "bin" / "nvcc",
            ]
            for nvcc in nvcc_paths:
                if nvcc.exists():
                    try:
                        result = subprocess.run(
                            [str(nvcc), "--version"], capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0:
                            for line in result.stdout.split("\n"):
                                if "release" in line.lower():
                                    print(f"  {line.strip()}")
                    except Exception:
                        pass
            break

    if not found_cuda:
        print_result("CUDA Toolkit", "Not found", "error")


def print_recommendations(pytorch_ok, ct2_ok, fw_ok):
    """Print troubleshooting recommendations"""
    print_header("Recommendations")

    issues = []

    if not pytorch_ok:
        issues.append("""
  PyTorch CUDA Issues:
  • Install PyTorch with CUDA support:
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
  • For CPU-only: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
""")

    if not ct2_ok:
        issues.append("""
  CTranslate2 CUDA Issues:
  • Ensure NVIDIA drivers are installed (version >= 525.60.13)
  • Reinstall CTranslate2 with CUDA support:
    pip install --force-reinstall ctranslate2
  • For CPU-only: pip install --force-reinstall ctranslate2 --no-binary ctranslate2
""")

    if not fw_ok:
        issues.append("""
  Faster-Whisper Issues:
  • Install faster-whisper:
    pip install faster-whisper
  • This requires working CTranslate2 with CUDA
""")

    # Check for Windows-specific issues
    if sys.platform == "win32":
        issues.append("""
  Windows-Specific:
  • Install Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe
  • Ensure CUDA_PATH environment variable is set
  • Restart your terminal after installing CUDA
""")

    if issues:
        print("\n".join(issues))
    else:
        print("  ✓ All CUDA components are properly configured!")

    print("\n  Quick fixes to try:")
    print("  1. Restart your terminal/computer")
    print("  2. Verify NVIDIA drivers: nvidia-smi")
    print('  3. Check PyTorch CUDA: python -c "import torch; print(torch.cuda.is_available())"')


def main():
    print_header("CUDA Diagnostic Report for Transcripta")
    print(f"  Platform: {sys.platform}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Executable: {sys.executable}")

    # Run all checks
    pytorch_ok, pytorch_cuda_ver = check_pytorch_cuda()
    ct2_ok = check_ctranslate2_cuda()
    fw_ok = check_faster_whisper()
    check_environment_variables()
    check_nvidia_smi()
    check_cuda_installation()

    # Summary
    print_header("Summary")
    print_result(
        "PyTorch CUDA", "Working" if pytorch_ok else "Not working", "ok" if pytorch_ok else "error"
    )
    print_result(
        "CTRANSLATE2 CUDA", "Working" if ct2_ok else "Not working", "ok" if ct2_ok else "error"
    )
    print_result(
        "Faster-Whisper", "Installed" if fw_ok else "Not installed", "ok" if fw_ok else "warn"
    )

    if pytorch_ok and ct2_ok:
        print("\n  🎉 CUDA is properly configured for Transcripta!")
    else:
        print("\n  ⚠️  CUDA configuration has issues. See recommendations above.")

    # Recommendations
    print_recommendations(pytorch_ok, ct2_ok, fw_ok)

    return 0 if (pytorch_ok and ct2_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
