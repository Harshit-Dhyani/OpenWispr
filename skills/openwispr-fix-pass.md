# OpenWispr Fix Pass

## Purpose
Guide agents through systematic fix passes for bugs, security issues, and architectural problems.

## When to Use
- When fixing bugs in existing functionality
- When addressing security vulnerabilities
- When resolving architectural problems or regressions
- When addressing issues found in audit reports

## When NOT to Use
- For documentation-only changes (use docs-pass instead)
- For simple one-line typo fixes
- For purely cosmetic UI changes
- When adding new features (use feature development workflow)

## Discovery Steps

1. **Identify root cause before implementing fix**
   - Trace the actual failure to its source
   - Read relevant code, don't guess
   - Check logs, tests, and error traces

2. **Trace actual source of truth**
   - Find the canonical owner for the affected code (see AGENTS.md)
   - Identify settings, contracts, or schemas that govern behavior
   - Verify which module truly owns the data flow

3. **Find all consumers of the affected code**
   - Search for imports, references, and usages
   - Check backend routes, services, and Electron IPC
   - Verify renderer/frontend consumers

4. **Check for similar issues elsewhere**
   - Search for similar patterns that might have the same bug
   - Check related modules with shared logic
   - Verify settings wiring in similar areas

## Implementation Rules

- **Prefer minimal diffs**: Fix only what's broken, don't refactor surrounding code
- **Don't mix bug fixes with broad cleanup**: Keep changes focused
- **Add regression tests for every bug class fixed**: Use openwispr-test-for-bug-fix skill
- **Update AGENTS.md if bug class should never repeat**: Add rules to prevent recurrence
- **One fix per batch**: Separate unrelated fixes into different commits

## Verification Requirements

- Run `python -m py_compile` on modified Python files
- Run settings generation if applicable: `python -m app.config.generate_ts`
- Run relevant tests: `pytest tests/ -v -k "<keyword>"`
- Verify backend, generated frontend config, and renderer consumers together
- For settings changes, verify settings wiring tests pass

## Common Failure Patterns

1. **Fixing symptoms not root cause**
   - Fix the underlying issue, not just the error message
   - Example: Adding null check instead of fixing why null is passed

2. **Not checking for similar issues**
   - Same bug likely exists in related code paths
   - Search for similar patterns before declaring fix complete

3. **Missing regression tests**
   - Every bug fix needs a test to prevent recurrence
   - Use openwispr-test-for-bug-fix skill

4. **Not updating AGENTS.md**
   - If this bug class should never happen again, add a rule

5. **Incomplete consumer verification**
   - Fix breaks in other parts of the system that consume the fixed code
   - Always find and verify all consumers

6. **Inconsistent state after fix**
   - Settings, generated config, and runtime state must stay in sync
   - Verify the full pipeline, not just the immediate fix
