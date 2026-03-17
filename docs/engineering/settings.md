---
title: Settings System
description: Persistent settings management with sync and migration support
audience: developers
last_verified: 2026-03-15
source_of_truth:
  - app/core/settings/manager.py
  - app/api/routes/settings.py
  - app/config/settings.py
---

# Settings System

The settings system provides persistent storage, validation, and synchronization of user preferences across the OpenWispr application.

## Overview

Two primary components manage settings:

1. **SettingsManager** (`app/core/settings_manager.py:431`) - Core storage and persistence
2. **SettingsSynchronizer** (`app/api/settings_sync.py:67`) - WebSocket sync coordination

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Settings System                          │
│                                                                 │
│  ┌─────────────────────┐      ┌─────────────────────────────┐  │
│  │   SettingsManager   │      │   SettingsSynchronizer      │  │
│  │                     │      │                             │  │
│  │  ┌───────────────┐  │      │  ┌───────────────────────┐  │  │
│  │  │ SettingsState │  │◀────▶│  │  Conflict Resolution  │  │  │
│  │  │ (dataclasses) │  │      │  │  Delta Calculation    │  │  │
│  │  └───────────────┘  │      │  │  Batch Updates        │  │  │
│  │                     │      │  └───────────────────────┘  │  │
│  │  ┌───────────────┐  │      │                             │  │
│  │  │SettingsContainer│  │◀────▶│  ┌───────────────────────┐  │  │
│  │  │(Mode-specific)│  │      │  │  WebSocket Broadcast    │  │  │
│  │  └───────────────┘  │      │  │  Client Subscriptions   │  │  │
│  │                     │      │  └─────────────────────────┘  │  │
│  │  ┌───────────────┐  │      └─────────────────────────────┘  │
│  │  │   Validation  │  │                                        │
│  │  │   Migration   │  │                                        │
│  │  └───────────────┘  │                                        │
│  └─────────────────────┘                                        │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────┐                    │
│  │      user_settings.json (disk)          │                    │
│  └─────────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘

## Known Issues (Audit 2026-03-08)

The following 17 bugs were identified in the settings system:

### CRITICAL (2)

| Bug ID | Description | Location |
|--------|-------------|----------|
| SET-001 | Duplicate backend setting: both `backend` and `audio_backend` exist in AudioSettings, causing confusion about which takes precedence | `app/config/settings.py:472-489` |
| SET-002 | Deprecated VAD settings in AudioSettings: `vadEnabled` and `vadThresholdDb` duplicate transcription settings but are not used by runtime | `app/config/settings.py:499-518` |

### HIGH (2)

| Bug ID | Description | Location |
|--------|-------------|----------|
| SET-003 | `style_default_profile` default mismatch: empty string in style settings vs. computed default in backend | `app/config/settings.py:888` |
| SET-004 | `refinement_profile` migration default mismatch: schema shows `clean_dictation` but migration may produce `raw` | `app/config/settings.py` + migration logic |

### MEDIUM (5)

| Bug ID | Description | Location |
|--------|-------------|----------|
| SET-005 | `transcription_mode` option mismatch: schema at `app/config/settings.py:209` includes `dictation` and `literal` but valid options may differ | Schema vs. runtime validation |
| SET-006 | Fake/not-working settings exposed in UI: certain settings marked as functional but have no runtime effect | Frontend components |
| SET-007 | Frontend settings defaults drift from backend registry | Generated settings vs. `app/config/settings.py` |
| SET-008 | Model routing inconsistency: source-specific model IDs (`microphone_asr_model_id`, `system_asr_model_id`) not always respected | STT module routing |
| SET-009 | Duplicate VAD config locations: audio category has VAD, transcription has VAD, mode-specific has VAD | Multiple dataclasses |

### LOW (8)

