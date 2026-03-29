---
title: API Endpoints Reference
audience: developers
last_verified: 2026-03-19
note: This file supplements FastAPI /api/docs. Run `python -m app.api.generate_docs` to regenerate.
source_of_truth:
  - app/api/server.py
  - app/api/routes/
---

# API Endpoints Reference

This document provides a comprehensive reference of all API endpoints. For interactive exploration, use FastAPI's built-in docs at `/api/docs` or `/api/openapi.json`.

## REST Endpoints

### Session Management

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/session` | `get_session` | Get current session state |
| GET | `/api/metrics/streaming` | `streaming_metrics` | Get streaming audio metrics |
| POST | `/api/session/start` | `start_session` | Start a new transcription session |
| POST | `/api/session/stop` | `stop_session` | Stop the current session |
| POST | `/api/session/attach-pdf` | `attach_pdf` | Attach a PDF document for formula extraction |

### Hotkey Transcription

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/api/transcription/hotkey/start` | `hotkey_start` | Start hotkey push-to-talk transcription |
| POST | `/api/transcription/hotkey/stop` | `hotkey_stop` | Stop hotkey transcription, return final result |
| GET | `/api/transcription/hotkey/status` | `hotkey_status` | Get current hotkey session status |
| POST | `/api/transcription/hotkey/inject` | `hotkey_inject` | Inject text into active window |
| POST | `/api/hotkey/config` | `update_hotkey_config` | Update hotkey configuration |

### Models

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/models/catalog` | `get_model_catalog` | Get available Whisper models |
| POST | `/api/models/preload` | `preload_model` | Preload a model into memory |
| GET | `/api/models/cache` | `get_cached_models` | List currently cached models |
| DELETE | `/api/models/cache` | `clear_model_cache` | Clear all cached models |
| GET | `/api/models/state` | `get_model_state` | Get current model loading state |
| POST | `/api/models/select` | `select_model` | Select model for next session |
| POST | `/api/models/refinement-mode` | `set_refinement_mode` | Set refinement enable/disable |
| GET | `/api/refiner/status` | `get_refiner_status` | Get refiner service status |

### Providers (LLM)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/providers/health` | `get_provider_health` | Check provider health status |
| GET | `/api/providers/models` | `get_provider_models` | List available LLM models |
| GET | `/api/providers/all-models` | `get_all_models` | List all models from all providers |
| POST | `/api/providers/test` | `test_provider` | Test provider connection |
| GET | `/api/providers/settings` | `get_provider_settings` | Get provider configuration |

### Settings

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/settings` | `get_settings` | Get all application settings |
| POST | `/api/settings` | `update_settings` | Update application settings |
| POST | `/api/settings/reset` | `reset_settings` | Reset settings to defaults |

### History

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/history/sessions` | `list_sessions` | List all transcription sessions |
| GET | `/api/history/sessions/{session_id}` | `get_session_detail` | Get session details |
| POST | `/api/history/sessions/{session_id}/undo-ai-edit` | `undo_ai_edit` | Undo AI edit to session |
| POST | `/api/history/sessions/{session_id}/retry` | `retry_transcription` | Retry transcription for session |
| DELETE | `/api/history/sessions/{session_id}` | `delete_session` | Delete a session |
| GET | `/api/history/sessions/{session_id}/download` | `download_session` | Download session as file |
| GET | `/api/history/analytics` | `get_analytics` | Get transcription analytics |
| POST | `/api/history/cleanup` | `cleanup_history` | Clean up old sessions |

### Dictionary

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/dictionary` | `list_dictionary` | List dictionary entries |
| POST | `/api/dictionary` | `create_entry` | Create dictionary entry |
| PUT | `/api/dictionary/{entry_id}` | `update_entry` | Update dictionary entry |
| DELETE | `/api/dictionary/{entry_id}` | `delete_entry` | Delete dictionary entry |
| POST | `/api/dictionary/preview-apply` | `preview_apply` | Preview dictionary replacements |

### Snippets

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/snippets` | `list_snippets` | List text expansion snippets |
| POST | `/api/snippets` | `create_snippet` | Create new snippet |
| PUT | `/api/snippets/{snippet_id}` | `update_snippet` | Update snippet |
| DELETE | `/api/snippets/{snippet_id}` | `delete_snippet` | Delete snippet |
| POST | `/api/snippets/preview-expand` | `preview_expand` | Preview text expansion |
| POST | `/api/snippets/import` | `import_snippets` | Bulk import snippets |
| GET | `/api/snippets/export` | `export_snippets` | Export all snippets |

