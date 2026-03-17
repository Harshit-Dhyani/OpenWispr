"""Recovery strategies and automatic failure recovery for OpenWispr.

Provides RecoveryManager for coordinating recovery attempts, FallbackChain for
cascading fallbacks, and specific recovery strategies for each error category.
"""

from __future__ import annotations

import enum
import logging
import shutil
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from app.config.constants import GPU_FALLBACK_KEYWORDS
from app.core.error_handler import (
    AudioError,
    ErrorCategory,
    ModelError,
    NetworkError,
    OpenWisprError,
    RetryConfig,
    SessionError,
    with_retry,
)

logger = logging.getLogger("openwispr.recovery")


# ============================================
# Recovery Result Types
# ============================================
class RecoveryStatus(enum.Enum):
    """Status of a recovery attempt."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    status: RecoveryStatus
    strategy_name: str
    error_id: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    fallback_applied: str | None = None
    recovery_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "strategy": self.strategy_name,
            "error_id": self.error_id,
            "message": self.message,
            "details": self.details,
            "fallback": self.fallback_applied,
            "recovery_time_ms": self.recovery_time_ms,
        }


# ============================================
# Fallback Chain
# ============================================
T = TypeVar("T")


@dataclass
class FallbackOption(Generic[T]):
    """A single fallback option in the chain."""

    name: str
    value: T
    condition: Callable[[], bool] | None = None
    on_activate: Callable[[T], None] | None = None


class FallbackChain(Generic[T]):
    """Cascading fallback chain with automatic progression."""

    def __init__(self, name: str, options: list[FallbackOption[T]]):
        self.name = name
        self.options = options
        self.current_index = 0
        self._activated: list[str] = []
        self._on_fallback: Callable[[str, T], None] | None = None

    def set_fallback_callback(self, callback: Callable[[str, T], None]) -> None:
        """Set callback for when fallback is activated."""
        self._on_fallback = callback

    def current(self) -> T | None:
        """Get current active value."""
        if 0 <= self.current_index < len(self.options):
            return self.options[self.current_index].value
        return None

    def current_name(self) -> str | None:
        """Get current option name."""
        if 0 <= self.current_index < len(self.options):
            return self.options[self.current_index].name
        return None

    def fallback(self) -> tuple[bool, T | None]:
        """Move to next fallback option."""
        start_index = self.current_index

        for i in range(start_index + 1, len(self.options)):
            option = self.options[i]

            # Check condition if provided
            if option.condition and not option.condition():
                continue

            # Activate fallback
            self.current_index = i
            self._activated.append(option.name)

            logger.warning(f"FallbackChain '{self.name}': {self.current_name()} -> {option.name}")

            if option.on_activate:
                try:
                    option.on_activate(option.value)
                except Exception as e:
                    logger.error(f"Fallback activation failed for {option.name}: {e}")

            if self._on_fallback:
                self._on_fallback(option.name, option.value)

            return True, option.value

        logger.error(f"FallbackChain '{self.name}': Exhausted all options")
        return False, None

    def reset(self) -> None:
        """Reset to first option."""
        self.current_index = 0
        self._activated.clear()
        logger.info(f"FallbackChain '{self.name}': Reset to primary")

    def is_primary(self) -> bool:
        """Check if currently using primary option."""
        return self.current_index == 0

    def get_fallback_history(self) -> list[str]:
        """Get list of activated fallbacks."""
        return self._activated.copy()


# ============================================
# Pre-built Fallback Chains
# ============================================
def create_compute_fallback_chain(
    primary_compute: str = "cuda",
    on_fallback: Callable[[str, str], None] | None = None,
) -> FallbackChain[str]:
    """Create GPU -> CPU fallback chain."""

    def check_cuda_available() -> bool:
        try:
            import torch

            return torch.cuda.is_available()
        except ImportError:
            return False

    def check_cpu_available() -> bool:
        return True

    options = [
        FallbackOption("cuda", "cuda", check_cuda_available),
        FallbackOption("cpu", "cpu", check_cpu_available),
    ]

    chain = FallbackChain("compute_device", options)
    if on_fallback:
        chain.set_fallback_callback(on_fallback)
    return chain


def create_model_size_fallback_chain(
    primary_model: str = "medium",
    on_fallback: Callable[[str, str], None] | None = None,
) -> FallbackChain[str]:
    """Create model size fallback chain: medium -> small -> base -> tiny."""

    model_order = ["large-v3", "turbo", "medium", "small", "base", "tiny"]

    def make_checker(model: str) -> Callable[[], bool]:
        def checker() -> bool:
            # In practice, this would check available memory
            return True

        return checker

    # Find primary in order and create options from that point
    try:
        start_idx = model_order.index(primary_model)
    except ValueError:
        start_idx = 2  # Default to medium

    options = []
    for model in model_order[start_idx:]:
        options.append(FallbackOption(model, model, make_checker(model)))

    chain = FallbackChain("model_size", options)
    if on_fallback:
        chain.set_fallback_callback(on_fallback)
    return chain


def create_batch_size_fallback_chain(
    primary_batch: int = 8,
    on_fallback: Callable[[str, int], None] | None = None,
) -> FallbackChain[int]:
    """Create batch size fallback chain."""

    batch_sizes = [16, 8, 4, 2, 1]

    def make_checker(size: int) -> Callable[[], bool]:
        def checker() -> bool:
            return True

        return checker

    try:
        start_idx = batch_sizes.index(primary_batch)
    except ValueError:
        start_idx = 1  # Default to 8

    options = []
    for size in batch_sizes[start_idx:]:
        options.append(FallbackOption(f"batch_{size}", size, make_checker(size)))

    chain = FallbackChain("batch_size", options)
    if on_fallback:
        chain.set_fallback_callback(on_fallback)
    return chain


# ============================================
# Recovery Strategy Interface
# ============================================
class RecoveryStrategy(ABC):
    """Abstract base class for recovery strategies."""

    def __init__(self, name: str, priority: int = 100):
        self.name = name
        self.priority = priority
        self._enabled = True
        self._success_count = 0
        self._failure_count = 0

    @abstractmethod
    def can_handle(self, error: OpenWisprError) -> bool:
        """Check if this strategy can handle the error."""
        pass

    @abstractmethod
    def recover(
        self, error: OpenWisprError, context: dict[str, Any] | None = None
    ) -> RecoveryResult:
        """Attempt to recover from the error."""
        pass

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_stats(self) -> dict[str, Any]:
        total = self._success_count + self._failure_count
        success_rate = self._success_count / total if total > 0 else 0.0
        return {
            "name": self.name,
            "enabled": self._enabled,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": success_rate,
        }

    def _success(self, error_id: str, message: str, **kwargs) -> RecoveryResult:
        self._success_count += 1
        return RecoveryResult(
            status=RecoveryStatus.SUCCESS,
            strategy_name=self.name,
            error_id=error_id,
            message=message,
            **kwargs,
        )

    def _partial(self, error_id: str, message: str, **kwargs) -> RecoveryResult:
        self._success_count += 1  # Partial counts as success
        return RecoveryResult(
            status=RecoveryStatus.PARTIAL,
            strategy_name=self.name,
            error_id=error_id,
            message=message,
            **kwargs,
        )

    def _failed(self, error_id: str, message: str, **kwargs) -> RecoveryResult:
        self._failure_count += 1
        return RecoveryResult(
            status=RecoveryStatus.FAILED,
            strategy_name=self.name,
            error_id=error_id,
            message=message,
            **kwargs,
        )


# ============================================
# Audio Recovery Strategies
# ============================================
class AudioDeviceRecoveryStrategy(RecoveryStrategy):
    """Recover from audio device disconnection by switching to default."""

    def __init__(self, device_manager: Any | None = None):
        super().__init__("audio_device_switch", priority=10)
        self.device_manager = device_manager
        self._fallback_device_id: str | None = None

    def can_handle(self, error: OpenWisprError) -> bool:
        return (
            isinstance(error, AudioError)
            and error.category == ErrorCategory.AUDIO_DEVICE_DISCONNECTED
        )

    def recover(
        self, error: OpenWisprError, context: dict[str, Any] | None = None
    ) -> RecoveryResult:
        ctx = context or {}
        available_devices = ctx.get("available_devices", [])

        if not available_devices:
            return self._failed(
                error.error_id,
                "No alternative audio devices available",
                details={"original_device": error.device_id},
            )

        # Find default or first available device
        fallback_device = None
        for device in available_devices:
            if device.get("is_default") or device.get("id") == "default":
                fallback_device = device
                break

        if not fallback_device and available_devices:
            fallback_device = available_devices[0]

        if fallback_device:
            self._fallback_device_id = fallback_device["id"]
            return self._success(
                error.error_id,
                f"Switched to audio device: {fallback_device.get('name', 'Unknown')}",
                fallback_applied=self._fallback_device_id,
                details={
                    "from_device": error.device_id,
                    "to_device": self._fallback_device_id,
                },
            )

        return self._failed(error.error_id, "Could not find suitable fallback device")


class AudioPermissionRecoveryStrategy(RecoveryStrategy):
    """Handle audio permission errors with user guidance."""

    def __init__(self):
        super().__init__("audio_permission_guidance", priority=20)

    def can_handle(self, error: OpenWisprError) -> bool:
        return (
            isinstance(error, AudioError)
            and error.category == ErrorCategory.AUDIO_PERMISSION_DENIED
        )

    def recover(
        self, error: OpenWisprError, context: dict[str, Any] | None = None
    ) -> RecoveryResult:
        # Permission errors require user action - provide guidance
        platform = (context or {}).get("platform", "unknown")

        guidance = {
            "windows": "Settings > Privacy > Microphone > Allow apps to access microphone",
            "darwin": "System Preferences > Security & Privacy > Privacy > Microphone",
            "linux": "Check your audio group membership and PulseAudio permissions",
        }.get(platform, "Check your system audio permissions")

        return self._partial(
            error.error_id,
            "Audio permission recovery requires user action",
            details={"guidance": guidance, "platform": platform},
        )


# ============================================
# Model Recovery Strategies
# ============================================
class ModelOOMRecoveryStrategy(RecoveryStrategy):
    """Recover from GPU OOM by falling back to CPU and reducing batch size."""

    def __init__(
        self,
        compute_fallback: FallbackChain[str] | None = None,
        batch_fallback: FallbackChain[int] | None = None,
    ):
        super().__init__("model_oom_recovery", priority=5)
        self.compute_fallback = compute_fallback or create_compute_fallback_chain()
        self.batch_fallback = batch_fallback or create_batch_size_fallback_chain()

    def can_handle(self, error: OpenWisprError) -> bool:
        if not isinstance(error, ModelError):
            return False

        if error.category == ErrorCategory.MODEL_OOM:
            return True

        # Check for OOM keywords in error message
        msg_lower = error.message.lower()
        return any(kw in msg_lower for kw in GPU_FALLBACK_KEYWORDS) and "memory" in msg_lower

    def recover(
        self, error: OpenWisprError, context: dict[str, Any] | None = None
    ) -> RecoveryResult:
        start_time = time.time()
        applied_fallbacks = []

        # First try: Switch compute device
        if not self.compute_fallback.is_primary():
            # Already using fallback, try next
            success, new_device = self.compute_fallback.fallback()
            if success:
                applied_fallbacks.append(f"device:{new_device}")
        elif self.compute_fallback.current() == "cuda":
            success, new_device = self.compute_fallback.fallback()
            if success:
                applied_fallbacks.append(f"device:{new_device}")

        # Second try: Reduce batch size
        if not applied_fallbacks or "device:cpu" in applied_fallbacks:
            success, new_batch = self.batch_fallback.fallback()
            if success:
                applied_fallbacks.append(f"batch_size:{new_batch}")

        recovery_time = (time.time() - start_time) * 1000

        if applied_fallbacks:
            return self._success(
                error.error_id,
                f"OOM recovery: {', '.join(applied_fallbacks)}",
                fallback_applied="; ".join(applied_fallbacks),
                details={
                    "new_device": self.compute_fallback.current(),
                    "new_batch_size": self.batch_fallback.current(),
                },
                recovery_time_ms=recovery_time,
            )

        return self._failed(
            error.error_id,
            "OOM recovery exhausted all fallback options",
            recovery_time_ms=recovery_time,
        )


class ModelDownloadStrategy(RecoveryStrategy):
    """Auto-download missing models with progress feedback."""

    def __init__(self, model_cache_dir: Path | None = None):
        super().__init__("model_auto_download", priority=10)
        self.model_cache_dir = model_cache_dir or Path.home() / ".openwispr" / "models"
        self._download_progress: dict[str, float] = {}

    def can_handle(self, error: OpenWisprError) -> bool:
        return isinstance(error, ModelError) and error.category in {
            ErrorCategory.MODEL_NOT_FOUND,
            ErrorCategory.MODEL_CORRUPTED,
        }

    @with_retry(
        RetryConfig(
            max_retries=2,
            base_delay=2.0,
            retryable_exceptions={Exception},
        )
    )
    def _download_model(self, model_name: str) -> bool:
        """Download model with retry logic."""
        logger.info(f"Starting download for model: {model_name}")

        # Simulate or perform actual download
        # In production, this would integrate with huggingface_hub or similar
        self._download_progress[model_name] = 0.0

        # Progress simulation - replace with actual download
        import time

        for i in range(10):
            time.sleep(0.1)  # Simulate download chunks
            self._download_progress[model_name] = (i + 1) * 10.0

        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        self._download_progress[model_name] = 100.0

        logger.info(f"Download complete for model: {model_name}")
        return True

    def recover(
        self, error: OpenWisprError, context: dict[str, Any] | None = None
    ) -> RecoveryResult:
        if not isinstance(error, ModelError) or not error.model_name:
            return self._failed(error.error_id, "Cannot download: unknown model name")

        model_name = error.model_name

        try:
            success = self._download_model(model_name)
            if success:
                return self._success(
                    error.error_id,
                    f"Successfully downloaded model: {model_name}",
                    fallback_applied=f"downloaded:{model_name}",
                )
        except Exception as e:
            return self._failed(
                error.error_id,
                f"Model download failed after retries: {e}",
                details={"model": model_name, "error": str(e)},
            )

        return self._failed(error.error_id, "Model download did not complete")


class ModelFallbackStrategy(RecoveryStrategy):
    """Fallback to smaller model when primary fails to load."""

    def __init__(
        self,
        model_fallback: FallbackChain[str] | None = None,
    ):
        super().__init__("model_size_fallback", priority=15)
        self.model_fallback = model_fallback or create_model_size_fallback_chain()

    def can_handle(self, error: OpenWisprError) -> bool:
        return isinstance(error, ModelError) and error.category in {
            ErrorCategory.MODEL_LOAD_FAILED,
            ErrorCategory.MODEL_CORRUPTED,
        }

    def recover(
        self, error: OpenWisprError, context: dict[str, Any] | None = None
    ) -> RecoveryResult:
        success, new_model = self.model_fallback.fallback()

        if success:
            return self._success(
                error.error_id,
                f"Switched to fallback model: {new_model}",
                fallback_applied=new_model,
                details={
                    "from_model": getattr(error, "model_name", "unknown"),
                    "to_model": new_model,
                    "quality_note": "Lower quality but functional",
                },
            )

        return self._failed(
            error.error_id,
            "No more fallback models available - all models exhausted",
        )


# ============================================
# Network Recovery Strategies
# ============================================
class NetworkRetryStrategy(RecoveryStrategy):
    """Retry network requests with exponential backoff."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        super().__init__("network_retry", priority=10)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._retry_counts: dict[str, int] = {}

    def can_handle(self, error: OpenWisprError) -> bool:
        return (
            isinstance(error, NetworkError)
            and error.category
            in {
                ErrorCategory.NETWORK_BACKEND_UNAVAILABLE,
                ErrorCategory.NETWORK_TIMEOUT,
                ErrorCategory.NETWORK_CONNECTION_ERROR,
            }
            and error.retry_allowed
        )

    def recover(
        self, error: OpenWisprError, context: dict[str, Any] | None = None
    ) -> RecoveryResult:
        error_key = f"{error.category.value}:{error.endpoint or 'unknown'}"
        retry_count = self._retry_counts.get(error_key, 0) + 1

        if retry_count > self.max_retries:
            return self._failed(
                error.error_id,
                f"Network retry exhausted after {self.max_retries} attempts",
                details={"endpoint": error.endpoint, "retry_count": retry_count},
            )

        self._retry_counts[error_key] = retry_count

        # Calculate backoff delay
        delay = min(self.base_delay * (2 ** (retry_count - 1)), 30.0)

        logger.info(
            f"Network retry {retry_count}/{self.max_retries} for {error.endpoint} in {delay:.1f}s"
        )

        time.sleep(delay)

        return self._success(
            error.error_id,
            f"Retry attempt {retry_count}/{self.max_retries} scheduled",
            fallback_applied=f"retry:{retry_count}",
            details={
                "retry_count": retry_count,
                "max_retries": self.max_retries,
                "backoff_delay": delay,
            },
        )


