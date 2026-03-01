"""System hardware detection and profiling for auto-optimization.

Detects GPU, CPU, RAM, and storage capabilities to recommend optimal settings.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency in some dev/test envs
    psutil = None


@dataclass
class GPUProfile:
    """GPU hardware profile."""

    available: bool
    name: str
    vram_gb: float
    compute_capability: tuple[int, int]
    cuda_available: bool
    device_count: int

    # Derived properties
    @property
    def can_run_large_models(self) -> bool:
        return self.vram_gb >= 10.0 and self.cuda_available

    @property
    def can_run_medium_models(self) -> bool:
        return self.vram_gb >= 5.0 and self.cuda_available

    @property
    def can_run_small_models(self) -> bool:
        return self.vram_gb >= 2.0 and self.cuda_available


@dataclass
class CPUProfile:
    """CPU hardware profile."""

    physical_cores: int
    logical_cores: int
    ram_gb: float
    architecture: str
    supports_avx2: bool

    @property
    def can_run_parallel(self) -> bool:
        return self.logical_cores >= 4

    @property
    def recommended_workers(self) -> int:
        return max(2, min(4, self.logical_cores // 2))


@dataclass
class StorageProfile:
    """Storage hardware profile."""

    total_gb: float
    free_gb: float
    download_path: Path
    is_ssd: bool

    @property
    def can_download_large_models(self) -> bool:
        return self.free_gb >= 15.0  # 3GB model + buffer

    @property
    def can_download_medium_models(self) -> bool:
        return self.free_gb >= 8.0  # 1.5GB model + buffer


@dataclass
class SystemProfile:
    """Complete system hardware profile."""

    gpu: GPUProfile
    cpu: CPUProfile
    storage: StorageProfile
    os_name: str

    @property
    def recommended_quality_level(self) -> str:
        """Return quality level: 'maximum', 'high', 'balanced', 'low'"""
        if self.gpu.can_run_large_models:
            return "maximum"
        elif self.gpu.can_run_medium_models or self.cpu.ram_gb >= 16:
            return "high"
        elif self.gpu.can_run_small_models or self.cpu.ram_gb >= 8:
            return "balanced"
        else:
            return "low"


class SystemProfiler:
    """Detects and profiles system hardware capabilities."""

    def __init__(self, download_root: Path = Path("models")):
        self.download_root = download_root
        self._cached_profile: Optional[SystemProfile] = None

    def profile_system(self) -> SystemProfile:
        """Profile complete system hardware."""
        if self._cached_profile is not None:
            return self._cached_profile

        gpu = self._profile_gpu()
        cpu = self._profile_cpu()
        storage = self._profile_storage()

        self._cached_profile = SystemProfile(
            gpu=gpu, cpu=cpu, storage=storage, os_name=platform.system()
        )

        return self._cached_profile

    def _profile_gpu(self) -> GPUProfile:
        """Detect GPU capabilities."""
        try:
            import torch

            if not torch.cuda.is_available():
                return GPUProfile(
                    available=False,
                    name="No GPU",
                    vram_gb=0.0,
                    compute_capability=(0, 0),
                    cuda_available=False,
                    device_count=0,
                )

            device_props = torch.cuda.get_device_properties(0)
            vram_gb = device_props.total_memory / (1024**3)

            # Compute capability (e.g., 8.6 for RTX 30 series)
            major = device_props.major
            minor = device_props.minor

            return GPUProfile(
                available=True,
                name=torch.cuda.get_device_name(0),
                vram_gb=vram_gb,
                compute_capability=(major, minor),
                cuda_available=True,
                device_count=torch.cuda.device_count(),
            )
        except Exception:
            return GPUProfile(
                available=False,
                name="No GPU",
                vram_gb=0.0,
                compute_capability=(0, 0),
                cuda_available=False,
                device_count=0,
            )

    def _profile_cpu(self) -> CPUProfile:
        """Detect CPU capabilities."""
        ram_bytes = self._virtual_memory_total()
        ram_gb = ram_bytes / (1024**3)

        # Check AVX2 support (simplified check)
        supports_avx2 = False
        try:
            import cpuinfo

            info = cpuinfo.get_cpu_info()
            flags = info.get("flags", [])
            supports_avx2 = "avx2" in flags
        except Exception:
            pass  # cpuinfo might not be available

        return CPUProfile(
            physical_cores=self._cpu_count(logical=False) or 2,
            logical_cores=self._cpu_count(logical=True) or 2,
            ram_gb=ram_gb,
            architecture=platform.machine(),
            supports_avx2=supports_avx2,
        )

    def _profile_storage(self) -> StorageProfile:
        """Detect storage capabilities."""
        resolved_path = self.download_root.resolve()
        total_bytes, free_bytes = self._disk_usage(resolved_path)
        total_gb = total_bytes / (1024**3)
        free_gb = free_bytes / (1024**3)

        # Simple SSD detection (not 100% accurate but good enough)
        is_ssd = False
        try:
            if platform.system() == "Windows":
                import ctypes
                from ctypes import wintypes

                # Could add actual SSD detection here
                is_ssd = True  # Assume SSD for modern systems
        except Exception:
            pass

        return StorageProfile(
            total_gb=total_gb, free_gb=free_gb, download_path=self.download_root, is_ssd=is_ssd
        )

    @staticmethod
    def _cpu_count(*, logical: bool) -> int:
        if psutil is not None:
            return psutil.cpu_count(logical=logical) or 0

        try:
            import os

            count = os.cpu_count() or 0
            if logical:
                return count
            return max(1, count // 2)
        except Exception:
            return 0

    @staticmethod
    def _virtual_memory_total() -> int:
        if psutil is not None:
            return int(psutil.virtual_memory().total)

        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        except Exception:
            pass

        return 8 * 1024**3

    @staticmethod
    def _disk_usage(path: Path) -> tuple[int, int]:
        if psutil is not None:
            usage = psutil.disk_usage(path)
            return int(usage.total), int(usage.free)

        try:
            import shutil

            usage = shutil.disk_usage(path)
            return int(usage.total), int(usage.free)
        except Exception:
            fallback = 100 * 1024**3
            return fallback, fallback // 2

    def get_summary(self) -> dict:
        """Get human-readable summary of system profile."""
        profile = self.profile_system()

        return {
            "gpu": {
                "available": profile.gpu.available,
                "name": profile.gpu.name,
                "vram_gb": round(profile.gpu.vram_gb, 1),
                "can_run_large": profile.gpu.can_run_large_models,
                "can_run_medium": profile.gpu.can_run_medium_models,
            },
            "cpu": {
                "cores": profile.cpu.logical_cores,
                "ram_gb": round(profile.cpu.ram_gb, 1),
                "can_parallel": profile.cpu.can_run_parallel,
            },
            "storage": {
                "free_gb": round(profile.storage.free_gb, 1),
                "can_download_large": profile.storage.can_download_large_models,
            },
            "recommended_quality": profile.recommended_quality_level,
        }
