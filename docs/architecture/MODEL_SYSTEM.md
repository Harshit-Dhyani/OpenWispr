---
title: Model System Architecture
audience: developers
last_verified: 2026-03-04
source_of_truth:
  - app/core/model_catalog.py
  - app/api/model_service.py
  - app/audio/transcription.py
---

# Model System

## Source of truth

`app/core/model_catalog.py` is the canonical model catalog.

- It defines ASR and refiner models.
- It defines download artifacts and runtime defaults.
- It is the only place where a model should be introduced or removed.

## Runtime contract

`app/api/model_service.py` converts the backend catalog into the API payload served by `/api/models/catalog`.

- The frontend should consume that payload.
- Electron download logic should consume that payload.
- Frontend state in `app/electron/frontend/src/lib/modelRegistry.ts` is a cache of API data, not a second catalog.

## Downloads and install state

- Downloaded models live under the backend download root, grouped by `category/id`.
- Install verification is performed in `ModelService._install_state()`.
- Electron main owns the download workflow in `app/electron/main/model-download-manager.js`.
- The downloader should not hardcode model lists; it should work from the backend catalog payload.

## Selection and persistence

- Selected ASR model is persisted in settings as `transcription.default_asr_model_id`.
- Selected refiner model is persisted in settings as `refiner.selected_model_id`.
- Refinement mode is persisted in settings as `transcription.refinement_mode`.

## ASR and refiner flow

1. Hotkey transcription creates the ASR transcriber from backend settings.
2. Partial transcript updates are emitted without refiner processing.
3. On finalized hotkey stop, backend collects the final ASR text.
4. If refinement is enabled and a local refiner model is available, `app/api/refiner_service.py` applies strict text cleanup.
5. If refiner output is empty or rewrites protected technical tokens too aggressively, backend falls back to the original finalized text.

## Guardrails

- Refinement is local-first through llama.cpp-backed GGUF models.
- Strict refinement should improve punctuation, capitalization, spacing, and paragraphing without changing meaning.
- Technical tokens such as identifiers, filenames, formulas, numbers, and units must be preserved.
