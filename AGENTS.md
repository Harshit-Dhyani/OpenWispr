# OpenWispr Agent Guidance

Keep this file short enough to stay enforceable. Add only concrete rules that prevent repeat regressions, reduce architecture drift, and make changes safer.

## Engineering Standards

- Treat this as a public repo. Never commit personal identifiers, real transcript snippets, or user-specific examples.
- Do not add user-facing copy inline. Renderer copy -> `app/electron/frontend/src/strings/en.ts`; Electron shell copy -> `app/electron/strings/en.js`; backend API copy -> `app/api/strings/en.py`; prompt text -> `app/stt/prompts.py`.
- Keep boundaries clean: routes handle transport/validation only, services own orchestration, STT modules own decoding/aggregation/cleanup/refinement/prompts, utilities stay pure.
- Split mixed-responsibility modules before they exceed roughly 300-500 lines.
- Discovery first: inspect existing wiring, contracts, and tests before editing.
- Prefer minimal diffs; do not mix bug fixes with broad cleanup unless the cleanup is required for the fix.
- Do not rename/move modules and change behavior in the same batch unless unavoidable.
- Treat file paths and ownership assumptions as hints until verified in the current repo.

## Core Project Guardrails

- Do not create a second source of truth for settings, model metadata, generated config, UI strings, event payloads, or docs ownership.
- If docs, code, generated outputs, and tests disagree, reconcile them in the same change or explicitly mark the drift.
- Do not document target architecture as current reality; label current, transitional, and target states explicitly.
- One concept should have one primary owner. Parallel implementations, schemas, or docs must be temporary, explicit, and justified.
- If a UI control is visible, it must change real behavior; remove or hide placebo controls.
- Any change crossing backend/Electron/frontend boundaries must verify all producers and consumers in the same batch.

## Never Reintroduce These Bugs

- Always route transcript/WebSocket/SSE payloads through a single JSON-safe encoder; never emit raw numpy/dataclass/datetime/Path objects.
- Draft/final transcript updates must replace by stable segment key (`session_id + segment_index` or equivalent), never append duplicate live text.
- Keep Dictation and Sessions live transcript state isolated; do not render shared cross-mode state.
- Keep source-specific model routing strict: microphone -> `microphone_asr_model_id`, system -> `system_asr_model_id`, fallback only when source-specific value is unset.
- Do not show fake download/preload progress; percent is valid only when total size is known.
- Treat normal SSE/WebSocket disconnects (`CancelledError`, clean closes) as expected behavior, not app errors.
- Do not make refiner runtime mandatory; if optional dependencies are missing, degrade once and return original text safely.
- Preserve hotkey final-text contract: `aggregated_clean_text` is canonical final transcript and `paste_text` is the only Electron injection/copy source.
- Keep floating waveform driven by real amplitude data and floating timer driven by local monotonic clock.
- Do not split transcription behavior settings across unrelated sections; transcription fidelity/finalization controls live under Transcription, Models only controls runtime/download/cache.
- Do not maintain parallel handwritten frontend settings schema/defaults in parallel with `app/config/settings.py` + generated settings outputs.
- Do not shadow imported Electron helper functions with local boolean flags of similar names.

## Change Safety Rules

- Verify existing contracts before editing: route payloads, preload APIs, WebSocket/SSE message shapes, generated config outputs, settings registry, and model catalogs.
- Every non-trivial fix must preserve or intentionally update the contract, state the risk, and include verification.
- Do not move files without checking imports, package/build allowlists, docs references, generated outputs, and tests in the same change.
- Do not leave compatibility shims half-updated; when a canonical path changes, verify both canonical and shim paths if both remain supported.
- Avoid broad “while I’m here” edits in risky areas such as hotkey flow, floating window, settings persistence, model loading, SSE/WebSocket paths, and download management.
- When a change introduces a new long-lived background task, queue, cache, retry loop, or poller, bound it and document the overflow/cleanup policy in code.

## Source of Truth Rules

- Backend settings registry in `app/config/settings.py` is authoritative unless explicitly superseded in the same batch.
- Frontend settings schema/defaults must be generated from or aligned with backend settings metadata; no silent handwritten drift.
- `app/core/model_catalog.py` is the canonical model catalog unless a same-batch migration explicitly changes that ownership.
- Renderer copy belongs only in `app/electron/frontend/src/strings/en.ts`.
- Electron shell copy belongs only in `app/electron/strings/en.js`.
- Backend API copy belongs only in `app/api/strings/en.py`.
- Prompt text belongs only in `app/stt/prompts.py` unless a prompt-specific owner is explicitly introduced.
- Generated files under `app/electron/frontend/src/config/generated/` are outputs, not handwritten sources.
- Audit reports in `reports/` are not source of truth for runtime behavior; verify claims against current code before repeating them.

