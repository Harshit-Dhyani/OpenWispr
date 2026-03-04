from __future__ import annotations

import json
import random
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


def test_make_json_safe_randomized_payloads_can_be_json_encoded() -> None:
    rng = random.Random(1337)

    def build_value(depth: int = 0):
        leaf_values = [
            lambda: rng.randint(-10, 10),
            lambda: np.int64(rng.randint(-10, 10)),
            lambda: np.float32(rng.random()),
            lambda: np.array([rng.random(), rng.random()], dtype=np.float32),
            lambda: Path(f"logs/sample-{rng.randint(1, 5)}.txt"),
            lambda: datetime(2026, 3, 4, 1, rng.randint(0, 59), tzinfo=timezone.utc),
            lambda: {"flag": bool(rng.randint(0, 1))},
        ]
        if depth >= 2:
            return rng.choice(leaf_values)()
        branch_builders = [
            lambda: [build_value(depth + 1) for _ in range(rng.randint(1, 3))],
            lambda: {f"k{idx}": build_value(depth + 1) for idx in range(rng.randint(1, 3))},
            lambda: rng.choice(leaf_values)(),
        ]
        return rng.choice(branch_builders)()

    for _ in range(25):
        payload = {"root": build_value()}
        encoded = json.dumps(_make_json_safe(payload))
        assert encoded.startswith("{")
