# Public Repo Readiness Prompt

Use this prompt when auditing or preparing OpenWispr for public release.

## When to Use

- Before making the repo public
- Before major release
- After significant structural changes
- When adding new CI/CD or automation

## Audit Areas

### 1. Secret Hygiene
- Check for `.env`, `.env.local`, secrets in code
- Verify `.gitignore` covers sensitive files
- Check for hardcoded API keys or tokens
- Verify no machine-specific paths in code

### 2. Contributor Onboarding
- Quickstart in README (10 minutes or less)
- Platform prerequisites table (Node, Python versions)
- Development setup commands work
- Test commands documented

### 3. Documentation Truth
- README accurately describes current behavior
- Known limitations clearly documented
- Experimental vs stable features separated
- Platform support clearly stated

### 4. Security
- SECURITY.md exists
- CODE_OF_CONDUCT.md exists
- ISSUE_TEMPLATE for bugs and features
- PULL_REQUEST_TEMPLATE exists

### 5. CI/CD
- Lint passes
- Typecheck passes
- Tests run and pass
- Build/test workflow exists
- Release workflow exists (if applicable)

### 6. Packaging
- Build commands work
- No hardcoded development paths
- Installer builds successfully
- Paths resolve correctly after packaging

### 7. Supportability
- Diagnostics tools exist
- Error messages are helpful
- Log collection possible
- Issue template asks for diagnostics

## Verification Commands

```bash
# Check for secrets
grep -r "api_key" --include="*.py" --include="*.js"
grep -r "password" --include="*.py" --include="*.js"

# Verify gitignore
cat .gitignore

# Run lint
pnpm run lint:python

# Run typecheck
pnpm run typecheck

# Verify build
pnpm run build:electron
```

## Output

Return:

- [ ] Secret hygiene: PASS/FAIL + issues found
- [ ] Contributor onboarding: PASS/FAIL + gaps
- [ ] Documentation truth: PASS/FAIL + gaps
- [ ] Security files: PASS/FAIL + missing
- [ ] CI/CD: PASS/FAIL + issues
- [ ] Packaging: PASS/FAIL + issues
- [ ] Supportability: PASS/FAIL + gaps

## Common Issues to Check

1. Local paths like `C:\Users\name` or `/home/name`
2. Hardcoded localhost URLs
3. Missing `.env` in `.gitignore`
4. Test output files in repo
5. Large binary files not in LFS
6. Stale report/archive files
7. Undocumented experimental features
8. Missing platform support info
