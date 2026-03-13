from __future__ import annotations

import numpy as np

from app.audio.backends.base import to_mono


def test_to_mono_prefers_active_channels_over_averaging_all_channels():
    frames = 160
    data = np.zeros((frames, 16), dtype=np.float32)
    t = np.linspace(0.0, 4.0 * np.pi, frames, dtype=np.float32)
    speech = 0.4 * np.sin(t)
    data[:, 3] = speech
    data[:, 7] = speech

    mono = to_mono(data)

    rms = float(np.sqrt(np.mean(np.square(mono)) + 1e-12))
    assert mono.shape == (frames,)
    assert rms > 0.2


def test_to_mono_uses_single_channel_when_only_one_is_present():
    data = np.linspace(-0.5, 0.5, 32, dtype=np.float32).reshape(32, 1)

    mono = to_mono(data)

    assert mono.shape == (32,)
    assert np.allclose(mono, data[:, 0])