### Style Profiles

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/style/profiles` | `list_profiles` | List style profiles |
| POST | `/api/style/profiles` | `create_profile` | Create style profile |
| PUT | `/api/style/profiles/{profile_id}` | `update_profile` | Update style profile |
| DELETE | `/api/style/profiles/{profile_id}` | `delete_profile` | Delete style profile |
| POST | `/api/style/assignments` | `assign_profile` | Assign profile to session |
| POST | `/api/style/preview` | `preview_style` | Preview style transformation |

### Text Transform

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/api/text/transform` | `transform_text` | Apply text transformations |
| POST | `/api/corrections` | `add_correction` | Add user correction |
| GET | `/api/corrections` | `list_corrections` | List user corrections |
| DELETE | `/api/corrections/{correction_id}` | `delete_correction` | Delete correction |
| DELETE | `/api/corrections` | `clear_corrections` | Clear all corrections |
| GET | `/api/corrections/export` | `export_corrections` | Export corrections |
| POST | `/api/corrections/import` | `import_corrections` | Import corrections |

### System

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/health` | `health_check` | Get system health status |
| GET | `/api/devices` | `list_devices` | List audio input devices |
| GET | `/api/devices/{device_id}/probe` | `probe_device` | Test audio device |
| GET | `/api/system/storage` | `get_storage_info` | Get storage information |
| GET | `/api/system/profile` | `get_system_profile` | Get system performance profile |
| GET | `/api/system/optimize` | `get_optimization` | Get optimization suggestions |
| GET | `/api/system/presets` | `get_presets` | Get available presets |

### Coach

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/api/coach/prompt-preview` | `coach_prompt_preview` | Preview effective coach prompt |

### WebSocket Management

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/api/ws/broadcast` | `websocket_broadcast` | Broadcast to all WS clients |
| GET | `/api/ws/stats` | `websocket_stats` | Get WebSocket statistics |

## WebSocket Endpoints

| Path | Handler | Description |
|------|---------|-------------|
| `/api/ws` | `websocket_main` | Main WebSocket for real-time transcription |
| `/api/ws/audio` | `websocket_audio` | Audio visualization data stream |
| `/api/ws/settings` | `websocket_settings` | Bidirectional settings sync |
| `/api/transcription/hotkey/ws` | `hotkey_websocket` | Hotkey transcription updates |

## SSE (Server-Sent Events) Endpoints

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/events` | `events` | General event stream |
| GET | `/api/transcription/hotkey/events` | `hotkey_events` | Hotkey transcription events |

## Authentication

The API does not require authentication. The server runs locally on `localhost:8765` and is intended for the desktop application only.

## Common Response Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 400 | Bad Request | Invalid request parameters |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists or state conflict |
| 503 | Service Unavailable | Service not ready or initializing |

## WebSocket Message Types

- `transcription_partial` - Streaming partial transcription
- `transcription_final` - Final transcription segment
- `transcription_segment` - Complete segment with metadata
- `audio_level` - Audio level for visualization
- `audio_spectrum` - Frequency spectrum data
- `settings_update` - Settings change notification
- `health_metrics` - System health metrics
- `session_started` - Session start event
- `session_stopped` - Session stop event
- `hotkey_started` - Hotkey recording started
- `hotkey_stopped` - Hotkey recording stopped
- `hotkey_partial` - Hotkey partial transcription
- `ping` / `pong` - Heartbeat messages

---

*This documentation supplements FastAPI /api/docs. See `/api/openapi.json` for machine-readable schema.*
