---
title: English Coach Service
description: LLM-powered writing coach for dictation transcript refinement
description: LLM-powered writing coach for dictation transcript refinement
audience: developers
last_verified: 2026-03-08
source_of_truth:
  - app/api/coach_service.py
  - app/api/coach_cache.py
  - app/config/coach_prompts.py
---

# English Coach Service

The English Coach provides LLM-powered refinement and feedback for dictation transcripts, offering polished text, grammar corrections, and learning tips.

## Overview

The Coach service consists of:

1. **CoachService** (`app/api/coach_service.py:86`) - Main service orchestration
2. **CoachCache** (`app/api/coach_cache.py:11`) - Persistent result caching
3. **Prompt Templates** (`app/config/coach_prompts.py`) - Configurable LLM prompts

## Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CoachService                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Request    │  │   Prompt     │  │   LLM Runtime    │  │
│  │   Context    │──▶│  Compiler    │──▶│  (llama.cpp)     │  │
│  └──────────────┘  └──────────────┘  └────────┬─────────┘  │
│                                               │            │
│  ┌──────────────┐  ┌──────────────┐          │            │
│  │   CoachCache │◀─┤  Response    │◀─────────┘            │
│  │   (SQLite)   │  │  Parser      │                       │
│  └──────────────┘  └──────┬───────┘                       │
│                           │                                │
└───────────────────────────┼────────────────────────────────┘
                            ▼
                   ┌─────────────────┐
                   │  CoachResult    │
                   │  - polished     │
                   │  - diff         │
                   │  - tips         │
                   │  - mistakes     │
                   └─────────────────┘
```

## Endpoints

### HTTP Endpoints

| Method | Path | Description | Request Body |
|--------|------|-------------|--------------|
| POST | `/api/coach/prompt-preview` | Compile prompt for preview | `CoachPromptPreviewRequest` |

The Coach service is invoked internally through `HotkeyTranscriptionService` during `/api/transcription/hotkey/stop` processing.

### generate()

Main generation method (`app/api/coach_service.py:94`):

```python
def generate(
    self,
    context: CoachRequestContext,
    *,
    fallback_text: str
) -> CoachResult
```

**Request Flow:**
1. Resolve prompt template
2. Compile prompt with context
3. Check cache (SHA-256 key)
4. If cache miss and allowed, call LLM
5. Parse and normalize result
6. Cache result
7. Return CoachResult

### prompt_preview()

Preview compiled prompts without LLM call (`app/api/coach_service.py:176`):

```python
def prompt_preview(self, context: CoachRequestContext) -> dict[str, Any]
```

### CoachPromptPreviewRequest

```python
class CoachPromptPreviewRequest(BaseModel):
    capture_source: Literal["microphone", "system"] = "microphone"
    original_text: str = ""
    language_mode: str = "auto"
    detail_level: Literal["compact", "standard", "deep"] = "compact"
    template_id: str = "default_english_coach"
    custom_user_template: str = ""
    overrides: dict[str, Any] = Field(default_factory=dict)
    privacy_mode: Literal["local_only", "allow_llm"] = "local_only"
    templates: list[dict[str, Any]] = Field(default_factory=list)
```

## Request Context

`CoachRequestContext` (`app/api/coach_service.py:71`) encapsulates all request parameters:

```python
@dataclass
class CoachRequestContext:
    text: str                          # Original transcript
    language_mode: str                 # Language mode (en, hi, etc.)
    detail_level: Literal["compact", "standard", "deep"]
    capture_source: Literal["microphone", "system"]
    template_id: str                   # Prompt template to use
    overrides: dict[str, Any]          # Style overrides
    privacy_mode: Literal["local_only", "allow_llm"]
    runtime_enabled: bool              # LLM runtime available
    model_id: str | None               # Specific model to use
    custom_user_template: str = ""     # Override template
    templates: list[dict] | None = None # Available templates
