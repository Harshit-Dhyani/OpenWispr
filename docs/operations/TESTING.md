# Transcripta Testing Guide

Complete guide for running automated and manual tests.

---

## Overview

Transcripta uses **Vitest** for unit testing and **Playwright** (optional) for E2E testing. This guide covers both approaches plus manual smoke testing.

---

## How to Run Unit Tests

### Run All Tests

```powershell
cd app/desktop/frontend
npm run test
```

### Run Tests in Watch Mode

```powershell
npm run test -- --watch
```

### Run Tests with Coverage

```powershell
npm run test -- --coverage
```

### Run Specific Test File

```powershell
npm run test -- src/lib/__tests__/settingsSchema.test.ts
```

### Run Tests Matching Pattern

```powershell
# Run all settings-related tests
npm run test -- settings

# Run all validation tests
npm run test -- validation
```

### Test Configuration

Tests are configured in `vitest.config.ts`:

```typescript
export default defineConfig({
  test: {
    environment: 'happy-dom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});
```

---

## How to Run Manual Smoke Tests

### Full Smoke Test (30 minutes)

Follow the complete checklist in [`VERIFICATION_CHECKLIST.md`](./VERIFICATION_CHECKLIST.md).

```powershell
# 1. Start backend
cd app
python -m uvicorn main:app --reload

# 2. In new terminal, start frontend
cd app/desktop/frontend
npm run dev

# 3. Run through VERIFICATION_CHECKLIST.md
```

### Quick Smoke Test (5 minutes)

For rapid verification before commits:

```powershell
cd app/desktop/frontend

# Run all automated checks
npm run typecheck
npm run lint
npm run test

# Manual checks:
# 1. Open app
# 2. Verify backend connected in diagnostics
# 3. Start session, verify audio meter moves
# 4. Speak, verify transcription appears
# 5. Export transcript
```

### Windows-Specific Testing

Test these Windows-specific features:

| Feature | Test | Expected |
|---------|------|----------|
| Global Hotkey | Press Ctrl+Shift+T | Recording starts |
| Minimize to Tray | Close window | Icon in system tray |
| Audio Devices | Test with multiple mics | Device switching works |
| File Export | Export to Documents folder | File appears |
| GPU | Test on NVIDIA/AMD/Intel | Model loads correctly |

---

## Debug Tips

### Enable Debug Mode

Set in `app/desktop/frontend/.env.local`:

```env
VITE_DEBUG=true
VITE_LOG_LEVEL=debug
```

Or in the app: Settings > Advanced > Debug Mode = ON

### View Logs

**Browser Console:**
- Press `Ctrl+Shift+I` to open DevTools
- Check Console tab for errors

**Backend Logs:**
```powershell
# Run backend with debug logging
cd app
$env:TRANSCRIPTA_LOG_LEVEL="DEBUG"
python -m uvicorn main:app --reload
```

**Session Logs:**
```powershell
# View session-specific logs
Get-Content sessions/<session-name>/logs/app.log -Wait
```

### Network Debugging

```powershell
# Test API endpoints
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/audio/devices"
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/models"
```

### Audio Pipeline Debugging

Add to `app/stt/fast_chunker.py`:

```python
print(f"[DEBUG] buffer={buffer.available}, chunk_size={adaptive_size}")
print(f"[DEBUG] vad_state={vad.state}, energy={energy_db}dB")
print(f"[DEBUG] chunks_created={len(chunks)}, samples_in_chunk={len(chunk.samples)}")
```

### VS Code Debugging

Add to `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Frontend",
      "type": "node",
      "request": "launch",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["run", "dev"],
      "cwd": "${workspaceFolder}/app/desktop/frontend"
    },
    {
      "name": "Debug Backend",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/app/main.py",
      "args": ["--reload"]
    }
  ]
}
```

### Common Debug Commands

```powershell
# Check if port is in use
Get-NetTCPConnection -LocalPort 8000

# Kill process on port
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process

# Check GPU status
nvidia-smi

# Monitor memory usage
while ($true) { Get-Process *python* | Select-Object Name, WorkingSet; Start-Sleep -Seconds 5 }
```

---

## Common Issues

### Issue: Tests Fail with "Module not found"

**Cause:** Missing dependencies or path issues

**Fix:**
```powershell
cd app/desktop/frontend
npm install
npm run test -- --clearCache
```

### Issue: "Cannot find module '@testing-library/react'"

**Fix:**
```powershell
npm install -D @testing-library/react @testing-library/jest-dom happy-dom
```

### Issue: Backend Connection Refused

**Symptoms:**
- Diagnostics shows "Backend Disconnected"
- Cannot start sessions

