# Transcripta UI Verification Checklist

Manual smoke test plan with detailed test procedures for pre-release validation.

---

## Pre-flight Checks

Verify environment is ready before testing.

### Environment Setup

| Step | Check | Command/Action | Expected Result |
|------|-------|----------------|-----------------|
| 1 | Node modules installed | `cd app/desktop/frontend && npm install` | No errors, node_modules exists |
| 2 | Dependencies up to date | `npm audit` | 0 high/critical vulnerabilities |
| 3 | TypeScript compiles | `npm run typecheck` | No errors |
| 4 | Linter passes | `npm run lint` | No errors or warnings |
| 5 | Unit tests pass | `npm run test` | All tests green |
| 6 | Backend running | `curl http://localhost:8000/health` | Returns `{"status":"healthy"}` |
| 7 | GPU available (optional) | `nvidia-smi` | Shows GPU with VRAM available |

**Quick Pre-flight Command:**
```powershell
cd app/desktop/frontend
npm install && npm run typecheck && npm run lint && npm run test
```

---

## Layout Tests

Test responsive layout at different viewport sizes.

### Wide Viewport (1920x1080)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open app at 1920x1080 | Main layout loads with sidebar visible |
| 2 | Check sidebar | Shows navigation icons + labels |
| 3 | Check main content area | Takes 80%+ of width |
| 4 | Check session panel | Properly sized, no overflow |
| 5 | Resize to 1600px width | Layout adapts, sidebar still expanded |
| 6 | Open Settings modal | Renders correctly without clipping |
| 7 | Open Diagnostics panel | All metric cards visible in grid layout |

### Medium Viewport (1366x768)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Resize to 1366x768 | Layout adapts gracefully |
| 2 | Check sidebar | May collapse to icons-only |
| 3 | Check transcription list | Scrollable, no horizontal overflow |
| 4 | Check settings modal | Fits within viewport |
| 5 | Open all settings tabs | Each tab accessible and usable |

### Small Viewport (1024x600)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Resize to 1024x600 | Mobile-style layout activates |
| 2 | Check sidebar | Collapsed to bottom or hamburger menu |
| 3 | Check controls | Buttons remain tappable (min 44px) |
| 4 | Scroll main content | Smooth, no clipped elements |
| 5 | Open settings | Modal takes full screen or max-width |

### Test Procedure

```powershell
# Start dev server
cd app/desktop/frontend
npm run dev

# Manually resize Electron window or use browser DevTools device emulation
# Test at: 1920x1080, 1366x768, 1024x600, 768x1024 (tablet)
```

---

## Settings Tests

Verify settings persistence, validation, and reset functionality.

### Change Settings

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open Settings (Ctrl+,) | Settings modal opens |
| 2 | Change Theme to "Dark" | UI immediately updates to dark theme |
| 3 | Change Model to "small" | Model selection updates with change indicator |
| 4 | Change Chunk Duration to 2.0s | Slider shows 2.0s |
| 5 | Change VAD Threshold to -35 dB | Value updates |
| 6 | Click Save | Modal closes, toast shows "Settings saved" |
| 7 | Close and reopen app | Settings persist (dark theme, small model) |

### Persist Settings

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Make multiple changes | Change theme, model, VAD threshold |
| 2 | Verify change indicators | Each modified field shows indicator |
| 3 | Click Save | Success toast appears |
| 4 | Check localStorage | `transcripta-settings` key exists with changes |
| 5 | Refresh browser | Settings persist |
| 6 | Verify all categories | General, Transcription, Audio, Hotkey, Advanced |

### Reset Settings

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Change theme to "Dracula" | Theme changes to Dracula |
| 2 | Click "Reset to Defaults" | Confirmation dialog appears |
| 3 | Confirm reset | All values reset to defaults |
| 4 | Verify theme | Returns to "light" theme |
| 5 | Click Save | Settings saved as defaults |
| 6 | Refresh and verify | Settings remain at defaults |

### Settings Validation

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Set auto-save interval to 5 | Validation error: "Must be at least 10" |
| 2 | Set auto-save interval to 400 | Validation error: "Must be at most 300" |
| 3 | Set confidence threshold to 1.5 | Validation error: "Must be at most 1" |
| 4 | Set VAD threshold to -10 | Validation error: "Must be at most -20" |
| 5 | Clear session title | Validation error: "Required" |
| 6 | Try to save with errors | Save button disabled or errors shown |

---

## Audio Tests

Verify audio capture and visualization.

### Audio Meter

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open Diagnostics (Ctrl+Shift+D) | Diagnostics panel opens |
| 2 | Check audio meter | Shows current input level |
| 3 | Make noise near microphone | Meter jumps with audio |
| 4 | Be silent | Meter shows low/no activity |
| 5 | Check dB value | Matches audio level (-60 to 0 dB) |

### Waveform Visualization

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Start test session | Session begins |
| 2 | Speak into microphone | Waveform animates with speech |
| 3 | Pause speaking | Waveform shows flat line |
| 4 | Resume speaking | Waveform resumes animation |
| 5 | Stop session | Waveform resets to idle state |

