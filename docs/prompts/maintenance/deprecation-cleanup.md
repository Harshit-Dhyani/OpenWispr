# Deprecation Cleanup Prompt

Use this prompt when auditing or planning deprecation of old code paths in OpenWispr.

## When to Use

- Before public release
- When old code exists alongside new code
- When transitional shims accumulate
- During major version bumps

## Audit Areas

### 1. Identify Transitional Code

Check for:
- Root-level files alongside subfolder versions
- Compatibility shims
- Aliases/re-exports
- "Legacy" or "Old" named files

### 2. Document Deprecation Policy

For each deprecated item:
- When was it deprecated
- When will it be removed
- What replaces it
- Migration path for users

### 3. Add Deprecation Markers

```python
import warnings

# In shim files
warnings.warn(
    "app.core.old_module is deprecated. Use app.core.new_module instead.",
    DeprecationWarning,
    stacklevel=2
)
```

### 4. Set Removal Timeline

- Version-based removal (e.g., "remove in v2.0")
- Date-based removal (e.g., "remove after 2025-06-01")
- Milestone-based removal (e.g., "remove after stable release")

## Common Areas with Transitional Code

### app/audio/
- Root files vs `pipelines/` subfolder
- Root files vs `backends/` subfolder
- Legacy pipeline files

### app/core/
- Root files vs `settings/`, `logging/`, etc.
- Old settings shims
- Compatibility exports

### app/electron/main/
- Root files vs `services/` subfolder
- Legacy preload files

## Verification Commands

```bash
# Find potential shims
grep -r "deprecated" --include="*.py" app/
grep -r "# TODO" --include="*.py" app/

# Find aliases
grep -r "^from.*import \*" --include="*.py" app/
```

## Output

Return:

- [ ] List of deprecated items found
- [ ] Deprecation warnings added
- [ ] Removal timeline documented
- [ ] Migration paths documented
- [ ] Shim policy created

## Example Shim Policy

```
# Shim Policy

## Purpose
Maintain backward compatibility while migrating to new structure.

## Rules
1. All shims must have deprecation warnings
2. Shims must document the canonical path
3. Shims must have removal version
4. No new shims after v1.0

## Current Shims
| Shim | Canonical | Removal |
|------|-----------|---------|
| app.core.config | app.core.settings.config | v2.0 |
| app.audio.pipeline_base | app.audio.pipelines.pipeline_base | v1.5 |
```
