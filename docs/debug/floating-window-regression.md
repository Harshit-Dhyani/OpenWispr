---
title: Floating Window Regression Report
description: Analysis of the floating window regression and compatibility fixes
audience: developers
last_verified: 2026-03-04
source_of_truth:
  - app/electron/main/windows/floatingWindow.js
  - app/electron/main/ipc/hotkeyHandlers.js
---

# Floating Window Regression Report

## Summary

The floating window regression was introduced during the Electron main-process refactor that split floating window state handling across:

- `app/electron/main/windows/floatingWindow.js`
- `app/electron/main/ipc/hotkeyHandlers.js`
- `app/electron/main/preload/floating.js`

The backend hotkey pipeline continued to emit valid websocket events and transcript payloads, but the floating renderer stayed stuck on `Waiting for speech...`.

## Last Known Good Behavior

The pre-refactor flow kept floating-window updates in the legacy Electron shell path and delivered recording/transcript state directly while the window was open. The last known good history for the current floating files is around:

- `39910972` `fix(hotkey): harden lifecycle and stop acknowledgement`
- older legacy UI path in commit `ddd466cd` under `ui-electron/floating-window.html`

## What Broke

The refactor preserved buffered audio-visualizer replay, but it did not preserve buffered replay for:

- recording state
- transcript text

That meant:

1. `Ctrl+T` started the backend session correctly.
2. Websocket events like `hotkey_started`, `hotkey_draft_partial`, and `hotkey_commit_final` were emitted.
3. If the floating renderer had not finished loading yet, those early updates were lost.
4. The floating page stayed on its default idle label and never caught up, even though transcription was happening.

## Contract Changes Restored

The compatibility fix restores and documents these expectations:

- `floatingWindow.js` now buffers and replays the latest:
  - `recording-state`
  - `transcription-update`
  - `audio-visualizer`
- `hotkeyHandlers.js` routes floating transcript updates through the shared floating-window helper instead of sending directly to the renderer.
- Backend stop now emits a stable `final_text` event in addition to `hotkey_stopped`.
- `session_paragraph` mode suppresses per-chunk `hotkey_commit_final` updates while still emitting one final paragraph at stop.

## Expected State Flow

1. `hotkey_started`
   - floating window switches from idle to recording/listening
2. `hotkey_draft_partial`
   - floating window shows live partial text
3. `hotkey_commit_final`
   - floating window updates committed transcript text
   - skipped when `transcription_mode == "session_paragraph"`
4. `hotkey_stop_ack` / `hotkey_stopping`
   - floating window switches to processing/finalizing
5. `final_text`
   - final deterministic paragraph becomes available for copy/paste and transcript display
6. `hotkey_stopped`
   - canonical stop payload arrives with final transcript metadata

## Manual Repro

1. Run `pnpm run dev`.
2. Press `Ctrl+T`.
3. Confirm the floating window leaves `Waiting for speech...` immediately.
4. Speak for a few seconds and confirm partial/final text appears.
5. Stop dictation and confirm:
   - the floating state moves to processing/finalizing
   - final transcript text is visible
   - `session_paragraph` mode only surfaces one final paragraph at the end
