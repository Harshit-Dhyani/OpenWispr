"""Audio device discovery and resolution.

Provides device enumeration, candidate resolution, and device selection
for audio capture. Supports both WASAPI and soundcard backends with
automatic device detection and fallback.

Key functions:
    list_audio_devices: Enumerate available audio devices
    resolve_capture_device: Find best capture device
    resolve_capture_device_candidates: Get ranked device candidates
    candidate_channel_counts: Get supported channel counts
    resolve_capture_name_hints: Match device by name hints
"""

import logging
from collections.abc import Iterable
from typing import Any

try:
    import soundcard as sc
except ModuleNotFoundError:  # pragma: no cover - depends on local Python environment
    sc = None

from app.core.models import AudioDeviceInfo

logger = logging.getLogger(__name__)


def _device_id(device: Any) -> str:
    return str(getattr(device, "id", None) or getattr(device, "name", "unknown"))


def _device_name(device: Any) -> str:
    return getattr(device, "name", "Unknown")


def _normalize_name(name: str) -> str:
    lowered = name.lower()
    for marker in ("(wasapi loopback)", "[rec]", "(loopback)"):
        lowered = lowered.replace(marker, " ")
    normalized = "".join(character if character.isalnum() else " " for character in lowered)
    return " ".join(normalized.split())


def _same_physical_device(first: AudioDeviceInfo, second: AudioDeviceInfo) -> bool:
    first_name = _normalize_name(first.name)
    second_name = _normalize_name(second.name)
    if not first_name or not second_name:
        return False
    if first_name == second_name:
        return True
    if first_name in second_name or second_name in first_name:
        return True
    return False


def _device_priority(device: AudioDeviceInfo) -> tuple[int, int, int, str]:
    lowered = device.name.lower()
    is_virtual_cable = "vb-audio" in lowered or "cable" in lowered
    return (
        0 if device.is_loopback else 1,
        0 if is_virtual_cable else 1,
        0 if device.kind == "microphone" else 1,
        lowered,
    )


def _is_loopback_microphone(device: Any) -> bool:
    return bool(getattr(device, "isloopback", False)) or any(
        token in _device_name(device).lower() for token in ("loopback", "vb-audio", "cable")
    )


def _iter_speakers() -> list[Any]:
    if sc is None:
        return []
    try:
        return list(sc.all_speakers())
    except Exception as exc:
        logger.warning(f"Failed to list speakers: {exc}")
        return []


def _iter_microphones() -> list[Any]:
    if sc is None:
        return []
    try:
        return list(sc.all_microphones(include_loopback=True))
    except Exception as exc:
        logger.warning(f"Failed to list microphones: {exc}")
        return []


def _speaker_info(speaker: Any) -> AudioDeviceInfo:
    return AudioDeviceInfo(
        id=_device_id(speaker),
        name=f"{_device_name(speaker)} (WASAPI loopback)",
        kind="speaker",
        is_loopback=True,
        channels=getattr(speaker, "channels", None),
        backend_candidates=["pyaudio", "soundcard"],
        is_output=True,
        supports_loopback=True,
        driver="wasapi",
    )


def _microphone_info(microphone: Any) -> AudioDeviceInfo:
    return AudioDeviceInfo(
        id=_device_id(microphone),
        name=_device_name(microphone),
        kind="microphone",
        is_loopback=_is_loopback_microphone(microphone),
        channels=getattr(microphone, "channels", None),
        backend_candidates=["pyaudio", "soundcard"],
        is_input=True,
        supports_loopback=_is_loopback_microphone(microphone),
        driver="wasapi",
    )


def list_audio_devices() -> list[AudioDeviceInfo]:
    devices = [_speaker_info(speaker) for speaker in _iter_speakers()]
    devices.extend(_microphone_info(microphone) for microphone in _iter_microphones())

    deduped: list[AudioDeviceInfo] = []
    for device in devices:
        existing_index = next(
            (
                index
                for index, existing in enumerate(deduped)
                if _same_physical_device(existing, device)
            ),
            None,
        )
        if existing_index is None:
            deduped.append(device)
            continue
        existing = deduped[existing_index]
        if _device_priority(device) < _device_priority(existing):
            deduped[existing_index] = device

    return sorted(
        deduped,
        key=_device_priority,
    )


