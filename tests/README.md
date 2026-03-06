# Backend Testing Suite for Transcripta

## Overview

This testing suite provides comprehensive coverage for the Transcripta Python backend.

**Last Updated:** 2026-03-04

## Test Structure

Tests are organized in a hierarchical structure within the `tests/` directory:

```
tests/
├── conftest.py                      # Shared fixtures and configuration
├── _contracts.py                    # Shared contract test helpers
│
├── Core Test Files (Root)
│   ├── test_audio_capture_contract.py   # Audio capture contract tests
│   ├── test_audio_pipelines.py          # Audio pipeline tests
│   ├── test_audio_probe.py              # Audio probing tests
│   ├── test_chunking_contract.py        # Audio chunking contract tests
│   ├── test_coach_service.py            # Coach service tests
│   ├── test_constants_exports.py        # Constants/exports verification
│   ├── test_deterministic_postprocess.py # Deterministic postprocessing
│   ├── test_dictation_cleanup.py        # Dictation cleanup tests
│   ├── test_error_handling.py           # Error handling tests
│   ├── test_fast_engine_metrics.py      # Fast engine metrics tests
│   ├── test_fast_whisper_backend.py     # Fast Whisper backend tests
│   ├── test_fixes.py                    # Bug fix verification tests
│   ├── test_flow_control.py             # Flow control tests
│   ├── test_formula_extraction_contract.py  # Formula extraction tests
│   ├── test_gpu_fallback.py             # GPU fallback behavior tests
│   ├── test_hotkey_service_lifecycle.py # Hotkey service lifecycle tests
│   ├── test_hotkey_session.py           # Hotkey session tests
│   ├── test_incremental_output.py       # Incremental output tests
│   ├── test_mode_manager.py             # Mode manager tests
│   ├── test_model_catalog.py            # Model catalog tests
│   ├── test_refinement_queue.py         # Refinement queue tests
│   ├── test_refiner_service.py          # Refiner service tests
│   ├── test_repetition_guard.py         # Repetition guard tests
│   ├── test_runtime_log_levels.py       # Runtime logging level tests
│   ├── test_server_logging.py           # Server logging tests
│   ├── test_server_serialization.py     # Server serialization tests
│   ├── test_session_device_resolution.py # Session device resolution tests
│   ├── test_session_writer_contract.py  # Session writer contract tests
│   ├── test_settings_manager.py         # Settings manager tests
│   ├── test_sse_events.py               # Server-sent events tests
│   ├── test_stability.py                # Stability tests
│   ├── test_stream_event_contract.py    # Stream event contract tests
│   ├── test_stream_quality_contract.py  # Stream quality contract tests
│   ├── test_system_session.py           # System session tests
│   ├── test_utterance_aggregator.py     # Utterance aggregator tests
│   ├── test_vad_config.py               # VAD configuration tests
│   ├── test_vad_optimized.py            # Optimized VAD tests
│   └── test_windows_mvp_sanity.py       # Windows MVP sanity tests
│
├── integration/                     # Integration tests
│   ├── test_api_endpoints.py        # API endpoint integration tests
│   ├── test_file_io.py              # File I/O integration tests
│   ├── test_serialization.py        # Serialization integration tests
│   └── test_websocket.py            # WebSocket integration tests
│
├── unit/                            # Unit tests
│   ├── test_audio_pipeline.py       # Audio pipeline unit tests
│   ├── test_error_handler.py        # Error handler unit tests
│   ├── test_session_handler.py      # Session handler unit tests
│   ├── test_settings_manager.py     # Settings manager unit tests
│   ├── test_system_pipeline.py      # System pipeline unit tests
│   ├── test_transcription_engine.py # Transcription engine unit tests
│   └── test_vad.py                  # VAD unit tests
│
├── performance/                     # Performance tests
│   ├── test_concurrency.py          # Concurrency performance tests
│   ├── test_latency.py              # Latency performance tests
│   ├── test_memory.py               # Memory performance tests
│   └── test_throughput.py           # Throughput performance tests
│
└── support/                         # Test support utilities
    └── __init__.py
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

### Path Fixtures
- `project_root` - Project root directory
- `temp_dir` - Temporary directory for test files
- `test_data_dir` - Test data directory
- `mock_settings_file` - Mock settings file on disk

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

### Event Loop Fixtures
- `event_loop` - Event loop for async tests (session-scoped)
- `async_client` - Async HTTP client mock

### API Fixtures
- `mock_fastapi_app` - Mock FastAPI application
- `mock_websocket` - Mock WebSocket connection
- `mock_http_client` - Mock async HTTP client

### Error Handler Fixtures
- `mock_error_handler` - Mock error handler
- `mock_user_notifier` - Mock user notifier

### Utility Fixtures
- `async_context_manager_mock` - Factory for async context manager mocks
- `async_iterator_mock` - Factory for async iterator mocks
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
