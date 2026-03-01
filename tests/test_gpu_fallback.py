from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestGPUOnlyModeFailure:
    """Test GPU-only mode fails correctly."""

    def test_gpu_only_fails_when_cuda_unavailable(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="gpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        with patch("app.stt.engine.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False

            with pytest.raises(RuntimeError) as exc_info:
                transcriber._load_model()

            assert "CUDA" in str(exc_info.value) or "GPU" in str(exc_info.value)

    def test_gpu_only_fails_on_memory_check(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="large-v3",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="gpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        with patch("app.stt.engine.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = True
            mock_torch.cuda.get_device_properties.return_value.total_memory = 2 * (1024**3)
            mock_torch.cuda.memory_reserved.return_value = 1 * (1024**3)

            with pytest.raises(RuntimeError) as exc_info:
                transcriber._load_model()

            assert (
                "memory" in str(exc_info.value).lower()
                or "insufficient" in str(exc_info.value).lower()
            )

    def test_gpu_only_error_message_includes_cuda_instructions(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="gpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        with patch("app.stt.engine.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False

            with pytest.raises(RuntimeError) as exc_info:
                transcriber._load_model()

            error_msg = str(exc_info.value)
            assert "GPU-only" in error_msg or "CUDA" in error_msg

    def test_validate_runtime_fails_gpu_only_on_cuda_error(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="gpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        mock_model = MagicMock()

        def raise_cuda_error(*args, **kwargs):
            raise RuntimeError("CUDA error: no kernel image is available")

        mock_model.transcribe = raise_cuda_error

        with patch.object(transcriber, "_load_model", return_value=mock_model):
            with pytest.raises(RuntimeError) as exc_info:
                transcriber.validate_runtime()

            assert "GPU-only" in str(exc_info.value)


class TestGPUFallback:
    """Test fallback triggers on CUDA error."""

    def test_fallback_triggers_on_cuda_runtime_error(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        with patch("app.stt.engine.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = True
            mock_torch.cuda.get_device_properties.return_value.total_memory = 10 * (1024**3)
            mock_torch.cuda.memory_reserved.return_value = 0

            with patch("app.stt.engine.WhisperModel") as mock_model_class:
                mock_model = MagicMock()
                mock_model_class.return_value = mock_model

                transcriber._load_model()

                assert mock_model_class.call_args[1]["device"] == "cpu"
                assert transcriber._warning is not None

    def test_fallback_sets_cpu_mode(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        transcriber._gpu_mode = "cpu/int8"
        transcriber._runtime_device = "cpu"

        assert transcriber._gpu_mode == "cpu/int8"
        assert transcriber._runtime_device == "cpu"

    def test_fallback_warning_includes_cpu_message(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        transcriber._warning = "GPU unavailable. Running on CPU fallback."

        assert "CPU" in transcriber._warning

    def test_reload_cpu_model_sets_correct_state(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        transcriber._gpu_mode = "cuda/float16"

        with patch("app.stt.engine.WhisperModel") as mock_model_class:
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model

            with patch.object(transcriber, "_cleanup_gpu_resources") as mock_cleanup:
                result = transcriber._reload_cpu_model()

                mock_cleanup.assert_called_once()
                assert transcriber._gpu_mode == "cpu/int8"
                assert transcriber._runtime_device == "cpu"
                assert "CPU" in transcriber._warning

    def test_gpu_only_mode_prevents_reload_cpu(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="gpu_only",
            max_queue_items=4,
            vad_params=None,
        )

        with pytest.raises(RuntimeError) as exc_info:
            transcriber._reload_cpu_model()

        assert "GPU-only" in str(exc_info.value)


class TestGPUCleanup:
    """Test GPU cleanup happens properly."""

    def test_cleanup_releases_gpu_resources(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        transcriber._model = MagicMock()

        with patch("app.stt.engine.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = True
            mock_torch.cuda.empty_cache = MagicMock()
            mock_torch.cuda.synchronize = MagicMock()

            transcriber._cleanup_gpu_resources()

            mock_torch.cuda.empty_cache.assert_called_once()
            mock_torch.cuda.synchronize.assert_called_once()

    def test_cleanup_handles_missing_torch(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        transcriber._model = MagicMock()

        with patch("app.stt.engine.torch", side_effect=ImportError("No module named 'torch'")):
            transcriber._cleanup_gpu_resources()

        assert transcriber._model is None

    def test_cleanup_handles_cuda_unavailable(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        transcriber._model = MagicMock()

        with patch("app.stt.engine.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False

            transcriber._cleanup_gpu_resources()

            mock_torch.cuda.empty_cache.assert_not_called()

    def test_model_deleted_during_cleanup(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        mock_model = MagicMock()
        transcriber._model = mock_model

        transcriber._cleanup_gpu_resources()

        assert transcriber._model is None

    def test_public_cleanup_method_calls_internal(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        with patch.object(transcriber, "_cleanup_gpu_resources") as mock_cleanup:
            transcriber.cleanup()
            mock_cleanup.assert_called_once()


class TestShouldFallbackToCPU:
    """Test _should_fallback_to_cpu helper function."""

    def test_detects_cublas_error(self) -> None:
        from app.stt.engine import _should_fallback_to_cpu

        error = RuntimeError("cublas64_12.dll not found")
        assert _should_fallback_to_cpu(error) is True

    def test_detects_cuda_error(self) -> None:
        from app.stt.engine import _should_fallback_to_cpu

        error = RuntimeError("CUDA error: out of memory")
        assert _should_fallback_to_cpu(error) is True

    def test_detects_gpu_error(self) -> None:
        from app.stt.engine import _should_fallback_to_cpu

        error = RuntimeError("GPU runtime failed")
        assert _should_fallback_to_cpu(error) is True

    def test_detects_out_of_memory(self) -> None:
        from app.stt.engine import _should_fallback_to_cpu

        error = RuntimeError("RuntimeError: CUDA out of memory")
        assert _should_fallback_to_cpu(error) is True

    def test_detects_device_side_assert(self) -> None:
        from app.stt.engine import _should_fallback_to_cpu

        error = RuntimeError("device-side assert triggered")
        assert _should_fallback_to_cpu(error) is True

    def test_ignores_non_gpu_errors(self) -> None:
        from app.stt.engine import _should_fallback_to_cpu

        error = RuntimeError("File not found: model.bin")
        assert _should_fallback_to_cpu(error) is False

    def test_case_insensitive_matching(self) -> None:
        from app.stt.engine import _should_fallback_to_cpu

        assert _should_fallback_to_cpu(RuntimeError("CUDNN ERROR")) is True
        assert _should_fallback_to_cpu(RuntimeError("Cuda Error")) is True
        assert _should_fallback_to_cpu(RuntimeError("nvidia driver")) is True


class TestGPUWarmup:
    """Test GPU warmup validation."""

    def test_warmup_success_returns_true(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        mock_model = MagicMock()
        mock_segments = MagicMock()
        mock_segments.__iter__ = MagicMock(return_value=iter([]))
        mock_model.transcribe.return_value = (mock_segments, MagicMock())

        result = transcriber._warmup_gpu(mock_model)

        assert result is True

    def test_warmup_failure_returns_false(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("CUDA error: no kernel image")

        result = transcriber._warmup_gpu(mock_model)

        assert result is False

    def test_warmup_raises_non_cuda_errors(self) -> None:
        from app.stt.engine import WhisperTranscriber

        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="./models",
            device="cuda",
            compute_type="float16",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=4,
            vad_params=None,
        )

        mock_model = MagicMock()
        mock_model.transcribe.side_effect = ValueError("Invalid input shape")

        with pytest.raises(ValueError):
            transcriber._warmup_gpu(mock_model)
