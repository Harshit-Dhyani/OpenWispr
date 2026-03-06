from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

import app.api.deps as api_deps
from app.api.deps import get_service
from app.api.route_utils import log_route
from app.api.service import BackendService
from app.core.auto_optimizer import AutoOptimizer, get_recommended_settings
from app.core.system_profiler import SystemProfiler

router = APIRouter()


@router.get("/api/health")
@log_route("GET", "/api/health")
def health(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    snapshot = svc.get_snapshot()
    hotkey_status_data = None
    if api_deps.hotkey_service is not None:
        hs = api_deps.hotkey_service.get_status()
        hotkey_status_data = {
            "is_recording": hs.is_recording,
            "session_id": hs.session_id,
            "duration_ms": hs.duration_ms,
        }

    health_dict = snapshot.health
    if isinstance(health_dict, dict) and "estimated_backlog_seconds" not in health_dict:
        health_dict["estimated_backlog_seconds"] = 0.0

    return {
        "ok": True,
        "health": health_dict,
        "meter_value": snapshot.meter_value,
        "model_cache": getattr(snapshot, "model_cache", {}),
        "hotkey": hotkey_status_data,
    }


@router.get("/api/devices")
@log_route("GET", "/api/devices")
def devices(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    return {"devices": svc.list_devices()}


@router.get("/api/devices/{device_id}/probe")
@log_route("GET", "/api/devices/{device_id}/probe")
def probe_device_endpoint(
    device_id: str,
    duration: float = 3.0,
    svc: BackendService = Depends(get_service),
) -> dict[str, Any]:
    actual_device_id = device_id if device_id != "default" else None
    return svc.probe_device(actual_device_id, duration=duration)


@router.get("/api/system/profile")
def get_system_profile() -> dict[str, Any]:
    profiler = SystemProfiler()
    return profiler.get_summary()


@router.get("/api/system/optimize")
def get_optimized_settings(
    mode: str = Query(
        "balanced", description="Optimization mode: maximum, balanced, speed, low_memory"
    ),
    hotkey: bool = Query(False, description="Optimize for hotkey/push-to-talk mode"),
) -> dict[str, Any]:
    settings = get_recommended_settings(mode=mode, hotkey=hotkey)
    return {
        "settings": {
            "model_name": settings.model_name,
            "compute_type": settings.compute_type,
            "chunk_duration": settings.chunk_duration,
            "overlap_ratio": settings.overlap_ratio,
            "vad_enabled": settings.vad_enabled,
            "vad_threshold_db": settings.vad_threshold_db,
            "confidence_threshold": settings.confidence_threshold,
            "enable_filler_filter": settings.enable_filler_filter,
            "enable_hallucination_filter": settings.enable_hallucination_filter,
            "min_segment_length": settings.min_segment_length,
            "max_workers": settings.max_workers,
            "use_parallel_processing": settings.use_parallel_processing,
            "preload_model": settings.preload_model,
            "hotkey_optimized": settings.hotkey_optimized,
        },
        "metadata": {
            "quality_level": settings.quality_level,
            "optimization_reason": settings.optimization_reason,
            "estimated_vram_usage_gb": settings.estimated_vram_usage_gb,
            "estimated_latency_ms": settings.estimated_latency_ms,
        },
        "mode": mode,
        "hotkey_mode": hotkey,
    }


@router.get("/api/system/presets")
def get_preset_settings() -> dict[str, Any]:
    optimizer = AutoOptimizer()
    presets: dict[str, Any] = {}
    for preset_name in [
        "maximum_quality",
        "balanced",
        "maximum_speed",
        "low_memory",
        "hotkey_mode",
    ]:
        settings = optimizer.get_preset_settings(preset_name)
        presets[preset_name] = {
            "model_name": settings.model_name,
            "compute_type": settings.compute_type,
            "chunk_duration": settings.chunk_duration,
            "confidence_threshold": settings.confidence_threshold,
            "estimated_vram_usage_gb": settings.estimated_vram_usage_gb,
            "estimated_latency_ms": settings.estimated_latency_ms,
            "optimization_reason": settings.optimization_reason,
        }
    return {"presets": presets}
