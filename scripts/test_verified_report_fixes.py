from __future__ import annotations

import importlib
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from app.audio.backends.base import AudioBackendError, BackendAttempt
from app.audio.backends.pyaudio_wasapi import PyAudioWasapiBackend


if "faster_whisper" not in sys.modules:
    fake = ModuleType("faster_whisper")
    fake.WhisperModel = object
    sys.modules["faster_whisper"] = fake

server_module = importlib.import_module("app.api.server")


class VerifiedReportFixesTest(unittest.TestCase):
    def test_sse_event_queue_is_bounded(self) -> None:
        queue = server_module._create_sse_event_queue()

        self.assertEqual(queue.maxsize, server_module.SSE_EVENT_QUEUE_MAXSIZE)
        self.assertEqual(server_module.SSE_EVENT_QUEUE_MAXSIZE, 100)

    def test_audio_backend_error_keeps_legacy_compatibility_helpers(self) -> None:
        error = AudioBackendError(
            backend="pyaudio",
            attempts=[
                BackendAttempt(
                    backend="pyaudio",
                    device_name="Mic",
                    sample_rate=16000,
                    channels=1,
                    error_type="RuntimeError",
                    error="boom",
                )
            ],
        )

        self.assertEqual(error.backend_name, "pyaudio")
        self.assertEqual(error.attempts[0].backend_name, "pyaudio")
        self.assertIn("Mic", error.describe_attempts())

    def test_pyaudio_backend_terminates_instance_when_start_fails(self) -> None:
        class FakePyAudioInstance:
            def __init__(self) -> None:
                self.terminated = False

            def get_device_count(self) -> int:
                return 1

            def get_device_info_by_index(self, index: int) -> dict[str, object]:
                return {
                    "index": index,
                    "name": "Broken device",
                    "maxInputChannels": 1,
                    "defaultSampleRate": 16000,
                }

            def open(self, **_: object) -> None:
                raise RuntimeError("cannot open")

            def terminate(self) -> None:
                self.terminated = True

        holder: dict[str, FakePyAudioInstance] = {}

        class FakePyAudioModule:
            paFloat32 = object()
            paInt16 = object()

            @staticmethod
            def PyAudio() -> FakePyAudioInstance:
                instance = FakePyAudioInstance()
                holder["instance"] = instance
                return instance

        with patch.dict(sys.modules, {"pyaudiowpatch": FakePyAudioModule}):
            backend = PyAudioWasapiBackend(
                device_id="default",
                sample_rate=16000,
                channels=1,
                block_size=320,
            )

            with self.assertRaises(AudioBackendError):
                backend.start()

        self.assertTrue(holder["instance"].terminated)
        self.assertIsNone(backend._pa)
        self.assertIsNone(backend._stream)

    def test_main_reuses_existing_qapplication(self) -> None:
        existing_app = SimpleNamespace(setApplicationName=lambda _: None, exec=lambda: 7)
        created: list[list[str]] = []
        shown: list[object] = []

        class FakeQApplication:
            @staticmethod
            def instance() -> object:
                return existing_app

            def __init__(self, argv: list[str]) -> None:
                created.append(list(argv))

        class FakeMainWindow:
            def __init__(self, *, settings: object) -> None:
                self.settings = settings

            def show(self) -> None:
                shown.append(self)

        fake_qtwidgets = ModuleType("PySide6.QtWidgets")
        fake_qtwidgets.QApplication = FakeQApplication
        fake_pyside = ModuleType("PySide6")
        fake_main_window_module = ModuleType("app.ui.main_window")
        fake_main_window_module.MainWindow = FakeMainWindow

        with patch.dict(
            sys.modules,
            {
                "PySide6": fake_pyside,
                "PySide6.QtWidgets": fake_qtwidgets,
                "app.ui.main_window": fake_main_window_module,
            },
        ):
            sys.modules.pop("app.main", None)
            main_module = importlib.import_module("app.main")
            self.assertEqual(main_module.main(), 7)

        self.assertEqual(created, [])
        self.assertEqual(len(shown), 1)


if __name__ == "__main__":
    unittest.main()
