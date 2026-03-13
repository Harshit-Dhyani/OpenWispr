# Master Improvement Roadmap - 2026-03-08

## Verification Update - 2026-03-09
This document is now a historical appendix plus a verified live tracker. The old aggregate counts below are not current source of truth.

## Verified Live Tracker

### Completed In This Pass
- Security: wildcard CORS credentials mismatch fixed in `app/api/server.py`.
- Security: hardcoded WebSocket token replaced with loopback-only fallback plus `OPENWISPR_WS_TOKEN` support in `app/api/websocket_server.py`.
- Security: bare `except:` replaced with `except Exception:` in `app/core/performance_monitor.py`.
- Settings/config: `base -> whisper-base` catalog mapping fixed in backend and generated frontend constants.
- Settings/config: unsupported quality labels replaced with `maximum|balanced|fast|low_memory` in `app/core/system_profiler.py`.
- Settings/config: `ultra` restored to backend live-mode snapshot.
- Settings/config: legacy `backend` setting downgraded to hidden compatibility alias; `audio_backend` remains authoritative.

### Still Open
- Security: document-store path traversal review still needs a dedicated containment fix.
- Settings/config: remaining duplicated VAD naming and mode-label drift need a separate follow-up batch.
- Architecture/runtime: large-file ownership and broader report inventory items remain historical findings until re-verified.

### Deferred By Design
- Full `TRANSCRIPTA_*` env/data-dir/preload-global rename.
- Repo-wide auth/versioning/rate-limit framework changes.
- Broad architecture extractions without a verified correctness payoff.

## Historical Summary
Consolidated roadmap from all audit reports (10 total). Prioritized by impact vs risk.
Total Issues: 153 | P0: 34 | P1: 72 | P2: 47

## Audit Reports Included
1. security-audit-2026-03-08.md - CORS, path traversal, WebSocket auth
2. performance-optimization-2026-03-08.md - O(n²) deduplication, unbounded buffers
3. api-audit-2026-03-08.md - 28 issues
4. audio-audit-2026-03-08.md - 22 issues
5. stt-audit-2026-03-08.md - 12 issues
6. settings-audit-2026-03-08.md - 10 issues
7. electron-audit-2026-03-08.md - 22 issues
8. frontend-audit-2026-03-08.md - 10+ issues
9. storage-audit-2026-03-08.md - 18 issues
10. config-dependencies-audit-2026-03-08.md - 12 issues
11. security-audit-2026-03-08.md
12. performance-optimization-2026-03-08.md
13. architecture-structure-audit-2026-03-08.md
14. settings-config-audit-2026-03-08.md
15. testing-gap-analysis-2026-03-08.md
16. docs-source-of-truth-audit-2026-03-08.md
17. release-readiness-audit-2026-03-08.md

---

## P0 - Must Fix (Immediate) - 34 Issues

### Security (P0) - 8 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| S0-1 | Security | Hardcoded WebSocket token | websocket_server.py:197 | Implement proper auth | 1h |
| S0-2 | Security | Bare except clause | performance_monitor.py:298 | Use specific exceptions | 10min |
| S0-3 | Security | CORS allows all origins | server.py | Restrict to known origins | 30min |
| S0-4 | Security | No path traversal protection | file serving endpoints | Add path validation | 1h |
| S0-5 | Security | WebSocket auth bypass | websocket_server.py | Implement token validation | 1h |
| S0-6 | Security | No rate limiting on API | server.py | Add rate limiting | 2h |
| S0-7 | Security | Sensitive data in logs | transcript logging | Add sanitization | 1h |
| S0-8 | Security | No CSRF protection | API endpoints | Implement CSRF tokens | 2h |

