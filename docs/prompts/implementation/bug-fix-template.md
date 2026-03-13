# Bug Fix Template

Use this template when fixing bugs to ensure proper verification and prevent regressions.

---

## BUG REPORT

**Description**: [One sentence describing the issue]

**Reproduction Steps**:
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Expected Behavior**: [What should happen]

**Actual Behavior**: [What actually happens]

**Evidence**:
- File: `path/to/file.py`
- Line: ~123
- Error message: `...`
- Logs: `...`

---

## DISCOVERY PHASE

### 1. Locate the Problem

Search for relevant code:
```bash
# Find related files
grep -r "relevant-keyword" app/

# Find test coverage
grep -r "function_name" tests/
```

### 2. Understand the Code Path

Read these files:
- [ ] `path/to/problem/file.py`
- [ ] `path/to/caller/file.py`
- [ ] `path/to/test/file.py`

### 3. Check for Related Issues

- [ ] Search for similar bugs in `reports/`
- [ ] Check `AGENTS.md` for known issues
- [ ] Search for existing tests

---

## IMPLEMENTATION

### Fix Strategy

[Describe your approach - minimal change, why it works]

### Changes

**File: `path/to/file.py`**

```python
# Before
def broken_function():
    return wrong_value

# After
def fixed_function():
    return correct_value
```

---

## VERIFICATION

### 1. Run Existing Tests
```bash
# Python tests
pytest tests/test_file.py -v

# Frontend tests  
cd app/electron/frontend && npm test

# E2E tests (if applicable)
pytest e2e/ -v
```

### 2. Verify the Fix Manually
- [ ] Reproduced the original bug
- [ ] Applied the fix
- [ ] Bug no longer occurs
- [ ] Related functionality still works

### 3. Check for Regressions
```bash
# Run full test suite
pytest tests/ -v
npm test

# Check lint
python -m py_compile app/path/to/file.py
```

---

## REGRESSION TEST

Add or update at least one test:

```python
# tests/test_file.py
def test_bug_fix_description():
    """Regression test for issue: brief description"""
    # Given: [setup]
    # When: [action]
    # Then: [assertion]
    result = broken_function()
    assert result == expected_value
```

---

## DONE CRITERIA

- [ ] Bug reproduced and confirmed fixed
- [ ] Existing tests pass
- [ ] Regression test added
- [ ] No lint errors
- [ ] No type errors (if applicable)
- [ ] Documentation updated if needed

---

## NOTES

[Document any follow-up work, architectural concerns, or temporary workarounds]
