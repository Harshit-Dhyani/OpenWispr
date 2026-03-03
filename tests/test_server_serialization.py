from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.modules.setdefault(
    "soundcard",
    SimpleNamespace(
        all_speakers=lambda: [],
        all_microphones=lambda include_loopback=True: [],
        default_microphone=lambda: None,
    ),
)
sys.modules.setdefault("faster_whisper", SimpleNamespace(WhisperModel=object))

from app.api.server import _make_json_safe


def test_make_json_safe_converts_numpy_scalars_and_arrays() -> None:
    payload = {
        "audio_level": np.float32(0.5),
        "levels": np.array([0.1, 0.2, 0.3], dtype=np.float32),
        "nested": {"peak": np.float64(0.9)},
    }

    result = _make_json_safe(payload)

    assert isinstance(result["audio_level"], float)
    assert result["audio_level"] == pytest.approx(0.5)
    assert result["levels"] == pytest.approx([0.1, 0.2, 0.3])
    assert isinstance(result["nested"]["peak"], float)


@dataclass
class _SerializableSample:
    when: datetime
    path: Path


def test_make_json_safe_handles_dataclasses_datetime_and_path() -> None:
    sample = _SerializableSample(
        when=datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc),
        path=Path("models/refiner.gguf"),
    )

    result = _make_json_safe(sample)

    assert result["when"] == "2026-03-03T12:00:00+00:00"
    assert Path(result["path"]) == Path("models/refiner.gguf")
