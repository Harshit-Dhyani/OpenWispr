# OpenWispr Agent Guidance

Keep this file short and enforceable. Add only rules that prevent repeat regressions, reduce architecture drift, and make changes safer.

## Core Rules

- Treat this as a public repo. Never commit secrets, credentials, personal identifiers, real transcript snippets, sensitive sample data, or user-specific examples.
- Discovery first: inspect current wiring, contracts, tests, packaging paths, and ownership before editing.
- Prefer minimal diffs. Do not mix bug fixes with broad cleanup unless the cleanup is required for the fix.
- Do not rename or move modules and change behavior in the same batch unless unavoidable.
- Treat file paths and ownership assumptions as hints until verified in the current repo.
- Write clear comments for non-obvious reasoning, tradeoffs, and edge cases. Do not add comment noise.

## Documentation Rules

- Docstrings must describe what the code actually does, not what it should do.
- Distinguish current behavior from target behavior in documentation.
- Module docstrings are required for: api/server.py, audio pipelines, stt engines, services.
- Generated docs under `app/electron/frontend/src/config/generated/` are output, never hand-edit.
- mkdocs.yml controls documentation site structure.
- Public docs must not overclaim support, privacy, performance, or provider behavior.
- Code comments explain why, not what. Narration is prohibited.
- Every API endpoint, service class, and pipeline module needs a docstring.
- Never add comments that merely restate what the code does.
- Distinguish current behavior from target behavior in documentation.
- Never hand-edit generated files - regenerate instead.
- When behavior changes, update the corresponding docstring in the same commit.
- A docstring that contradicts actual code is worse than no docstring.
- Documentation ownership: docs/ (mkdocs), API reference (mkdocstrings + docs/api/endpoints.md), code docstrings (source files).
- FastAPI /api/docs and /api/openapi.json are the runtime contract; docs/api/endpoints.md is human-context supplement.

## Docstring and Comment Quality

- Non-obvious modules need module-level docstrings explaining purpose and key collaborators
- Important classes need docstrings explaining state ownership and lifecycle assumptions
- Non-trivial functions need docstrings with Args, Returns, and behavior notes
- Inline comments explain "why", not "what" - do not narrate obvious code
- Generated frontend config under app/electron/frontend/src/config/generated/ is output, never hand-edit
- Follow Google-style docstrings (Args:, Returns:, Example:) matching the style in fast_chunker.py
- For mkdocs documentation, use the skills in skills/ folder for systematic passes

## Skills System

- Skills MUST be created in `.codex/skills/{skill-name}/skill.md` format
- NEVER create skills in the root-level `skills/` folder
- Each skill must have its own folder with a `skill.md` file inside
- After creating/modifying skills in `.codex/skills/`, run `bun run skills sync` to sync to `skills/`
- All skills must be documented in AGENTS.md with description and usage
- Use skills in `.codex/skills/` folder for repeated workflows
- Run mkdocs serve locally to preview docs during documentation work
- Use mkdocs build to verify docs site generation before committing
- Keep skills practical and grounded in actual repo structure
- Sync command: `bun run skills sync` or `codex sync`

## Available Skills (in skills/)