| Bug ID | Description | Location |
|--------|-------------|----------|
| SET-010 | Settings sync delta calculation may miss nested object changes | `app/api/settings_sync.py:234` |
| SET-011 | Batch update interval may cause stale reads | `app/api/settings_sync.py:448` |
| SET-012 | Import validation allows unknown categories silently | `app/core/settings_manager.py:474` |
| SET-013 | Mode-specific settings override validation not enforced | Mode switching logic |
| SET-014 | Hotkey settings key_combination vs microphone_key_combination overlap | `app/config/settings.py` hotkey section |
| SET-015 | Coach prompt overrides structure complex/misleading | CoachSettings dataclass |
| SET-016 | Environment variable prefix inconsistency: some use `OPENWISPR_`, others implied | `app/config/constants.py` |
| SET-017 | Settings version migration not atomic | `app/core/settings_manager.py:391` |

## Settings Architecture

### SettingsState (`app/core/settings_manager.py:413`)

Top-level container for all settings:

```python
@dataclass
class SettingsState:
    general: GeneralSettings
    transcription: TranscriptionSettings
    refiner: RefinerSettings
    audio: AudioSettings
    hotkey: HotkeySettings
    coach: CoachSettings
    advanced: AdvancedSettings
    modes: ModeSpecificSettings
    version: int = CURRENT_SETTINGS_VERSION  # 5
```

### Category Schemas

#### GeneralSettings
```python
@dataclass
class GeneralSettings:
    defaultSessionTitle: str
    defaultLanguage: str
    exportDirectory: str
    autoSaveInterval: int
    showNotifications: bool
    minimizeToTray: bool
    startupWithSystem: bool
    theme: str
```

#### TranscriptionSettings
```python
@dataclass
class TranscriptionSettings:
    model_name: str
    default_asr_model_id: str
    microphone_asr_model_id: str
    system_asr_model_id: str
    refinement_mode: str
    refinement_profile: str
    transcription_mode: str
    compute_type: str  # int8, float16, float32
    chunk_duration: float
    overlap_ratio: float
    vad_enabled: bool
    vad_threshold_db: float
    vad_min_silence_ms: int
    vad_speech_pad_ms: int
    confidence_threshold: float
    enable_filler_filter: bool
    enable_hallucination_filter: bool
    min_segment_length: float
    max_workers: int
    use_parallel_processing: bool
    preload_model: bool
    hotkey_optimized: bool
    beam_size: int
    best_of: int
    patience: float
    temperature: float
```

#### AudioSettings
```python
@dataclass
class AudioSettings:
    captureMode: str
    default_capture_source: str  # microphone, system
    defaultDeviceId: str
    backend: str
    audio_backend: str
    sampleRate: int
    vadEnabled: bool
    vadThresholdDb: float
    noiseFiltering: bool
    echoCancellation: bool
    autoGainControl: bool
```

#### HotkeySettings
```python
@dataclass
class HotkeySettings:
    enabled: bool
    key_combination: str
    microphone_key_combination: str
    system_key_combination: str
    hold_mode: bool
    auto_inject: bool
    language: str
    device_id: str
    capture_source: str
    finish_mode_default: str
    enable_refiner_on_stop: bool
    save_debug_wav: bool
    show_floating_window: bool
    floating_window_position: str
    record_on_start: bool
    stop_on_release: bool
    copy_to_clipboard: bool
```

#### CoachSettings
```python
@dataclass
class CoachSettings:
    coach_enabled: bool
    coach_show_live_hints: bool
    coach_detail_level: str  # compact, standard, deep
    copy_polished_by_default: bool
    show_diff_view: bool
    coach_template_id_mic: str
    coach_template_id_system: str
    coach_prompt_custom_enabled: bool
    coach_prompt_custom_text: str
    coach_overrides: CoachPromptOverrides
    privacy_mode: str  # local_only, allow_llm
    show_floating_coach_result: bool
    coach_prompt_templates: list[CoachPromptTemplateSettings]
```

#### RefinerSettings
```python
@dataclass
class RefinerSettings:
    selected_model_id: str
    runtime_enabled: bool
    cleanup_instructions: str
    engine_preference: str
```

#### AdvancedSettings
```python
@dataclass
class AdvancedSettings:
    debugMode: bool
    logLevel: str
    enableMetrics: bool
    maxLogFiles: int
    experimentalStem: bool
    experimentalGpuAccel: bool
```

### Mode-Specific Settings

```python
@dataclass
class ModeSpecificSettings:
    wispr: dict[str, Any]  # Hotkey mode
    system: dict[str, Any]  # System audio mode
    active_mode: str  # "wispr" or "system"
```

