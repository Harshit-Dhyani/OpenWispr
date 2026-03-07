# OpenWispr Agent Guidance

Keep this file short. Only add rules that prevent repeat regressions.


## Engineering Standards

- Treat this as a public repo. Never commit personal identifiers, real transcript snippets, or user-specific examples.
- Do not add user-facing copy inline. Put renderer strings in `app/electron/frontend/src/strings/en.ts`, Electron shell strings in `app/electron/strings/en.js`, backend API copy in `app/api/strings/en.py`, and prompt text in `app/stt/prompts.py`.
- Do not let files grow without bounds. If a module mixes routing, orchestration, and pure logic or grows past roughly 300-500 lines, split it by responsibility before adding more behavior.
- Keep boundaries clean:
  - routes: HTTP/WebSocket validation and transport only
  - services: orchestration and stateful business logic
  - STT modules: decoding, aggregation, cleanup, refinement, prompts
  - utilities: pure helpers with focused tests

## Never Reintroduce These Bugs

- Always route transcript/websocket/SSE payloads through a single JSON-safe encoder. Numpy scalars/arrays, dataclasses, `datetime`, and `Path` must never be sent raw.
- Do not append live transcript text for the same session/segment. Draft and final transcript updates must replace by `session_id + segment_index` (or equivalent stable key).
- Do not share live transcript state between Dictation and Sessions. Keep separate scoped slices and render only the active mode's data.
- Do not emit duplicate hotkey transcript events for the same draft/final update. One live draft lane and one final lane only.
- Do not let microphone/system model selection drift. Active capture source must resolve the matching ASR model:
  - microphone -> `microphone_asr_model_id`
  - system -> `system_asr_model_id`
  - fallback only if the source-specific model is unset
- Do not show fake progress. Downloads may show percent only when total size is known. Model preload/model warmup must use truthful state labels, not fake `0%` progress.
- Do not hard-fail model downloads on optional Hugging Face artifacts. Missing vocabulary-style files must be skipped gracefully.
- Do not make refiner runtime mandatory. If `llama-cpp-python` is unavailable, degrade once, log clearly once, and return original text safely.
- Do not treat normal SSE/WebSocket client disconnects as application errors. Handle `CancelledError` and clean closes as expected behavior.
- Do not log everything at DEBUG just because debug mode is enabled. `debugMode` controls extra diagnostics; `logLevel` controls verbosity.
- Do not leave verbose backend or Electron dev logging on by default. Default to INFO/WARNING noise levels unless `TRANSCRIPTA_LOG_LEVEL=DEBUG` is explicitly set.
- Do not trust legacy class names or stale UI labels as truth. Use resolved runtime fields (`capture_source`, resolved device kind, resolved model id, runtime model name).
- Do not let hotkey final text sources drift. For microphone dictation, `aggregated_clean_text` is the canonical deterministic final transcript, `paste_text` is the only text Electron should inject/copy, and coach/refiner output must layer on top of that instead of rebuilding from raw segments elsewhere.
- Do not hardcode a separate tray/quick-settings palette. Shared app themes must come from the common theme-token source so the main window, quick settings, and floating surfaces stay visually aligned.
- Do not ship fake floating-window activity. Waveforms must come from real live audio amplitude (RMS/peak from PCM), silence must render flat, and the floating timer must be owned by a local monotonic clock instead of transcript events.
- Do not let floating-window transcript UX regress. The transcript surface must stay scrollable, auto-scroll only while pinned to bottom, and Cancel/Finish must respect discard vs configured finish behavior without reopening stale result state.
- Do not split transcription behavior settings across unrelated sections. Language, presets, finish action, refinement intensity/profile, and cleanup instructions belong under Transcription; Models is only for download/cache/runtime controls.
- Do not let finish-time cleanup profiles corrupt technical text. Protect decimals, percentages, version-like strings, hotkeys, uppercase tokens, and code/log tokens with placeholders before runtime cleanup and restore them exactly afterward.
- Do not reintroduce `Style` as a top-level workflow page. Writing tone is configured inside Settings; top-level navigation is for workflows (`Home`, `Microphone`, `System Audio`, `Dictionary`, `Snippets`, `Settings`).
- Do not let transcript cleanup and writing tone overlap in UI copy. Cleanup/refinement controls govern transcript fidelity and finalization; writing tone is optional post-cleanup wording only.
- Do not default normal microphone dictation to code/log cleanup behavior. Spoken-English defaults must stay faithful-first (`clean_dictation`-style cleanup) unless the user explicitly switches profiles.
- Do not leave Settings wiring half-removed. If `App.tsx` passes model/settings callbacks into `SettingsPanel`, the corresponding functions must exist and use the current Electron/backend contract.
- What went wrong: frontend settings defaults and validation drifted away from the backend settings registry.
- Why it happened: handwritten renderer schema layers duplicated ownership that already existed in `app/config/settings.py` and generated settings outputs.
- Detect earlier: whenever a setting is added, renamed, or re-categorized, compare the backend registry, generated frontend settings output, and renderer consumers in the same change.
- Prevention rule: do not maintain parallel handwritten frontend settings defaults or validation rules unless the divergence is explicitly justified; `app/config/settings.py` remains the leading registry and generated settings outputs must be updated in the same change.
- Do not shadow imported Electron window/service helpers with local booleans or config flags. Keep decision flags and callable helpers named distinctly, especially around floating window and coach result flows.
- Do not maintain a hand-written frontend settings schema/default source in parallel with `app/config/settings.py` and `app/config/generate_ts.py` outputs. What went wrong: settings ownership drifted across backend registry, generated TS metadata, and `app/electron/frontend/src/lib/settingsSchema.ts`; why: renderer validation/defaults were maintained separately from the declared registry; detect earlier: compare added or renamed settings against `config/generated/settings.ts` and renderer consumers before merging; prevention rule: backend registry stays authoritative and any frontend schema layer must be generated from it or proved necessary with sync coverage.