### Performance (P0) - 6 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| P0-1 | Performance | MODEL_TTL_SECONDS = 1800 | model_pool.py:179 | Change to 300 | 5min |
| P0-2 | Performance | max_models = 3 | model_pool.py:67,183 | Change to 1 | 5min |
| P0-3 | Performance | O(n²) deduplication | transcript aggregation | Use hash-based dedup | 4h |
| P0-4 | Performance | Unbounded buffer | audio capture | Add buffer limits | 2h |
| P0-5 | Performance | Memory leak in model pool | model_pool.py | Fix reference counting | 4h |
| P0-6 | Performance | No streaming backpressure | WebSocket handler | Add flow control | 2h |

### API (P0) - 6 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| API0-1 | API | Missing input validation | multiple routes | Add validation schemas | 2h |
| API0-2 | API | No error response standardization | routes | Create error handlers | 1h |
| API0-3 | API | Auth bypass in /api/session | session route | Fix auth middleware | 1h |
| API0-4 | API | File upload without size limit | upload endpoint | Add max size check | 30min |
| API0-5 | API | Missing pagination | list endpoints | Add pagination | 2h |
| API0-6 | API | Inconsistent response formats | routes | Standardize JSON responses | 1h |

### Audio (P0) - 4 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| AU0-1 | Audio | Audio buffer overflow | capture.py | Add bounds checking | 1h |
| AU0-2 | Audio | Device selection race condition | backends/ | Add mutex locks | 2h |
| AU0-3 | Audio | No sample rate validation | capture.py | Add validation | 30min |
| AU0-4 | Audio | Crash on disconnected device | soundcard_backend.py | Add reconnect logic | 1h |

### STT (P0) - 3 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| STT0-1 | STT | Model not released on error | model_pool.py | Add cleanup | 1h |
| STT0-2 | STT | Whisper threading issue | decoder.py | Fix thread safety | 2h |
| STT0-3 | STT | Chunk buffering OOM | aggregator.py | Add max chunks limit | 1h |

### Settings (P0) - 2 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| C0-1 | Settings | Duplicate backend setting | settings.py:472-489 | Remove duplicate | 10min |
| C0-2 | Settings | Deprecated VAD settings in audio | settings.py:499-518 | Remove from audio | 10min |

### Electron (P0) - 2 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| E0-1 | Electron | Context isolation disabled | main.js | Enable contextIsolation | 30min |
| E0-2 | Electron | Node integration in renderer | main.js | Set nodeIntegration: false | 30min |

### Frontend (P0) - 1 Issue

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| F0-1 | Frontend | XSS vulnerability in transcript display | React components | Sanitize output | 1h |

### Storage (P0) - 1 Issue

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| ST0-1 | Storage | Database file not encrypted | storage/ | Add encryption | 4h |

### Architecture (P0) - 1 Issue

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| A0-1 | Architecture | HotkeyTranscriptionService too large (3000+ lines) | server.py | Extract services | 1d |

---

## P1 - Should Fix (This Sprint) - 72 Issues

### Security (P1) - 6 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| S1-1 | Security | Transcript logging may contain sensitive data | transcript logging | Add sanitization | 1h |
| S1-2 | Security | Settings password field detection gaps | route_utils.py:96 | Mark sensitive fields | 30min |
| S1-3 | Security | Insecure cookie settings | server.py | Add secure flags | 30min |
| S1-4 | Security | No security headers | server.py | Add CSP, HSTS | 1h |
| S1-5 | Security | Token expiry too long | auth | Reduce expiry | 30min |
| S1-6 | Security | Debug mode in production | config | Disable debug | 10min |

### Performance (P1) - 8 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| P1-1 | Performance | DEFAULT_MODEL_NAME = medium | constants.py:70 | Change to small | 5min |
| P1-2 | Performance | DEFAULT_COMPUTE_TYPE = float16 | constants.py:71 | Change to int8 | 5min |
| P1-3 | Performance | DEFAULT_CHUNK_SECONDS = 1.6 | constants.py:28 | Change to 0.5 | 5min |
| P1-4 | Performance | No model caching | model_loader.py | Add persistent cache | 4h |
| P1-5 | Performance | Inefficient audio resampling | backends/ | Use faster algorithm | 2h |
| P1-6 | Performance | Redundant model reinitialization | model_pool.py | Reuse model instances | 2h |
| P1-7 | Performance | No GPU memory tracking | performance_monitor.py | Add monitoring | 2h |
| P1-8 | Performance | Large transcript payload | WebSocket | Add compression | 1h |