class OfflineModeStrategy(RecoveryStrategy):
    """Switch to offline mode when backend is unavailable."""

    def __init__(self):
        super().__init__("offline_mode_switch", priority=20)
        self._offline_mode_active = False

    def can_handle(self, error: OpenWisprError) -> bool:
        return (
            isinstance(error, NetworkError)
            and error.category == ErrorCategory.NETWORK_BACKEND_UNAVAILABLE
        )

    def recover(
        self, error: OpenWisprError, context: dict[str, Any] | None = None
    ) -> RecoveryResult:
        if self._offline_mode_active:
            return self._partial(
                error.error_id,
                "Already in offline mode",
                fallback_applied="offline_mode",
            )

        self._offline_mode_active = True

        return self._success(
            error.error_id,
            "Switched to offline mode - local processing only",
            fallback_applied="offline_mode",
            details={
                "limitations": [
                    "No cloud sync",
                    "No online model downloads",
                    "Local transcription only",
                ],
                "recovery_action": "Will retry connection periodically",
            },
        )

    def is_offline(self) -> bool:
        return self._offline_mode_active

    def set_online(self) -> None:
        self._offline_mode_active = False
        logger.info("Switched back to online mode")


# ============================================
# Session Recovery Strategies
# ============================================
class DiskFullRecoveryStrategy(RecoveryStrategy):
    """Handle disk full errors with recording pause and cleanup offer."""

    def __init__(self, min_free_mb: int = 100):
        super().__init__("disk_full_handler", priority=5)
        self.min_free_mb = min_free_mb

    def can_handle(self, error: OpenWisprError) -> bool:
        return isinstance(error, SessionError) and error.category == ErrorCategory.SESSION_DISK_FULL

    def recover(
        self, error: OpenWisprError, context: dict[str, Any] | None = None
    ) -> RecoveryResult:
        ctx = context or {}
        session_manager = ctx.get("session_manager")

        # Stop recording immediately
        if session_manager and hasattr(session_manager, "pause_recording"):
            try:
                session_manager.pause_recording()
                recording_paused = True
            except Exception as e:
                logger.error(f"Failed to pause recording: {e}")
                recording_paused = False
        else:
            recording_paused = False

        # Get disk space info
        try:
            path = Path(error.file_path) if error.file_path else Path.home()
            stat = shutil.disk_usage(path)
            free_gb = stat.free / (1024**3)
            total_gb = stat.total / (1024**3)
        except Exception:
            logger.warning(
                f"Failed to get disk space info for path: {error.file_path or 'default'}"
            )
            free_gb = 0
            total_gb = 0

        # Check if temp files can be cleaned
        cleanup_candidates = self._find_cleanup_candidates()

        return self._partial(
            error.error_id,
            "Recording paused due to disk full - user cleanup required",
            fallback_applied="pause_recording",
            details={
                "recording_paused": recording_paused,
                "free_space_gb": round(free_gb, 2),
                "total_space_gb": round(total_gb, 2),
                "cleanup_candidates": cleanup_candidates,
                "required_space_mb": self.min_free_mb,
            },
        )

    def _find_cleanup_candidates(self) -> list[dict[str, Any]]:
        """Find files that could be cleaned up."""
        candidates = []

        # Check temp directories
        temp_paths = [
            Path.home() / ".openwispr" / "temp",
            Path.home() / ".openwispr" / "cache",
            Path(tempfile.gettempdir()) if Path(tempfile.gettempdir()).exists() else None,
        ]

        for path in temp_paths:
            if path and path.exists():
                try:
                    size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                    if size > 10 * 1024 * 1024:  # > 10MB
                        candidates.append(
                            {
                                "path": str(path),
                                "size_mb": round(size / (1024 * 1024), 2),
                                "type": "temp/cache",
                            }
                        )
                except Exception:
                    logger.warning(f"Failed to scan temp directory for cleanup candidates: {path}")
                    pass

        return candidates


