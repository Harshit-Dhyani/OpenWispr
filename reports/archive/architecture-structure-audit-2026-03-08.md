# Architecture & Structure Audit Report - 2026-03-08

## Summary
134+ issues across API, Audio, STT, Electron, Frontend, Storage.

## API Issues (28) - P0

### API0-1: Settings Raw Dict
- **File**: app/api/routes/settings.py:22
- **Code**: `def save_settings(request: dict[str, Any])`
- **Fix**: Add Pydantic schema

### API0-2: Dictionary Unvalidated
- **File**: app/api/routes/dictionary.py:24-39
- **Code**: `str(request.get("phrase", ""))`
- **Fix**: Add validation

### API0-3: Snippets Unvalidated
- **File**: app/api/routes/snippets.py:84-93
- **Code**: `if not isinstance(payload, list):`
- **Fix**: Validate entries

### API0-4: Style Profile Unvalidated
- **File**: app/api/routes/style.py:25-39
- **Fix**: Add schema validation

### API0-5: Query Param Not Validated
- **File**: app/api/routes/system.py:66-73
- **Code**: `mode: str = Query("balanced")`
- **Fix**: Add enum validation

### API0-6: StartSessionRequest Missing Validation
- **File**: app/api/schemas.py:8-20
- **Fix**: Add length limits, path validation

### API0-7: PreloadModelRequest Missing Validation
- **File**: app/api/schemas.py:26-29
- **Fix**: Add model validation

### API0-8: History Query Missing Validation
- **File**: app/api/routes/history.py:13-38

### API0-9: HotkeyStopResponse Exposes Paths
- **File**: app/api/server.py:168-202
- **Code**: `debug_wav_path: str | None = None`

### API0-10: Session Response Exposes Settings
- **File**: app/api/routes/session.py:104-130
- **Code**: `"settings_snapshot": settings_snapshot`

### API0-11: Connection Stats Leak IPs
- **File**: app/api/websocket_server.py:633-650

### API0-12: Blocking Time Loop
- **File**: app/api/server.py:697-719
- **Code**: `while time.perf_counter() < deadline:`

### API0-13: Blocking time.sleep in Backend
- **File**: app/api/services/backend_service.py:256-344
- **Code**: `time.sleep(0.4)`

### API0-14: Sync time.time in Async
- **File**: app/api/server.py:2942,3017,3057,3084
- **Code**: `if time.time() - connection._last_pong >`

### API0-15: Async Callback Handling
- **File**: app/api/server.py:2117-2136

### API0-16: AttachPdfRequest No Path Validation
- **File**: app/api/schemas.py:22-24
- **Code**: `path: str` - no path traversal check

### API0-17: RefinementModeRequest No Enum
- **File**: app/api/schemas.py:36-37
- **Code**: `mode: str` - no enum constraint

### API0-18: ModelSelectionRequest No Validation
- **File**: app/api/schemas.py:31-34

### API0-19: HotkeyStartRequest Missing Constraints
- **File**: app/api/server.py:159-166

### API0-20: HotkeyConfigRequest Missing Validation
- **File**: app/api/server.py:249-257

### API0-21: History Download Asset Query
- **File**: app/api/routes/history.py:91-118
- **Code**: `asset: str = Query("transcript")` - no enum

### API0-22: Dictionary Preview Text
- **File**: app/api/routes/dictionary.py:72-78
- **Code**: `str(request.get("text", ""))` - no length limit

### API0-23: Snippets Preview Text
- **File**: app/api/routes/snippets.py:75-81
- **Code**: `str(request.get("text", ""))` - no length limit

### API0-24: Style Preview Text
- **File**: app/api/routes/style.py:91-101
- **Code**: `str(request.get("text", ""))` - no length limit

### API0-25: CORS Security Violation
- **File**: app/api/server.py:2218-2222
- **Code**: `allow_origins=["*"]` with `allow_credentials=True`

### API0-26: Hardcoded WebSocket Token
- **File**: app/api/websocket_server.py:197
- **Code**: `"valid_token"` hardcoded in production code

### API0-27: Bare Except Catches Everything
- **File**: app/core/performance_monitor.py:298
- **Code**: `except:` without specific exception type

### API0-28: WebSocket Auth Disabled
- **File**: app/api/websocket_server.py:92
- **Code**: `auth_required: bool = False` - auth disabled by default

## API Issues P1 (13 more)

### API1-1: Missing Rate Limiting
- **Files**: All route files

### API1-2: No Input Sanitization on Strings
- **Files**: Multiple route handlers

### API1-3: Error Messages Expose Internals
- **Files**: Multiple routes

### API1-4: Log Sanitization Incomplete
- **File**: app/api/route_utils.py:93-97

