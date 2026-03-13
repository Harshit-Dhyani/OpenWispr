# Testing Gap Analysis - 2026-03-08

## Summary
Audit of test coverage, test organization, and testing gaps. Found 60+ test files but some critical areas lack coverage.

## Scope
- tests/
- tests/unit/
- tests/integration/
- tests/performance/
- e2e/

## Test Files Found: 60+

### Test Categories
- Unit tests: 25+ files
- Integration tests: 8+ files
- Performance tests: 5+ files
- E2E tests: e2e/ directory

## Findings

### P0 - Must Fix

**T0-1: No Tests for Settings Backend/Frontend Alignment**
- What: No verification that frontend settings match backend
- Why: Settings drift undetected
- Evidence: No test verifies settings schema alignment
- Fix: Add integration test comparing backend/frontend settings
- Verify: Run settings sync tests

### P1 - Should Fix

**T1-1: WebSocket Security Tests Missing**
- What: No tests for WebSocket authentication
- Why: Security vulnerability undetected
- Fix: Add tests for token validation

**T1-2: Model Pool Eviction Tests Missing**
- What: No tests for model TTL/eviction
- Why: Memory issues undetected
- Evidence: No test for MODEL_TTL_SECONDS
- Fix: Add test for model pool eviction

**T1-3: Settings Migration Tests Incomplete**
- What: Python and TS migrations not tested together
- Why: Drift between migrations
- Fix: Add integration test for migration integrity

### P2 - Nice to Have

**T2-1: E2E Coverage for Critical Paths**
- What: Some critical user paths lack E2E tests
- Fix: Add E2E for hotkey flow, system audio capture

**T2-2: Performance Regression Tests**
- What: No automated performance regression tests
- Fix: Add baseline performance tests

## Quick Wins
1. Add settings alignment test
2. Add WebSocket auth test
3. Add model pool eviction test

## Done-When
- [ ] Settings alignment tested
- [ ] Security tests for WebSocket
- [ ] Model pool eviction tested
