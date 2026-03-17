"""Deprecated: Re-exports from app.audio.capture.capture.

This module is a transitional shim. Use app.audio.capture.capture instead.
"""

from __future__ import annotations

import warnings

from app.audio.capture.capture import LoopbackAudioSource as _LoopbackAudioSource
from app.audio.capture.capture import MeterSmoother as _MeterSmoother

warnings.warn(
    "app.audio.capture is deprecated. Use app.audio.capture.capture instead.",
    DeprecationWarning,
    stacklevel=2,
)


class LoopbackAudioSource(_LoopbackAudioSource):
    pass


class MeterSmoother(_MeterSmoother):
    pass