**Fix:**
```powershell
# 1. Check if backend is running
Invoke-RestMethod -Uri "http://localhost:8000/health"

# 2. If not running, start it
cd app
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 3. Check firewall settings
# Allow Python through Windows Defender Firewall
```

### Issue: GPU Not Detected

**Symptoms:**
- Diagnostics shows "CPU Only"
- Model loading is slow

**Fix:**
```powershell
# 1. Check CUDA is installed
nvidia-smi

# 2. Verify PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"

# 3. Install CUDA-enabled PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 4. For AMD/Intel, use DirectML
pip install torch-directml
```

### Issue: Audio Device Not Found

**Symptoms:**
- No devices in dropdown
- "No audio devices available" error

**Fix:**
```powershell
# 1. Check Windows audio devices
Get-PnpDevice -Class AudioEndpoint | Select-Object Name, Status

# 2. Restart Windows Audio service
Restart-Service -Name "Audiosrv" -Force

# 3. Check if microphone is default recording device
# Settings > System > Sound > Input
```

### Issue: Model Fails to Load

**Symptoms:**
- "Failed to load model" error
- Out of memory error

**Fix:**
```powershell
# 1. Check available VRAM
nvidia-smi

# 2. Use smaller model
# Settings > Transcription > Model = "small" or "base"

# 3. Use CPU instead
# Settings > Transcription > Compute Type = "int8"

# 4. Clear model cache
Remove-Item -Recurse -Force ~\.cache\whisper
```

### Issue: Transcription Delayed or Missing

**Symptoms:**
- Waveform shows activity but no text
- Segments appear after long delay

**Fix:**
```powershell
# 1. Check backend logs for errors
# 2. Verify VAD threshold is not too high
# Settings > Transcription > VAD Threshold = -40 dB

# 3. Disable VAD temporarily for testing
# Settings > Transcription > Enable VAD = OFF

# 4. Check confidence threshold
# Settings > Transcription > Confidence Threshold = 0.6
```

### Issue: Settings Not Persisting

**Symptoms:**
- Settings reset on app restart
- Changes not saved

**Fix:**
```powershell
# 1. Check localStorage in DevTools
# Application > Local Storage > http://localhost:5173

# 2. Clear and reset
localStorage.clear()

# 3. Check for schema version mismatch
# Settings are versioned, old versions may be rejected
```

### Issue: Hotkey Not Working

**Symptoms:**
- Ctrl+Shift+T does nothing
- Global hotkey doesn't register

**Fix:**
```powershell
# 1. Check hotkey is enabled
# Settings > Hotkey > Enable Global Hotkey = ON

# 2. Check for conflicts
# Windows may have reserved the hotkey

# 3. Change hotkey combination
# Settings > Hotkey > Key Combination = "Ctrl+Alt+T"

# 4. Run as administrator (may be required for global hotkeys)
```

### Issue: SSE Connection Drops

**Symptoms:**
- Transcription stops mid-session
- "Connection lost" errors

**Fix:**
```powershell
# 1. Increase timeout in backend
# app/config.py: SSE_TIMEOUT = 300

# 2. Check for proxy/firewall blocking SSE
# SSE uses long-lived connections that some proxies block

# 3. Add retry logic to frontend
# Already implemented in useEventSource.ts
```

---

## Test Data

### Sample Audio for Testing

```powershell
# Generate test audio file (requires ffmpeg)
ffmpeg -f lavfi -i "sine=frequency=1000:duration=5" test_audio.wav

# Use in mock mode by setting
$env:USE_MOCK_AUDIO="true"
$env:MOCK_AUDIO_FILE="test_audio.wav"
```

### Mock Session Data

```typescript
// Create test session for UI testing
const testSession = {
  id: 'test-session-001',
  title: 'Test Session',
  createdAt: new Date().toISOString(),
  status: 'recording',
  segments: [
    {
      id: 1,
      text: 'Hello, this is a test transcription.',
      startTime: 0,
      endTime: 3.5,
      confidence: 0.95,
    },
  ],
};
```

---

## CI/CD Testing

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          
      - name: Install dependencies
        run: |
          cd app/desktop/frontend
          npm ci
          
      - name: Run typecheck
        run: npm run typecheck
        
      - name: Run linter
        run: npm run lint
        
      - name: Run tests
        run: npm run test
```

---

## Additional Resources

- [Vitest Documentation](https://vitest.dev/)
- [Testing Library](https://testing-library.com/)
- [Playwright E2E Testing](https://playwright.dev/)
- [AGENTS.md](../AGENTS.md) - Project guidelines
