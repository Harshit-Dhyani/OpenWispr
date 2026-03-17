"""Model catalog and metadata definitions.

Provides ModelCatalogEntry, DownloadArtifact dataclasses and related
type definitions for describing available STT and refiner models.

Defines model families (whisper, qwen, mistral, phi), engines
(faster-whisper, llamacpp, ollama), and speed tiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ModelCategory = Literal["asr", "refiner"]
ModelFamily = Literal["whisper", "qwen", "mistral", "phi"]
ModelEngine = Literal["faster-whisper", "llamacpp", "ollama"]
SpeedTier = Literal["fast", "balanced", "quality"]


@dataclass(frozen=True, slots=True)
class DownloadArtifact:
    filename: str
    url: str
    min_size_bytes: int
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ModelCatalogEntry:
    id: str
    display_name: str
    category: ModelCategory
    family: ModelFamily
    engine: ModelEngine
    size_gb_estimate: float
    recommended_vram_gb: int
    speed_tier: SpeedTier
    license_note: str
    description_short: str
    why_choose_this: str
    runtime_model_name: str | None
    enabled_runtime: bool
    download_artifacts: tuple[DownloadArtifact, ...]
    default_runtime_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "category": self.category,
            "family": self.family,
            "engine": self.engine,
            "size_gb_estimate": self.size_gb_estimate,
            "recommended_vram_gb": self.recommended_vram_gb,
            "speed_tier": self.speed_tier,
            "license_note": self.license_note,
            "description_short": self.description_short,
            "why_choose_this": self.why_choose_this,
            "runtime_model_name": self.runtime_model_name,
            "enabled_runtime": self.enabled_runtime,
            "download_artifacts": [
                {
                    "filename": artifact.filename,
                    "url": artifact.url,
                    "min_size_bytes": artifact.min_size_bytes,
                    "sha256": artifact.sha256,
                }
                for artifact in self.download_artifacts
            ],
            "default_runtime_config": dict(self.default_runtime_config),
        }


def _hf_file(repo: str, filename: str, min_size_bytes: int) -> DownloadArtifact:
    return DownloadArtifact(
        filename=filename,
        url=f"https://huggingface.co/{repo}/resolve/main/{filename}?download=true",
        min_size_bytes=min_size_bytes,
    )


MODEL_CATALOG: tuple[ModelCatalogEntry, ...] = (
    ModelCatalogEntry(
        id="whisper-tiny",
        display_name="Whisper Tiny",
        category="asr",
        family="whisper",
        engine="faster-whisper",
        size_gb_estimate=0.08,
        recommended_vram_gb=0,
        speed_tier="fast",
        license_note="OpenAI Whisper weights via Systran CTranslate2 conversion.",
        description_short="Smallest local ASR model for CPU-first or low-latency runs.",
        why_choose_this="Fastest practical option on weaker CPUs and useful for quick device checks.",
        runtime_model_name="tiny",
        enabled_runtime=True,
        download_artifacts=(
            _hf_file("Systran/faster-whisper-tiny", "model.bin", 50_000_000),
            _hf_file("Systran/faster-whisper-tiny", "config.json", 512),
            _hf_file("Systran/faster-whisper-tiny", "tokenizer.json", 1_000),
            _hf_file("Systran/faster-whisper-tiny", "vocabulary.txt", 1_000),
        ),
        default_runtime_config={"computeType": "int8", "threads": 4},
    ),
    ModelCatalogEntry(
        id="whisper-small",
        display_name="Whisper Small",
        category="asr",
        family="whisper",
        engine="faster-whisper",
        size_gb_estimate=0.46,
        recommended_vram_gb=2,
        speed_tier="fast",
        license_note="OpenAI Whisper weights via Systran CTranslate2 conversion.",
        description_short="Fast local speech model with noticeably better quality than Tiny/Base.",
        why_choose_this="Best fast option for local dictation and lower-end GPUs.",
        runtime_model_name="small",
        enabled_runtime=True,
        download_artifacts=(
            _hf_file("Systran/faster-whisper-small", "model.bin", 250_000_000),
            _hf_file("Systran/faster-whisper-small", "config.json", 512),
            _hf_file("Systran/faster-whisper-small", "tokenizer.json", 1_000),
            _hf_file("Systran/faster-whisper-small", "vocabulary.txt", 1_000),
        ),
        default_runtime_config={"computeType": "float16", "threads": 6},
    ),
    ModelCatalogEntry(
        id="whisper-medium",
        display_name="Whisper Medium",
        category="asr",
        family="whisper",
        engine="faster-whisper",
        size_gb_estimate=1.5,
        recommended_vram_gb=5,
        speed_tier="balanced",
        license_note="OpenAI Whisper weights via Systran CTranslate2 conversion.",
        description_short="Default balance of accuracy and speed for most desktop systems.",
        why_choose_this="Recommended default for most Windows machines with a discrete GPU.",
        runtime_model_name="medium",
        enabled_runtime=True,
        download_artifacts=(
            _hf_file("Systran/faster-whisper-medium", "model.bin", 1_000_000_000),
            _hf_file("Systran/faster-whisper-medium", "config.json", 512),
            _hf_file("Systran/faster-whisper-medium", "tokenizer.json", 1_000),
            _hf_file("Systran/faster-whisper-medium", "vocabulary.txt", 1_000),
        ),
        default_runtime_config={"computeType": "float16", "threads": 8},
    ),
    ModelCatalogEntry(
        id="whisper-large-v3",
        display_name="Whisper Large v3",
        category="asr",
        family="whisper",
        engine="faster-whisper",
        size_gb_estimate=3.1,
        recommended_vram_gb=10,
        speed_tier="quality",
        license_note="OpenAI Whisper weights via Systran CTranslate2 conversion.",
        description_short="Highest accuracy local Whisper model for stronger GPUs.",
        why_choose_this="Choose this for long-form sessions when accuracy matters more than startup cost.",
        runtime_model_name="large-v3",
        enabled_runtime=True,
        download_artifacts=(
            _hf_file("Systran/faster-whisper-large-v3", "model.bin", 2_000_000_000),
            _hf_file("Systran/faster-whisper-large-v3", "config.json", 512),
            _hf_file("Systran/faster-whisper-large-v3", "tokenizer.json", 1_000),
            _hf_file("Systran/faster-whisper-large-v3", "vocabulary.txt", 1_000),
        ),
        default_runtime_config={"computeType": "float16", "threads": 8},
    ),
    ModelCatalogEntry(
        id="whisper-turbo",
        display_name="Whisper Turbo",
        category="asr",
        family="whisper",
        engine="faster-whisper",
        size_gb_estimate=1.6,
        recommended_vram_gb=6,
        speed_tier="fast",
        license_note="Turbo-weight support depends on faster-whisper runtime availability.",
        description_short="Fast high-end ASR option when Turbo is supported by the local runtime.",
        why_choose_this="Choose this when you want faster large-model style decoding on a good GPU.",
        runtime_model_name="turbo",
        enabled_runtime=True,
        download_artifacts=(
            _hf_file("mobiuslabsgmbh/faster-whisper-large-v3-turbo", "model.bin", 1_000_000_000),
            _hf_file("mobiuslabsgmbh/faster-whisper-large-v3-turbo", "config.json", 512),
            _hf_file("mobiuslabsgmbh/faster-whisper-large-v3-turbo", "tokenizer.json", 1_000),
        ),
        default_runtime_config={"computeType": "float16", "threads": 8},
    ),
    ModelCatalogEntry(
        id="qwen2.5-3b-instruct",
        display_name="Qwen2.5 3B Instruct",
        category="refiner",
        family="qwen",
        engine="llamacpp",
        size_gb_estimate=1.93,
        recommended_vram_gb=4,
        speed_tier="fast",
        license_note="Use under the upstream Qwen model license.",
        description_short="Compact local refiner with better quality than ultra-small models and much lower VRAM than 7B.",
        why_choose_this="Best small local refiner when you want strong cleanup quality on a 4-6GB GPU or CPU-first setup.",
        runtime_model_name=None,
        enabled_runtime=False,
        download_artifacts=(
            _hf_file(
                "Qwen/Qwen2.5-3B-Instruct-GGUF", "qwen2.5-3b-instruct-q4_k_m.gguf", 1_700_000_000
            ),
        ),
        default_runtime_config={"threads": 6, "gpuLayers": 24},
    ),
    ModelCatalogEntry(
        id="qwen2.5-7b-instruct",
        display_name="Qwen2.5 7B Instruct",
        category="refiner",
        family="qwen",
        engine="llamacpp",
        size_gb_estimate=4.7,
        recommended_vram_gb=8,
        speed_tier="balanced",
        license_note="Use under the upstream Qwen model license.",
        description_short="Best balanced local transcript refiner for quality and instruction following.",
        why_choose_this="Strong default refiner once local LLM runtime is enabled.",
        runtime_model_name=None,
        enabled_runtime=False,
        download_artifacts=(
            _hf_file(
                "Qwen/Qwen2.5-7B-Instruct-GGUF", "qwen2.5-7b-instruct-q4_k_m.gguf", 3_000_000_000
            ),
        ),
        default_runtime_config={"threads": 8, "gpuLayers": 35},
    ),
    ModelCatalogEntry(
        id="mistral-7b-instruct-v0.3",
        display_name="Mistral 7B Instruct v0.3",
        category="refiner",
        family="mistral",
        engine="llamacpp",
        size_gb_estimate=4.4,
        recommended_vram_gb=8,
        speed_tier="quality",
        license_note="Use under the upstream Mistral license.",
        description_short="Quality-oriented local refiner for richer punctuation and cleanup passes.",
        why_choose_this="Good fit when you want slightly stronger stylistic cleanup in Polished mode.",
        runtime_model_name=None,
        enabled_runtime=False,
        download_artifacts=(
            _hf_file(
                "MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF",
                "Mistral-7B-Instruct-v0.3.Q4_K_M.gguf",
                3_000_000_000,
            ),
        ),
        default_runtime_config={"threads": 8, "gpuLayers": 35},
    ),
    ModelCatalogEntry(
        id="phi-3-mini-4k-instruct",
        display_name="Phi-3 Mini 4K Instruct",
        category="refiner",
        family="phi",
        engine="llamacpp",
        size_gb_estimate=2.4,
        recommended_vram_gb=4,
        speed_tier="fast",
        license_note="Use under the upstream Microsoft Phi license.",
        description_short="Compact local refiner for lower-memory systems.",
        why_choose_this="Best refiner choice when you want local cleanup on a modest machine.",
        runtime_model_name=None,
        enabled_runtime=False,
        download_artifacts=(
            _hf_file(
                "microsoft/Phi-3-mini-4k-instruct-gguf",
                "Phi-3-mini-4k-instruct-q4.gguf",
                1_500_000_000,
            ),
        ),
        default_runtime_config={"threads": 6, "gpuLayers": 20},
    ),
)


MODEL_CATALOG_BY_ID = {entry.id: entry for entry in MODEL_CATALOG}


def list_model_catalog() -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in MODEL_CATALOG]


def get_model_catalog_entry(model_id: str) -> ModelCatalogEntry | None:
    return MODEL_CATALOG_BY_ID.get(model_id)


def get_default_model_id(category: ModelCategory) -> str:
    if category == "asr":
        return "whisper-medium"
    return "qwen2.5-3b-instruct"


def runtime_name_for_model(model_id: str) -> str | None:
    entry = get_model_catalog_entry(model_id)
    if not entry:
        return None
    return entry.runtime_model_name
