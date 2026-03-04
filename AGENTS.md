# Transcripta Agent Guidance

Keep this file short. Only add rules that prevent repeat regressions.

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
- Keep exactly one active SSE/WebSocket subscription per workflow/route. New listeners must have stable deps and guaranteed cleanup.
- Do not introduce repeated idle polling loops for `/api/settings`, `/api/devices`, `/api/session`, or `/api/models/catalog`. Load once, cache, and resubscribe only when needed.
- Prefer one canonical source of truth for shared constants/settings. Compatibility shims are acceptable; duplicate live definitions are not.
- Keep microphone and system audio as mutually exclusive active capture modes.

## Before Merging

- Run the smallest relevant backend/frontend tests for the touched area.
- If you changed hotkey/session flows, verify both transcript correctness and model routing in logs.
- If you changed downloads, verify resume/retry behavior and monotonic progress.