### API (P1) - 10 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| API1-1 | API | Missing request timeout | routes | Add timeout middleware | 30min |
| API1-2 | API | No retry logic for external calls | routes | Add retries | 1h |
| API1-3 | API | Incomplete health check | /health endpoint | Add component checks | 1h |
| API1-4 | API | Missing API versioning | routes | Add /api/v1/ prefix | 1h |
| API1-5 | API | No request ID for tracing | routes | Add correlation IDs | 30min |
| API1-6 | API | Deprecated endpoints still active | old routes | Deprecate or remove | 2h |
| API1-7 | API | No batch operation support | CRUD routes | Add batch endpoints | 2h |
| API1-8 | API | Missing OPTIONS handling | CORS | Add OPTIONS handler | 30min |
| API1-9 | API | No query param validation | routes | Add schema validation | 1h |
| API1-10 | API | Inconsistent error codes | routes | Standardize codes | 1h |

### Audio (P1) - 8 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| AU1-1 | Audio | Empty except blocks (7+) | soundcard_backend.py:74, capture.py:236,290 | Add logging | 1h |
| AU1-2 | Audio | No audio level metering | capture.py | Add VU meter | 1h |
| AU1-3 | Audio | Device enumeration slow | backends/ | Cache device list | 30min |
| AU1-4 | Audio | No echo cancellation | backends/ | Add AEC | 2h |
| AU1-5 | Audio | Buffer underrun not handled | capture.py | Add underrun handling | 1h |
| AU1-6 | Audio | No noise suppression | backends/ | Add noise gate | 1h |
| AU1-7 | Audio | Format conversion inefficient | backends/ | Optimize conversion | 1h |
| AU1-8 | Audio | Multiple backend conflicts | backends/ | Add conflict resolution | 2h |

### STT (P1) - 5 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| STT1-1 | STT | Language detection inaccurate | decoder.py | Improve detection | 2h |
| STT1-2 | STT | No punctuation by default | decoder.py | Enable punctuation | 30min |
| STT1-3 | STT | Timestamp generation slow | aggregator.py | Optimize timestamp | 1h |
| STT1-4 | STT | Vocabulary filtering missing | decoder.py | Add custom vocab | 1h |
| STT1-5 | STT | Multiple model routing broken | model_router.py | Fix routing logic | 2h |

### Settings (P1) - 6 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| C1-1 | Settings | style_default_profile default mismatch | settings.py:888 vs schema | Align to "casual" | 10min |
| C1-2 | Settings | refinement_profile migration default | migration vs schema | Use clean_dictation | 10min |
| C1-3 | Settings | transcription_mode missing session_paragraph | settings.py:209 | Add to backend | 10min |
| C1-4 | Settings | 13 fake settings exposed in UI | settings.py | Hide or implement | varies |
| C1-5 | Settings | Settings not persisted correctly | manager.py | Fix persistence | 2h |
| C1-6 | Settings | No settings export/import | UI | Add feature | 2h |

### Electron (P1) - 8 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| E1-1 | Electron | Empty except in system profiler | system_profiler.py:155,178,205,224,252,268 | Add logging | 1h |
| E1-2 | Electron | No auto-update mechanism | main.js | Add updater | 4h |
| E1-3 | Electron | Window state not saved | main.js | Persist window state | 1h |
| E1-4 | Electron | No system tray menu | main.js | Add tray menu | 1h |
| E1-5 | Electron | Global shortcut conflicts | main.js | Add conflict detection | 1h |
| E1-6 | Electron | No native notifications | main.js | Add notification API | 1h |
| E1-7 | Electron | Memory leak in renderer | frontend/ | Fix memory issues | 3h |
| E1-8 | Electron | IPC channel not validated | preload.js | Add channel validation | 1h |

