"""Model pool for managing multiple Whisper model instances.

Provides thread-safe access to multiple model instances with:
- GPU memory estimation and tracking
- Automatic model lifecycle management
- Warmup at startup
- CPU fallback on GPU OOM
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

# Lazy load numpy and faster-whisper to speed up import time
import numpy as np

logger = logging.getLogger(__name__)

# Lazy load torch only when needed
torch = None
HAS_TORCH = False


def _ensure_torch():
    """Lazy load torch on first use."""
    global torch, HAS_TORCH
    if not HAS_TORCH:
        try:
            import torch
            import torch.cuda

            HAS_TORCH = True
        except ImportError:
            torch = None
            HAS_TORCH = False


# Lazy load faster-whisper only when needed
_WhisperModel = None


def _get_whisper_model():
    """Lazy load WhisperModel on first use."""
    global _WhisperModel
    if _WhisperModel is None:
        from faster_whisper import WhisperModel

        _WhisperModel = WhisperModel
    return _WhisperModel


@dataclass(slots=True)
class ModelInstance:
    """A managed model instance with metadata."""

    model: Any  # WhisperModel - lazy loaded
    model_name: str
    device: str
    compute_type: str
    created_at: float
    last_access: float
    access_count: int = 0
    warmup_complete: bool = False
    load_time_ms: float = 0.0


@dataclass
class ModelSlot:
    """A slot holding a reference to a pooled model."""

    model: Any  # WhisperModel - lazy loaded
    model_name: str
    device: str
    compute_type: str
    key: str


@dataclass(slots=True)
class GPUMemoryPool:
    """Manages GPU memory allocation for models."""

    total_gb: float = 0.0
    reserved_gb: float = 0.0
    allocated_gb: float = 0.0
    max_models: int = 2
    _model_memory: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_torch()
        if HAS_TORCH and torch and torch.cuda.is_available():
            self._update_stats()

    def _update_stats(self) -> None:
        """Update GPU memory statistics."""
        if not HAS_TORCH or not torch.cuda.is_available():
            return

        props = torch.cuda.get_device_properties(0)
        self.total_gb = props.total_memory / (1024**3)
        self.reserved_gb = torch.cuda.memory_reserved(0) / (1024**3)
        self.allocated_gb = torch.cuda.memory_allocated(0) / (1024**3)

    def can_fit_model(self, model_name: str, compute_type: str) -> bool:
        """Check if another model can fit in GPU memory."""
        if not HAS_TORCH or not torch.cuda.is_available():
            return False

        self._update_stats()

        required_gb = self._estimate_model_memory(model_name, compute_type)
        available_gb = self.total_gb - self.reserved_gb

        # Leave 20% headroom
        return available_gb >= required_gb * 1.2

    def _estimate_model_memory(self, model_name: str, compute_type: str) -> float:
        """Estimate memory required for a model."""
        base_memory = {
            "tiny": 0.4,
            "base": 0.5,
            "small": 1.0,
            "medium": 3.0,
            "large-v1": 4.5,
            "large-v2": 4.5,
            "large-v3": 5.0,
            "large-v3-turbo": 3.5,
        }.get(model_name, 2.0)

        multiplier = {
            "int8": 0.6,
            "float16": 1.0,
            "float32": 2.0,
        }.get(compute_type, 1.0)

        return base_memory * multiplier

    def reserve_memory(self, model_name: str, compute_type: str) -> bool:
        """Reserve memory for a model."""
        if not self.can_fit_model(model_name, compute_type):
            return False

        key = f"{model_name}:{compute_type}"
        self._model_memory[key] = self._estimate_model_memory(model_name, compute_type)
        return True

    def release_memory(self, model_name: str, compute_type: str) -> None:
        """Release reserved memory."""
        key = f"{model_name}:{compute_type}"
        if key in self._model_memory:
            del self._model_memory[key]


@dataclass(slots=True)
class PoolMetrics:
    """Metrics for the model pool."""

    total_models: int = 0
    gpu_models: int = 0
    cpu_models: int = 0
    total_accesses: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    load_failures: int = 0
    warmup_failures: int = 0
    gpu_fallbacks: int = 0
    evictions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_models": self.total_models,
            "gpu_models": self.gpu_models,
            "cpu_models": self.cpu_models,
            "total_accesses": self.total_accesses,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "load_failures": self.load_failures,
            "warmup_failures": self.warmup_failures,
            "gpu_fallbacks": self.gpu_fallbacks,
            "evictions": self.evictions,
        }


class ModelPool:
    """Thread-safe pool for managing multiple Whisper model instances."""

    _instance: ModelPool | None = None
    _lock = threading.Lock()

    def __new__(cls) -> ModelPool:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    # Model TTL in seconds (30 minutes)
    MODEL_TTL_SECONDS = 1800

    def __init__(
        self,
        max_models: int = 3,
        enable_gpu_pool: bool = True,
        warmup_on_load: bool = True,
    ) -> None:
        if self._initialized:
            return

        self._initialized = True
        self.max_models = max_models
        self.enable_gpu_pool = enable_gpu_pool
        self.warmup_on_load = warmup_on_load

        # Storage
        self._models: dict[str, ModelInstance] = {}
        self._model_locks: dict[str, threading.Lock] = {}
        self._access_queue: deque[str] = deque(maxlen=max_models)

        # Threading
        self._pool_lock = threading.RLock()

        # GPU memory management
        self._gpu_pool = GPUMemoryPool() if enable_gpu_pool else None

        # Metrics
        self._metrics = PoolMetrics()

        # Configuration
        self._download_root: str = "./models"

        # Model loading defaults
        self._max_retries = 3
        self._retry_delay_base = 0.5

    def configure(
        self,
        download_root: str | None = None,
        max_models: int | None = None,
        warmup_on_load: bool | None = None,
    ) -> None:
        """Configure the model pool."""
        with self._pool_lock:
            if download_root is not None:
                self._download_root = download_root
            if max_models is not None:
                self.max_models = max_models
                self._access_queue = deque(maxlen=max_models)
            if warmup_on_load is not None:
                self.warmup_on_load = warmup_on_load

    def acquire(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        download_root: str | None = None,
        warmup: bool | None = None,
    ) -> ModelSlot:
        """Acquire a model slot from the pool."""
        model = self.get_model(
            model_name=model_name,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
            warmup=warmup,
        )
        return ModelSlot(
            model=model,
            model_name=model_name,
            device=device,
            compute_type=compute_type,
            key=f"{model_name}:{device}:{compute_type}",
        )

    def release(self, slot: ModelSlot) -> None:
        """Release a model slot back to the pool."""
        if slot.key:
            self.release_model(slot.key)

    def get_model(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        download_root: str | None = None,
        warmup: bool | None = None,
    ) -> Any:  # WhisperModel - lazy loaded
        """Get or create a cached model with automatic GPU/CPU selection."""
        cache_key = f"{model_name}:{device}:{compute_type}"
        download_root = download_root or self._download_root
        should_warmup = warmup if warmup is not None else self.warmup_on_load

        with self._pool_lock:
            self._metrics.total_accesses += 1

            # Fast path: cached model exists
            if cache_key in self._models:
                instance = self._models[cache_key]
                instance.last_access = time.time()
                instance.access_count += 1
                self._metrics.cache_hits += 1

                # Update access queue (LRU tracking)
                if cache_key in self._access_queue:
                    self._access_queue.remove(cache_key)
                self._access_queue.append(cache_key)

                logger.info(
                    "Model cache hit: model=%s device=%s compute_type=%s cache_key=%s",
                    model_name,
                    device,
                    compute_type,
                    cache_key,
                )
                return instance.model

            self._metrics.cache_misses += 1

        # Slow path: create model
        logger.info(
            "Model load start: model=%s device=%s compute_type=%s cache_key=%s warmup=%s",
            model_name,
            device,
            compute_type,
            cache_key,
            should_warmup,
        )
        return self._create_model(
            cache_key=cache_key,
            model_name=model_name,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
            warmup=should_warmup,
        )

    def _create_model(
        self,
        cache_key: str,
        model_name: str,
        device: str,
        compute_type: str,
        download_root: str,
        warmup: bool,
    ) -> Any:  # WhisperModel - lazy loaded
        """Create a new model instance with retry and fallback logic."""

        # Per-key lock to prevent duplicate loads
        with self._pool_lock:
            if cache_key not in self._model_locks:
                self._model_locks[cache_key] = threading.Lock()

        with self._model_locks[cache_key]:
            # Double-check after acquiring lock
            with self._pool_lock:
                if cache_key in self._models:
                    return self._models[cache_key].model

            # Clean up old models if at capacity
            self._maybe_evict_oldest()

            # Try GPU if requested
            if device == "cuda" and self.enable_gpu_pool:
                if self._gpu_pool and not self._gpu_pool.can_fit_model(model_name, compute_type):
                    logger.warning(f"Insufficient GPU memory for {model_name}, trying CPU")
                    device = "cpu"
                    compute_type = "int8"
                    self._metrics.gpu_fallbacks += 1

            # Load model with retries
            model = None
            load_time_ms = 0.0
            last_error: Exception | None = None

            for attempt in range(self._max_retries):
                try:
                    load_start = time.perf_counter()
                    WhisperModel = _get_whisper_model()
                    model = WhisperModel(
                        model_name,
                        device=device,
                        compute_type=compute_type,
                        download_root=download_root,
                    )
                    load_time_ms = (time.perf_counter() - load_start) * 1000

                    logger.info(
                        f"Model loaded: {model_name} on {device} ({compute_type}) "
                        f"in {load_time_ms:.1f}ms"
                    )
                    break

                except RuntimeError as e:
                    last_error = e
                    error_text = str(e).lower()

                    # Handle GPU OOM - fallback to CPU
                    if "out of memory" in error_text or "cuda" in error_text:
                        if device == "cuda":
                            logger.warning(f"GPU OOM loading {model_name}, falling back to CPU")
                            device = "cpu"
                            compute_type = "int8"
                            self._metrics.gpu_fallbacks += 1

                            # Clear GPU cache
                            _ensure_torch()
                            if HAS_TORCH and torch and torch.cuda.is_available():
                                torch.cuda.empty_cache()
                                torch.cuda.synchronize()
                            continue

                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay_base * (2**attempt)
                        logger.warning(
                            f"Model load attempt {attempt + 1} failed, retrying in {delay:.1f}s: {e}"
                        )
                        time.sleep(delay)
                    else:
                        self._metrics.load_failures += 1
                        raise RuntimeError(
                            f"Failed to load model {model_name} after {self._max_retries} attempts: {last_error}"
                        ) from last_error

            if model is None:
                self._metrics.load_failures += 1
                raise RuntimeError(f"Failed to load model {model_name}")

            # Warm up model
            warmup_ok = False
            if warmup:
                warmup_ok = self._warmup_model(model, model_name)
                if not warmup_ok:
                    self._metrics.warmup_failures += 1

            # Store model
            with self._pool_lock:
                instance = ModelInstance(
                    model=model,
                    model_name=model_name,
                    device=device,
                    compute_type=compute_type,
                    created_at=time.time(),
                    last_access=time.time(),
                    access_count=1,
                    warmup_complete=warmup_ok,
                    load_time_ms=load_time_ms,
                )
                self._models[cache_key] = instance
                self._access_queue.append(cache_key)
                self._update_metrics()

                # Reserve GPU memory
                if device == "cuda" and self._gpu_pool:
                    self._gpu_pool.reserve_memory(model_name, compute_type)

            return model

    def _warmup_model(self, model: WhisperModel, model_name: str) -> bool:
        """Warm up a model with dummy inference."""
        try:
            # Use appropriate warmup audio length based on model size
            warmup_duration = {
                "tiny": 16000,
                "base": 16000,
                "small": 16000,
                "medium": 16000,
                "large-v1": 32000,
                "large-v2": 32000,
                "large-v3": 32000,
                "large-v3-turbo": 16000,
            }.get(model_name, 16000)

            dummy = np.zeros(warmup_duration, dtype=np.float32)
            segments, _ = model.transcribe(dummy, beam_size=1, temperature=0.0)
            list(segments)  # Consume generator

            logger.debug(f"Model warmup complete: {model_name}")
            return True
        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")
            return False

    def _maybe_evict_oldest(self) -> None:
        """Evict oldest model if at capacity."""
        with self._pool_lock:
            while len(self._models) >= self.max_models and self._access_queue:
                oldest_key = self._access_queue.popleft()
                if oldest_key in self._models:
                    self._evict_model(oldest_key)

    def _evict_model(self, cache_key: str) -> None:
        """Evict a model from the pool."""
        if cache_key not in self._models:
            return

        instance = self._models[cache_key]
        logger.info(f"Evicting model: {cache_key}")

        # Release GPU memory
        if instance.device == "cuda" and self._gpu_pool:
            self._gpu_pool.release_memory(instance.model_name, instance.compute_type)

        del self._models[cache_key]
        if cache_key in self._model_locks:
            del self._model_locks[cache_key]

        self._metrics.evictions += 1

    def release_model(self, cache_key: str) -> None:
        """Release a model from the pool."""
        with self._pool_lock:
            self._evict_model(cache_key)

    def cleanup_expired(self, max_age_seconds: float | None = None) -> int:
        """Remove models that haven't been accessed recently."""
        max_age = max_age_seconds or self.MODEL_TTL_SECONDS
        now = time.time()
        expired = []

        with self._pool_lock:
            for key, instance in self._models.items():
                if now - instance.last_access > max_age:
                    expired.append(key)

        for key in expired:
            self.release_model(key)
            logger.debug(f"Expired model removed: {key}")

        return len(expired)

    def warmup_all(self) -> dict[str, bool]:
        """Warm up all models in the pool."""
        results = {}

        with self._pool_lock:
            instances = list(self._models.items())

        for key, instance in instances:
            if not instance.warmup_complete:
                success = self._warmup_model(instance.model, instance.model_name)
                with self._pool_lock:
                    if key in self._models:
                        self._models[key].warmup_complete = success
                results[key] = success
            else:
                results[key] = True

        return results

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        with self._pool_lock:
            self._update_metrics()
            return {
                "metrics": self._metrics.to_dict(),
                "models": {
                    key: {
                        "model_name": inst.model_name,
                        "device": inst.device,
                        "compute_type": inst.compute_type,
                        "access_count": inst.access_count,
                        "warmup_complete": inst.warmup_complete,
                        "load_time_ms": round(inst.load_time_ms, 2),
                        "age_seconds": round(time.time() - inst.created_at, 1),
                        "idle_seconds": round(time.time() - inst.last_access, 1),
                    }
                    for key, inst in self._models.items()
                },
                "gpu_memory": {
                    "total_gb": round(self._gpu_pool.total_gb, 2) if self._gpu_pool else 0,
                    "reserved_gb": round(self._gpu_pool.reserved_gb, 2) if self._gpu_pool else 0,
                    "allocated_gb": round(self._gpu_pool.allocated_gb, 2) if self._gpu_pool else 0,
                }
                if self._gpu_pool and HAS_TORCH and torch.cuda.is_available()
                else None,
            }

    def _update_metrics(self) -> None:
        """Update internal metrics."""
        self._metrics.total_models = len(self._models)
        self._metrics.gpu_models = sum(1 for inst in self._models.values() if inst.device == "cuda")
        self._metrics.cpu_models = sum(1 for inst in self._models.values() if inst.device == "cpu")

    def clear(self) -> None:
        """Clear all models from the pool."""
        with self._pool_lock:
            # Release GPU memory
            if self._gpu_pool:
                for instance in self._models.values():
                    if instance.device == "cuda":
                        self._gpu_pool.release_memory(instance.model_name, instance.compute_type)

            self._models.clear()
            self._model_locks.clear()
            self._access_queue.clear()
            self._metrics = PoolMetrics()

            # Clear GPU cache
            _ensure_torch()
        if HAS_TORCH and torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

    def preload_models(
        self,
        configs: list[dict[str, Any]],
        download_root: str | None = None,
    ) -> dict[str, bool]:
        """Preload multiple models at startup.

        Args:
            configs: List of dicts with keys: model_name, device, compute_type
            download_root: Root directory for model downloads

        Returns:
            Dict mapping cache_key to success status
        """
        results = {}
        download_root = download_root or self._download_root

        for config in configs:
            cache_key = f"{config['model_name']}:{config['device']}:{config['compute_type']}"
            try:
                self.get_model(
                    model_name=config["model_name"],
                    device=config["device"],
                    compute_type=config["compute_type"],
                    download_root=download_root,
                    warmup=True,
                )
                results[cache_key] = True
            except Exception as e:
                logger.error(f"Failed to preload {cache_key}: {e}")
                results[cache_key] = False

        return results