## Required Rules For New Work

- If a control is visible in the UI, it must change real behavior. Remove or hide placebo controls.
- When fixing a bug, add or update at least one focused regression test.
- For any non-trivial feature or workflow change, add the smallest sensible test mix:
  - unit test for local logic
  - integration test for wiring/contracts
  - regression test for the bug or failure mode
  - E2E coverage if the user-visible flow changed materially
  - property-style/invariant test when ordering, serialization, dedupe, or aggregation logic is involved
- When changing event schemas, update both backend and frontend consumers in the same change.
- When changing config/text/constants on the Python side, update the generated frontend exports or regenerate them in the same change.
- Keep exactly one active SSE/WebSocket subscription per workflow/route. New listeners must have stable deps and guaranteed cleanup.
- Do not introduce repeated idle polling loops for `/api/settings`, `/api/devices`, `/api/session`, or `/api/models/catalog`. Load once, cache, and resubscribe only when needed.
- Prefer one canonical source of truth for shared constants/settings. Compatibility shims are acceptable; duplicate live definitions are not.
- Keep microphone and system audio as mutually exclusive active capture modes.

## Regression Checklist

- Floating waveform is driven by real amplitude data, not fake animation.
- Floating timer starts immediately, increments correctly, and resets on cancel/finish.
- Floating transcript scrolls correctly, auto-scrolls only while pinned to the bottom, and pauses when the user scrolls up.
- Cancel discards transcript and closes without paste/copy. Finish uses the configured finish behavior.
- Floating header remains draggable, while transcript/buttons stay `no-drag`.
- Transcription presets actually update the active profile/runtime behavior.
- Code/Logs mode preserves numbers, percentages, versions, hotkeys, uppercase tokens, and command-like strings.
- Models owns runtime/download/cache controls only. Transcription owns language, presets, finish mode, and refinement behavior.

## Feature Placement

- Strings:
  - renderer copy -> `app/electron/frontend/src/strings/en.ts`
  - Electron shell copy -> `app/electron/strings/en.js`
  - backend API messages -> `app/api/strings/en.py`
- Prompts:
  - add new prompt templates or refiner instructions in `app/stt/prompts.py`
- Routes / services:
  - new HTTP/WebSocket handlers go in `app/api/routes/`
  - orchestration belongs in service modules, not routers
  - pure STT behavior belongs in `app/stt/`
- Tests:
  - pure logic -> unit test
  - wiring/contracts -> integration or smoke test
  - user-visible regression -> add the smallest focused regression for the affected flow
  - renderer copy rule -> run `python tools/check_renderer_strings.py`

## Before Merging

- Run the smallest relevant backend/frontend tests for the touched area.
- If you changed hotkey/session flows, verify both transcript correctness and model routing in logs.
- If you changed downloads, verify resume/retry behavior and monotonic progress.