```

## Cache Strategy

### Cache Key Generation

The `CoachCache` (`app/api/coach_cache.py:36`) creates deterministic keys:

```python
@staticmethod
def build_key(*parts: object) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()
```

**Key Components:**
- Original text
- Fallback text
- Language mode
- Detail level
- Template ID and version
- Overrides (JSON-serialized)
- Privacy mode

### Cache Persistence

```python
# Storage: JSON file (default: ~/.transcripta/coach_cache.json)
# Max entries: 500 (LRU eviction)
# TTL: None (persistent until max_entries exceeded)

def _persist(self) -> None:
    if len(payload) > self.max_entries:
        ordered = sorted(
            payload.items(),
            key=lambda item: item[1].get("created_at", 0),
            reverse=True
        )
        payload = dict(ordered[:self.max_entries])
```

### Cache Hit Behavior

```python
def get(self, key: str) -> dict[str, Any] | None:
    entry = self._entries.get(key)
    if entry is None:
        return None
    entry["created_at"] = time()  # Update LRU timestamp
    self._persist()
    return dict(entry)
```

## Prompt Templates

### Default Template

`DEFAULT_COACH_TEMPLATE` (`app/config/coach_prompts.py:56`):

```python
CoachPromptTemplate(
    id="default_english_coach",
    name="Default English Coach",
    version=1,
    system=DEFAULT_COACH_SYSTEM_PROMPT,
    user_template=DEFAULT_COACH_USER_TEMPLATE,
    enabled=True,
    built_in=True,
)
```

### System Prompt

```
You are an English writing coach for dictation transcripts.
You must preserve the speakers meaning and tone.
You must NOT add new facts.
Prefer minimal edits.
Output MUST be valid JSON only, matching the schema exactly.
```

### User Template Variables

Available template variables (`app/config/coach_prompts.py:83`):

| Variable | Description |
|----------|-------------|
| `{original_text}` | The raw transcript text |
| `{language_mode}` | Current language mode |
| `{detail_level}` | compact/standard/deep |
| `{overrides_json}` | Serialized override settings |

### Template Compilation

```python
def compile_coach_prompt(
    *,
    template: dict[str, object],
    original_text: str,
    language_mode: str,
    detail_level: str,
    overrides: dict[str, object],
    custom_user_template: str = "",
) -> dict[str, object]:
    resolved_user_template = (
        custom_user_template or str(template.get("user_template", ""))
    ).strip()
    resolved_system = str(template.get("system", "")).strip()
    overrides_json = json.dumps(overrides, ensure_ascii=True, sort_keys=True)

    variables = {
        "original_text": original_text,
        "language_mode": language_mode,
        "detail_level": detail_level,
        "overrides_json": overrides_json,
    }

    return {
        "system_prompt": resolved_system,
        "user_prompt": resolved_user_template.format(**variables),
        "variables": variables,
        "resolved_template_id": template.get("id"),
        "resolved_template_version": int(template.get("version", 1)),
    }
```

## Response Schema

### CoachResult

```python
class CoachResult(BaseModel):
    original: str                      # Original transcript
    polished: str                      # Refined text
    diff: list[CoachDiffOp]            # Text diff operations
    tips: list[str]                    # Writing tips (max 5)
    mistakes: list[CoachMistake]       # Identified mistakes (max 5)
    practice: CoachPractice            # Practice exercise
    meta: CoachMeta                    # Metadata
```

### CoachDiffOp

```python
class CoachDiffOp(BaseModel):
    op: Literal["delete", "insert", "replace"]
    from_: str = Field(alias="from")   # Original text
    to: str                            # Replacement text
    start: int                         # Start index in original
    end: int                           # End index in original
```

Diffs are computed using `difflib.SequenceMatcher` (`app/api/coach_service.py:265`):

```python
def _build_diff(self, original: str, polished: str) -> list[CoachDiffOp]:
    matcher = SequenceMatcher(None, original, polished)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        # Create CoachDiffOp for delete/insert/replace