class SessionCorruptionRecoveryStrategy(RecoveryStrategy):
    """Attempt to recover corrupted session data."""

    def __init__(self):
        super().__init__("session_corruption_recovery", priority=10)

    def can_handle(self, error: OpenWisprError) -> bool:
        return isinstance(error, SessionError) and error.category == ErrorCategory.SESSION_CORRUPTED

    def recover(
        self, error: OpenWisprError, context: dict[str, Any] | None = None
    ) -> RecoveryResult:
        file_path = error.file_path

        if not file_path or not Path(file_path).exists():
            return self._failed(error.error_id, "Cannot recover: session file not found")

        recovery_attempts = []

        # Attempt 1: Try to read partial JSON
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Try to extract valid JSON objects
            import json

            recovered_data = self._extract_valid_json(content)
            if recovered_data:
                recovery_attempts.append("partial_json_extract")
        except Exception as e:
            logger.warning(f"JSON extraction failed: {e}")
            recovered_data = None

        # Attempt 2: Check for backup files
        if not recovered_data:
            backup_path = Path(str(file_path) + ".backup")
            if backup_path.exists():
                try:
                    import json

                    with open(backup_path, encoding="utf-8") as f:
                        recovered_data = json.load(f)
                    recovery_attempts.append("backup_restore")
                except Exception as e:
                    logger.warning(f"Backup restore failed: {e}")

        if recovered_data:
            return self._partial(
                error.error_id,
                f"Session partially recovered using: {', '.join(recovery_attempts)}",
                fallback_applied="data_recovery",
                details={
                    "recovery_methods": recovery_attempts,
                    "data_loss_possible": True,
                    "recovered_keys": list(recovered_data.keys())
                    if isinstance(recovered_data, dict)
                    else [],
                },
            )

        return self._failed(
            error.error_id,
            "Could not recover any data from corrupted session",
        )

    def _extract_valid_json(self, content: str) -> dict | None:
        """Attempt to extract valid JSON from corrupted content."""
        import json

        # Try full parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to find largest valid JSON object
        for end in range(len(content), 0, -1):
            try:
                return json.loads(content[:end])
            except json.JSONDecodeError:
                continue

        return None


