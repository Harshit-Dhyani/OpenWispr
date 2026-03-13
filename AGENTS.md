# OpenWispr Agent Guidance

Keep this file short and enforceable. Add only rules that prevent repeat regressions, reduce architecture drift, and make changes safer.

## Core Rules

- Treat this as a public repo. Never commit personal identifiers, real transcript snippets, or user-specific examples.
- Discovery first: inspect current wiring, contracts, tests, and ownership before editing.
- Prefer minimal diffs. Do not mix bug fixes with broad cleanup unless the cleanup is required for the fix.
- Do not rename or move modules and change behavior in the same batch unless unavoidable.
- Treat file paths and ownership assumptions as hints until verified in the current repo.

## Copy and Ownership Rules

- Do not add user-facing copy inline.
- Renderer copy -> `app/electron/frontend/src/strings/en.ts`
- Electron shell copy -> `app/electron/strings/en.js`
- Backend API copy -> `app/api/strings/en.py`
- Prompt text -> `app/stt/prompts.py`
- Do not create a second source of truth for settings, model metadata, generated config, UI strings, event payloads, or docs ownership.
- One concept should have one primary owner. Parallel implementations must be temporary, explicit, and justified.

## Architectural Boundaries

- Routes handle transport and validation only.
- Services own orchestration.
- STT modules own decoding, aggregation, cleanup, refinement, and prompts.
- Utilities stay pure.
- Do not leave new code in transitional locations if a target owner already exists.
- Do not merge microphone dictation and system-audio session logic unless the shared abstraction is concrete and verified.
- If a UI control is visible, it must change real behavior. Remove or hide placebo controls.

## Structural Change Safety

- Split mixed-responsibility modules before they grow much beyond roughly 300 to 500 lines.
- Large-file refactors must split by responsibility, not arbitrary chunks.
- Do not move files without checking imports, packaging/build allowlists, docs references, generated outputs, and tests in the same change.
- If a canonical path changes and a shim remains, verify both canonical and shim paths.
- Do not leave compatibility shims half-migrated.
- Root-level API and core shim files may be intentional backward-compatibility bridges; do not remove them blindly.

## Source of Truth Rules

- `app/config/settings.py` is the authoritative backend settings registry unless changed in the same batch.
- Frontend settings schema/defaults must be generated from or aligned with backend settings metadata.
- `app/core/model_catalog.py` is the canonical model catalog unless changed in the same batch.
- Generated frontend config under `app/electron/frontend/src/config/generated/` is output, not handwritten source.
- Reports in `reports/` are not source of truth for runtime behavior.

## Runtime and Contract Guardrails

- Keep one active source of truth per event payload, settings contract, and model-routing decision.
- Any backend/Electron/frontend contract change must update producers, consumers, and direct contract tests in the same change.
- Always route transcript/WebSocket/SSE payloads through a single JSON-safe encoder.
- Draft/final transcript updates must replace by stable segment key, never append duplicate live text.
- Keep Dictation and Sessions live transcript state isolated.
- Keep source-specific model routing strict: microphone uses microphone model, system uses system model, fallback only when source-specific value is unset.
- Do not show fake preload/download progress.
- Treat normal SSE/WebSocket disconnects as expected behavior, not app errors.
- Do not make optional refiner/runtime dependencies mandatory when safe fallback is possible.
- `aggregated_clean_text` is the canonical final transcript and `paste_text` is the only Electron injection/copy source.

## Security and Performance Baseline

- Never trust renderer/client input; validate at the transport boundary.
- Never expose privileged Electron or OS capabilities beyond the narrow preload contract.
- Prefer allowlists over broad passthrough behavior for IPC, file access, downloads, model actions, and subprocess paths.
- Bound every queue, cache, retry loop, audio buffer, and background stream.
- Do not add polling where push, caching, memoization, or existing subscriptions are sufficient.
- Do not log secrets, raw transcript content, raw document contents, or sensitive machine-specific paths unless explicitly redacted and required.

## Testing Rules

- For bug fixes, add or update at least one focused regression test.
- For non-trivial workflow changes, add the smallest sensible mix of unit, integration/wiring, and regression coverage.
- Refactors must prove behavior parity with at least one focused wiring or integration test.
- Do not delete failing tests to make a change pass unless the test is demonstrably wrong and replaced by a correct one.
- Root validation wrappers must call real package-level validation commands; never silently downgrade to echo/fallback behavior.