### API1-5: Missing Response Schema Documentation
- **Files**: app/api/routes/*.py

### API1-6: Error Responses Not Standardized
- **Files**: app/api/routes/*.py

### API1-7: Route/Service Boundary Blur
- **Files**: app/api/, app/api/services/

### API1-8: No Dependency Injection
- **Files**: app/api/routes/*.py

### API1-9: No Request ID Propagation
- **File**: app/api/server.py

### API1-10: File Upload No Size Limit
- **File**: app/api/routes/snippets.py

### API1-11: Streaming Response Inconsistency
- **Files**: app/api/routes/sessions.py

### API1-12: Missing API Versioning
- **File**: app/api/server.py

### API1-13: No Pagination
- **Files**: app/api/routes/dictionary.py, app/api/routes/snippets.py

## Audio Issues (22)

### AU0-1: Missing Exception in stop()
- **File**: app/audio/backends/pyaudio_wasapi.py:188-190

### AU0-2: No Exception in read()
- **File**: app/audio/backends/soundcard_backend.py:103-118

### AU0-3: Race Condition _running
- **File**: app/audio/backends/pyaudio_wasapi.py:51

### AU0-4: Race Condition _running
- **File**: app/audio/backends/soundcard_backend.py:41

### AU0-5: Unbounded _pre_buffer
- **File**: app/audio/wispr_pipeline.py:168

### AU0-6: Unbounded _pending_audio
- **File**: app/audio/wispr_pipeline.py:173

### AU0-7: Unbounded _current_segment
- **File**: app/audio/system_pipeline.py:247

### AU0-8: RingBuffer Silent Drop
- **File**: app/audio/system_pipeline.py:127-143

### AU0-9: _stream Race Condition
- **File**: app/audio/backends/pyaudio_wasapi.py:193-241

### AU0-10: _recorder Race Condition
- **File**: app/audio/backends/soundcard_backend.py:103-118

### AU0-11: No Exception in pyaudio read()
- **File**: app/audio/backends/pyaudio_wasapi.py:193-241

### AU0-12: Blocking Read Timeout
- **File**: app/audio/backends/pyaudio_wasapi.py:197-198

### AU0-13: Blocking Read Timeout
- **File**: app/audio/backends/soundcard_backend.py:106-107

### AU0-14: Empty Except Blocks
- **Files**: app/audio/backends/soundcard_backend.py:74, app/audio/capture.py:236,290

### AU0-15: Resource Leaks Not Handled
- **Files**: app/audio/backends/*.py

### AU0-16: Buffer Overflow Risk
- **File**: app/audio/capture.py

### AU0-17: Thread Safety Issues
- **Files**: app/audio/capture.py, app/audio/backends/

### AU0-18: No Audio Device Hotplug Handling
- **Files**: app/audio/backends/*.py

### AU0-19: Memory Leak in Audio Pipeline
- **File**: app/audio/capture.py

### AU0-20: Blocking Audio Operations
- **File**: app/audio/backends/soundcard_backend.py

### AU0-21: No Graceful Degradation
- **Files**: app/audio/backends/*.py

### AU0-22: Duplicate Backend Settings
- **File**: app/config/settings.py:472-489

## STT Issues (12)

### STT0-1: Unbounded _processing_times
- **File**: app/stt/engine.py:86

### STT0-2: Unprotected Segment Callbacks
- **File**: app/stt/fast_engine.py:487-488

### STT0-3: Unprotected Segment Callbacks
- **File**: app/stt/fast_engine.py:659-660

### STT0-4: Unprotected Segment Callbacks
- **File**: app/stt/streaming_engine.py:913-917

### STT0-5: Unprotected Segment Callbacks
- **File**: app/stt/engine.py:524-525

### STT0-6: Unprotected Partial Callbacks
- **File**: app/stt/fast_engine.py:490-495

### STT0-7: Unprotected Status Callbacks
- **File**: app/stt/engine.py:110-111

### STT0-8: Unprotected Health Callbacks
- **File**: app/stt/engine.py:550-551

### STT0-9: Error Callback Not Protected
- **File**: app/stt/engine.py:541-542

### STT0-10: Callback Memory Leak
- **File**: app/stt/

### STT0-11: Blocking Model Inference
- **Files**: app/stt/decoding/*.py

### STT0-12: No Transcription Timeout
- **Files**: app/stt/

## Electron Issues (22)

### E0-1: Unvalidated Text Injection
- **File**: app/electron/main/ipc/handlers.js:140

### E0-2: Unvalidated Hotkey Config
- **File**: app/electron/main/ipc/handlers.js:130

### E0-3: Unvalidated Quick Settings
- **File**: app/electron/main/ipc/handlers.js:232

### E0-4: Preload fetchJson Exposes API
- **File**: app/electron/main/preload/main.js:18-58

### E0-5: Hotkey Handler Missing Validation
- **File**: app/electron/main/ipc/hotkeyHandlers.js

### E0-6: Text Injector No Validation
- **File**: app/electron/main/services/textInjector.js:69-79

### E0-7: Tray Session Directory Traversal
- **File**: app/electron/main/windows/tray.js:16

### E0-8: Tray ReadFile No Error Handling
- **File**: app/electron/main/windows/tray.js:32-43

### E0-9: Floating Window Position No Validation
- **File**: app/electron/main/windows/floatingWindow.js:47-60

### E0-10: Floating Window Persist No Error Handling
- **File**: app/electron/main/windows/floatingWindow.js:63-76

### E0-11: Model Download Manager No Path Validation
- **File**: app/electron/main/services/modelDownloadManager.js

### E0-12: Model Cancel No Validation
- **File**: app/electron/main/ipc/handlers.js:188

### E0-13: Model Remove No Validation
- **File**: app/electron/main/ipc/handlers.js:199

### E0-14: Quick Settings Get No Error Handling
- **File**: app/electron/main/ipc/handlers.js:216-230

### E0-15: Main Window State Not Validated
- **File**: app/electron/main/shared/state.js

### E0-16: Floating Action No Validation
- **File**: app/electron/main/ipc/handlers.js:260-298

### E0-17: Clipboard Write No Error Handling
- **File**: app/electron/main/services/textInjector.js:56

### E0-18: Memory Leak in Window Management
- **File**: app/electron/main/

### E0-19: Tray Reopen Dead Window
- **File**: app/electron/main/

### E0-20: No Context Isolation
- **File**: app/electron/main/

### E0-21: Sandbox Disabled
- **File**: app/electron/main/

### E0-22: Node Integration in Renderer
- **File**: app/electron/main/

## Frontend Issues (10+)

### F0-1: Unsafe any Casting
- **File**: app/electron/frontend/src/App.tsx:166,483,642

### F0-2: Inline Arrow Functions
- **File**: app/electron/frontend/src/pages/SnippetsPage.tsx:140,146,165

### F0-3: Settings Migration Type Safety
- **File**: app/electron/frontend/src/lib/settingsMigration.ts

### F0-4: Settings Schema Drift
- **File**: app/electron/frontend/src/config/generated/settings.ts

### F0-5: API Response Type Safety
- **File**: app/electron/frontend/src/types/api.ts

### F0-6: Event Handler Memory Leak Risk
- **File**: app/electron/frontend/src/App.tsx

### F0-7: Model Registry State Management
- **File**: app/electron/frontend/src/lib/modelRegistry.ts

### F0-8: Session Reducer Not Tested
- **File**: app/electron/frontend/src/lib/sessionReducer.ts

### F0-9: Live Transcript State Isolation
- **File**: app/electron/frontend/src/lib/liveTranscript.ts

### F0-10: WebSocket Reconnection Logic
- **File**: app/electron/frontend/src/hooks/useWebSocket.ts

### F0-11: EventSource Reconnection
- **File**: app/electron/frontend/src/hooks/useEventSource.ts

### F0-12: Backend Request Error Handling
- **File**: app/electron/frontend/src/api/settings.ts

## Storage Issues (18)

### ST0-1: Unsafe Schema Version Parsing
- **File**: app/storage/migrations.py:136

### ST0-2: Non-idempotent Close
- **File**: app/storage/history_db.py:77-79

### ST0-3: Path Traversal Risk
- **File**: app/storage/document_store.py:12-16

### ST0-4: Session Writer No Atomic Write
- **File**: app/storage/session_store.py:80-88

### ST0-5: Session Append No Error Recovery
- **File**: app/storage/session_store.py:25-39

### ST0-6: JSONL Append Not Synchronized
- **File**: app/storage/session_store.py:30-33

### ST0-7: Transcript Text Write Not Atomic
- **File**: app/storage/session_store.py:35-39

### ST0-8: Notes Append Not Synchronized
- **File**: app/storage/session_store.py:57-63

### ST0-9: Session Document No Cleanup
- **File**: app/storage/document_store.py

### ST0-10: History DB WAL Not Checked
- **File**: app/storage/history_db.py:25

### ST0-11: History DB Migration No Backup
- **File**: app/storage/migrations.py

### ST0-12: History Query No Pagination
- **File**: app/api/routes/history.py:13-38

### ST0-13: History Delete Not Cascading
- **File**: app/storage/history_db.py

### ST0-14: Style Profile JSON Not Validated
- **File**: app/storage/session_store.py:50

### ST0-15: Settings Snapshot JSON Size
- **File**: app/api/routes/session.py:127

### ST0-16: Transcript Segment JSON Size
- **File**: app/storage/session_store.py:28

### ST0-17: Database Connection Pool Not Configured
- **File**: app/storage/history_db.py

### ST0-18: Query Parameterization Missing
- **File**: app/storage/history_db.py

## Quick Wins
1. Fix CORS + hardcoded token + bare except (security)
2. Remove duplicate settings and deprecated VAD
3. Add proper error handling to audio except blocks
4. Fix IPC validation in Electron
5. Add input validation to API routes
6. Fix path traversal in storage
7. Remove fake settings from UI

## Done-When
- [ ] All P0 issues fixed