## Security Baseline Rules

- Never trust renderer/client input; validate at the transport boundary.
- Never expose privileged Electron or OS capabilities beyond the narrow preload contract.
- Prefer allowlists over broad passthrough behavior for IPC, file access, downloads, model actions, and shell/subprocess paths.
- Do not introduce unbounded queues, unbounded retries, or unbounded file growth without explicit limits.
- Do not log secrets, raw transcript content, raw document contents, or machine-specific sensitive paths unless redacted and explicitly required for debug mode.
- Any new network, file-system, subprocess, shell, or download code must include failure handling and abuse-case thinking in the same change.
- Do not treat local-only assumptions as a reason to skip validation or boundary checks.

## Performance Guardrails

- Do not add polling where push, caching, memoization, or existing subscriptions are sufficient.
- Avoid repeated idle polling loops for `/api/settings`, `/api/devices`, `/api/session`, `/api/models/catalog`; load once, cache, and resubscribe only when needed.
- Bound every long-lived queue, cache, retry loop, audio buffer, and background stream.
- Do not duplicate computation across backend, Electron, and renderer when one layer can own it cleanly.
- Measure before and after for hot paths: startup, hotkey start/stop, floating updates, model download, settings sync, and session streaming.
- Do not raise default memory or latency cost without a clear user-visible benefit and explicit verification.
- Streaming queues and fanout paths must have explicit maxsize and deliberate overflow policy.

## Testing Contract Rules

- For bug fixes, add or update at least one focused regression test.
- For non-trivial workflow changes, add the smallest sensible mix: unit + integration/wiring + regression, and E2E only when user-visible flow changed materially.
- Contract change: update backend and frontend consumers plus direct contract tests in the same change.
- Refactor: prove behavior parity with at least one focused wiring/integration test.
- Do not remove failing tests to make a change pass unless the test is demonstrably wrong and replaced with a correct one.
- Run the smallest relevant backend/frontend tests for touched areas before merging.
- Root validation wrappers must call real package-level validation commands; never silently downgrade to echo/fallback behavior.

## Architecture Drift Rules

- Do not leave new code in transitional locations if a target owner already exists.
- If a module remains in a non-ideal location for compatibility, mark it as transitional and keep the shim explicit.
- Routes handle transport only; move orchestration out instead of letting route files accumulate business logic.
- Keep one active source of truth per concept; duplicates must be justified or scheduled for consolidation.
- When moving modules, update imports, packaging allowlists, docs inventory/source-of-truth references, and tests in the same batch.
- Do not merge microphone dictation and system-audio session logic unless the shared abstraction is concrete and verified.

## Docs and Reports Hygiene Rules

- README is public-facing; do not dump internal audits, migration notes, or deep implementation contracts into it.
- Internal engineering docs must be labeled clearly as current-state, audit, transitional, or target-state documents.
- Do not create duplicate docs for the same concept without a clearly different responsibility.
- If a report or doc is superseded, mark it explicitly instead of leaving competing truths in the repo.
- Do not claim performance, coverage, reliability, or security status numbers unless verified in the current repo state.
- Every runtime path move must include same-batch docs inventory/source-of-truth updates for renamed entrypoints, moved files, and changed ownership.

## Verified Prevention Entries

### Settings ownership drift
- What went wrong: frontend settings defaults/validation drifted away from backend settings registry.
- Why it happened: renderer schema/defaults were maintained separately from `app/config/settings.py` and generated outputs.
- Detect earlier: for every setting add/rename/re-category, compare backend registry, generated frontend settings, and renderer consumers in the same change.
- Prevention rule: backend registry is authoritative; frontend settings schema/defaults must be generated from it or explicitly justified with sync coverage.

### Typecheck wrapper false green
- What went wrong: repo-root `typecheck` passed via fallback even when package-level validation contract was missing.
- Why it happened: wrapper script allowed echo/fallback behavior instead of enforcing a real frontend typecheck command.
- Detect earlier: run the package-level typecheck command directly once when adding/changing root validation wrappers.
- Prevention rule: never ship required validation wrappers that silently downgrade to fallback behavior.

