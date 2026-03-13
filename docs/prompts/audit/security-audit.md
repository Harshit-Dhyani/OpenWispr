# Security Audit Prompt

Use this prompt when auditing OpenWispr for security issues.

## When to Use

- Before public release
- After adding new dependencies
- When modifying Electron main process
- When adding new IPC handlers

## Audit Areas

### 1. Electron Security
- CSP headers configured
- nodeIntegration disabled
- contextIsolation enabled
- Preload scripts use contextBridge
- No remote module usage
- No unsafe eval in renderer

### 2. IPC Security
- All IPC handlers validate input
- No arbitrary command execution
- File path validation
- No path traversal vulnerabilities
- Allowlist-based IPC (not broad passthrough)

### 3. Backend Security
- No shell command injection
- Input validation on all endpoints
- Proper error handling (no stack traces leaked)
- CORS configured correctly
- Rate limiting if needed

### 4. Dependencies
- No known CVE in direct dependencies
- Minimal dependency surface
- No abandoned packages
- License compliance

### 5. Data Privacy
- No telemetry without disclosure
- Local processing emphasized
- No unexpected network calls
- Sensitive data not logged

## Verification Commands

```bash
# Check for common issues
grep -r "nodeIntegration" app/electron/
grep -r "contextIsolation" app/electron/
grep -r "shell.exec" app/electron/
grep -r "eval(" app/electron/

# Check dependencies
pip-audit || pip check
npm audit
```

## Output

Return:

- [ ] Electron security: PASS/FAIL + issues
- [ ] IPC security: PASS/FAIL + issues
- [ ] Backend security: PASS/FAIL + issues
- [ ] Dependencies: PASS/FAIL + issues
- [ ] Data privacy: PASS/FAIL + issues

## Common Issues

1. `nodeIntegration: true` in BrowserWindow
2. Missing input validation in IPC handlers
3. Using `shell.execute` with user input
4. Exposing dangerous Electron APIs to renderer
5. Logging sensitive data
6. Missing CORS configuration
