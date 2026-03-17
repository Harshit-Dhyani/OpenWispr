# Documentation Pass Skill

## Purpose

Perform systematic whole-repo documentation passes to ensure AGENTS.md standards are met across the codebase. This includes adding missing docstrings, fixing incorrect ones, and keeping generated docs in sync.

## When to Use

- Initial documentation audit of new module areas
- Post-refactor cleanup when module boundaries changed
- Periodic maintenance to catch documentation debt
- When AGENTS.md documentation rules change

## When Not to Use

- Adding new user-facing documentation (use mkdocs/docs/)
- Fixing code behavior (that requires implementation work, not docs)
- Writing README files (these have their own patterns)
- Temporary documentation needs that won't be permanent

## Discovery Steps

1. Review AGENTS.md "Documentation Rules" and "Code Documentation Rules" sections
2. Identify the scope of the pass:
   - Full repo: check all owned directories
   - Module area: e.g., all STT modules, all audio modules
   - Specific file types: routes, services, pipelines
3. Check mkdocs.yml for current docs structure and any documentation gaps
4. Identify files lacking required docstrings:
   - `app/stt/**` - all modules need module docstrings
   - `app/audio/**` - all modules need module docstrings
   - `app/api/**` - all modules need module docstrings
   - `app/core/**` - all modules need module docstrings
   - `app/storage/**` - all modules need module docstrings
5. Check `app/config/settings.py` for settings documentation needs
6. Verify generated frontend config at `app/electron/frontend/src/config/generated/` matches Python settings

## Implementation Rules

1. **Prioritize by ownership**: Follow AGENTS.md "Primary Ownership Rules" for where documentation lives
2. **Generated docs are output**: Never hand-edit files in `app/electron/frontend/src/config/generated/`—regenerate instead
3. **String ownership**:
   - Renderer strings: `app/electron/frontend/src/strings/en.ts`
   - Electron shell strings: `app/electron/strings/en.js`
   - Backend API strings: `app/api/strings/en.py`
   - Prompt text: `app/stt/prompts.py`
4. **Settings wiring**: When documenting settings, verify:
   - Metadata in `app/config/settings.py`
   - Generated frontend config via `python -m app.config.generate_ts`
   - Frontend migration/wiring if needed
   - Settings wiring tests
5. **mkdocs sync**: Keep mkdocs.yml aligned with docs/ folder structure
6. **Smallest relevant set**: Only update docs touched by the pass, don't expand scope

## Verification Steps

1. Run `python -m py_compile` on all modified Python files
2. For settings changes: run `python -m app.config.generate_ts` and verify generated output
3. Run any existing documentation tests if present
4. For mkdocs changes: verify with `mkdocs build` (if available)
5. Check that no generated files were hand-edited
6. Verify no import regressions in modified modules