### Electron module move import break
- What went wrong: moving model download manager broke internal relative imports after directory change.
- Why it happened: compatibility shim path was updated, but module-internal `require()` paths were not validated.
- Detect earlier: after Node/Electron module moves, require both canonical and shim paths, then run colocated unit tests.
- Prevention rule: update internal relative imports in the same move commit and verify both canonical + shim load paths.

### Electron packaging allowlist mismatch
- What went wrong: moving preload scripts risked broken packaged builds because `app/electron/package.json` allowlist still matched old paths.
- Why it happened: runtime path migration and packaging globs were changed in separate steps.
- Detect earlier: after Electron file moves, diff moved canonical paths against `build.files` globs.
- Prevention rule: whenever Electron main/preload paths move, update packaging globs in the same change.

### Doc path drift after runtime refactors
- What went wrong: architecture docs still referenced legacy Electron entry/preload paths after canonical file moves.
- Why it happened: runtime refactor landed before docs source-of-truth references were reconciled.
- Detect earlier: run a stale-path grep in `docs/` for moved canonical paths before merging structural batches.
- Prevention rule: every runtime path move must include same-batch docs inventory/source-of-truth updates for renamed entrypoints and preloads.

### SSE queue growth under slow consumers
- What went wrong: `/api/events` used an unbounded asyncio queue, so a slow or stalled SSE client could accumulate backend events without limit.
- Why it happened: hotkey SSE had a queue cap, but the main SSE path kept a separate queue implementation without the same bound.
- Detect earlier: compare all SSE/WebSocket fanout queues for matching maxsize and drop policy whenever adding a new transport path.
- Prevention rule: every long-lived streaming queue must declare an explicit bounded maxsize and a deliberate overflow policy in the same module.

### Contradiction map key mismatch in incremental STEM review
- What went wrong: incremental STEM note rebuilding checked segment timestamps against the contradiction map itself before checking the per-variable timestamp sets, so existing segments missed contradiction review flags.
- Why it happened: the contradiction structure is keyed by variable name, but the incremental update path treated it like a timestamp-indexed map.
- Detect earlier: whenever a helper returns `dict[str, set[float]]`, add one regression test that exercises both the dict keys and the nested timestamp membership path.
- Prevention rule: when propagating contradiction or review state, compare timestamps only against the nested timestamp sets, never against the outer variable-keyed dict.

### Windows dev launcher shell regression
- What went wrong: `npm run dev` failed before startup because the dev launcher spawned child scripts through `cmd.exe`, which treated an extended-length Windows current directory (`\\?\...`) as unsupported and then resolved `scripts/dev.cjs` from `C:\Windows`.
- Why it happened: `scripts/dev.cjs` used `shell: true` instead of launching `pnpm` through a Node-resolved executable path.
- Detect earlier: run `node scripts/dev.cjs` once on Windows after launcher changes and verify there is no `CMD.EXE ... UNC paths are not supported` banner.
- Prevention rule: on Windows, do not use `shell: true` for repo launchers that inherit cwd; spawn package managers through a resolved executable/script path, sanitize extended-length cwd values first, and avoid root npm scripts that reference `node scripts/...` by relative path when `npm_package_json` can provide the repo root.

### Nested dev runner package-root regression
- What went wrong: `npm run dev` still failed after the root launcher fix because child backend/Electron dev processes were started through nested package-manager commands that could still resolve `package.json` from `C:\Windows`.
- Why it happened: the root launcher delegated to `npm`/`pnpm run ...` instead of invoking the canonical backend and Electron dev entry scripts directly from known repo paths.
- Detect earlier: after Windows launcher changes, run full `npm run dev`, not just `node scripts/dev.cjs`, and verify backend plus Electron both start without `ENOENT ... C:\Windows\package.json`.
- Prevention rule: repo launchers must call canonical child entry scripts directly with explicit `cwd`; do not nest dev startup through package-manager subcommands when a stable script path already exists.