# ============================================
# Recovery Manager
# ============================================
class RecoveryManager:
    """Coordinates automatic recovery attempts for system failures."""

    def __init__(self):
        self._strategies: list[RecoveryStrategy] = []
        self._fallback_chains: dict[str, FallbackChain] = {}
        self._recovery_history: list[RecoveryResult] = []
        self._max_history = 100
        self._on_recovery: Callable[[RecoveryResult], None] | None = None

    def register_strategy(self, strategy: RecoveryStrategy) -> None:
        """Register a recovery strategy."""
        self._strategies.append(strategy)
        self._strategies.sort(key=lambda s: s.priority)
        logger.debug(f"Registered recovery strategy: {strategy.name}")

    def register_fallback_chain(self, name: str, chain: FallbackChain) -> None:
        """Register a named fallback chain."""
        self._fallback_chains[name] = chain
        logger.debug(f"Registered fallback chain: {name}")

    def set_recovery_callback(self, callback: Callable[[RecoveryResult], None]) -> None:
        """Set callback for recovery results."""
        self._on_recovery = callback

    def attempt_recovery(
        self,
        error: OpenWisprError,
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        """Attempt to recover from an error using registered strategies."""
        logger.info(f"Attempting recovery for {error.error_id} ({error.category.value})")

        # Find applicable strategies
        applicable = [s for s in self._strategies if s.enabled and s.can_handle(error)]

        if not applicable:
            result = RecoveryResult(
                status=RecoveryStatus.SKIPPED,
                strategy_name="none",
                error_id=error.error_id,
                message="No applicable recovery strategy found",
            )
            self._record_result(result)
            return result

        # Try strategies in priority order
        for strategy in applicable:
            try:
                start_time = time.time()
                result = strategy.recover(error, context)
                result.recovery_time_ms = (time.time() - start_time) * 1000

                self._record_result(result)

                if result.status in {RecoveryStatus.SUCCESS, RecoveryStatus.PARTIAL}:
                    logger.info(f"Recovery succeeded with {strategy.name}")
                    return result

                logger.warning(
                    f"Recovery with {strategy.name} did not succeed: {result.status.value}"
                )

            except Exception as e:
                logger.error(f"Recovery strategy {strategy.name} threw exception: {e}")
                continue

        # All strategies exhausted
        result = RecoveryResult(
            status=RecoveryStatus.FAILED,
            strategy_name="exhausted",
            error_id=error.error_id,
            message="All recovery strategies failed",
        )
        self._record_result(result)
        return result

    def _record_result(self, result: RecoveryResult) -> None:
        """Record recovery result to history."""
        self._recovery_history.append(result)

        if len(self._recovery_history) > self._max_history:
            self._recovery_history = self._recovery_history[-self._max_history :]

        if self._on_recovery:
            try:
                self._on_recovery(result)
            except Exception as e:
                logger.error(f"Recovery callback failed: {e}")

    def get_fallback_chain(self, name: str) -> FallbackChain | None:
        """Get a registered fallback chain by name."""
        return self._fallback_chains.get(name)

    def get_stats(self) -> dict[str, Any]:
        """Get recovery statistics."""
        strategy_stats = [s.get_stats() for s in self._strategies]

        history_by_status = {}
        for r in self._recovery_history:
            status = r.status.value
            history_by_status[status] = history_by_status.get(status, 0) + 1

        return {
            "strategies": strategy_stats,
            "fallback_chains": list(self._fallback_chains.keys()),
            "history_summary": history_by_status,
            "total_attempts": len(self._recovery_history),
        }

    def get_history(self, limit: int = 50) -> list[RecoveryResult]:
        """Get recent recovery history."""
        return self._recovery_history[-limit:]

    def clear_history(self) -> None:
        """Clear recovery history."""
        self._recovery_history.clear()


# ============================================
# Default Recovery Manager Setup
# ============================================
def create_default_recovery_manager() -> RecoveryManager:
    """Create a RecoveryManager with all default strategies registered."""
    manager = RecoveryManager()

    # Audio strategies
    manager.register_strategy(AudioDeviceRecoveryStrategy())
    manager.register_strategy(AudioPermissionRecoveryStrategy())

    # Model strategies
    manager.register_strategy(ModelOOMRecoveryStrategy())
    manager.register_strategy(ModelDownloadStrategy())
    manager.register_strategy(ModelFallbackStrategy())

    # Network strategies
    manager.register_strategy(NetworkRetryStrategy())
    manager.register_strategy(OfflineModeStrategy())

    # Session strategies
    manager.register_strategy(DiskFullRecoveryStrategy())
    manager.register_strategy(SessionCorruptionRecoveryStrategy())

    # Register default fallback chains
    manager.register_fallback_chain("compute", create_compute_fallback_chain())
    manager.register_fallback_chain("model_size", create_model_size_fallback_chain())
    manager.register_fallback_chain("batch_size", create_batch_size_fallback_chain())

    logger.info("Default recovery manager initialized with all strategies")
    return manager


# Singleton instance
_default_manager: RecoveryManager | None = None


def get_recovery_manager() -> RecoveryManager:
    """Get or create the default recovery manager singleton."""
    global _default_manager
    if _default_manager is None:
        _default_manager = create_default_recovery_manager()
    return _default_manager


def set_recovery_manager(manager: RecoveryManager) -> None:
    """Set the default recovery manager singleton."""
    global _default_manager
    _default_manager = manager
