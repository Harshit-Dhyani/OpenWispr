---
title: Testing Guide
audience: developers
last_verified: 2026-03-04  # Verified by Sub-Agent 16
source_of_truth:
  - tests/conftest.py
  - tests/unit/
  - tests/integration/
  - e2e/
  - app/electron/frontend/vitest.config.ts
---

## Overview

Transcripta uses a multi-layered testing strategy covering Python backend tests (unit, integration, regression) and TypeScript/React frontend tests.

## Test Structure

```
tests/
├── conftest.py              # Shared pytest fixtures
├── unit/                    # Unit tests
│   ├── test_vad.py
│   ├── test_audio_pipeline.py
│   ├── test_session_handler.py
│   ├── test_settings_manager.py
│   ├── test_transcription_engine.py
│   ├── test_system_pipeline.py
│   └── test_error_handler.py
├── integration/             # Integration tests
│   ├── test_api_endpoints.py
│   ├── test_websocket.py
│   ├── test_file_io.py
│   └── test_serialization.py
├── performance/             # Performance benchmarks
├── test_*.py                # 35 regression & contract tests (root level)
│   # Key test files include:
│   # - test_hotkey_service_lifecycle.py, test_hotkey_session.py
│   # - test_system_session.py, test_system_pipeline.py
│   # - test_refiner_service.py, test_refinement_queue.py
│   # - test_audio_pipelines.py, test_vad_optimized.py
│   # - test_sse_events.py, test_stream_event_contract.py
│   # - test_server_serialization.py, test_deterministic_postprocess.py
│   # - test_coach_service.py, test_mode_manager.py
│   # - test_model_catalog.py, test_gpu_fallback.py
│   # - test_error_handling.py, test_stability.py
│   # - test_fixes.py (regression tests), test_windows_mvp_sanity.py
│   # And 17 more contract/integration tests...
└── README.md                # Backend test documentation

e2e/                         # End-to-end tests
├── conftest.py              # E2E fixtures (Electron, audio gen)
├── test_hotkey_mode.py
├── test_system_mode.py
└── test_models_flow.py

app/electron/frontend/
├── src/components/__tests__/ # Component tests
│   ├── App.test.tsx
│   ├── SettingsPanel.test.tsx
│   ├── Sidebar.test.tsx
│   ├── FloatingWindow.test.tsx
│   ├── ActivityFeed.test.tsx
│   └── MainContentCoach.test.tsx
├── src/test/
│   ├── setup.ts              # Test setup
│   └── factories.ts          # Mock factories
└── vitest.config.ts          # Vitest configuration
```

## Running Tests

### Backend Tests

#### All Tests
```bash
pytest
```

#### Unit Tests Only
```bash
pytest tests/unit/ -v
```

#### Integration Tests
```bash
pytest tests/integration/ -v
```

#### Regression Tests (Root Level)
```bash
pytest tests/test_*.py -v
```

#### With Coverage
```bash
pytest --cov=app --cov-report=html
```

#### Exclude Slow Tests
```bash
pytest -m "not slow"
```

#### Run Specific Marker
```bash
pytest -m unit -v
pytest -m integration -v
pytest -m performance -v
pytest -m benchmark -v
```

### E2E Tests

```bash
# Run all E2E tests
pytest e2e/ -v

# Headless mode
E2E_HEADLESS=true pytest e2e/ -v

# Keep test data for debugging
E2E_KEEP_DATA=true pytest e2e/test_hotkey_mode.py -v

# Parallel execution
E2E_PARALLEL=true pytest e2e/ -v -n auto
```

### Frontend Tests

```bash
cd app/electron/frontend

# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run in watch mode
npm run test:watch

# Run specific test
npm test -- App.test.tsx

# Run with UI
npm run test:ui

# Debug mode
npm run test:debug

# Integration tests only
npm run test:integration

# Unit tests only (excludes integration)
npm run test:unit
```

