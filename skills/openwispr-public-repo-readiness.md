---
name: openwispr-public-repo-readiness
description: Guide agents through preparing the OpenWispr repo for public release, including secret detection, platform claim verification, documentation accuracy, and compliance checks.
---

# OpenWispr Public Repo Readiness

Systematic guidance for preparing the OpenWispr repository for public release.

## Purpose

Guide agents through public repo preparation to ensure:
- No secrets, credentials, or sensitive data are exposed
- Platform support claims are accurate and verified
- Documentation reflects actual behavior
- Dependencies are secure and compliant
- Build paths are correct for packaging

## When to Use

- Preparing for initial public release
- Preparing for open source release
- Reviewing before publishing to GitHub
- Verifying platform support claims
- Checking for sensitive content before release
- Periodic security audits before major releases

## When NOT to Use

- Internal-only development changes
- Experimental features not intended for release
- Bug fixes in already-released code
- Documentation-only updates
- Test additions without release implications

## Discovery Steps

### 1. Check for Secrets and Credentials

Search for common secret patterns:
- API keys, tokens, passwords in code and config
- AWS/GCP/Azure credentials
- Database connection strings
- Private keys and certificates
- OAuth secrets

Files to inspect:
- `.env` files (check .gitignore)
- Configuration files
- Source code comments and strings
- Log files
- History (git log --all --oneline --grep="password\|secret\|key")

```bash
# Search for common patterns
grep -r "api_key\|api-key\|apikey\|secret\|password\|token" --include="*.py" --include="*.js" --include="*.ts" --include="*.json" app/
```

### 2. Verify Platform Support Claims

Check documentation and code for platform claims:
- `README.md` - supported platforms
- `docs/` - any platform-specific documentation
- `package.json` - engines, os fields
- `app/electron/package.json` - Electron-specific platform claims
- Code with platform-specific paths or features

Verify:
- Windows support claims match actual code
- macOS support claims match actual code  
- Linux support claims match actual code
- Platform-specific paths are configurable or use proper detection

### 3. Check License and Dependency Compliance

- `LICENSE` file exists and is appropriate
- `package.json` - license field
- Third-party dependencies are compatible with intended license
- License headers in source files if required
- NOTICE file for bundled dependencies if needed

Check for:
- Proprietary dependencies that conflict with open source
- Unlicensed dependencies
- Incompatible license combinations

### 4. Verify Documentation Accuracy

- `README.md` - installation, usage, features
- `CONTRIBUTING.md` - contribution guidelines
- `CODE_OF_CONDUCT.md` - community guidelines
- `SECURITY.md` - security policy
- `docs/` - technical documentation

Verify claims match actual behavior:
- Feature availability
- Platform support
- Privacy guarantees
- Performance claims
- Provider support

### 5. Check for Personal Identifiers

Search for:
- Real email addresses in code/docs
- Names of real people
- Company-specific information
- Customer or user data examples
- Real transcript snippets or audio samples
- Sensitive sample data

### 6. Verify Build and Packaging Paths

- `package.json` - build scripts
- `app/electron/package.json` - Electron build config
- `scripts/build.py` - Python build logic
- `.github/workflows/` - CI/CD pipelines
- Installer/runner scripts

Ensure:
- No hardcoded absolute paths
- No machine-specific paths
- Build outputs go to proper locations
- Installers include correct assets

## Verification Checklist

### Security

- [ ] No hardcoded credentials or API keys
- [ ] No personal identifiers or sensitive data
- [ ] No real transcript/audio sample data
- [ ] No example data with real info
- [ ] .env files are gitignored
- [ ] No secrets in commit history

### Documentation

- [ ] Platform support claims verified in code
- [ ] Feature claims match implementation
- [ ] Privacy claims are accurate
- [ ] Performance claims are measured/verified
- [ ] No placeholder content or TODOs in docs
- [ ] External links are working

### Compliance

- [ ] License file is present and correct
- [ ] Dependencies are properly licensed
- [ ] No conflicting licenses
- [ ] NOTICE file if required
- [ ] License headers in source files if required

### Build

- [ ] No hardcoded machine-specific paths
- [ ] Build scripts work on clean checkout
- [ ] Packaging paths are correct
- [ ] CI/CD workflows are properly configured
- [ ] .gitignore is complete

### Code Quality

- [ ] No debug artifacts left in code
- [ ] No TODO/FIXME comments (unless ticketed)
- [ ] No placeholder or stub code
- [ ] No broken imports or dead code

## Common Issues to Fix

### Hardcoded Paths

```python
# Bad - machine-specific path
MODEL_PATH = "C:/Users/John/Downloads/model.bin"

# Good - configurable or relative
MODEL_PATH = os.environ.get("MODEL_PATH", "models/default.bin")
```

### Example Data with Real Info

```javascript
// Bad - real email
const adminEmail = "john.doe@company.com";

// Good - placeholder
const adminEmail = "admin@example.com";
```

### Unverified Platform Claims

```markdown
<!-- Bad - unverified claim -->
## Supported Platforms
- Windows 10/11
- macOS 11+
- Ubuntu 20.04+

<!-- Good - verified in code -->
## Supported Platforms
- Windows 10/11 (verified in app/core/platform_detection.py)
- macOS 11+ (verified in app/core/platform_detection.py)
```

### Sensitive Comments in Code

```python
# Bad - revealing internal info
# TODO: Remove before release - this uses John's API key
API_KEY = "sk-xxxxx"

# Good - no sensitive info
# API key loaded from environment
API_KEY = os.environ.get("API_KEY")
```

## Reference Files

- `.gitignore` - ensure proper exclusions
- `LICENSE` - license file
- `README.md` - main documentation
- `CONTRIBUTING.md` - contribution guidelines
- `SECURITY.md` - security policy
- `package.json` - project metadata
- `app/electron/package.json` - Electron config
- `AGENTS.md` - development guidance

## Additional Resources

- GitHub's "Preparing for release" guidelines
- Open Source Initiative license list
- npm audit for dependency security
- GitHub security advisories
