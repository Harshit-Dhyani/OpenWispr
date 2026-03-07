---
title: Model Runtime and Routing
audience: developers
last_verified: 2026-03-05
source_of_truth:
  - app/core/model_catalog.py
  - app/api/model_service.py
  - app/stt/model_pool.py
  - app/electron/main/model-download-manager.js
  - app/core/system_profiler.py
---

# Model Runtime and Routing

## Overview

The model runtime system manages the complete lifecycle of AI models in OpenWispr:

1. **Model Catalog** - Canonical source of model definitions
2. **Installation State** - Verification of locally installed models
3. **Download Flow** - Resilient downloading with resume/retry
4. **Model Pool** - Caching and GPU memory management
5. **Source-Aware Selection** - Microphone vs system audio routing

## Model Catalog

Source: `app/core/model_catalog.py`

The `MODEL_CATALOG` tuple contains all supported models. Each entry is a `ModelCatalogEntry` dataclass:

```python
@dataclass(frozen=True, slots=True)
class ModelCatalogEntry:
    id: str                           # Unique identifier (e.g., "whisper-medium")
    display_name: str                 # Human-readable name
    category: ModelCategory           # "asr" | "refiner"
    family: ModelFamily               # "whisper" | "qwen" | "mistral" | "phi"
    engine: ModelEngine               # "faster-whisper" | "llamacpp" | "ollama"
    size_gb_estimate: float          # Download size estimate
    recommended_vram_gb: int          # Minimum VRAM recommendation
    speed_tier: SpeedTier            # "fast" | "balanced" | "quality"
    license_note: str                 # Licensing information
    description_short: str            # Brief description
    why_choose_this: str              # Selection guidance
    runtime_model_name: str | None   # Engine-specific name (e.g., "medium" for whisper)
    enabled_runtime: bool             # Whether available in runtime
    download_artifacts: tuple[DownloadArtifact, ...]
    default_runtime_config: dict[str, Any]
```

### ASR Models

| Model | Size | VRAM | Speed | Runtime | Status |
|-------|------|------|-------|---------|--------|
| `whisper-tiny` | 0.08 GB | 0 GB | fast | `tiny` | Enabled |
| `whisper-small` | 0.46 GB | 2 GB | fast | `small` | Enabled |
| `whisper-medium` | 1.5 GB | 5 GB | balanced | `medium` | Enabled |
| `whisper-large-v3` | 3.1 GB | 10 GB | quality | `large-v3` | Enabled |
| `whisper-turbo` | 1.6 GB | 6 GB | fast | `turbo` | Disabled |

### Refiner Models

| Model | Size | VRAM | Speed | Engine | Status |
|-------|------|------|-------|--------|--------|
| `qwen2.5-3b-instruct` | 1.93 GB | 4 GB | fast | llama.cpp | Disabled |
| `qwen2.5-7b-instruct` | 4.7 GB | 8 GB | balanced | llama.cpp | Disabled |
| `mistral-7b-instruct-v0.3` | 4.4 GB | 8 GB | quality | llama.cpp | Disabled |
| `phi-3-mini-4k-instruct` | 2.4 GB | 4 GB | fast | llama.cpp | Disabled |

### Download Artifacts

Each model specifies download artifacts from HuggingFace:

```python
def _hf_file(repo: str, filename: str, min_size_bytes: int) -> DownloadArtifact:
    return DownloadArtifact(
        filename=filename,
        url=f"https://huggingface.co/{repo}/resolve/main/{filename}?download=true",
        min_size_bytes=min_size_bytes,
    )
```

Artifacts include:
- **model.bin** (or .gguf) - Primary model weights
- **config.json** - Model configuration
- **tokenizer.json** - Tokenization vocabulary
- **vocabulary.txt** - Optional vocabulary file

### Catalog Access

```python
# List all models
list_model_catalog() -> list[dict]

# Get specific model
get_model_catalog_entry("whisper-medium") -> ModelCatalogEntry | None

# Get default for category
get_default_model_id("asr") -> "whisper-medium"
get_default_model_id("refiner") -> "qwen2.5-3b-instruct"

# Get runtime name
runtime_name_for_model("whisper-medium") -> "medium"
```

## Installation State

Source: `app/api/model_service.py`

The `ModelService` class manages model installation state:

```python
@dataclass(slots=True)
class ModelInstallState:
    model_id: str
    installed: bool          # All artifacts present
    verified: bool           # All artifacts pass size check
    install_path: str
    size_bytes: int
    last_checked_at: float
```

### Verification Logic

```python
def _install_state(self, entry: ModelCatalogEntry) -> ModelInstallState:
    install_dir = self.models_root / entry.category / entry.id
    
    # Check each artifact exists and meets minimum size
    for artifact in entry.download_artifacts:
        file_path = install_dir / artifact.filename
        if not file_path.exists():
            installed = False
            break
        if file_path.stat().st_size < artifact.min_size_bytes:
            installed = False
            break
```

### Catalog Payload

GET `/api/models/catalog` returns:

```json
{
  "catalog": [
    {
      "id": "whisper-medium",
      "display_name": "Whisper Medium",
      "category": "asr",
      "family": "whisper",
      "engine": "faster-whisper",
      "size_gb_estimate": 1.5,
      "recommended_vram_gb": 5,
      "speed_tier": "balanced",
      "installed": true,
      "verified": true,
      "recommended": true,
      ...
    }
  ],
  "installed": [...],
  "selected_asr_model_id": "whisper-medium",
  "selected_refiner_model_id": "qwen2.5-3b-instruct",
  "refinement_mode": "standard",
  "recommendations": ["whisper-medium", "whisper-small", "qwen2.5-3b-instruct"]
}
```

## Model Pool and Caching

Source: `app/stt/model_pool.py`

The `ModelPool` is a singleton thread-safe pool for managing Whisper model instances:

```python
class ModelPool:
    _instance: ModelPool | None = None
    _lock = threading.Lock()
    MODEL_TTL_SECONDS = 1800  # 30 minutes
```

### GPU Memory Management

```python
@dataclass(slots=True)
class GPUMemoryPool:
    total_gb: float
    reserved_gb: float
    allocated_gb: float
    max_models: int = 2
    
    def can_fit_model(self, model_name: str, compute_type: str) -> bool:
        required_gb = self._estimate_model_memory(model_name, compute_type)
        available_gb = self.total_gb - self.reserved_gb
        return available_gb >= required_gb * 1.2  # 20% headroom
```

### Memory Estimates by Model

| Model | int8 | float16 | float32 |
|-------|------|---------|---------|
| tiny | 0.24 GB | 0.4 GB | 0.8 GB |
| base | 0.30 GB | 0.50 GB | 1.00 GB |
| small | 0.60 GB | 1.0 GB | 2.0 GB |
| medium | 1.80 GB | 3.0 GB | 6.0 GB |
| large-v3 | 3.00 GB | 5.0 GB | 10.0 GB |
| large-v3-turbo | 2.10 GB | 3.5 GB | 7.0 GB |

### Cache Key Format

Models are cached by: `{model_name}:{device}:{compute_type}`

Examples:
- `medium:cuda:float16`
- `small:cpu:int8`

### Pool Metrics

```python
@dataclass(slots=True)
class PoolMetrics:
    total_models: int
    gpu_models: int
    cpu_models: int
    total_accesses: int
    cache_hits: int
    cache_misses: int
    load_failures: int
    warmup_failures: int
    gpu_fallbacks: int
    evictions: int
```

### Fallback Behavior

1. **GPU OOM Detection**: Catches `RuntimeError` with "out of memory" or "cuda"
2. **Automatic Fallback**: Switches to CPU with int8 compute type
3. **Cache Clearing**: Calls `torch.cuda.empty_cache()` and `torch.cuda.synchronize()`
4. **Metrics Tracking**: Increments `gpu_fallbacks` counter

### Warmup Process

```python
def _warmup_model(self, model: WhisperModel, model_name: str) -> bool:
    # Model-specific warmup duration
    warmup_duration = {
        "tiny": 16000,
        "base": 16000,
        "small": 16000,
        "medium": 16000,
        "large-v1": 32000,
        "large-v2": 32000,
        "large-v3": 32000,
        "large-v3-turbo": 16000,
    }.get(model_name, 16000)
    
    dummy = np.zeros(warmup_duration, dtype=np.float32)
    segments, _ = model.transcribe(dummy, beam_size=1, temperature=0.0)
    list(segments)  # Consume generator
```

## Download Flow