## Test Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.unit` | Unit tests - fast, isolated |
| `@pytest.mark.integration` | Integration tests - API, I/O |
| `@pytest.mark.slow` | Slow tests (exclude for quick runs) |
| `@pytest.mark.performance` | Performance tests |
| `@pytest.mark.benchmark` | Benchmark tests |
| `@pytest.mark.e2e` | E2E tests (auto-added for e2e/*) |
| `@pytest.mark.flaky` | Potentially flaky tests |
| `@pytest.mark.hotkey` | Hotkey mode E2E tests |
| `@pytest.mark.system` | System mode E2E tests |

## Key Fixtures

### Audio Fixtures (`conftest.py`)

```python
mock_audio_data      # 1 second silence (np.zeros)
mock_speech_audio    # Speech-like audio with harmonics
mock_noisy_audio     # White noise audio
mock_audio_chunk     # 100ms audio chunk
mock_audio_devices   # List of mock device dicts
sample_rate          # Default 16000
```

### Model Fixtures

```python
mock_whisper_model   # Mock WhisperModel with transcribe()
mock_whisper_segments # List of 3 mock segments
mock_torch           # PyTorch with GPU available
mock_torch_cpu       # PyTorch CPU-only
mock_torch_oom       # PyTorch simulating OOM
```

### Device Fixtures

```python
mock_sounddevice     # Mock sounddevice module
mock_soundcard       # Mock soundcard module
mock_pyaudio         # Mock PyAudio module
mock_recorder        # Mock audio recorder context manager
```

### Settings Fixtures

```python
test_settings        # Complete settings dict
mock_settings_manager # Mock SettingsManager instance
mock_settings_file   # JSON settings file on disk
```

### Session Fixtures

```python
sample_segment       # Sample transcript segment dict
sample_session_state # Sample session state dict
mock_session_writer  # Mock SessionWriter
```

### API Fixtures

```python
mock_fastapi_app     # Mock FastAPI app
mock_websocket       # Mock WebSocket connection
async_client         # Mock async HTTP client
mock_http_client     # Mock aiohttp client
```

### VAD Fixtures

```python
mock_vad             # Mock OptimizedVAD instance
mock_vad_config      # VAD configuration dict
```

### Performance Fixtures

```python
performance_tracker  # Factory for PerformanceMetrics
benchmark_config     # Benchmark thresholds dict
```

### E2E Fixtures (`e2e/conftest.py`)

```python
e2e_config           # E2EConfig (headless, video, etc.)
audio_generator      # AudioTestDataGenerator
test_audio_files     # Dict of generated WAV files
test_session         # TestSession (temp dir, metrics)
electron_app         # Running ElectronAppController
mock_stt_engine      # MockSTTEngine for injection
api_client           # APIClient for HTTP requests
```

## Test Patterns

### Backend Unit Test Pattern

```python
class TestFeatureName:
    """Tests for FeatureName."""

    def test_specific_behavior(self, mock_dependency) -> None:
        """Test that specific behavior works."""
        # Arrange
        instance = FeatureName()
        
        # Act
        result = instance.method()
        
        # Assert
        assert result.expected_value == actual_value
```

### Async Test Pattern

```python
import pytest

@pytest.mark.asyncio
async def test_async_feature(async_client) -> None:
    """Test async functionality."""
    result = await async_client.get('/api/endpoint')
    assert result['status'] == 'ok'
```

### Mock Patch Pattern

```python
def test_with_patching(self) -> None:
    """Test using context manager patches."""
    with patch('app.module.function') as mock_func:
        mock_func.return_value = MagicMock(data='test')
        result = function_under_test()
        assert result == expected
```

### E2E Test Pattern

```python
import pytest

@pytest.mark.e2e
@pytest.mark.hotkey
async def test_hotkey_recording(electron_app, api_client) -> None:
    """Test hotkey recording flow."""
    # Start session
    response = await api_client.start_hotkey_session()
    assert response['status'] == 'recording'
    
    # Wait for condition
    assert await async_wait_for_condition(
        lambda: check_state(), timeout=5.0
    )
    
    # Stop session
    result = await api_client.stop_hotkey_session()
    assert 'text' in result
```

### Frontend Test Pattern

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';

describe('ComponentName', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.transcriptaDesktop.fetchJson.mockResolvedValue({});
  });

  it('renders correctly', async () => {
    await act(async () => {
      render(<ComponentName />);
    });
    expect(screen.getByText('Expected')).toBeInTheDocument();
  });
});
```

## Frontend Mock Factories

Located in `app/electron/frontend/src/test/factories.ts`:

```typescript
createMockSettings(overrides?)    // Settings object
createMockSnapshot(overrides?)    // Session snapshot
createMockSegment(overrides?)     // Transcript segment
createMockDevice(overrides?)      // Audio device
MOCK_DEVICES                       // Array of mock devices
MOCK_MODELS                        // Array of mock models
```

## Configuration

### pytest (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "-v",
    "--tb=short",
]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "performance: marks tests as performance tests",
    "benchmark: marks tests as benchmarks",
]
asyncio_mode = "auto"
```

### Vitest (vitest.config.ts)

```typescript
{
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      thresholds: {
        branches: 80,
        functions: 80,
        lines: 80,
        statements: 80,
      },
    },
    testTimeout: 10000,
    retry: 2,
  }
}
```

## Flaky Test Playbook

### 1. Identify Flakiness

```bash
# Run test multiple times
pytest tests/test_file.py::test_name -v --count=10

# With different seeds
pytest tests/test_file.py --randomly-seed=1234
```

### 2. Common Causes & Fixes

**Timing Issues:**
```python
# Bad: Fixed sleep
time.sleep(1)

# Good: Wait for condition
assert wait_for_condition(lambda: check(), timeout=5.0)

# Async: Use wait_for
await wait_for(async_check, timeout=5.0)
```

**State Leakage:**
```python
# Use autouse fixtures for cleanup
@pytest.fixture(autouse=True)
def reset_state():
    yield
    cleanup_state()

# Or use reset_singletons fixture
@pytest.fixture(autouse=True)
def reset_singletons():
    with patch("app.core.settings_manager._settings_manager", None):
        yield
```

**Resource Conflicts:**
```python
# Use unique temp directories
@pytest.fixture
def temp_test_dir(request) -> Path:
    test_name = request.node.name.replace("[", "_").replace("]", "_")
    temp_dir = tempfile.mkdtemp(prefix=f"test_{test_name}_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)
```

**Async Race Conditions:**
```python
# Use proper async fixtures
@pytest_asyncio.fixture
async def async_resource():
    resource = await create()
    yield resource
    await resource.cleanup()
```

### 3. Mark and Retry

```python
@pytest.mark.flaky(reruns=3)
def test_sometimes_fails():
    ...
```

### 4. Debug Flaky Tests

```bash
# Run with detailed output
pytest test_file.py -v --tb=long --capture=no

# With logging
pytest test_file.py --log-cli-level=DEBUG

# Isolated process
pytest test_file.py --forked
```

### 5. E2E Specific

```bash
# Run headless for CI consistency
E2E_HEADLESS=true pytest e2e/

# Keep artifacts on failure
E2E_KEEP_DATA=true pytest e2e/

# Disable video/screenshots for speed
E2E_RECORD_VIDEO=false E2E_SCREENSHOTS=false pytest e2e/
```

## Debugging Tips

### Backend

```python
# Add breakpoint
import pytest; pytest.set_trace()

# Or use pdb
import pdb; pdb.set_trace()

# Run with debugger
pytest --pdb test_file.py
```

### Frontend

```bash
# Debug mode
npm test -- --reporter=verbose

# Single file with UI
npm test -- App.test.tsx --ui
```

## CI/CD Integration

Tests run with:
- Strict markers and config checking
- Verbose output
- Short traceback format
- Auto async mode
- Coverage reporting (80% threshold for frontend)

Quick validation: `pytest -m "not slow"`
Full suite: `pytest`
E2E: `pytest e2e/`