| Skill | Description |
|-------|-------------|
| api-docs | Create and maintain accurate API endpoint documentation that reflects actual request/response contracts. |
| docs-pass | Perform systematic whole-repo documentation passes to ensure AGENTS.md standards are met across the codebase. |
| docstring-quality | Ensure all code documentation (docstrings) meets AGENTS.md standards - describing what code actually does, not what it should do. |
| public-doc-honesty | Ensure all public-facing documentation, marketing materials, and user-facing content accurately reflects the current state of the codebase. |
| public-repo-readiness | Guide agents through preparing the OpenWispr repo for public release, including secret detection, platform claim verification, documentation accuracy, and compliance checks. |
| runtime-verification | Verify that code changes work correctly at runtime, not just in tests. |
| settings-docs | Ensure settings documentation stays synchronized with code by documenting settings in the canonical locations, verifying wiring between backend and frontend. |
| source-of-truth | Use this skill when you need to identify, establish, or verify the authoritative source for any piece of information in the OpenWispr codebase. |
| sync-skills | Sync skills from .codex folder to the main skills/ folder for backward compatibility. |
| openwispr-audit | Guide agents through systematic repo audits to assess codebase health, find bugs, and identify architectural issues. |
| openwispr-fix-pass | Guide agents through systematic fix passes for bugs, security issues, and architectural problems. |
| openwispr-test-generation | Guide agents through generating tests for bug fixes and new features in OpenWispr. This skill ensures consistent, high-quality test coverage that follows project conventions. |
| openwispr-maintainer | Maintains owned documentation files for the OpenWispr repository without touching application code. |
| openwispr-settings-wiring-check | Verify that settings flow correctly from backend to frontend through the generated config pipeline. |
| openwispr-oversized-file-detector | Detect files that exceed recommended size limits and need to be split. |
| openwispr-audio-pipeline-audit | Detect and report audio pipeline duplication across the codebase. |
| openwispr-model-routing-test | Verify that model selection correctly routes to the appropriate model based on audio source. |
| openwispr-electron-ipc-contract | Verify that Electron IPC contracts between main and renderer processes are properly defined and maintained. |
| openwispr-test-for-bug-fix | Generate focused regression tests when fixing bugs. |
| openwispr-transcript-event-contract | Verify transcript events follow contract - ensuring SSE/WebSocket event formats are consistent, JSON-safe, and properly structured. |
| openwispr-release-validation | Use when validating OpenWispr changes before merge or release. Covers typecheck, targeted tests, renderer string validation, runtime smoke checks, and packaging/release command sanity. |
| openwispr-agents-memory | Use when a verified OpenWispr bug, regression, security issue, or unsafe pattern should become a permanent prevention rule in AGENTS.md. |
| openwispr-repo-discovery | Use when mapping the OpenWispr codebase before changes. Covers entrypoints, backend/Electron/frontend boundaries, settings ownership, model/runtime flow, audio/transcription flow, sessions/history flow, generated config outputs, and duplicate ownership hotspots. |
| openwispr-ui-fix | Use when fixing OpenWispr renderer or Electron UI behavior. Covers string ownership, floating window behavior, quick settings, page/feature ownership, and renderer contract-safe validation. |
| openwispr-safe-refactor | Use when moving, renaming, splitting, or consolidating OpenWispr code without changing behavior. Focuses on compatibility shims, boundary preservation, generated-file awareness, and targeted validation order. |
| openwispr-runtime-debug | Use when debugging OpenWispr model/runtime/audio/transcription failures. Covers model catalog and download ownership, audio backend/device selection, hotkey and session flows, and existing repo diagnostics. |

## Primary Ownership Rules

- `app/config/settings.py` is the authoritative backend settings registry unless changed in the same batch.
- `app/core/settings/config.py` owns runtime Pydantic settings.
- Generated frontend config lives under `app/electron/frontend/src/config/generated/` and is output, not handwritten source.
- Renderer copy belongs only in `app/electron/frontend/src/strings/en.ts`.
- Electron shell copy belongs only in `app/electron/strings/en.js`.
- Backend API copy belongs only in `app/api/strings/en.py`.
- Prompt text belongs only in `app/stt/prompts.py` unless a new canonical prompt owner is introduced in the same batch.
- Reports and docs are not runtime source of truth.

## Architectural Boundaries

- Routes handle transport and validation only.
- Services own orchestration.
- Provider-backed text transform, coach, and refiner behavior must be routed through service-layer ownership, not scattered across routes or UI.
- STT modules own decoding, aggregation, cleanup, repetition control, transcript quality, and transcription prompts.
- Utilities stay pure.
- Do not leave new code in transitional locations if a better target owner already exists.
- Do not merge microphone dictation and system-audio session logic unless the shared abstraction is concrete and verified.
- If a UI control is visible, it must change real behavior. Remove or hide placebo controls.

## Settings Wiring Rules

When changing settings:
1. Add or update metadata in `app/config/settings.py`
2. Regenerate frontend config with `python -m app.config.generate_ts`
3. Update frontend migration/wiring if needed
4. Add or update settings wiring tests
5. Verify backend, generated frontend config, and renderer consumers together

Never:
- add placebo settings
- expose fake settings as real controls
- hardcode settings values in UI when generated config should own them
- create duplicate settings with different names for the same concept