Mode settings include:
- `model_name` - ASR model for this mode
- `beam_size` - Beam search width
- `best_of` - Best-of sampling
- `vad_threshold` - VAD sensitivity
- `chunk_duration` - Processing chunk size
- `overlap_ratio` - Window overlap
- `compute_type` - Quantization type
- `vad_enabled` - VAD on/off
- `hotkey_optimized` - Low-latency mode

## Persistence

### Storage Location

```python
SETTINGS_FILENAME = "user_settings.json"
# Default: <app_dir>/user_settings.json
```

### Save Format

Settings are stored as JSON with full dataclass serialization:

```python
def _save(self) -> None:
    self.settings_path.parent.mkdir(parents=True, exist_ok=True)
    self._settings.modes = ModeSpecificSettings.from_container(self._mode_container)
    with open(self.settings_path, "w", encoding="utf-8") as f:
        json.dump(asdict(self._settings), f, indent=2)
```

### Thread Safety

All read/write operations are protected by `threading.RLock`:

```python
def get_settings(self) -> SettingsState:
    with self._lock:
        return self._settings

def update_settings(self, settings: SettingsState) -> None:
    with self._lock:
        self._settings = settings
        self._save()
        self._notify_sync("settings_update", self.get_settings_dict())
```

## Sync Protocol

### SyncConfig (`app/api/settings_sync.py:43`)

```python
@dataclass
class SyncConfig:
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_resolution: SyncConflictResolution = SyncConflictResolution.SERVER_WINS
    debounce_ms: float = 100.0
    validate_on_receive: bool = True
    notify_on_change: bool = True
    batch_updates: bool = True
    batch_interval_ms: float = 50.0
```

### Sync Directions

```python
class SyncDirection(str, Enum):
    SERVER_TO_CLIENT = "server_to_client"
    CLIENT_TO_SERVER = "client_to_server"
    BIDIRECTIONAL = "bidirectional"
```

### Message Types

| Event Type | Description |
|------------|-------------|
| `settings_update` | Full settings replacement |
| `partial_update` | Category-specific update |
| `mode_change` | Active transcription mode changed |
| `mode_settings_update` | Mode-specific settings changed |
| `mode_reset` | Mode reset to defaults |
| `reset` | All settings reset |
| `import` | Settings imported from file |

### Delta Calculation

```python
async def get_settings_delta(self) -> dict[str, Any] | None:
    current = self.settings_manager.get_settings_dict()

    if self._last_synced_settings is None:
        self._last_synced_settings = copy.deepcopy(current)
        return None

    delta = {}
    for category, settings in current.items():
        if isinstance(settings, dict):
            last_category = self._last_synced_settings.get(category, {})
            category_delta = {}
            for key, value in settings.items():
                if last_category.get(key) != value:
                    category_delta[key] = value
            if category_delta:
                delta[category] = category_delta

    self._last_synced_settings = copy.deepcopy(current)
    return delta if delta else None
```

## Conflict Resolution

### Resolution Strategies

```python
class SyncConflictResolution(str, Enum):
    SERVER_WINS = "server_wins"      # Server values override client
    CLIENT_WINS = "client_wins"      # Client values override server
    LAST_WRITE_WINS = "last_write_wins"  # Timestamp-based
    REJECT = "reject"                # Reject conflicting update
```

### Current Implementation

Default is `SERVER_WINS` for bidirectional sync. Client updates are validated before application:

```python
async def handle_client_update(
    self,
    settings_update: dict[str, Any],
    connection: WebSocketConnection,
) -> dict[str, Any]:
    # Extract and validate
    for key, value in updates.items():
        is_valid, error = await self._validate_change(category, key, value)
        if is_valid:
            valid_updates[key] = value
        else:
            validation_errors.append({"key": key, "error": error})

    # Apply or queue
    if immediate or not self.config.batch_updates:
        await self._apply_changes(category, valid_updates, "client")
    else:
        await self._queue_changes(category, valid_updates, "client")
```

## Validation

### Category Validation

```python
def validate_category(self, category: str, updates: dict[str, Any]) -> ValidationResult:
    return self._validator.validate_category(category, updates, check_unknown=True)
```

