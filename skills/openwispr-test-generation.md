# Test Generation Skill

## Purpose

Guide agents through generating tests for bug fixes and new features in OpenWispr. This skill ensures consistent, high-quality test coverage that follows project conventions.

Use this skill when:
- Adding new functionality to the codebase
- Fixing bugs that need regression protection
- Changing existing behavior that needs verification
- Modifying settings, configuration, or wiring
- Creating new services or components

## When NOT to Use

- Pure cosmetic changes (formatting, renaming variables without behavior change)
- Documentation-only updates
- Dependency updates that don't change behavior
- Changes that are purely additive without affecting existing behavior

## Discovery Steps

### 1. Find Existing Tests for Similar Functionality

Look in the `tests/` directory for tests related to the area being modified:

```
tests/
├── unit/                    # Unit tests for isolated logic
├── integration/             # Integration tests for cross-component behavior
├── performance/             # Performance benchmarks
├── test_*.py                # Contract, wiring, and regression tests
```

### 2. Identify Test Framework

OpenWispr uses:
- **pytest** as the test runner
- **pytest-asyncio** for async tests
- **unittest.mock** for mocking

Check `tests/conftest.py` for available fixtures.

### 3. Check Test Patterns in the Codebase

Review existing tests to understand conventions:

- Test naming: `test_<feature>_<expected_behavior>`
- Class-based tests for grouped assertions
- Use fixtures from `conftest.py` for common test data
- Async tests use `@pytest.mark.asyncio` decorator

### 4. Find Fixtures and Harnesses

Available fixtures in `tests/conftest.py`:

| Fixture | Purpose |
|---------|---------|
| `project_root` | Project root directory |
| `temp_dir` | Temporary directory for test files |
| `sample_rate` | Default audio sample rate (16000) |
| `mock_audio_data` | Mock silence audio (1 second) |
| `mock_speech_audio` | Mock speech-like audio |
| `mock_audio_devices` | Mock audio device list |
| `mock_whisper_model` | Mock Whisper transcription model |
| `test_settings` | Complete test settings dictionary |
| `mock_settings_manager` | Mock settings manager |
| `sample_segment` | Sample transcript segment |
| `sample_session_state` | Sample session state |
| `mock_websocket` | Mock WebSocket connection |
| `mock_vad` | Mock VAD instance |

## Test Type Selection

### Unit Tests

For isolated logic, pure functions, and class methods with no external dependencies.

**Location**: `tests/unit/`

**When to use**:
- Testing utility functions
- Testing class methods with mocked dependencies
- Testing data transformations
- Testing error handling paths

### Integration Tests

For cross-component behavior and real I/O operations.

**Location**: `tests/integration/`

**When to use**:
- Testing API endpoints
- Testing file I/O operations
- Testing serialization/deserialization
- Testing component interactions

### Wiring Tests

For settings/config flow and component wiring.

**Location**: `tests/test_settings_wiring_integration.py`

**When to use**:
- Settings changes propagating through layers
- Config generation and validation
- Frontend/backend settings contract

### Contract Tests

For API/IPC boundaries and external interfaces.

**Location**: `tests/test_*_contract.py`

**When to use**:
- Verifying API response formats
- Testing WebSocket event schemas
- Testing IPC message contracts
- Validating external API compatibility

### E2E Tests

For user journeys and full application flows.

**Location**: `e2e/` (Playwright)

**When to use**:
- Testing complete user workflows
- UI interaction testing
- Cross-browser testing
- Critical path validation

## Required Test Elements

### 1. Clear Test Name

Name tests to describe what is tested and expected outcome:

```python
def test_settings_wiring_propagates_language_to_transcription():
    """Verify language setting flows from config to transcription service."""

def test_transcript_segment_key_replacement():
    """Verify segments with same key are replaced, not duplicated."""
```

### 2. Arrange/Act/Assert Structure