## Runtime and Contract Guardrails

- Keep one active source of truth per settings contract, event payload, provider contract, and model-routing decision.
- Any backend/Electron/frontend contract change must update producers, consumers, and direct contract tests in the same change.
- Always route transcript, WebSocket, and SSE payloads through JSON-safe serialization.
- Draft and final transcript updates must replace by stable segment key, not append duplicate live text.
- Keep Dictation and Sessions transcript state isolated.
- Keep source-specific STT model routing strict: microphone uses microphone model, system uses system model, fallback only when source-specific value is unset.
- Do not show fake progress. If progress cannot be measured honestly, use indeterminate UI.
- Treat normal SSE/WebSocket disconnects as expected behavior, not app errors.
- Do not make optional coach, refiner, or provider runtime dependencies mandatory when safe fallback is possible.
- `aggregated_clean_text` is the canonical final transcript and `paste_text` is the only Electron injection/copy source.

## Provider Integration Rules

- Provider-managed local runtimes are preferred when supported; do not make OpenWispr pretend it owns install/download state for provider-managed models.
- Keep provider settings, provider health, provider model discovery, and provider request routing aligned across backend, Electron, and frontend.
- Do not silently override the user's selected provider or provider model without surfacing it.
- If provider health is unknown or degraded, show honest state and safe fallback behavior.
- Keep provider-specific logic behind a clear adapter or service boundary, not spread across routes and components.
- Provider UI must reflect real backend/provider state, not guessed state.

## Security and Safety Rules

- Never use wildcard CORS with credentials.
- Never trust renderer or client input. Validate at the transport boundary.
- Never expose privileged Electron or OS capabilities beyond the narrow preload contract.
- Prefer allowlists over passthrough behavior for IPC, file access, downloads, subprocesses, and model actions.
- Never use unbounded queues, retries, caches, audio buffers, or background streams.
- Never hardcode model names, language values, provider URLs, runtime paths, or machine-specific paths when settings or discovery should own them.
- Do not log secrets, raw transcript content, raw document contents, or sensitive machine-specific paths unless explicitly redacted and required.
- Use parameterized queries only. Never concatenate user input into SQL.
- Use loopback-only local bindings unless the change explicitly introduces a reviewed remote-access path.

## Structural Change Safety

- Split mixed-responsibility modules before they grow much beyond roughly 300 to 500 lines.
- Large-file refactors must split by responsibility, not arbitrary chunks.
- Do not move files without checking imports, packaging/build allowlists, docs references, generated outputs, and tests in the same change.
- Transitional shims (flat root files re-exporting from nested) must be documented as transitional. Do not create new duplicate flat+nested layouts without explicit transitional justification.
- Remove duplicate services or parallel module layouts when imports are verified stable. Do not leave duplicate "Manager" and "Service" classes for the same domain.
- If a canonical path changes and a shim remains, verify both canonical and shim paths.
- Do not leave compatibility shims half-migrated.
- Root-level API, core, audio, and Electron files may be temporary compatibility bridges. Do not remove them blindly.
- Do not create duplicate files at both root level AND nested folder for the same module. Choose one canonical location.

## Transitional Structure Rules

- `app/audio/**` currently contains both grouped subfolders and legacy root-level modules. Canonical ownership should converge into the grouped subfolders; legacy root files should become explicit shims or be removed only after imports, tests, and docs are updated.
- `app/core/**` still contains grouped folders plus legacy-style root files. Do not duplicate behavior across both locations.
- `app/electron/main/**` contains grouped services/preload/windows plus legacy root files. Keep one canonical owner per concept and treat root files as transitional only when justified.
- Do not create new duplicate roots while migrations are in progress.

## Audio, Coach, and UI-Specific Rules

- Audio pipeline code should converge on canonical locations under `app/audio/**`; transitional duplicates must be removed or reduced to explicit shims.
- Model download managers, pipeline factories, and similar infrastructure must have one canonical owner.
- Coach and refiner must have independent settings and must not silently gate each other.
- Floating-window behavior settings must be wired in the floating-window code path, not just stored.
- Dictation mode and session mode must use separate UI components and separate state.
- Session-only concepts must not leak into dictation UI.
- Provider health and provider model selection UI must reflect real backend/provider state, not guessed state.
- Error states should be actionable for users when the UI exposes the failure.
- Do not leave silent failures in user-facing flows.

