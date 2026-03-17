# Source of Truth Skill

## Purpose

Use this skill when you need to identify, establish, or verify the authoritative source for any piece of information in the OpenWispr codebase.

Use this skill when:
- Adding new configuration, settings, text, or constants
- Creating new contracts between backend, Electron, or frontend
- Discovering where information truly lives before making changes
- Resolving confusion about which file owns which data
- Creating new generated output files
- Establishing ownership for new features or modules
- Documenting architecture decisions

## When NOT to Use

Do not use this skill for:
- General code documentation (use docstrings in source files)
- User-facing feature documentation (use mkdocs/docs/)
- API endpoint docs (use docs/api/endpoints.md)
- Troubleshooting or how-to guides
- Deciding on code implementation patterns

## Discovery Steps

### 1. Identify What Type of Information It Is

| Information Type | Canonical Source | Consumer Files |
|-----------------|------------------|----------------|
| Backend settings | `app/config/settings.py` | Generated to `app/electron/frontend/src/config/generated/settings.ts` |
| Settings text (labels, descriptions) | `app/config/text.py` | Generated to `app/electron/frontend/src/config/generated/text.ts` |
| Runtime Pydantic settings | `app/core/settings/config.py` (derived, not canonical) | Routes, services |
| Renderer strings | `app/electron/frontend/src/strings/en.ts` | Frontend components |
| Electron shell strings | `app/electron/strings/en.js` | Electron main process |
| Backend API strings | `app/api/strings/en.py` | API responses, errors |
| Prompt text | `app/stt/prompts.py` | STT modules |
| Constants | `app/config/constants.py` | Generated to `app/electron/frontend/src/config/generated/constants.ts` |
| Documentation structure | `mkdocs.yml` | Generated docs site |
| Module docstrings | Source files in `app/**` | N/A - source of truth |

### 2. Find Existing Ownership

Search for the information pattern:
- Settings: grep `SettingDefinition` in `app/config/settings.py`
- Text: grep key name in `app/config/text.py`
- Strings: grep in `app/electron/frontend/src/strings/en.ts`
- Prompts: check `app/stt/prompts.py`
- Generated output: check `app/electron/frontend/src/config/generated/`

### 3. Check AGENTS.md Ownership Rules

Review the Primary Ownership Rules section in AGENTS.md for explicit declarations.

## Implementation Rules

### General Principles

1. **One owner per piece of information**: Never have two canonical sources for the same data.
2. **Generate don't copy**: Prefer generated files over manual copies where regeneration is possible.
3. **Explicit over implicit**: Document ownership explicitly in module docstrings.
4. **Derived vs canonical**: Clearly distinguish between canonical (hand-edited source) and derived (generated).
5. **Wire completely or not at all**: If A generates B and B is consumed by C, all three must be updated together.

### For New Canonical Sources

1. **Add to AGENTS.md**: Document the ownership in Primary Ownership Rules section.
2. **Add discovery steps**: If the source is complex, add a discovery step to this skill.
3. **Wire consumers**: Ensure all downstream consumers import from the canonical source.
4. **Add tests**: Add wiring or contract tests to verify the chain.
5. **Run generation**: If applicable, run the generator command.

### For Generated Files

1. **Never hand-edit**: Generated files are output, never source.
2. **Document generation command**: Note how to regenerate in verification steps.
3. **Add to .gitignore**: If the generated directory should not be committed, add to .gitignore.

## Verification Steps

### 1. Verify Single Source
```bash
grep -r "pattern" app/config/ app/core/ app/api/
```

### 2. Verify Wiring Chain
For settings/config changes:
```bash
python -m py_compile app/config/settings.py
python -m app.config.generate_ts
pytest tests/test_settings_wiring.py -v
```

### 3. Verify No Drift
- Check generated files match source
- Check all consumers import from canonical
- Check tests pass with new ownership
