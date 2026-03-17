"""Audio backends module.

Re-exports audio backend abstractions from app.audio.backends.base
and factory functions from app.audio.backends.factory.
"""

from app.audio.backends.base import AudioBackend, AudioBackendError, BackendAttempt
from app.audio.backends.factory import (
    AudioBackendSelection,
    open_audio_backend,
)

__all__ = [
    "AudioBackend",
    "AudioBackendError",
    "AudioBackendSelection",
    "BackendAttempt",
    "open_audio_backend",
]