```python
def test_feature_behavior():
    # Arrange - set up test data and mocks
    settings = {"language": "en", "model_name": "tiny"}
    
    # Act - perform the action being tested
    result = apply_settings(settings)
    
    # Assert - verify expected outcome
    assert result.language == "en"
```

### 3. Proper Cleanup in Teardown

Use fixtures for automatic cleanup:

```python
@pytest.fixture
def temp_settings_file(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{}")
    yield settings_file
    # Cleanup automatic via tmp_path
```

For manual cleanup:
```python
def test_with_manual_cleanup():
    resource = acquire_resource()
    yield resource
    resource.close()  # Teardown
```

### 4. Assertions That Verify Actual Behavior

**Good assertions** - test actual behavior:
```python
assert result.transcript == "expected text"
assert segments[0].id == "seg-001"
assert settings_manager.get_settings().language == "en"
```

**Bad assertions** - only verify execution:
```python
# Bad - doesn't verify outcome
process_audio(audio)
# Missing assertion

# Good - verifies outcome
transcript = process_audio(audio)
assert transcript.text == "hello world"
```

## Test Generation Workflow

### Step 1: Analyze the Change

1. Identify what code changed and why
2. Determine the affected components
3. Identify dependencies and mocks needed
4. Select appropriate test type(s)

### Step 2: Find Similar Tests

Look for existing tests in:
- Same directory as the feature
- Similar functionality elsewhere
- Contract tests for API boundaries

### Step 3: Write the Test

1. Use appropriate fixture from `conftest.py`
2. Follow naming conventions
3. Include docstring explaining what is tested
4. Structure with Arrange/Act/Assert
5. Add cleanup if needed

### Step 4: Run the Tests

```bash
# Run specific test file
pytest tests/test_my_feature.py -v

# Run specific test
pytest tests/test_my_feature.py::test_specific_case -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Run async tests
pytest tests/ -v --asyncio-mode=auto
```

### Step 5: Verify Quality

- Tests should pass consistently
- No flaky tests (intermittent failures)
- Assertions verify actual behavior
- Proper isolation between tests
- Clean teardown/cleanup

## Common Test Patterns in OpenWispr

### Testing Settings Wiring

```python
def test_settings_propagate_to_service():
    from app.config.settings import SETTINGS_REGISTRY
    
    settings_dict = {
        "transcription": {"model_name": "tiny", "language": "en"}
    }
    
    # Verify settings can be loaded and applied
    manager = SettingsManager(settings_file)
    settings = manager.get_settings()
    
    assert settings.transcription.model_name == "tiny"
```

### Testing Transcription

```python
@pytest.mark.asyncio
async def test_transcription_processes_audio(mock_whisper_model, mock_audio_data):
    engine = WhisperTranscriptionEngine()
    
    result = await engine.transcribe(mock_audio_data)
    
    assert result.text is not None
    assert len(result.segments) > 0
```

### Testing Audio Pipeline

```python
def test_audio_pipeline_routing(mock_audio_devices):
    pipeline = AudioPipeline()
    
    devices = pipeline.enumerate_devices()
    
    assert len(devices) == 3
    assert devices[0]["name"] == "Test Microphone"
```

## Verification Checklist

Before considering tests complete:

- [ ] Test file follows naming convention (`test_*.py`)
- [ ] Test name describes what is tested
- [ ] Uses existing fixtures from `conftest.py` when available
- [ ] Has proper Arrange/Act/Assert structure
- [ ] Assertions verify actual behavior, not just execution
- [ ] Cleans up resources in teardown
- [ ] Test passes when run with `pytest`
- [ ] No hardcoded paths or machine-specific values
- [ ] Follows project's mock patterns

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific category
pytest tests/unit/ -v
pytest tests/integration/ -v

# With markers
pytest tests/ -m "contract" -v
pytest tests/ -m "wiring" -v

# With coverage
pytest tests/ --cov=app --cov-report=term-missing

# Fast fail on first error
pytest tests/ -x

# Verbose output
pytest tests/ -vv -s
```