### Frontend (P1) - 5 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| F1-1 | Frontend | State management issues | React context | Fix state updates | 2h |
| F1-2 | Frontend | No loading states | components | Add loading indicators | 1h |
| F1-3 | Frontend | Accessibility issues | components | Add ARIA labels | 2h |
| F1-4 | Frontend | Keyboard navigation broken | UI components | Fix focus management | 1h |
| F1-5 | Frontend | No error boundaries | React app | Add error boundaries | 1h |

### Storage (P1) - 6 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| ST1-1 | Storage | No backup mechanism | storage/ | Add auto-backup | 2h |
| ST1-2 | Storage | Database migration issues | storage/ | Fix migrations | 2h |
| ST1-3 | Storage | No data retention policy | storage/ | Add cleanup | 1h |
| ST1-4 | Storage | Large file handling | storage/ | Add streaming | 2h |
| ST1-5 | Storage | Concurrent access issues | storage/ | Add locking | 1h |
| ST1-6 | Storage | Missing indexes | storage/ | Add indexes | 1h |

### Config/Dependencies (P1) - 4 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| CD1-1 | Config | Deprecated dependencies | pyproject.toml | Update dependencies | 2h |
| CD1-2 | Config | Missing type hints | multiple files | Add type hints | 4h |
| CD1-3 | Config | No CI/CD pipeline | repo root | Add CI/CD | 4h |
| CD1-4 | Config | Build not reproducible | electron build | Fix build | 2h |

### Architecture (P1) - 3 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| A1-1 | Architecture | Duplicate settings definitions | settings.py vs manager.py | Consolidate to single source | 1h |
| A1-2 | Architecture | API/Service boundary blur | api/ vs services/ | Move logic to services/ | 2h |
| A1-3 | Architecture | Duplicate model documentation | MODEL_SYSTEM.md vs model-runtime.md | Archive duplicates | 30min |

### Testing (P1) - 3 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| T1-1 | Testing | WebSocket security tests missing | tests/ | Add tests | 2h |
| T1-2 | Testing | Model pool eviction tests missing | tests/ | Add test | 1h |
| T1-3 | Testing | Settings migration tests incomplete | tests/ | Add integration test | 2h |

### Docs (P1) - 2 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| D1-1 | Docs | Transitional docs not labeled | docs/engineering/ | Add status: transitional | 30min |
| D1-2 | Docs | Settings docs don't mention known bugs | docs/ | Add Known Issues section | 1h |

### Release (P1) - 3 Issues

| ID | Category | Issue | Location | Fix | Effort |
|----|----------|-------|----------|-----|--------|
| R1-1 | Release | Empty except blocks in audio | soundcard_backend.py:74, capture.py | Add logging | 1h |
| R1-2 | Release | Empty except in system profiler | system_profiler.py | Add logging | 1h |
| R1-3 | Release | Health endpoint may be incomplete | server.py | Verify/enhance | 30min |

---

## P2 - Nice to Have (Backlog) - 47 Issues

### Security (P2) - 2 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| S2-1 | Security | Two-factor auth not supported | Add 2FA | 8h |
| S2-2 | Security | Audit logging incomplete | Enhance audit trail | 4h |

### Performance (P2) - 3 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| P2-1 | Performance | preload_model defaults to True | Change to False | 5min |
| P2-2 | Performance | Profiling not enabled | Add profiling | 2h |
| P2-3 | Performance | No metrics dashboard | Add dashboard | 4h |

### API (P2) - 6 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| API2-1 | API | GraphQL not supported | Add GraphQL | 8h |
| API2-2 | API | Webhooks not supported | Add webhooks | 4h |
| API2-3 | API | OpenAPI spec incomplete | Enhance spec | 2h |
| API2-4 | API | Rate limit not configurable | Add config | 1h |
| API2-5 | API | Response caching missing | Add cache | 2h |
| API2-6 | API | No async operation support | Add async ops | 4h |