### Real vs Simulated Audio

| Mode | Test | Expected Result |
|------|------|-----------------|
| Real | Connect microphone, start session | Waveform shows actual audio patterns |
| Real | Disconnect microphone mid-session | Error: "Audio device lost" |
| Simulated | Set `USE_MOCK_AUDIO=true` in .env | Waveform shows synthetic sine wave |
| Simulated | Start with no device | Session starts, shows demo waveform |

### Debug Audio Pipeline

```powershell
# Check audio devices are detected
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/audio/devices"

# Expected response:
# {
#   "devices": [
#     { "id": "default", "name": "Default Microphone", "isDefault": true }
#   ]
# }
```

---

## Session Tests

Verify full transcription session lifecycle.

### Start Session

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "New Session" button | Create session dialog opens |
| 2 | Enter title "Test Session" | Title field populated |
| 3 | Click "Start Recording" | Session starts, recording indicator shows |
| 4 | Check status bar | Shows "Recording..." with timer |
| 5 | Check waveform | Active animation |
| 6 | Verify SSE connection | Network tab shows `/api/stream` connection |

### Transcription Flow

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Start session and speak | "Hello, this is a test" |
| 2 | Wait 2-3 seconds | Transcript appears in panel |
| 3 | Check segment format | Shows timestamp + text |
| 4 | Speak again | New segment added |
| 5 | Check confidence | Each segment has confidence indicator |
| 6 | Test STEM detection | Speak "E equals mc squared" - formula badge appears |

### Stop Session

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | While recording, click Stop | Recording stops, session saved |
| 2 | Check status | Shows "Session Complete" |
| 3 | Check transcript | Full transcript displayed |
| 4 | Click Export | Export options shown (TXT, JSON, SRT) |
| 5 | Export to TXT | File saved with transcript content |
| 6 | Verify SSE closed | Network tab shows connection closed |

### Keyboard Shortcuts

| Shortcut | Action | Expected Result |
|----------|--------|-----------------|
| Ctrl+N | New Session | Create session dialog opens |
| Ctrl+R | Start/Stop Recording | Toggles recording state |
| Ctrl+S | Save Session | Saves current session |
| Ctrl+Shift+D | Open Diagnostics | Diagnostics panel opens |
| Ctrl+, | Open Settings | Settings modal opens |

---

## Diagnostics Tests

Verify diagnostics panel shows accurate data and handles failures gracefully.

### Show Real Data

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open Diagnostics (Ctrl+Shift+D) | Panel opens |
| 2 | Check backend status | Shows "Connected" with green indicator |
| 3 | Check GPU info | Shows GPU name, VRAM, utilization |
| 4 | Check model status | Shows loaded model or "Not loaded" |
| 5 | Check session metrics | Shows segments/minute, latency |
| 6 | Check audio stats | Shows buffer depth, chunk count |
| 7 | Click refresh | Metrics update within 2 seconds |

### Handle Backend Down

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | With app running, stop backend | Kill Python process |
| 2 | Check diagnostics | Shows "Backend Disconnected" in red |
| 3 | Check error message | Shows "Connection failed to localhost:8000" |
| 4 | Try to start session | Error: "Backend unavailable" |
| 5 | Observe retry behavior | Retry count increments with backoff |
| 6 | Restart backend | Status updates to "Connected" |
| 7 | Resume operation | Can start new session |

### Degraded Mode

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Block SSE in DevTools | Connection fails |
| 2 | Check fallback | Falls back to polling mode |
| 3 | Check status indicator | Shows "degraded" with warning color |
| 4 | Verify polling | Periodic requests to `/api/session` |

---

## Post-Smoke Checklist

After completing all tests, verify:

- [ ] No console errors during testing
- [ ] No memory leaks (check Task Manager)
- [ ] Settings persisted correctly
- [ ] No zombie Python processes
- [ ] Log files contain expected entries
- [ ] Session exports work correctly

### Sign-off

| Date | Tester | Version | Result | Notes |
|------|--------|---------|--------|-------|
| | | | ⬜ Pass / ⬜ Fail | |

### Critical Issues Found

<!-- List any blocking issues here -->

1. 
2. 
3. 

### Minor Issues Found

<!-- List non-blocking issues here -->

1. 
2. 
3. 

---

## Quick Smoke Test (5 minutes)

For rapid verification, run these critical tests only:

- [ ] Pre-flight checks pass
- [ ] App opens without errors
- [ ] Change theme (light -> dark)
- [ ] Open diagnostics, verify backend connected
- [ ] Start session, verify waveform moves
- [ ] Speak 5 seconds, verify transcript appears
- [ ] Stop session, verify saved
- [ ] Export transcript

**All checks pass = Ready for use**

---

## Regression Test Suite (15 minutes)

Run through all tests in this document marked with high priority:

1. Pre-flight checks (all)
2. Layout tests (wide, medium viewports)
3. Settings tests (change, persist, reset)
4. Audio tests (meter moves, waveform real vs simulated)
5. Session tests (start, transcribe, stop)
6. Diagnostics tests (show real data, handle backend down)