## Performance and Runtime Discipline

- Do not make strong latency, throughput, memory, or startup claims unless they are measured in the current repo state.
- Do not add polling where push, caching, memoization, or existing subscriptions are sufficient.
- Bound queues and streaming fanout paths with explicit overflow policy.
- Avoid blocking the event loop with audio processing, provider calls, or synchronous heavy work.
- Do not silently drop audio frames, transcript segments, or provider failures without logging/metrics.
- If a performance-sensitive path changes, capture at least one concrete measurement or mark the claim unverified.

## Error, Recovery, and Accessibility Rules

- User-facing errors should state what failed and what the user can do next when a recovery path exists.
- Do not hide degraded runtime/provider/audio states behind fake success UI.
- Keyboard navigation and focus behavior must not regress on primary screens, drawers, dialogs, and floating-window flows.
- Do not claim accessibility support, screen-reader support, or cross-platform support unless verified.

## Testing Rules

- For bug fixes, add or update at least one focused regression test.
- For non-trivial workflow changes, add the smallest sensible mix of unit, integration/wiring, and regression coverage.
- For new user-facing workflows, add e2e coverage when the path is important enough to regress.
- Refactors must prove behavior parity with at least one focused wiring or integration test.
- Do not delete failing tests to make a change pass unless the test is demonstrably wrong and replaced by a correct one.
- Root validation wrappers must call real package-level validation commands, never silent fallback behavior.
- Provider changes must add or update provider, settings-wiring, and fallback-path tests.
- Runtime-sensitive fixes should include live verification where feasible and should state what remained environment-limited.

## Documentation Rules

- Keep docs honest about current behavior vs target behavior.
- Do not claim production readiness, platform support, privacy guarantees, accessibility support, performance targets, or provider support that is not verified in the current repo state.
- When behavior changes, update the smallest relevant set of docs in the same batch.
- Public docs should be enough for a new contributor or reviewer to understand setup, support limits, packaging truth, and known limitations.
- A docstring that contradicts actual code is worse than no docstring.
- When renaming or removing features, update or remove corresponding documentation in the same batch.
- Verify external links in docs are working before merging doc changes.
- Do not leave placeholder content, "TODO", or empty sections in committed docs.

## Code Documentation Rules