### Audio (P2) - 4 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| AU2-1 | Audio | Voice activity detection basic | Enhance VAD | 4h |
| AU2-2 | Audio | No multi-channel support | Add channel support | 4h |
| AU2-3 | Audio | Audio format support limited | Add more formats | 2h |
| AU2-4 | Audio | No spatial audio | Add spatial support | 8h |

### STT (P2) - 3 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| STT2-1 | STT | Speaker diarization missing | Add diarization | 8h |
| STT2-2 | STT | Multi-language support limited | Enhance multilingual | 4h |
| STT2-3 | STT | Custom model upload not supported | Add model upload | 4h |

### Settings (P2) - 1 Issue

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| C2-1 | Settings | TRANSCRIPTA naming drift | Document in operations | done |

### Electron (P2) - 6 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| E2-1 | Electron | No macOS touch bar support | Add touch bar | 2h |
| E2-2 | Electron | No Linux desktop integration | Add Linux integration | 4h |
| E2-3 | Electron | No snap/appimage packaging | Add packaging | 4h |
| E2-4 | Electron | Plugin system not supported | Add plugins | 8h |
| E2-5 | Electron | No remote debugging | Add debugging | 1h |
| E2-6 | Electron | Window effects not cross-platform | Add effects | 4h |

### Frontend (P2) - 4 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| F2-1 | Frontend | No dark mode | Add theme | 2h |
| F2-2 | Frontend | Localization incomplete | Add i18n | 8h |
| F2-3 | Frontend | No keyboard shortcuts | Add shortcuts | 2h |
| F2-4 | Frontend | Offline mode not supported | Add PWA | 4h |

### Storage (P2) - 4 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| ST2-1 | Storage | Cloud sync not supported | Add sync | 8h |
| ST2-2 | Storage | No export formats | Add exports | 2h |
| ST2-3 | Storage | Compression not used | Add compression | 1h |
| ST2-4 | Storage | No data validation | Add validation | 2h |

### Config/Dependencies (P2) - 4 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| CD2-1 | Config | No dependency security scanner | Add scanner | 2h |
| CD2-2 | Config | Outdated documentation links | Update docs | 1h |
| CD2-3 | Config | No containerization | Add Docker | 4h |
| CD2-4 | Config | No secret management | Add secrets | 4h |

### Architecture (P2) - 2 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| A2-1 | Architecture | Test file organization | Consolidate | 1h |
| A2-2 | Architecture | Config files scattered | Consolidate | varies |

### Testing (P2) - 2 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| T2-1 | Testing | E2E coverage gaps | Add E2E tests | varies |
| T2-2 | Testing | No performance regression tests | Add baseline tests | 2h |

### Docs (P2) - 2 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| D2-1 | Docs | TRANSCRIPTA naming not acknowledged | Document | done |
| D2-2 | Docs | README overloaded | Trimmed to 56 lines | done |

### Release (P2) - 2 Issues

| ID | Category | Issue | Fix | Effort |
|----|----------|-------|-----|--------|
| R2-1 | Release | No central __version__ variable | Add to app/__init__.py | 10min |
| R2-2 | Release | Settings version separate from app version | Document rationale | 30min |

---

## Error Handling Findings

### Critical Error Handling (P0)

| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| S0-2 | app/core/performance_monitor.py:298 | Bare except catches everything | Use specific exceptions |
| S0-1 | app/api/websocket_server.py:197 | Hardcoded token bypasses auth | Implement proper auth |
| AU0-1 | app/audio/capture.py | Audio buffer overflow | Add bounds checking |
| STT0-1 | app/stt/model_pool.py | Model not released on error | Add cleanup |

### Error Handling Improvements (P1)

| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| AU1-1 | app/audio/backends/soundcard_backend.py:74, capture.py:236,290 | Empty except blocks (7+) | Add logging |
| E1-1 | app/core/system_profiler.py:155,178,205,224,252,268 | Empty except blocks (6) | Add logging |
| S1-1 | Transcript logging | Silent error swallowing | Add error handling |
| API0-2 | Multiple routes | No error response standardization | Create error handlers |

---

## Execution Sequence

### Week 1-2: Security Critical (P0)
1. Fix hardcoded WebSocket token (S0-1, R0-1)
2. Fix CORS issues (S0-3)
3. Fix path traversal (S0-4)
4. Fix bare except (S0-2)
5. Enable context isolation (E0-1)
6. Disable node integration (E0-2)
7. Add input validation (API0-1)
8. Add encryption (ST0-1)

### Week 3-4: Performance Critical (P0)
1. Change MODEL_TTL_SECONDS (P0-1)
2. Change max_models (P0-2)
3. Fix O(n²) deduplication (P0-3)
4. Add unbounded buffer limits (P0-4)
5. Fix memory leak (P0-5)
6. Add streaming backpressure (P0-6)

### Week 5-6: API & Audio (P1)
1. Fix auth bypass (API0-3)
2. Add file size limits (API0-4)
3. Standardize responses (API0-6, API1-10)
4. Add logging to audio except blocks (AU1-1)
5. Add device selection locks (AU0-2)
6. Fix sample rate validation (AU0-3)

### Week 7-8: Settings & Storage (P1)
1. Remove duplicate backend (C0-1)
2. Remove deprecated VAD (C0-2)
3. Fix style_default_profile (C1-1)
4. Fix refinement_profile migration (C1-2)
5. Add session_paragraph option (C1-3)
6. Add backup mechanism (ST1-1)
7. Fix database migrations (ST1-2)

### Week 9-10: Architecture & Electron (P1)
1. Extract HotkeyTranscriptionService (A0-1)
2. Clarify API/Service boundaries (A1-2)
3. Consolidate duplicate settings (A1-1)
4. Add logging to system profiler (E1-1)
5. Add window state persistence (E1-3)
6. Fix IPC channel validation (E1-8)

### Week 11-12: Testing & Documentation
1. Add settings alignment test (T0-1)
2. Add WebSocket security tests (T1-1)
3. Add model pool eviction test (T1-2)
4. Archive duplicate docs (D0-1, D0-2)
5. Label transitional docs (D1-1)
6. Add known issues to docs (D1-2)

---

## Verification Checklist

- [ ] All P0 issues fixed
- [ ] Security audit passes
- [ ] Performance improved (measure before/after)
- [ ] No settings drift
- [ ] Error handling has proper logging
- [ ] Release readiness criteria met
- [ ] Documentation updated

## Done-When
- [ ] All P0 items completed (34/34)
- [ ] At least 70% of P1 items completed (50+/72)
- [ ] Performance tests pass
- [ ] No security vulnerabilities
- [ ] Error handling verified

## Priority Summary

| Category | P0 | P1 | P2 | Total |
|----------|----|----|----|-------|
| Security | 8 | 6 | 2 | 16 |
| Performance | 6 | 8 | 3 | 17 |
| API | 6 | 10 | 6 | 22 |
| Audio | 4 | 8 | 4 | 16 |
| STT | 3 | 5 | 3 | 11 |
| Settings | 2 | 6 | 1 | 9 |
| Electron | 2 | 8 | 6 | 16 |
| Frontend | 1 | 5 | 4 | 10 |
| Storage | 1 | 6 | 4 | 11 |
| Config/Dependencies | 0 | 4 | 4 | 8 |
| Architecture | 1 | 3 | 2 | 6 |
| Testing | 0 | 3 | 2 | 5 |
| Docs | 0 | 2 | 2 | 4 |
| Release | 0 | 3 | 2 | 5 |
| **Total** | **34** | **72** | **47** | **153** |
