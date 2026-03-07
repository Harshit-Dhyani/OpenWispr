# OpenWispr Agent Guidance

Keep this file short. Add only concrete rules that prevent repeat regressions.

## Engineering Standards

- Treat this as a public repo. Never commit personal identifiers, real transcript snippets, or user-specific examples.
- Do not add user-facing copy inline. Renderer copy -> `app/electron/frontend/src/strings/en.ts`; Electron shell copy -> `app/electron/strings/en.js`; backend API copy -> `app/api/strings/en.py`; prompt text -> `app/stt/prompts.py`.
- Keep boundaries clean: routes handle transport/validation only, services own orchestration, STT modules own decoding/aggregation/cleanup/refinement/prompts, utilities stay pure.
- Split mixed-responsibility modules before they exceed roughly 300-500 lines.

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

## Required Rules For New Work

- If a UI control is visible, it must change real behavior; remove or hide placebo controls.
- For bug fixes, add or update at least one focused regression test.
- For non-trivial workflow changes, add the smallest sensible mix: unit + integration/wiring + regression, and E2E only when user-visible flow changed materially.
- When changing event schemas, update backend and frontend consumers in the same change.
- When changing Python config/text/constants, regenerate or update frontend generated exports in the same change.
- Keep one active SSE/WebSocket subscription per workflow/route with stable dependency cleanup.
- Avoid repeated idle polling loops for `/api/settings`, `/api/devices`, `/api/session`, `/api/models/catalog`; load once, cache, and resubscribe only when needed.
- Keep microphone and system audio as mutually exclusive active capture modes.

## Regression Checklist

- Floating waveform uses real amplitude data (no fake animation).
- Floating timer starts immediately, increments correctly, and resets on cancel/finish.
- Floating transcript auto-scrolls only while pinned to bottom and pauses when user scrolls up.
- Cancel discards transcript with no paste/copy; Finish follows configured finish behavior.
- Transcription presets change active runtime profile behavior.
- Code/log cleanup mode preserves numbers, percentages, versions, hotkeys, uppercase tokens, and command-like strings.
- Models section owns runtime/download/cache controls only.

## Before Merging

- Run smallest relevant backend/frontend tests for touched areas.
- For hotkey/session changes, verify transcript correctness and model routing in logs.
- For download changes, verify resume/retry behavior and monotonic progress.