Source: `app/electron/main/model-download-manager.js`

The `ModelDownloadManager` handles model downloads in the Electron main process:

### Configuration

```javascript
const CONNECT_TIMEOUT_MS = 60_000;
const REQUEST_TIMEOUT_MS = 20 * 60 * 1000;  // 20 minutes
const OPTIONAL_ARTIFACT_FILENAMES = new Set([
  "vocabulary.txt",
  "vocab.json",
  "vocabulary.json",
  "merges.txt",
]);
```

### Retryable Error Codes

```javascript
const NETWORK_RETRYABLE_CODES = new Set([
  "ECONNRESET", "ETIMEDOUT", "ENOTFOUND", "ECONNREFUSED", "EPIPE",
  "UND_ERR_CONNECT_TIMEOUT", "UND_ERR_HEADERS_TIMEOUT",
  "UND_ERR_BODY_TIMEOUT", "UND_ERR_SOCKET",
]);
```

### Download Process

1. **Fetch Catalog**: GET `/api/models/catalog` for model metadata
2. **Create Directories**: `{userData}/models/{category}/{modelId}/`
3. **Resume Support**: Checks for `.partial` files and uses HTTP Range requests
4. **Verify Artifacts**: SHA256 check (if specified) + minimum size validation
5. **Emit Events**: `model-download-started`, `model-download-progress`, `model-download-completed`

### Resume Logic

```javascript
const resumeOffset = fs.existsSync(tempPath) ? fs.statSync(tempPath).size : 0;
let response = await this.fetchArtifactResponse(entry, artifact, signal, {
  offset: resumeOffset,
});

// Handle 416 Range Not Satisfiable (partial is stale)
if (response.status === 416 && resumeOffset > 0) {
  const remoteTotal = this._extractContentRangeTotal(response);
  if (remoteTotal > 0 && resumeOffset >= remoteTotal) {
    // Partial is complete, finalize it
    await this._finalizeArtifact(tempPath, targetPath);
  } else {
    // Partial is stale, restart
    fs.rmSync(tempPath, { force: true });
    response = await this.fetchArtifactResponse(entry, artifact, signal, { offset: 0 });
  }
}
```

### Optional Artifacts

If an optional artifact returns 404, it is skipped gracefully:

```javascript
if (response?.status === 404 && this._isOptionalArtifactFilename(artifact.filename)) {
  logger.warn('Optional artifact missing, skipping:', { filename: artifact.filename });
  continue;
}
```

### HuggingFace Fallback Resolution

If primary fetch fails for HuggingFace URLs, attempts to resolve the correct filename:

1. Exact match on `rfilename`
2. Fuzzy match (ignoring `-_.` characters)
3. Scored match based on token overlap
4. Extension-based fallback

## Hardware Recommendations

Source: `app/core/system_profiler.py` + `app/api/model_service.py`

### System Profiling

```python
@dataclass
class GPUProfile:
    available: bool
    name: str
    vram_gb: float
    compute_capability: tuple[int, int]
    cuda_available: bool
    device_count: int

@dataclass
class CPUProfile:
    physical_cores: int
    logical_cores: int
    ram_gb: float
    architecture: str
    supports_avx2: bool
```

### Quality Levels

| Level | GPU Requirement | RAM Requirement |
|-------|-----------------|-----------------|
| maximum | VRAM >= 10 GB + CUDA | - |
| high | VRAM >= 5 GB + CUDA | OR RAM >= 16 GB |
| balanced | VRAM >= 2 GB + CUDA | OR RAM >= 8 GB |
| low | No GPU | RAM < 8 GB |

### Model Recommendations by Hardware

```python
def get_recommendations(self) -> list[str]:
    profile = self._profiler.profile_system()
    
    if not profile.gpu.available:
        # CPU-only systems
        return ["whisper-small", "whisper-medium", "qwen2.5-3b-instruct"]
    
    elif profile.gpu.vram_gb >= 10:
        # High-end GPUs
        return [
            "whisper-large-v3",      # Best ASR quality
            "whisper-medium",         # Fallback ASR
            "qwen2.5-7b-instruct",   # Best refiner
            "qwen2.5-3b-instruct"    # Fallback refiner
        ]
    
    elif profile.gpu.vram_gb >= 5:
        # Mid-range GPUs
        return ["whisper-medium", "whisper-small", "qwen2.5-3b-instruct"]
    
    else:
        # Low-end GPUs
        return [
            "whisper-small",
            "whisper-medium",
            "qwen2.5-3b-instruct",
            "phi-3-mini-4k-instruct"
        ]
```