### Icon asset transparent-margin regression
- What went wrong: the Windows taskbar icon looked much smaller than other desktop apps even though the source logo itself was high resolution.
- Why it happened: the brand asset generator preserved transparent margins from the source art and used a thumbnail-style resize path that never upscaled trimmed artwork, so the visible mark only occupied about 70-83% of the icon canvas.
- Detect earlier: after changing branding assets, measure the non-transparent bounds of generated `build/icon.ico` and `build/icons/*` outputs and compare the visible-area ratio against the source intent.
- Prevention rule: packaging icons must trim transparent outer margins before resizing, use explicit scale-and-resize logic that can upscale to the target canvas, and render with a defined icon padding ratio instead of inheriting arbitrary empty space from the source canvas.

### Model install root drift
- What went wrong: the Models UI could show `completed` downloads while still marking the same model as `Not Installed`.
- Why it happened: Electron wrote model files under the roaming app-data models directory, but backend install-state checks defaulted to a separate repo-local `./models` path.
- Detect earlier: after a model download completes, compare the downloader target path with `/api/models/catalog` install paths in the same session.
- Prevention rule: backend model install-state, runtime loading, and Electron download management must share one canonical models root, and default paths must match the Electron user-data contract on desktop builds.

### Floating warmup duplicate-state rendering
- What went wrong: the floating hotkey warmup state rendered the same model-loading message in both the prep panel and the transcript body.
- Why it happened: the new warmup panel was added without suppressing the empty transcript placeholder for the same state.
- Detect earlier: when adding a new floating phase, verify each phase has one primary status surface and run the floating-window test against the rendered DOM.
- Prevention rule: floating warmup/loading states must have a single authoritative message surface; when a dedicated status panel is visible, transcript placeholders must stay empty unless they add distinct information.

### Tray reopen dead window
- What went wrong: tray click and tray show flows could target a destroyed main window, leaving the app apparently stuck in the tray.
- Why it happened: tray handlers assumed `state.mainWindow` existed and was still usable after close/minimize lifecycle changes.
- Detect earlier: after changing main-window close semantics, exercise tray click, tray show, and reopen-from-hidden flows against both hidden and destroyed window states.
- Prevention rule: tray entrypoints must recreate the main window when the reference is missing or destroyed; never early-return on a stale window handle.

### Explicit floating finish action drift
- What went wrong: clicking floating `Finish` could inherit the default stop mode and behave like `Finish & Paste`.
- Why it happened: the explicit floating action reused config-derived pending-action fallback logic instead of locking its own intent.
- Detect earlier: for each floating action, assert the pending action seen by the stop path in a focused IPC test.
- Prevention rule: explicit floating actions must set an explicit pending action and never inherit another finish mode from defaults.

### Tray quick-settings live-state drift
- What went wrong: tray quick-setting changes could persist to disk without refreshing renderer-visible settings or reapplying the active Electron hotkey config.
- Why it happened: only one tray toggle path emitted `settings-updated` and called `applyHotkeyConfig`; the other quick-setting branches saved settings in isolation and left `state.cachedSettings` stale.
- Detect earlier: after changing any tray or quick-settings handler, verify one toggle from each submenu updates persisted settings, `state.cachedSettings`, Electron hotkey state, and renderer subscriptions in the same run.
- Prevention rule: every Electron tray/quick-settings mutation must use one shared persistence path that updates cached settings, reapplies hotkey config when relevant, and emits the canonical renderer settings refresh event.

### Wildcard CORS with credentials
- What went wrong: the FastAPI API allowed `allow_origins=["*"]` together with credentialed CORS responses, which is rejected by browsers and weakens intent around trusted origins.
- Why it happened: the desktop-local API kept a permissive wildcard origin while also enabling credentials by default.
- Detect earlier: inspect middleware configuration whenever API transport defaults change and reject wildcard-plus-credentials combinations in a focused test.
- Prevention rule: never combine wildcard CORS origins with `allow_credentials=True`; if origins stay wildcard, credentials must stay disabled.

### Local-only WebSocket auth fallback
- What went wrong: the shared WebSocket server accepted unauthenticated connections outright and also kept a hardcoded token example, making the transport look protected when it was not.
- Why it happened: the desktop-local assumption bypassed auth entirely instead of restricting unauthenticated access to loopback clients and environment-configured tokens.
- Detect earlier: for every WebSocket auth change, test one loopback client, one non-loopback unauthenticated client, and one token-authenticated client against the same connection class.
- Prevention rule: desktop-local WebSocket fallbacks may skip explicit auth only for verified loopback clients; any non-local access must require a real configured token, never a hardcoded placeholder.