## Stop and Rethink

Pause before merging if:
- a change creates a second schema/default/config owner
- a change introduces new polling, queues, or background loops without explicit bounds
- a UI control does not map to real behavior
- a migration leaves old and new paths active without clear ownership notes
- a backend/Electron/frontend change lands without an explicit contract check
- a fix works only because a failing consumer or test was bypassed
- a docs or report claim is being repeated without verification against current code

## Before Merging

- Run the smallest relevant backend/frontend tests for touched areas.
- For settings/config/schema changes, verify backend registry, generated frontend outputs, and renderer consumers together.
- For Electron file moves, verify imports, packaging globs, and runtime entrypoints.
- For hotkey/session changes, verify transcript correctness and model routing in logs.
- For docs changes after runtime moves, update inventory/source-of-truth references in the same batch.

## Anti-Regression Rules

### Import Safety
- Never import modules that don't exist. Always verify imports resolve correctly before committing.
- When creating new Electron services, verify the import path exists before using it in main.js.
- Run `python -m py_compile` on modified Python files to catch syntax errors.

### CI Requirements
- Every PR must pass lint (Python and JavaScript/TypeScript).
- Every PR should have tests for behavioral changes.
- Do not merge PRs with syntax errors or broken imports.

### Settings Safety
- Settings marked as `is_fake: true` must be hidden from UI or implemented.
- Never add placebo settings that don't affect runtime behavior.
- Generated settings files must be regenerated after Python settings changes.

### Module Size Limits
- Electron main entry point (index.js) must stay under 1000 lines. Split large modules into focused services.
- API server.py must stay under responsibility-based limits. Extract route handlers to app/api/routes/.
- Frontend App.tsx should stay under 1500 lines. Split into feature components.
- Frontend components (MainContent, FloatingWindow) should stay under 500 lines each.
- Python modules should stay under 500 lines. Split large files by responsibility.

### Audio Pipeline
- Audio pipeline modules must not be duplicated. All audio pipeline code must live in `app/audio/pipelines/` only. Old locations should be removed or converted to backward-compatible shims.

### Single Source of Truth for Audio
- Model download managers, pipeline factories, and similar utilities must have a single canonical location. Do not create duplicate files.

### CI Quality Gates
- CI must not use `continue-on-error: true` on tests, typecheck, or build steps. Only unstable linting may continue on error with explicit comment.

### Skills Requirement
- For repeated issue classes, create or update repo-local skills in `skills/` directory rather than relying on documentation alone.

### Prompts Requirement
- Maintain reusable prompts in `prompts/` for common workflows: audit, fix-pass, test-generation, release-validation.

### Legacy Naming
- Do not use "Transcripta" or other legacy project names in new code.
- Update legacy references when working in affected files.

### E2E Coverage
- Add e2e tests for any new user-facing workflow.
- Critical paths: hotkey dictation, settings persistence, model selection, session capture.

### Transcript State Isolation
- Keep dictation and session transcript state completely isolated in React state.
- Do not share live draft or snapshot state between dictation and session modes.

### Settings Naming Conventions
- Use snake_case for backend settings (Python).
- Frontend generated settings will convert to camelCase automatically.
- Do not create duplicate settings with different naming conventions in the same category.

### No Fake Progress Indicators
- Never show progress that doesn't correspond to actual work being done.
- If progress cannot be measured accurately, show a spinner or indeterminate state instead.
- Progress updates must come from actual background work, not time.sleep() loops.

### Coach/Refiner Independence
- Coach and refiner must have independent settings.
- Do not gate coach runtime on refiner settings.
- Each feature must have its own runtime_enabled and model_id settings.

### Floating Window Settings
- Any setting that controls floating window behavior must be wired in FloatingWindow.tsx.
- Do not add settings that claim to control UI behavior without implementing the check.

### CSP Security
- All Electron HTML windows must include CSP meta tags.
- Use minimal CSP that allows the app to function: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'

### Session/Dictation UI Separation
- Dictation mode and session mode must have separate UI components.
- Session-specific concepts (review, formulas, suppressed panels) must not appear in dictation mode.
- Use separate components (DictationContent, SessionContent) to enforce separation.