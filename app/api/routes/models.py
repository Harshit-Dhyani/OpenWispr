"""Model management API endpoints.

Provides APIs for model discovery, download, preloading, and cache management
for Whisper transcription models and LLM refiner models.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_service
from app.api.route_utils import log_route
from app.api.schemas import ModelSelectionRequest, PreloadModelRequest, RefinementModeRequest
from app.api.services.backend_service import BackendService
from app.api.services.refiner_service import RefinerService, is_llama_cpp_available
from app.api.strings.en import API_STRINGS
from app.core.settings.config import AppSettings
from app.core.settings.manager import get_settings_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/refiner/status")
@log_route("GET", "/api/refiner/status")
def get_refiner_status() -> dict[str, Any]:
    """
    Get current refiner runtime status.

    Returns:
        dict: Contains runtime_enabled, import_available, selected_model_id, model_installed, available, and reason
    """
    settings = get_settings_manager().get_settings()
    selected_model_id = settings.refiner.selected_model_id
    runtime_enabled = settings.refiner.runtime_enabled

    import_available = is_llama_cpp_available()
    refiner = RefinerService(AppSettings().download_root)
    model_installed = bool(selected_model_id and refiner.is_available(selected_model_id))

    reason = None
    if not runtime_enabled:
        reason = "runtime_disabled"
    elif not import_available:
        reason = "llama_cpp_missing"
    elif not selected_model_id:
        reason = "no_model_selected"
    elif not model_installed:
        reason = "model_not_installed"

    return {
        "runtime_enabled": runtime_enabled,
        "import_available": import_available,
        "selected_model_id": selected_model_id,
        "model_installed": model_installed,
        "available": runtime_enabled and import_available and model_installed,
        "reason": reason,
    }


@router.post("/api/models/preload")
@log_route("POST", "/api/models/preload")
def preload_model(
    request: PreloadModelRequest,
    svc: BackendService = Depends(get_service),
) -> dict[str, Any]:
    """
    Preload a model into memory.

    Args:
        request: PreloadModelRequest containing model_name and execution_mode

    Returns:
        dict: Contains preload result status

    Raises:
        HTTPException: 400 if preload fails, 500 on internal error
    """
    start_time = time.perf_counter()
    logger.debug(
        "Preload model: model_name=%s, execution_mode=%s",
        request.model_name,
        request.execution_mode,
    )
    try:
        result = svc.preload_model(
            model_name=request.model_name,
            execution_mode=request.execution_mode,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to preload model: %s", request.model_name)
        raise HTTPException(status_code=500, detail="Failed to preload model") from exc
    logger.debug(
        "Preload model complete: model_name=%s, status=%s, time=%.2fms",
        request.model_name,
        result.get("status", "unknown"),
        (time.perf_counter() - start_time) * 1000,
    )
    return result


@router.get("/api/models/cache")
@log_route("GET", "/api/models/cache")
def get_model_cache(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    """
    Get currently cached models.

    Returns:
        dict: Contains cached_models and available_models
    """
    snapshot = svc.get_snapshot()
    cached_models = getattr(snapshot, "model_cache", {})
    return {
        "cached_models": cached_models,
        "available_models": snapshot.available_models,
    }


@router.delete("/api/models/cache")
@log_route("DELETE", "/api/models/cache")
def clear_model_cache(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    """
    Clear all cached models from memory.

    Returns:
        dict: Contains cache clear result
    """
    return svc.clear_model_cache()


@router.get("/api/models/catalog")
@log_route("GET", "/api/models/catalog")
def get_model_catalog(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    """
    Get available models catalog.

    Returns:
        dict: Contains available model catalog
    """
    return svc.get_model_catalog_payload()


@router.get("/api/models/state")
@log_route("GET", "/api/models/state")
def get_model_state(svc: BackendService = Depends(get_service)) -> dict[str, Any]:
    """
    Get installed model state.

    Returns:
        dict: Contains installed model information
    """
    return {"installed": svc.get_model_install_state()}


@router.post("/api/models/select")
@log_route("POST", "/api/models/select")
def select_model(request: ModelSelectionRequest) -> dict[str, Any]:
    """
    Select a model for transcription or refinement.

    Args:
        request: ModelSelectionRequest containing category ('asr' or 'refiner') and model_id

    Returns:
        dict: Contains ok status and selected model IDs

    Raises:
        HTTPException: 400 if category is invalid
    """
    manager = get_settings_manager()
    settings = manager.get_settings()

    if request.category == "asr":
        settings.transcription.default_asr_model_id = request.model_id
    elif request.category == "refiner":
        settings.refiner.selected_model_id = request.model_id
    else:
        raise HTTPException(status_code=400, detail=API_STRINGS.errors.unknown_model_category)

    manager.update_settings(settings)
    return {
        "ok": True,
        "selected_asr_model_id": settings.transcription.default_asr_model_id,
        "selected_refiner_model_id": settings.refiner.selected_model_id,
    }


@router.post("/api/models/refinement-mode")
@log_route("POST", "/api/models/refinement-mode")
def set_refinement_mode(request: RefinementModeRequest) -> dict[str, Any]:
    """
    Set transcript refinement mode.

    Args:
        request: RefinementModeRequest containing mode ('off', 'strict', or 'polished')

    Returns:
        dict: Contains ok status and current refinement_mode

    Raises:
        HTTPException: 400 if mode is unsupported
    """
    if request.mode not in {"off", "strict", "polished"}:
        raise HTTPException(status_code=400, detail=API_STRINGS.errors.unsupported_refinement_mode)
    manager = get_settings_manager()
    settings = manager.get_settings()
    settings.transcription.refinement_mode = request.mode
    manager.update_settings(settings)
    return {"ok": True, "refinement_mode": settings.transcription.refinement_mode}
