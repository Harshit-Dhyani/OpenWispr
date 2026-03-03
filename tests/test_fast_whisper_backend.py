from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.modules.setdefault("faster_whisper", SimpleNamespace(WhisperModel=object))

from app.stt.fast_whisper_backend import FastWhisperBackend, ModeConfig, normalize_suppress_tokens


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ([-1], [-1]),
        ("-1", [-1]),
        ("[-1]", [-1]),
        ("-1,50257", [-1, 50257]),
        (" [ -1 , 50257 ] ", [-1, 50257]),
        ("abc", None),
        ("[oops]", None),
    ],
)
def test_normalize_suppress_tokens(value, expected) -> None:
    assert normalize_suppress_tokens(value) == expected


def test_warmup_uses_direct_model_transcribe_without_vad() -> None:
    captured_kwargs: dict[str, object] = {}

    class FakeModel:
        def transcribe(self, audio: np.ndarray, **kwargs: object):
            captured_kwargs.update(kwargs)
            return iter(()), SimpleNamespace(language="en")

    backend = FastWhisperBackend(
        model=FakeModel(),
        mode_config=ModeConfig(),
        device="cpu",
        sample_rate=16000,
        language="en",
    )

    assert backend.warmup() is True
    assert captured_kwargs["vad_filter"] is False
    assert captured_kwargs["beam_size"] == 1
    assert captured_kwargs["best_of"] == 1
    assert captured_kwargs["suppress_tokens"] == [-1]


def test_transcribe_normalizes_string_suppress_tokens_before_model_call() -> None:
    captured_kwargs: dict[str, object] = {}

    class FakeSegment:
        text = "hello"
        start = 0.0
        end = 0.1
        avg_logprob = -0.1
        no_speech_prob = 0.0
        compression_ratio = 1.0

    class FakeModel:
        def transcribe(self, audio: np.ndarray, **kwargs: object):
            captured_kwargs.update(kwargs)
            return iter([FakeSegment()]), SimpleNamespace(language="en")

    backend = FastWhisperBackend(
        model=FakeModel(),
        mode_config=ModeConfig(),
        device="cpu",
        sample_rate=16000,
        language="en",
    )

    result = backend.transcribe(np.zeros(16000, dtype=np.float32))

    assert result.text == "hello"
    assert captured_kwargs["suppress_tokens"] == [-1]
    assert not isinstance(captured_kwargs["suppress_tokens"], str)