## Source-Aware ASR Selection

Source: `app/api/server.py` (`_resolve_model_name_for_hotkey` method)

Settings control ASR model selection by capture source:

```python
@dataclass
class TranscriptionSettings:
    default_asr_model_id: str              # General default
    microphone_asr_model_id: str | None    # Microphone-specific
    system_asr_model_id: str | None        # System audio-specific
```

### Resolution Logic

```python
def _resolve_model_name_for_hotkey(
    self,
    *,
    capture_source: Literal["microphone", "system"],
    requested_model_name: str | None,
) -> str:
    # Use explicitly requested model if provided
    resolved = runtime_name_for_model(requested_model_name) if requested_model_name else None
    if resolved:
        return resolved
    if requested_model_name:
        return requested_model_name

    # Resolve based on capture source settings
    settings = get_settings_manager().get_settings()
    model_id = (
        settings.transcription.system_asr_model_id
        if capture_source == "system"
        else settings.transcription.microphone_asr_model_id
    )
    return (
        runtime_name_for_model(model_id)
        or runtime_name_for_model(settings.transcription.default_asr_model_id)
        or settings.transcription.model_name
    )
```

### Constraints

- Microphone and system audio are **mutually exclusive** capture modes
- Each source can have its own model preference
- Fallback chain: `source_specific` -> `default_asr_model_id` -> "whisper-medium"

## Runtime Contract

### Settings Persistence

| Setting | Key | Values |
|---------|-----|--------|
| Default ASR | `transcription.default_asr_model_id` | Model ID from catalog |
| Microphone ASR | `transcription.microphone_asr_model_id` | Model ID or null |
| System ASR | `transcription.system_asr_model_id` | Model ID or null |
| Refiner Model | `refiner.selected_model_id` | Model ID from catalog |
| Refinement Mode | `transcription.refinement_mode` | "off", "fast", "standard", "polished" |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/models/catalog` | GET | Full catalog with install state |
| `/api/models/download` | POST | Trigger model download |
| `/api/models/cancel` | POST | Cancel active download |
| `/api/models/remove` | POST | Remove installed model |

### IPC Events (Electron)

| Event | Direction | Payload |
|-------|-----------|---------|
| `model-download-started` | main -> renderer | `{ model_id, download_id, status }` |
| `model-download-progress` | main -> renderer | `{ model_id, progress, bytes_downloaded, total_bytes }` |
| `model-download-completed` | main -> renderer | `{ model_id, status: "completed" }` |
| `model-download-failed` | main -> renderer | `{ model_id, status: "failed", error }` |
| `model-download-cancelled` | main -> renderer | `{ model_id, status: "cancelled" }` |
| `model-removed` | main -> renderer | `{ model_id }` |

## Guardrails

1. **Single Source of Truth**: `app/core/model_catalog.py` is the only place to add/modify models
2. **API-Driven Frontend**: Frontend consumes `/api/models/catalog`, never hardcodes model lists
3. **Graceful Degradation**: Missing optional artifacts don't fail downloads
4. **GPU Fallback**: OOM automatically falls back to CPU with int8
5. **Resume Support**: Downloads survive network interruptions
6. **Size Verification**: All artifacts verified against `min_size_bytes`
7. **Runtime Availability**: `enabled_runtime` flag controls whether model appears in UI

## Merged from MODEL_SYSTEM.md

### ASR and Refiner Flow

1. Hotkey transcription creates the ASR transcriber from backend settings
2. Partial transcript updates are emitted without refiner processing
3. On finalized hotkey stop, backend collects the final ASR text
4. If refinement is enabled and a local refiner model is available, `app/api/refiner_service.py` applies strict text cleanup
5. If refiner output is empty or rewrites protected technical tokens too aggressively, backend falls back to the original finalized text

### Refinement Guardrails

- Refinement is local-first through llama.cpp-backed GGUF models
- Strict refinement should improve punctuation, capitalization, spacing, and paragraphing without changing meaning
- Technical tokens such as identifiers, filenames, formulas, numbers, and units must be preserved