def _score_microphone(
    microphone: Any, selected_id: str | None, speaker_name: str | None
) -> tuple[int, int, str]:
    name = _device_name(microphone)
    lowered = name.lower()
    normalized = _normalize_name(name)
    matches_selected_id = selected_id is not None and _device_id(microphone) == selected_id
    if speaker_name:
        speaker_name_normalized = _normalize_name(speaker_name)
        matches_speaker_name = (
            speaker_name_normalized in normalized or normalized in speaker_name_normalized
        )
    else:
        matches_speaker_name = False
    is_loopback = _is_loopback_microphone(microphone)
    is_virtual_cable = "vb-audio" in lowered or "cable" in lowered
    return (
        0 if matches_selected_id else 1,
        0 if is_virtual_cable else 1,
        f"{0 if is_loopback else 1}{0 if matches_speaker_name else 1}{name.lower()}",
    )


def resolve_capture_name_hints(device_id: str | None) -> list[str]:
    microphones = _iter_microphones()
    speakers = _iter_speakers()
    hints: list[str] = []

    if not device_id:
        for microphone in microphones:
            if _is_loopback_microphone(microphone):
                hints.append(_device_name(microphone))
        for speaker in speakers:
            hints.append(_device_name(speaker))
    else:
        exact_microphone_matches = [
            microphone for microphone in microphones if _device_id(microphone) == device_id
        ]
        exact_speaker_match = next(
            (speaker for speaker in speakers if _device_id(speaker) == device_id), None
        )

        for microphone in exact_microphone_matches:
            hints.append(_device_name(microphone))
        if exact_speaker_match is not None:
            speaker_name = _device_name(exact_speaker_match)
            hints.append(speaker_name)
            ranked_microphones = sorted(
                [microphone for microphone in microphones if _is_loopback_microphone(microphone)],
                key=lambda microphone: _score_microphone(microphone, device_id, speaker_name),
            )
            hints.extend(_device_name(microphone) for microphone in ranked_microphones)

    unique_hints: list[str] = []
    seen: set[str] = set()
    for hint in hints:
        normalized = _normalize_name(hint)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_hints.append(hint)
    return unique_hints


def resolve_capture_device_candidates(device_id: str | None) -> list[tuple[Any, str]]:
    microphones = _iter_microphones()
    speakers = _iter_speakers()
    loopback_microphones = [
        microphone for microphone in microphones if _is_loopback_microphone(microphone)
    ]

    if not device_id:
        ranked = sorted(
            loopback_microphones or microphones,
            key=lambda microphone: (
                0 if _is_loopback_microphone(microphone) else 1,
                0
                if "vb-audio" in _device_name(microphone).lower()
                or "cable" in _device_name(microphone).lower()
                else 1,
                _device_name(microphone).lower(),
            ),
        )
        if ranked:
            return [(microphone, _device_name(microphone)) for microphone in ranked]
        default_mic = sc.default_microphone() if sc is not None else None
        if default_mic:
            return [(default_mic, _device_name(default_mic))]
        raise RuntimeError("No audio devices found")

    exact_microphone_matches = [
        microphone for microphone in microphones if _device_id(microphone) == device_id
    ]
    if exact_microphone_matches:
        return [(microphone, _device_name(microphone)) for microphone in exact_microphone_matches]

    selected_speaker = next(
        (speaker for speaker in speakers if _device_id(speaker) == device_id), None
    )
    selected_speaker_name = _device_name(selected_speaker) if selected_speaker else None

    if selected_speaker is not None:
        ranked_loopbacks = sorted(
            loopback_microphones,
            key=lambda microphone: _score_microphone(microphone, device_id, selected_speaker_name),
        )
        if ranked_loopbacks:
            return [(microphone, _device_name(microphone)) for microphone in ranked_loopbacks]

    ranked_microphones = sorted(
        microphones,
        key=lambda microphone: _score_microphone(microphone, device_id, selected_speaker_name),
    )
    if ranked_microphones:
        return [(microphone, _device_name(microphone)) for microphone in ranked_microphones]

    return resolve_capture_device_candidates(None)


def resolve_capture_device(device_id: str | None) -> tuple[Any, str]:
    candidates = resolve_capture_device_candidates(device_id)
    if not candidates:
        raise RuntimeError("No compatible audio capture device found")
    return candidates[0]


def candidate_channel_counts(
    preferred_channels: int, available_channels: int | None
) -> Iterable[int]:
    ordered: list[int] = []
    for candidate in (
        preferred_channels,
        2,
        1,
        available_channels
        if isinstance(available_channels, int) and available_channels > 0
        else None,
    ):
        if candidate is None or candidate <= 0 or candidate in ordered:
            continue
        ordered.append(candidate)
    return ordered