- Add module docstrings to: app/stt/**, app/audio/**, app/api/**, app/core/**, app/storage/**.
- Class docstrings required for: SessionManager, LoopbackAudioSource, WhisperTranscriber, HistoryDatabase, AppSettings.
- Function docstrings required for: public API functions, service methods, callback handlers.
- Docstrings must describe what the code actually does, not what it should do.
- Distinguish current behavior from target behavior in docstrings.
- Do not add comments that merely restate what the code does - comments should explain why, not what.
- Generated frontend config under app/electron/frontend/src/config/generated/ is output, never hand-edit.
- Run `python -m app.config.generate_ts` after modifying Python settings/constants.

## MkDocs and Docs Site Rules

- mkdocs.yml controls documentation site structure. Keep it in sync with docs folder.
- Use mkdocstrings for Python API reference extraction.
- Generated reference docs (via mkdocstrings) should not be hand-edited.
- Docs site preview: `mkdocs serve` (dev) or `mkdocs build` (production).
- Keep docs/ structure aligned with AGENTS.md ownership rules.
- Enable FastAPI /api/docs and /api/openapi.json endpoints for interactive API exploration.
- API endpoint documentation lives in docs/api/endpoints.md, not as the sole API docs source.
- mkdocs.yml must have mkdocs, mkdocs-material, and mkdocstrings[python] in dependencies.
- Run mkdocs build to verify docs generation before merging documentation changes.
- Generated docs outputs are never hand-edited sources - regenerate instead.
- Documentation passes should not mix behavior changes - keep docs and code changes in separate batches unless the behavior change requires the doc update.

## Structural Organization Rules

- Do not move files without checking imports, packaging/build allowlists, docs references, generated outputs, and tests in the same change.
- When moving Python files, update all imports in: app/, tests/, e2e/, scripts/, tools/.
- When moving Electron files, verify imports in index.js, preload scripts, and IPC handlers.
- Created transitional shims must re-export from the new canonical location.
- Document shims as transitional with expected removal timeline.
- Root-level API, core, audio, and Electron files may be temporary compatibility bridges. Do not remove them blindly.
- Split mixed-responsibility modules before they grow much beyond roughly 500 lines.
- Do not create duplicate flat and nested module layouts without clear ownership notes.
- app/audio/ transitional duplicates must be reduced to explicit shims.
- app/core/ session files should converge into app/core/session/ subpackage.
- Electron dead code (unused files) should be removed, not left as legacy.
- Tests should use consistent pytest markers: @pytest.mark.unit, @pytest.mark.integration, @pytest.mark.performance.
- Generated site/ output should be regenerated, never hand-edited.

## Stop and Rethink

Pause before merging if:
- a change creates a second schema, settings, config, provider, or contract owner
- a change introduces polling, queues, retries, or background loops without explicit bounds
- a UI control does not map to real behavior
- a migration leaves old and new paths active without clear ownership notes
- a backend/Electron/frontend change lands without an explicit contract check
- a fix works only because a failing consumer or test was bypassed
- a docs or report claim is being repeated without verifying current code
- a structural cleanup is turning into a behavior rewrite
- a runtime-sensitive fix is being marked complete without live verification or an explicit environment-limited note

## Before Merging

- Run the smallest relevant backend/frontend tests for touched areas.
- For settings/config/schema changes, verify backend registry, generated frontend outputs, and renderer consumers together.
- For provider changes, verify provider health, model discovery, runtime routing, and fallback behavior.
- For Electron file moves, verify imports, packaging globs, and runtime entrypoints.
- For hotkey/session changes, verify transcript correctness and model routing in logs.
- Run `python -m py_compile` on modified Python files.
- Run `python -m app.config.generate_ts` after modifying Python settings/constants.
- Run `mkdocs build` to verify documentation site generation.
- If the normal local dev verification flow is healthy in this repo state, run it before merging.
- For docs changes after runtime moves, update source-of-truth references in the same batch.
- Do not leave tracked model caches, debug artifacts, metrics dumps, or local runtime blobs in the repo.

## Public Repo and Release Discipline

- Never commit secrets, credentials, sensitive sample data, unsafe debug artifacts, tracked model caches, or generated runtime blobs.
- Keep platform support statements honest.
- Document known limitations and experimental features clearly.
- Verify packaged build paths after Electron packaging changes.
- Include license and third-party notice hygiene for bundled dependencies and assets.
- Do not publish provider, privacy, accessibility, performance, or local-only claims that code does not support.

## Skills and Prompts

- For repeated issue classes, create or update repo-local skills in `skills/` instead of relying on docs alone.
- Maintain reusable prompts for common workflows such as audit, fix pass, test generation, release validation, and public-repo readiness.
- Prefer improving existing skills before creating new ones.
- Do not create decorative skills that merely restate AGENTS.md.

## Code Quality Gates

- Never leave TODO/FIXME comments in committed production paths unless they are intentional, ticketed, and clearly scoped.
- Never commit broken imports, syntax errors, or placeholder code that fakes completion.
- Add new generated/cache/debug directories to `.gitignore` before they can be committed.

## Regression Prevention Rules

These rules prevent the critical P0 bugs identified in the audit from recurring:

- Never hardcode language values (e.g., "hi", "en") in transcription code. Always read from user settings.
- Never hardcode model names in transcription code. Always use model IDs from settings or catalog.
- Settings name changes require migration logic. Never rename a setting without adding migration in `app/core/settings_manager.py`.
- Coach and refiner must have independent runtime settings. Do not read coach `runtime_enabled` or `model_id` from refiner settings.
- If a feature provides visual progress (model preload, downloads), the progress must reflect actual work, not fake increments.
- If a setting enables a feature (e.g., `preload_model`), the feature must actually use the preloaded value at runtime.
- UI controls must map to real behavior. Never expose a toggle or setting that has no runtime effect.
- Floating window features must respect their settings. Do not load a setting and then ignore it.
- Mode-specific features must not leak into other modes. Session concepts must not appear in dictation UI.
- Duplicate classes with the same name create confusion. Choose one canonical location and remove or document duplicates.
