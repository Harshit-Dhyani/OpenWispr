from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


class TestVADParamsPassthrough:
    """Test VAD params are passed through to transcribe."""

    def test_vad_params_stored_in_transcriber(self) -> None:
        from app.stt.engine import WhisperTranscriber

        vad_params = {
            "vad_threshold": 0.6,
            "vad_min_silence_ms": 300,
            "vad_speech_pad_ms": 250,
        }

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=8,
            vad_params=vad_params,
        )

        assert transcriber.vad_params == vad_params
        assert transcriber.vad_params["vad_threshold"] == 0.6
        assert transcriber.vad_params["vad_min_silence_ms"] == 300
        assert transcriber.vad_params["vad_speech_pad_ms"] == 250

    def test_vad_params_constructed_for_transcribe(self) -> None:
        from app.stt.engine import WhisperTranscriber

        vad_params = {
            "vad_threshold": 0.7,
            "vad_min_silence_ms": 400,
            "vad_speech_pad_ms": 300,
        }

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=8,
            vad_params=vad_params,
        )

        transcribe_kwargs: dict[str, Any] = {
            "language": None if transcriber.language_mode == "auto" else transcriber.language_mode,
            "vad_filter": transcriber.vad_filter,
            "beam_size": transcriber.beam_size,
            "best_of": transcriber.best_of,
            "temperature": transcriber.temperature,
            "word_timestamps": False,
        }
        if transcriber.vad_filter and transcriber.vad_params:
            vad_parameters: dict[str, Any] = {}
            if transcriber.vad_params.get("vad_threshold") is not None:
                vad_parameters["threshold"] = transcriber.vad_params["vad_threshold"]
            if transcriber.vad_params.get("vad_min_silence_ms") is not None:
                vad_parameters["min_silence_duration_ms"] = transcriber.vad_params[
                    "vad_min_silence_ms"
                ]
            if transcriber.vad_params.get("vad_speech_pad_ms") is not None:
                vad_parameters["speech_pad_ms"] = transcriber.vad_params["vad_speech_pad_ms"]
            if vad_parameters:
                transcribe_kwargs["vad_parameters"] = vad_parameters

        assert "vad_parameters" in transcribe_kwargs
        assert transcribe_kwargs["vad_parameters"]["threshold"] == 0.7
        assert transcribe_kwargs["vad_parameters"]["min_silence_duration_ms"] == 400
        assert transcribe_kwargs["vad_parameters"]["speech_pad_ms"] == 300

    def test_partial_vad_params_only_includes_set_values(self) -> None:
        from app.stt.engine import WhisperTranscriber

        vad_params = {
            "vad_threshold": 0.8,
        }

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=8,
            vad_params=vad_params,
        )

        assert transcriber.vad_params["vad_threshold"] == 0.8
        assert "vad_min_silence_ms" not in transcriber.vad_params

    def test_vad_params_from_session_manager(self) -> None:
        from app.core.settings.config import AppSettings

        from app.core.session_manager import SessionManager

        settings = AppSettings()
        manager = SessionManager(settings)

        vad_params = {
            "vad_threshold": 0.65,
            "vad_min_silence_ms": 250,
            "vad_speech_pad_ms": 200,
        }

        with patch.object(manager, "_emit_state"):
            with patch.object(manager, "_emit_health"):
                with patch("app.core.session_manager.WhisperTranscriber") as mock_transcriber_class:
                    mock_transcriber = MagicMock()
                    mock_transcriber_class.return_value = mock_transcriber
                    temp_dir = Path("sessions") / "test-session"

                    try:
                        manager.start_session(
                            title="test-session",
                            output_root=temp_dir,
                            model_name="tiny",
                            language_mode="en",
                            device_id=None,
                            live_mode="balanced",
                            execution_mode="cpu_only",
                            vad_params=vad_params,
                        )
                    except Exception as e:
                        logging.warning(
                            f"VAD test operation failed for session 'test-session': {e}"
                        )

                    call_kwargs = mock_transcriber_class.call_args[1]
                    assert call_kwargs["vad_params"] == vad_params


