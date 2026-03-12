# Security Audit Report - 2026-03-08

## Verification Update - 2026-03-09
- Scope reviewed: `app/api/server.py`, `app/api/websocket_server.py`, `app/core/performance_monitor.py`, `tests/test_report_verified_fixes_wave2.py`
- Status counts for items verified in this pass: `completed=3`, `superseded=1`, `still-open=1`
- Validation: `pytest tests/test_report_verified_fixes_wave2.py -q`, `python -m py_compile app/api/server.py app/api/websocket_server.py app/core/performance_monitor.py`

## Summary
15 verified security issues found.

## P0 - Must Fix (5 issues)

### S0-1: CORS Misconfiguration
- **Status**: completed (2026-03-09)
- **Evidence**: `allow_credentials=False` now matches wildcard origin usage in `app/api/server.py`; covered by `tests/test_report_verified_fixes_wave2.py`.
- **File**: app/api/server.py
- **Line**: 2218-2222
- **Code**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
- **Why**: Cannot have "*" origins with credentials - browser security violation
- **Fix**: Restrict to known origins or remove credentials

### S0-2: Hardcoded WebSocket Token
- **Status**: completed (2026-03-09)
- **Evidence**: hardcoded token removed; authenticated mode now uses `OPENWISPR_WS_TOKEN`, and unauthenticated fallback is loopback-only in `app/api/websocket_server.py`.
- **File**: app/api/websocket_server.py
- **Line**: 197
- **Code**: `if token == "valid_token":`
- **Why**: Anyone can authenticate with this token
- **Fix**: Implement proper token validation

### S0-3: Bare Except Clause
- **Status**: completed (2026-03-09)
- **Evidence**: `app/core/performance_monitor.py` now uses `except Exception:`.
- **File**: app/core/performance_monitor.py
- **Line**: 298
- **Code**: `except:`
- **Why**: Catches KeyboardInterrupt, SystemExit
- **Fix**: Use `except Exception:`

### S0-4: Path Traversal Risk
- **File**: app/storage/document_store.py
- **Line**: 12-13
- **Code**: `file_path = Path(path).expanduser().resolve()`
- **Why**: No directory containment validation
- **Fix**: Validate path is within allowed directory

### S0-5: WebSocket Auth Disabled
- **Status**: superseded (2026-03-09)
- **Evidence**: the current safe desktop contract is loopback-only unauthenticated access plus `OPENWISPR_WS_TOKEN` for non-local clients, not a blanket `auth_required=True` default.
- **File**: app/api/websocket_server.py
- **Line**: 92
- **Code**: `auth_required: bool = False`
- **Why**: Default allows unauthenticated connections
- **Fix**: Set auth_required=True

## P1 - Should Fix (5 issues)

### S1-1: Weak Log Sanitization
- **File**: app/api/route_utils.py
- **Line**: 93-97
- **Code**:
```python
request_info = {
    k: v
    for k, v in req_dict.items()
    if k not in ("password", "token", "secret", "api_key")
}
```
- **Why**: Only checks exact key matches, misses nested
- **Fix**: Add recursive sanitization

### S1-2: Unvalidated Dictionary Input
- **File**: app/api/routes/dictionary.py
- **Line**: 24-39
- **Code**: `str(request.get("phrase", ""))`
- **Why**: Accepts any input without validation
- **Fix**: Add schema validation

### S1-3: Unvalidated Snippets Import
- **File**: app/api/routes/snippets.py
- **Line**: 84-93
- **Code**: `if not isinstance(payload, list):`
- **Why**: Only checks type, not structure
- **Fix**: Validate each entry

### S1-4: IPC Text Injection
- **File**: app/electron/main/ipc/handlers.js
- **Line**: 140
- **Code**: `ipcMain.handle("text:inject", async (event, text) => {`
- **Why**: No length limit or sanitization
- **Fix**: Add input validation

### S1-5: Preload Exposes Full API
- **File**: app/electron/main/preload/main.js
- **Line**: 18-58
- **Code**: `fetchJson: async (path, options = {}) => {`
- **Why**: Allows arbitrary backend paths
- **Fix**: Limit exposed endpoints

## P2 - Nice to Have (5 issues)

### S2-1: Preload URL Exposed
- **File**: app/electron/main/preload/main.js
- **Line**: 15
- **Code**: `getApiOrigin: () => "http://127.0.0.1:8765"`

### S2-2: Settings Raw Dict Input
- **File**: app/api/routes/settings.py
- **Line**: 22
- **Code**: `def save_settings(request: dict[str, Any])`

### S2-3: Error Details Exposed
- **File**: app/api/websocket_server.py
- **Line**: 332-337
- **Code**: `async def send_error(self, error_message: str, ...)`

### S2-4: No API Rate Limiting
- **File**: app/api/server.py
- **Why**: No rate limiting on endpoints

### S2-5: Version Info Exposed
- **File**: app/electron/main/preload/main.js
- **Line**: 172-180
- **Code**: `versions: { node: process.versions.node, ...}`

## Quick Wins
1. Fix CORS (cannot have "*" with credentials)
2. Fix hardcoded token
3. Fix bare except
4. Add path validation

## Done-When
- [ ] All P0 issues fixed
