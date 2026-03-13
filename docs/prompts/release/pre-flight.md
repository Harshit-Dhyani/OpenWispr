# Pre-Flight Checklist

Use this checklist before releasing a new version of OpenWispr.

---

## VERSION BUMP

- [ ] Updated version in `pyproject.toml`
- [ ] Updated version in `package.json`
- [ ] Updated `app/__init__.py` version (if applicable)

---

## CODE QUALITY

### Python
```bash
# Syntax check
python -m py_compile app/**/*.py

# Lint
ruff check app/ tests/

# Type check (if configured)
mypy app/
```

### Frontend
```bash
cd app/electron/frontend

# Lint
npm run lint

# Type check
npm run typecheck

# Build
npm run build
```

---

## TESTS

### Python Tests
```bash
# Unit tests
pytest tests/ -v --tb=short

# Integration tests
pytest tests/integration/ -v
```

### Frontend Tests
```bash
cd app/electron/frontend
npm test
```

### E2E Tests
```bash
pytest e2e/ -v
```

---

## VERIFICATION

### Documentation
```bash
# Verify docs
python tools/ci/verify-docs.py

# Check for broken links
python tools/ci/check-links.py
```

### Settings
- [ ] No fake settings (`is_fake: true`) in UI
- [ ] Generated frontend config matches backend

### Build
- [ ] Python build succeeds
- [ ] Electron build succeeds
- [ ] Executable runs without errors

---

## RELEASE ARTIFACTS

- [ ] Changelog updated
- [ ] Git tag created (`vX.Y.Z`)
- [ ] GitHub release created (if applicable)

---

## PRE-COMMIT CHECK

```bash
git status
git diff --stat
```

- [ ] No unintended changes
- [ ] No secrets committed
- [ ] No large files added

---

## DONE CRITERIA

- [ ] All lint checks pass
- [ ] All tests pass
- [ ] Documentation verified
- [ ] Build succeeds
- [ ] Version bumped correctly
- [ ] No regressions identified