### ValidationResult

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    settings: dict[str, Any]
```

## Migration

### Migration Flow

```python
def _load(self) -> None:
    with open(self.settings_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Migrate if needed
    if needs_migration(data):
        data = migrate_to_current(data)
    data = _normalize_settings_payload(data)
```

### Normalization

The `_normalize_settings_payload` function (`app/core/settings_manager.py:68`) handles legacy settings:

```python
def _normalize_settings_payload(data: dict[str, Any]) -> dict[str, Any]:
    # Legacy hotkey model migration
    legacy_hotkey_model = hotkey.pop("model_name", None)

    # Capture source normalization
    default_capture_source = _normalize_capture_source(
        audio.get("default_capture_source") or audio.get("captureMode")
    )

    # Model ID normalization (runtime name → catalog ID)
    transcription["default_asr_model_id"] = (
        _normalize_asr_model_id(transcription.get("default_asr_model_id"))
        or _normalize_asr_model_id(transcription.get("model_name"))
        or _normalize_asr_model_id(legacy_hotkey_model)
        or get_setting("default_asr_model_id").default
    )
```

### Model ID Mapping

```python
RUNTIME_TO_CATALOG_MODEL = {
    "tiny": "whisper-tiny",
    "base": "whisper-tiny",
    "small": "whisper-small",
    "medium": "whisper-medium",
    "large-v3": "whisper-large-v3",
    "turbo": "whisper-turbo",
}
```

## Batching

Rapid settings changes are batched to reduce I/O:

```python
async def _queue_changes(self, category: str, updates: dict[str, Any], source: str) -> None:
    async with self._lock:
        if category not in self._batched_updates:
            self._batched_updates[category] = {}
        self._batched_updates[category].update(updates)

        # Cancel existing batch task
        if self._batch_task and not self._batch_task.done():
            self._batch_task.cancel()

        # Start new batch task
        self._batch_task = asyncio.create_task(self._process_batch(source))

async def _process_batch(self, source: str) -> None:
    await asyncio.sleep(self.config.batch_interval_ms / 1000.0)
    # Apply batched updates
```

## Import/Export

### Export Format

Full settings as JSON with all categories and version info.

### Import Flow

```python
def import_settings(self, data: dict[str, Any]) -> bool:
    # Validate required categories
    required = ["general", "transcription", "refiner", "audio", "hotkey", "coach", "advanced"]
    for cat in required:
        if cat not in data:
            data[cat] = {}

    data = _normalize_settings_payload(data)

    # Run validation
    validation = self._validator.validate(data, check_unknown=True)
    if not validation.is_valid:
        return False

    # Apply settings
    self._settings = SettingsState(...)
    if "modes" in data:
        self._mode_container = ModeSpecificSettings(...).to_container()

    self._save()
    self._notify_sync("import", self.get_settings_dict())
    return True
```

## Global Instance

### Singleton Pattern

```python
_settings_manager: SettingsManager | None = None
_settings_lock = threading.Lock()

def get_settings_manager() -> SettingsManager:
    global _settings_manager
    if _settings_manager is None:
        with _settings_lock:
            if _settings_manager is None:
                _settings_manager = SettingsManager()
    return _settings_manager
```

## Key Code Paths

| Function | File | Line | Purpose |
|----------|------|------|---------|
| `get_settings_manager` | settings_manager.py | 880 | Global instance accessor |
| `_load` | settings_manager.py | 459 | Settings loading |
| `_save` | settings_manager.py | 555 | Settings persistence |
| `_normalize_settings_payload` | settings_manager.py | 68 | Legacy migration |
| `update_partial` | settings_manager.py | 679 | Category update |
| `get_settings_synchronizer` | settings_sync.py | 417 | Sync instance accessor |
| `handle_client_update` | settings_sync.py | 124 | Client update handler |
| `_apply_changes` | settings_sync.py | 313 | Apply with validation |
| `get_settings_delta` | settings_sync.py | 234 | Delta calculation |

## Related Documentation

- [Architecture Overview](./architecture-overview.md) - System architecture
- [Dictation Pipeline](./dictation-pipeline.md) - Transcription settings usage
- [English Coach](./english-coach.md) - Coach settings
