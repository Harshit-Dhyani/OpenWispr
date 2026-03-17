# Runtime Verification Skill

## Purpose

Verify that code changes work correctly at runtime, not just in tests. Use this skill for validating behavior that cannot be fully tested in the test suite.

Use this skill when:
- Making changes to audio pipeline, STT, or transcription behavior
- Modifying settings wiring or runtime behavior
- Changing provider integrations (Ollama, LM Studio, llama.cpp)
- Updating model management or loading
- Any change affecting user-facing functionality

## When NOT to Use

- Pure documentation changes
- Refactoring that doesn't change behavior
- Test-only changes
- Configuration changes that are testable

## Discovery Steps

1. Identify what type of change was made:
   - Audio pipeline changes → test microphone and system audio
   - Settings wiring → verify generated config and health endpoints
   - Provider integration → test provider connection and model loading
   - STT/transcription → run test transcription
2. Determine the local dev environment setup needed
3. Check for existing test patterns in similar areas

## Verification Methods

### 1. Local Dev Verification
```bash
npm run dev
```
- Start the app and test the feature manually
- Check for errors in console/backend logs

### 2. Backend Health Checks
```bash
curl http://127.0.0.1:8765/api/health
curl http://127.0.0.1:8765/api/providers/health
curl http://127.0.0.1:8765/api/devices
```

### 3. Provider Verification
- Test Ollama/LM Studio connections
- Verify model loading
- Check health endpoints

### 4. Audio Pipeline Tests
- Test microphone capture
- Test system audio capture
- Verify VAD behavior

### 5. Transcription Tests
- Run a test transcription
- Verify output quality
- Check refiner/coach behavior

## Common Runtime Issues

- Settings not wiring correctly
- Provider connection failures
- Audio device not found
- Model loading errors
- Memory/performance issues
- Race conditions not caught in tests

## Reporting

Document:
- What was tested
- Environment (OS, Python version, Node version)
- Any errors or unexpected behavior
- Whether the change was verified working