```

### CoachMistake

```python
class CoachMistake(BaseModel):
    type: Literal[
        "grammar", "wording", "tense",
        "article", "preposition", "clarity"
    ]
    example: str                       # Original problematic text
    fix: str                           # Corrected version
    why: str                           # Explanation
```

### CoachMeta

```python
class CoachMeta(BaseModel):
    model: str = "none"                # Model used
    confidence: float = 0.0            # Result confidence
    cache_hit: bool = False            # From cache
    provider: str = "fallback"         # "local_llm", "cache", "fallback"
    prompt_template_id: str
    prompt_version: int
```

## Privacy Modes

### local_only

```python
if context.privacy_mode == "local_only":
    result = self._fallback_result(
        original=context.text,
        polished=fallback_text,
        provider="disabled_local_only",
        ...
    )
```

No LLM call is made; returns original text with minimal processing.

### allow_llm

Normal operation - LLM is called if runtime is enabled.

## LLM Runtime Integration

### Model Loading

```python
def _ensure_model(self, model_id: str) -> Llama:
    if self._llm is not None and self._loaded_model_id == model_id:
        return self._llm  # Return cached model

    entry = get_model_catalog_entry(model_id)
    model_path = next(model_dir.glob("*.gguf"), None)

    self._llm = Llama(
        model_path=str(model_path),
        n_ctx=4096,
        n_threads=int(runtime_config.get("threads", 4)),
        n_gpu_layers=int(runtime_config.get("gpuLayers", 0)),
        verbose=False,
    )
```

### Generation Parameters

```python
response = llm.create_completion(
    prompt=f"{system_prompt}\n\n{user_prompt}\n",
    max_tokens=min(1400, max(384, len(context.text.split()) * 12)),
    temperature=0.05,
    stop=["```", "\n\nOriginal transcript:"],
)
```

## Fallback Behavior

The service gracefully degrades when LLM is unavailable:

| Condition | Provider | Behavior |
|-----------|----------|----------|
| `privacy_mode == "local_only"` | `disabled_local_only` | Return original text |
| `runtime_enabled == False` | `fallback_runtime_unavailable` | Return original text |
| LLM exception | `fallback_error` | Return original text |
| Cache hit | `cache` | Return cached result |

## Settings Integration

### Coach Settings (from settings_manager.py)

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

### Prompt Overrides

```python
@dataclass
class CoachPromptOverrides:
    tone: str              # formal, casual, professional
    aggressiveness: str    # minimal, moderate, aggressive
    filler_removal: bool
    keep_slang: bool
    target_style: str      # email, message, document
```

### CoachPromptTemplateSettings

```python
@dataclass
class CoachPromptTemplateSettings:
    id: str
    name: str
    version: int
    system: str
    user_template: str
    enabled: bool = True
    built_in: bool = False
```

## Error Handling

All LLM errors are caught and result in fallback behavior:

```python
try:
    llm = self._ensure_model(context.model_id)
    response = llm.create_completion(...)
    result = self._parse_candidate(...)
    self._cache.put(cache_key, {"result": result.model_dump(by_alias=True)})
    return result
except Exception as exc:
    logger.warning("Coach generation failed: %s", exc)
    return self._fallback_result(
        original=context.text,
        polished=fallback_text,
        provider="fallback_error",
        ...
    )
```

## Key Code Paths

| Function | File | Line | Purpose |
|----------|------|------|---------|
| `generate` | coach_service.py | 94 | Main entry point |
| `_resolve_template` | coach_service.py | 191 | Template selection |
| `compile_coach_prompt` | coach_prompts.py | 71 | Prompt compilation |
| `build_key` | coach_cache.py | 36 | Cache key generation |
| `_parse_candidate` | coach_service.py | 201 | LLM response parsing |
| `_build_diff` | coach_service.py | 265 | Diff generation |
| `_ensure_model` | coach_service.py | 291 | LLM model loading |

## Related Documentation

- [Settings System](./settings.md) - Coach settings schema
- [Model System](../architecture/MODEL_SYSTEM.md) - LLM model management
