# Backend Testing Suite for Transcripta

## Overview

This testing suite provides comprehensive coverage for the Transcripta Python backend.

## Test Structure

Tests are organized in a flat structure within the `tests/` directory:

```
tests/
├── conftest.py                      # Shared fixtures and configuration
├── test_audio_capture_contract.py   # Audio capture contract tests
├── test_audio_pipelines.py          # Audio pipeline tests
├── test_audio_probe.py              # Audio probing tests
├── test_chunking_contract.py        # Audio chunking contract tests
├── test_dictation_cleanup.py        # Dictation cleanup tests
├── test_error_handling.py           # Error handling tests
├── test_fast_engine_metrics.py      # Fast engine metrics tests
├── test_fast_whisper_backend.py     # Fast Whisper backend tests
├── test_fixes.py                    # Bug fix verification tests
├── test_flow_control.py             # Flow control tests
├── test_formula_extraction_contract.py  # Formula extraction tests
├── test_gpu_fallback.py             # GPU fallback behavior tests
├── test_hotkey_service_lifecycle.py # Hotkey service lifecycle tests
├── test_hotkey_session.py           # Hotkey session tests
├── test_incremental_output.py       # Incremental output tests
├── test_mode_manager.py             # Mode manager tests
├── test_model_catalog.py            # Model catalog tests
├── test_refinement_queue.py         # Refinement queue tests
├── test_refiner_service.py          # Refiner service tests
├── test_session_writer_contract.py  # Session writer contract tests
├── test_settings_manager.py         # Settings manager tests
├── test_sse_events.py               # Server-sent events tests
├── test_stability.py                # Stability tests
├── test_stream_event_contract.py    # Stream event contract tests
├── test_stream_quality_contract.py  # Stream quality contract tests
├── test_system_mode.py              # System mode tests
├── test_system_session.py           # System session tests
├── test_vad_config.py               # VAD configuration tests
├── test_vad_optimized.py            # Optimized VAD tests
└── test_windows_mvp_sanity.py       # Windows MVP sanity tests
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run specific test file
```bash
pytest tests/test_vad_optimized.py -v
```

### Run with coverage report
```bash
pytest --cov=app --cov-report=html
```

### Run excluding slow tests
```bash
pytest -m "not slow"
```

### Run only unit tests
```bash
pytest -m unit -v
```

### Run only integration tests
```bash
pytest -m integration -v
```

### Run only performance tests
```bash
pytest -m performance -v
```

### Run benchmark tests
```bash
pytest -m benchmark -v
```

## Test Markers

The following markers are available (defined in `pyproject.toml`):

| Marker | Description |
|--------|-------------|
| `@pytest.mark.slow` | Slow tests (may be excluded in quick runs) |
| `@pytest.mark.integration` | Integration tests |
| `@pytest.mark.unit` | Unit tests |
| `@pytest.mark.performance` | Performance tests |
| `@pytest.mark.benchmark` | Benchmark tests |

## Pytest Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = ["--strict-markers", "--strict-config", "-v", "--tb=short"]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "performance: marks tests as performance tests",
    "benchmark: marks tests as benchmarks",
]
asyncio_mode = "auto"
```

## Fixtures

### Audio Fixtures
- `mock_audio_data` - Silent audio data (1 second of zeros)
- `mock_speech_audio` - Speech-like audio data with harmonics
- `mock_noisy_audio` - White noise audio data
- `mock_audio_chunk` - Small audio chunk (100ms)
- `mock_audio_devices` - Mock audio device list

### Model Fixtures
- `mock_whisper_model` - Mock Whisper model with transcribe method
- `mock_whisper_segments` - Mock transcription segments
- `mock_torch` - Mock PyTorch (GPU available)
- `mock_torch_cpu` - Mock PyTorch (CPU only)
- `mock_torch_oom` - Mock PyTorch simulating out of memory

### Settings Fixtures
- `test_settings` - Complete test settings dictionary
- `mock_settings_manager` - Mock settings manager with test configuration
- `mock_settings_file` - Mock settings file on disk

### Session Fixtures
- `sample_segment` - Sample transcript segment data
- `sample_session_state` - Sample session state dictionary
- `mock_session_writer` - Mock session writer

### Device Fixtures
- `mock_sounddevice` - Mock sounddevice module
- `mock_soundcard` - Mock soundcard module
- `mock_pyaudio` - Mock PyAudio module
- `mock_recorder` - Mock audio recorder

### VAD Fixtures
- `mock_vad` - Mock VAD instance
- `mock_vad_config` - Mock VAD configuration dictionary

### Performance Fixtures
- `performance_tracker` - Factory for tracking performance metrics
- `benchmark_config` - Benchmark configuration dictionary

### Utility Fixtures
- `temp_dir` - Temporary directory for test files
- `test_data_dir` - Test data directory
- `project_root` - Project root directory
- `sample_rate` - Default sample rate (16000)

## Other Test Locations

### E2E Tests
End-to-end tests are located in the `e2e/` directory at the project root.

### Frontend Tests
Frontend tests for the Electron application are located in:
```
app/electron/frontend/
```

## CI/CD Integration

The test suite is configured for CI/CD with:
- Strict marker and config checking (`--strict-markers`, `--strict-config`)
- Verbose output (`-v`)
- Short traceback format (`--tb=short`)
- Auto async mode for asyncio tests