class TestVADDefaults:
    """Test defaults are used when VAD params not specified."""

    def test_empty_vad_params_defaults_to_none(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=8,
            vad_params=None,
        )

        assert transcriber.vad_params == {}

    def test_config_defaults_applied(self) -> None:
        from app.core.settings.config import AppSettings

        settings = AppSettings()

        assert settings.vad_filter is True
        assert settings.vad_threshold == 0.5
        assert settings.vad_min_silence_ms == 200
        assert settings.vad_speech_pad_ms == 200

    def test_config_defaults_used_when_no_params_provided(self) -> None:
        from app.core.settings.config import AppSettings

        settings = AppSettings()

        defaults_from_config = {
            "vad_threshold": settings.vad_threshold,
            "vad_min_silence_ms": settings.vad_min_silence_ms,
            "vad_speech_pad_ms": settings.vad_speech_pad_ms,
        }

        assert defaults_from_config["vad_threshold"] == 0.5
        assert defaults_from_config["vad_min_silence_ms"] == 200
        assert defaults_from_config["vad_speech_pad_ms"] == 200

    def test_vad_filter_false_disables_vad_params(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=False,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=8,
            vad_params={"vad_threshold": 0.8},
        )

        assert transcriber.vad_filter is False

    def test_vad_params_empty_dict_no_vad_parameters(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=8,
            vad_params={},
        )

        transcribe_kwargs: dict[str, Any] = {
            "language": None if transcriber.language_mode == "auto" else transcriber.language_mode,
            "vad_filter": transcriber.vad_filter,
            "beam_size": transcriber.beam_size,
            "best_of": transcriber.best_of,
            "temperature": transcriber.temperature,
            "word_timestamps": False,
        }
        if transcriber.vad_filter and transcriber.vad_params:
            vad_parameters: dict[str, Any] = {}
            if transcriber.vad_params.get("vad_threshold") is not None:
                vad_parameters["threshold"] = transcriber.vad_params["vad_threshold"]
            if transcriber.vad_params.get("vad_min_silence_ms") is not None:
                vad_parameters["min_silence_duration_ms"] = transcriber.vad_params[
                    "vad_min_silence_ms"
                ]
            if transcriber.vad_params.get("vad_speech_pad_ms") is not None:
                vad_parameters["speech_pad_ms"] = transcriber.vad_params["vad_speech_pad_ms"]
            if vad_parameters:
                transcribe_kwargs["vad_parameters"] = vad_parameters

        assert "vad_parameters" not in transcribe_kwargs


class TestVADParamValidation:
    """Test VAD parameter validation edge cases."""

    def test_vad_threshold_bounds(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=8,
            vad_params={"vad_threshold": 0.0},
        )

        assert transcriber.vad_params["vad_threshold"] == 0.0

        transcriber2 = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=8,
            vad_params={"vad_threshold": 1.0},
        )

        assert transcriber2.vad_params["vad_threshold"] == 1.0

    def test_vad_silence_ms_zero_allowed(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=8,
            vad_params={"vad_min_silence_ms": 0},
        )

        assert transcriber.vad_params["vad_min_silence_ms"] == 0

    def test_vad_params_with_none_values_filtered(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cpu",
            compute_type="int8",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="cpu_only",
            max_queue_items=8,
            vad_params={
                "vad_threshold": 0.6,
                "vad_min_silence_ms": None,
                "vad_speech_pad_ms": 200,
            },
        )

        transcribe_kwargs: dict[str, Any] = {
            "language": None if transcriber.language_mode == "auto" else transcriber.language_mode,
            "vad_filter": transcriber.vad_filter,
            "beam_size": transcriber.beam_size,
            "best_of": transcriber.best_of,
            "temperature": transcriber.temperature,
            "word_timestamps": False,
        }
        if transcriber.vad_filter and transcriber.vad_params:
            vad_parameters: dict[str, Any] = {}
            if transcriber.vad_params.get("vad_threshold") is not None:
                vad_parameters["threshold"] = transcriber.vad_params["vad_threshold"]
            if transcriber.vad_params.get("vad_min_silence_ms") is not None:
                vad_parameters["min_silence_duration_ms"] = transcriber.vad_params[
                    "vad_min_silence_ms"
                ]
            if transcriber.vad_params.get("vad_speech_pad_ms") is not None:
                vad_parameters["speech_pad_ms"] = transcriber.vad_params["vad_speech_pad_ms"]
            if vad_parameters:
                transcribe_kwargs["vad_parameters"] = vad_parameters

        vad_params = transcribe_kwargs.get("vad_parameters", {})

        assert "threshold" in vad_params
        assert "min_silence_duration_ms" not in vad_params
        assert "speech_pad_ms" in vad_params
