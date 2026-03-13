# Test Generation Guide

Use this guide when creating tests for OpenWispr.

---

## TEST STRUCTURE

### Location
- Python tests: `tests/`
- E2E tests: `e2e/`
- Frontend tests: `app/electron/frontend/src/components/__tests__/`

### Naming Convention
- `test_<module>_<function>.py` for unit tests
- `test_<workflow>_integration.py` for integration tests
- `<Component>.test.tsx` for React component tests

---

## WHEN TO TEST

### Must Have Tests
- Bug fixes (regression tests)
- New features
- API contracts
- Settings serialization
- IPC handlers
- WebSocket message flow
- Audio capture logic

### Nice to Have
- Utility functions (if complex)
- Edge cases
- Error paths

---

## TEST PATTERNS

### Unit Test Pattern
```python
def test_function_name_given_condition_then_result():
    """Description of what is being tested"""
    # Given
    input_data = create_test_data()
    
    # When
    result = function_under_test(input_data)
    
    # Then
    assert result == expected_output
    assert result.property == expected_value
```

### Integration Test Pattern
```python
def test_api_endpoint_flow():
    """Test complete API flow"""
    with TestClient(app) as client:
        # Given
        payload = {"key": "value"}
        
        # When
        response = client.post("/api/endpoint", json=payload)
        
        # Then
        assert response.status_code == 200
        assert response.json()["result"] == expected
```

### E2E Test Pattern
```python
def test_dictation_workflow():
    """Test full dictation workflow"""
    # Start app in test mode
    with run_app_test_instance() as app:
        # Given: App running with test audio
        inject_test_audio("test_audio.wav")
        
        # When: Trigger dictation
        trigger_hotkey()
        
        # Then: Verify transcript
        wait_for_transcript()
        assert get_transcript() == expected_text
```

---

## TESTING AREAS

### Backend/API
- `app/api/server.py` - Route handlers
- `app/api/websocket_server.py` - WebSocket messages
- `app/api/settings_sync.py` - Settings sync

### Core
- `app/core/settings_manager.py` - Settings loading
- `app/core/model_catalog.py` - Model selection

### STT
- `app/stt/streaming_engine.py` - Stream processing
- `app/stt/utterance_aggregator.py` - Aggregation
- `app/stt/quality.py` - Quality scoring

### Storage
- `app/storage/session_store.py` - Persistence

---

## MOCKING

### Common Mocks
```python
from unittest.mock import Mock, patch

@patch('app.stt.model_pool.ModelPool.load_model')
def test_with_mocked_model(mock_load):
    mock_load.return_value = Mock(predict=mock_predict)
    # Test code here
```

### Fixtures (in `tests/conftest.py`)
```python
@pytest.fixture
def test_settings():
    return SettingsState(
        model_name="test-model",
        language="en",
        # ... other fields
    )
```

---

## VERIFICATION

### Before Submitting
```bash
# Run affected tests
pytest tests/path/to/test_file.py -v

# Run full suite (if change is significant)
pytest tests/ -v

# Check coverage
pytest tests/ --cov=app --cov-report=term-missing

# Lint
ruff check tests/
```

---

## DONE CRITERIA

- [ ] Test follows naming convention
- [ ] Test has clear docstring
- [ ] Uses Given/When/Then structure
- [ ] Tests actual behavior, not implementation
- [ ] Includes edge cases
- [ ] All tests pass
- [ ] No lint errors

---

## RESOURCES

- Test commands: See `pyproject.toml` and `package.json`
- Fixtures: `tests/conftest.py`
- Fixtures: `e2e/conftest.py`
- Frontend testing: React Testing Library patterns