### Settings name drift between backend and frontend
- What went wrong: the frontend used `mute_transcripta_audio_during_dictation` while backend used `mute_openwispr_audio_during_dictation`, causing setting changes to have no effect.
- Why it happened: legacy "Transcripta" naming wasn't updated consistently when renamed to "OpenWispr".
- Detect earlier: run tests/test_settings_wiring.py which validates backend/frontend setting name consistency.
- Prevention rule: any setting rename must update all layers (backend registry, frontend schema, frontend components, migrations) in the same change; run settings wiring tests before merging.

### Settings options drift between backend and API
- What went wrong: backend settings definition had `transcription_mode` options ["dictation", "literal"] but API accepted "session_paragraph", creating validation mismatch.
- Why it happened: settings definition not synchronized with API schema.
- Detect earlier: compare SettingDefinition.options with Literal types in API route handlers.
- Prevention rule: backend settings options must match API Literal types exactly; add wiring test to catch drift.

### Package.json main entry mismatch
- What went wrong: package.json specified main: "app/electron/main/index.js" but actual file was "app/electron/main/main.js", causing startup failure.
- Why it happened: copy-paste error from template.
- Detect earlier: electron startup will fail immediately; verify file exists before packaging.
- Prevention rule: main entry in package.json must point to existing file; validate on build.

### Module size violation
- What went wrong: app/electron/main/main.js exceeded 1900 lines, violating the 300-500 line module guideline.
- Why it happened: organic growth without module splitting.
- Detect earlier: measure module line count during lint.
- Prevention rule: split modules exceeding 500 lines; use clear subdirectory structure (windows/, tray/, hotkey/, etc.).

## Required Rules For New Work

- If a UI control is visible, it must change real behavior; remove or hide placebo controls.
- For bug fixes, add or update at least one focused regression test.
- For non-trivial workflow changes, add the smallest sensible mix: unit + integration/wiring + regression, and E2E only when user-visible flow changed materially.
- When changing event schemas, update backend and frontend consumers in the same change.
- When changing Python config/text/constants, regenerate or update frontend generated exports in the same change.
- Keep one active SSE/WebSocket subscription per workflow/route with stable dependency cleanup.
- Avoid repeated idle polling loops for `/api/settings`, `/api/devices`, `/api/session`, `/api/models/catalog`; load once, cache, and resubscribe only when needed.
- Keep microphone and system audio as mutually exclusive active capture modes.
- For risky fixes, include the smallest useful verification note in the change: what contract was checked, what tests ran, and what user-visible path was validated.
- If a file move or ownership change leaves a temporary shim, add a follow-up cleanup note instead of pretending the migration is complete.

## Regression Checklist

- Floating waveform uses real amplitude data (no fake animation).
- Floating timer starts immediately, increments correctly, and resets on cancel/finish.
- Floating transcript auto-scrolls only while pinned to bottom and pauses when user scrolls up.
- Cancel discards transcript with no paste/copy; Finish follows configured finish behavior.
- Transcription presets change active runtime profile behavior.
- Code/log cleanup mode preserves numbers, percentages, versions, hotkeys, uppercase tokens, and command-like strings.
- Models section owns runtime/download/cache controls only.
- Backend/Electron/frontend consumers still agree on touched event payloads.
- Settings changes preserve backend registry, generated frontend outputs, and renderer behavior alignment.
- Moved files still resolve in package/build/runtime/test contexts where compatibility is expected.
- Any new queue/cache/retry/background loop is bounded and has explicit cleanup behavior.

## Stop-And-Rethink Triggers

Pause and reassess before merging if:
- a fix adds a second schema/default/config owner
- a change introduces new polling, a new queue, or a new background loop without a bound
- a UI control does not map to real behavior
- a migration leaves old and new paths active without a clear ownership note
- a docs change describes target architecture as already implemented
- a change crosses backend/Electron/frontend boundaries without an explicit contract check
- a bug fix “works” only because a failing test or consumer was bypassed
- a report/doc claim is being repeated without verification against current code

## Before Merging

- Run the smallest relevant backend/frontend tests for touched areas.
- For hotkey/session changes, verify transcript correctness and model routing in logs.
- For download changes, verify resume/retry behavior and monotonic progress.
- For settings/config/schema changes, verify backend registry, generated frontend outputs, and renderer consumers together.
- For Electron file moves, verify imports, packaging globs, and packaged/runtime entrypoints.
- For docs changes after runtime moves, verify inventory/source-of-truth paths are updated in the same batch.