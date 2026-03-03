import sys
from types import SimpleNamespace

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

from app.api import server
from app.audio import devices
from app.audio.backends import factory
from app.core.models import AudioDeviceInfo


def _device(
    device_id: str,
    *,
    is_loopback: bool,
    supports_loopback: bool,
    is_input: bool = True,
) -> AudioDeviceInfo:
    return AudioDeviceInfo(
        id=device_id,
        name=device_id,
        kind="speaker" if is_loopback else "microphone",
        is_loopback=is_loopback,
        supports_loopback=supports_loopback,
        is_input=is_input,
    )


def test_resolve_input_device_for_microphone_prefers_real_microphone(monkeypatch):
    monkeypatch.setattr(
        server,
        "list_audio_devices",
        lambda: [
            _device("loopback-1", is_loopback=True, supports_loopback=True),
            _device("mic-1", is_loopback=False, supports_loopback=False),
        ],
    )
    monkeypatch.setattr(
        server,
        "get_settings_manager",
        lambda: SimpleNamespace(
            get_settings=lambda: SimpleNamespace(
                audio=SimpleNamespace(default_capture_source="microphone", defaultDeviceId="loopback-1")
            )
        ),
    )

    resolved = server._resolve_input_device_for_source("microphone", None)

    assert resolved == "mic-1"


def test_resolve_input_device_for_system_prefers_loopback(monkeypatch):
    monkeypatch.setattr(
        server,
        "list_audio_devices",
        lambda: [
            _device("mic-1", is_loopback=False, supports_loopback=False),
            _device("loopback-1", is_loopback=True, supports_loopback=True),
        ],
    )
    monkeypatch.setattr(
        server,
        "get_settings_manager",
        lambda: SimpleNamespace(
            get_settings=lambda: SimpleNamespace(
                audio=SimpleNamespace(default_capture_source="system", defaultDeviceId="loopback-1")
            )
        ),
    )

    resolved = server._resolve_input_device_for_source("system", None)

    assert resolved == "loopback-1"


def test_list_audio_devices_returns_empty_when_soundcard_missing(monkeypatch):
    monkeypatch.setattr(devices, "sc", None)

    assert devices.list_audio_devices() == []


def test_open_audio_backend_reports_unavailable_soundcard_backend(monkeypatch):
    monkeypatch.setattr(factory, "SoundcardBackend", None)

    with pytest.raises(RuntimeError, match="soundcard"):
        factory.open_audio_backend(
            device_id=None,
            sample_rate=16000,
            channels=1,
            block_size=1600,
            preferred_backend="soundcard",
        )
