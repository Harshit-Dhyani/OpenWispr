"""Model catalog and installation state management service.

This module provides ModelService for querying the model catalog,
installation status, and recommendations based on system capabilities:

Features:
- Model catalog with metadata (name, size, category, runtime requirements)
- Installation state detection (installed, verified, size)
- System-aware recommendations (GPU VRAM -> appropriate models)
- Fallback selection when preferred model unavailable

Model Categories:
- asr: Automatic Speech Recognition models (Whisper variants)
- refiner: LLM models for transcript refinement
- coach: LLM models for English coaching

Recommendations Logic:
- No GPU: whisper-small, whisper-medium, qwen2.5-3b-instruct
- VRAM >= 10GB: whisper-large-v3, whisper-medium, qwen2.5-7b-instruct
- VRAM >= 5GB: whisper-medium, whisper-small, qwen2.5-3b-instruct
- VRAM < 5GB: whisper-small, whisper-medium, qwen2.5-3b-instruct, phi-3-mini

Edge Cases:
- Missing model directory: marked as not installed
- Incomplete download: marked as not installed, not verified
- File too small (< min_size_bytes): marked as not verified
- No GPU available: recommends CPU-compatible models
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.model_catalog import MODEL_CATALOG, ModelCatalogEntry, get_default_model_id
from app.core.settings.manager import SettingsState
from app.core.profiling.system_profiler import SystemProfiler


@dataclass(slots=True)
class ModelInstallState:
    model_id: str
    installed: bool
    verified: bool
    install_path: str
    size_bytes: int
    last_checked_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "installed": self.installed,
            "verified": self.verified,
            "install_path": self.install_path,
            "size_bytes": self.size_bytes,
            "last_checked_at": self.last_checked_at,
        }


class ModelService:
    """Model catalog and installation state management service.

    Provides model catalog querying, installation state detection, and
    system-aware recommendations based on GPU VRAM.

    State ownership:
    - Stateless; re-scans installation state on each query
    - SystemProfiler for hardware capability detection

    Key operations:
    - get_installed_state: scans model directories for installation
    - get_recommendations: returns models appropriate for system capabilities
    - resolve_fallback_selection: finds first available model in category
    """

    def __init__(self, models_root: Path) -> None:
        self.models_root = models_root
        self._profiler = SystemProfiler(download_root=models_root)

    def get_catalog_payload(self, settings: SettingsState) -> dict[str, Any]:
        installed = self.get_installed_state()
        recommendations = self.get_recommendations()
        installed_map = {entry["model_id"]: entry for entry in installed}
        catalog = []
        for entry in MODEL_CATALOG:
            item = entry.to_dict()
            item["recommended"] = entry.id in recommendations
            item["installed"] = installed_map.get(entry.id, {}).get("installed", False)
            item["verified"] = installed_map.get(entry.id, {}).get("verified", False)
            catalog.append(item)

        return {
            "catalog": catalog,
            "installed": installed,
            "selected_asr_model_id": settings.transcription.default_asr_model_id,
            "selected_refiner_model_id": settings.refiner.selected_model_id,
            "refinement_mode": settings.transcription.refinement_mode,
            "recommendations": recommendations,
        }

    def get_installed_state(self) -> list[dict[str, Any]]:
        return [self._install_state(entry).to_dict() for entry in MODEL_CATALOG]

    def get_recommendations(self) -> list[str]:
        profile = self._profiler.profile_system()
        recommendations: list[str] = []
        if not profile.gpu.available:
            recommendations.extend(["whisper-small", "whisper-medium", "qwen2.5-3b-instruct"])
        elif profile.gpu.vram_gb >= 10:
            recommendations.extend(
                ["whisper-large-v3", "whisper-medium", "qwen2.5-7b-instruct", "qwen2.5-3b-instruct"]
            )
        elif profile.gpu.vram_gb >= 5:
            recommendations.extend(["whisper-medium", "whisper-small", "qwen2.5-3b-instruct"])
        else:
            recommendations.extend(
                ["whisper-small", "whisper-medium", "qwen2.5-3b-instruct", "phi-3-mini-4k-instruct"]
            )
        return recommendations

    def resolve_fallback_selection(self, category: str) -> str:
        for item in self.get_installed_state():
            entry = next(
                (
                    catalog_entry
                    for catalog_entry in MODEL_CATALOG
                    if catalog_entry.id == item["model_id"]
                ),
                None,
            )
            if entry and entry.category == category and item["installed"] and entry.enabled_runtime:
                return entry.id
        return get_default_model_id("asr" if category == "asr" else "refiner")

    def _install_state(self, entry: ModelCatalogEntry) -> ModelInstallState:
        install_dir = self.models_root / entry.category / entry.id
        size_bytes = 0
        verified = False
        installed = install_dir.exists()
        if installed:
            for artifact in entry.download_artifacts:
                file_path = install_dir / artifact.filename
                if not file_path.exists():
                    installed = False
                    verified = False
                    break
                artifact_size = file_path.stat().st_size
                size_bytes += artifact_size
                if artifact_size < artifact.min_size_bytes:
                    installed = False
                    verified = False
                    break
                verified = True
        timestamp = install_dir.stat().st_mtime if install_dir.exists() else 0.0
        return ModelInstallState(
            model_id=entry.id,
            installed=installed,
            verified=verified,
            install_path=str(install_dir),
            size_bytes=size_bytes,
            last_checked_at=timestamp,
        )
