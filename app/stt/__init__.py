"""Speech-to-text engine and rolling chunking.

Optimized transcription engine with dual-mode support (Wispr/System),
adaptive beam sizing, and GPU memory estimation/tracking.

Note: These imports require faster-whisper to be installed. If faster-whisper
is not available, individual modules can still be imported directly.
"""

__all__ = [
    # Components available without faster-whisper (lazy loaded)
    "TranscriptionMode",
    "PartialResult",
    "PerformanceMetrics",
    "ModelPool",
    # Components requiring faster-whisper (lazy loaded)
    "DualModeTranscriptionEngine",
    "StreamingInferenceEngine",
    "OptimizedWhisperBackend",
    "OptimizedWhisperFactory",
    "WISPR_MODE",
    "SYSTEM_MODE",
    "ModeConfig",
]

__lazy_imports__ = {
    "TranscriptionMode": "app.stt.streaming_engine",
    "PartialResult": "app.stt.streaming_engine",
    "PerformanceMetrics": "app.stt.streaming_engine",
    "ModelPool": "app.stt.model_pool",
    "DualModeTranscriptionEngine": "app.stt.streaming_engine",
    "StreamingInferenceEngine": "app.stt.streaming_engine",
    "OptimizedWhisperBackend": "app.stt.fast_whisper_backend",
    "OptimizedWhisperFactory": "app.stt.fast_whisper_backend",
    "WISPR_MODE": "app.stt.fast_whisper_backend",
    "SYSTEM_MODE": "app.stt.fast_whisper_backend",
    "ModeConfig": "app.stt.fast_whisper_backend",
}


def __getattr__(name):
    """Lazy import for module attributes."""
    if name in __lazy_imports__:
        import importlib

        module_name = __lazy_imports__[name]
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            if "faster_whisper" in str(e):
                raise AttributeError(
                    f"module 'app.stt' attribute '{name}' requires faster-whisper: {e}"
                )
            raise
        return getattr(module, name)
    raise AttributeError(f"module 'app.stt' has no attribute '{name}'")


def __dir__():
    """Include all exports in dir()."""
    return sorted(set(__all__) | set(__lazy_imports__.keys()))
