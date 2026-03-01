"""Auto-optimization engine that generates optimal settings based on hardware."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.system_profiler import SystemProfiler, SystemProfile


@dataclass
class OptimizedSettings:
    """Complete optimized settings configuration."""

    # Model Settings
    model_name: str
    compute_type: str  # "int8", "float16", "float32"

    # Audio Pipeline
    chunk_duration: float  # seconds
    overlap_ratio: float
    vad_enabled: bool
    vad_threshold_db: float

    # Quality Filtering
    confidence_threshold: float
    enable_filler_filter: bool
    enable_hallucination_filter: bool
    min_segment_length: int

    # Performance
    max_workers: int
    use_parallel_processing: bool
    preload_model: bool

    # Hotkey Mode
    hotkey_optimized: bool  # Optimize for low latency when using hotkey

    # Metadata
    quality_level: str
    optimization_reason: str
    estimated_vram_usage_gb: float
    estimated_latency_ms: int


class AutoOptimizer:
    """Generates optimal settings based on detected hardware."""

    # VRAM requirements for each model (in GB for float16)
    MODEL_VRAM_REQUIREMENTS = {
        "tiny": 1.0,
        "base": 1.0,
        "small": 2.0,
        "medium": 5.0,
        "large-v3": 10.0,
    }

    # Compute type efficiency multiplier
    COMPUTE_EFFICIENCY = {
        "int8": 0.6,  # Uses 60% of float16 memory
        "float16": 1.0,  # Baseline
        "float32": 2.0,  # Uses 2x float16 memory
    }

    def __init__(self, profiler: Optional[SystemProfiler] = None):
        self.profiler = profiler or SystemProfiler()
        self.profile = self.profiler.profile_system()

    def generate_optimal_settings(
        self, mode: str = "balanced", force_gpu: bool = False, hotkey_mode: bool = False
    ) -> OptimizedSettings:
        """Generate optimal settings based on hardware and mode.

        Args:
            mode: One of "maximum", "balanced", "speed", "low_memory"
            force_gpu: Whether to force GPU usage even if borderline
            hotkey_mode: Optimize for low latency push-to-talk
        """

        # Select best model for hardware
        model_name = self._select_optimal_model(mode, force_gpu)

        # Select compute type
        compute_type = self._select_compute_type(model_name, mode)

        # Configure audio pipeline
        audio_config = self._configure_audio_pipeline(mode, hotkey_mode)

        # Configure quality filters
        quality_config = self._configure_quality_filters(mode)

        # Configure performance
        performance_config = self._configure_performance(mode, hotkey_mode)

        # Calculate estimates
        vram_usage = self._estimate_vram_usage(model_name, compute_type)
        latency = self._estimate_latency(model_name, compute_type, hotkey_mode)

        # Generate reason
        reason = self._generate_optimization_reason(model_name, compute_type, mode, vram_usage)

        return OptimizedSettings(
            model_name=model_name,
            compute_type=compute_type,
            chunk_duration=audio_config["chunk_duration"],
            overlap_ratio=audio_config["overlap_ratio"],
            vad_enabled=audio_config["vad_enabled"],
            vad_threshold_db=audio_config["vad_threshold_db"],
            confidence_threshold=quality_config["confidence_threshold"],
            enable_filler_filter=quality_config["enable_filler_filter"],
            enable_hallucination_filter=quality_config["enable_hallucination_filter"],
            min_segment_length=quality_config["min_segment_length"],
            max_workers=performance_config["max_workers"],
            use_parallel_processing=performance_config["use_parallel"],
            preload_model=performance_config["preload"],
            hotkey_optimized=hotkey_mode,
            quality_level=self.profile.recommended_quality_level,
            optimization_reason=reason,
            estimated_vram_usage_gb=vram_usage,
            estimated_latency_ms=latency,
        )

    def _select_optimal_model(self, mode: str, force_gpu: bool) -> str:
        """Select best model based on hardware and mode."""
        gpu = self.profile.gpu

        if mode == "maximum":
            # Try to use largest model possible
            if gpu.can_run_large_models or force_gpu and gpu.vram_gb >= 8:
                return "large-v3"
            elif gpu.can_run_medium_models:
                return "medium"
            elif gpu.can_run_small_models:
                return "small"

        elif mode == "balanced":
            # Best quality that fits comfortably
            if gpu.can_run_medium_models:
                return "medium"
            elif gpu.can_run_small_models:
                return "small"
            elif gpu.can_run_large_models:
                return "large-v3"  # Edge case

        elif mode == "speed":
            # Fastest model
            return "tiny"

        elif mode == "low_memory":
            # Fits in limited VRAM
            if gpu.can_run_small_models:
                return "small"
            return "tiny"

        # Default fallback
        if gpu.can_run_medium_models:
            return "medium"
        elif gpu.can_run_small_models:
            return "small"
        elif gpu.available:
            return "tiny"

        # CPU only - use smallest
        return "tiny"

    def _select_compute_type(self, model_name: str, mode: str) -> str:
        """Select compute type based on model and hardware."""
        gpu = self.profile.gpu
        required_vram = self.MODEL_VRAM_REQUIREMENTS.get(model_name, 2.0)

        # If we have plenty of VRAM, use float16 for best quality
        if gpu.vram_gb >= required_vram * 1.5:
            return "float16"

        # If we're tight on VRAM or using large model on 8GB
        if gpu.vram_gb >= required_vram * 0.8:
            return "int8"  # Still fits with quantization

        # CPU fallback
        return "int8"

    def _configure_audio_pipeline(self, mode: str, hotkey_mode: bool) -> dict:
        """Configure audio processing parameters."""

        if hotkey_mode:
            # Optimize for low latency
            return {
                "chunk_duration": 0.5,  # 500ms chunks
                "overlap_ratio": 0.1,
                "vad_enabled": True,
                "vad_threshold_db": -35.0,  # More sensitive
            }

        configs = {
            "maximum": {
                "chunk_duration": 1.0,
                "overlap_ratio": 0.2,
                "vad_enabled": True,
                "vad_threshold_db": -40.0,
            },
            "balanced": {
                "chunk_duration": 0.8,
                "overlap_ratio": 0.15,
                "vad_enabled": True,
                "vad_threshold_db": -40.0,
            },
            "speed": {
                "chunk_duration": 0.3,
                "overlap_ratio": 0.1,
                "vad_enabled": False,  # Skip VAD for speed
                "vad_threshold_db": -35.0,
            },
            "low_memory": {
                "chunk_duration": 1.2,
                "overlap_ratio": 0.25,
                "vad_enabled": True,
                "vad_threshold_db": -40.0,
            },
        }

        return configs.get(mode, configs["balanced"])

    def _configure_quality_filters(self, mode: str) -> dict:
        """Configure quality filtering parameters."""

        configs = {
            "maximum": {
                "confidence_threshold": 0.75,  # High bar for quality
                "enable_filler_filter": True,
                "enable_hallucination_filter": True,
                "min_segment_length": 3,
            },
            "balanced": {
                "confidence_threshold": 0.70,
                "enable_filler_filter": True,
                "enable_hallucination_filter": True,
                "min_segment_length": 3,
            },
            "speed": {
                "confidence_threshold": 0.60,  # Lower for speed
                "enable_filler_filter": False,  # Skip for speed
                "enable_hallucination_filter": True,
                "min_segment_length": 2,
            },
            "low_memory": {
                "confidence_threshold": 0.65,
                "enable_filler_filter": True,
                "enable_hallucination_filter": True,
                "min_segment_length": 3,
            },
        }

        return configs.get(mode, configs["balanced"])

    def _configure_performance(self, mode: str, hotkey_mode: bool) -> dict:
        """Configure performance settings."""
        cpu = self.profile.cpu

        if hotkey_mode:
            return {
                "max_workers": 1,  # Single worker for predictable latency
                "use_parallel": False,
                "preload": True,  # Keep model in memory
            }

        return {
            "max_workers": cpu.recommended_workers,
            "use_parallel": cpu.can_run_parallel,
            "preload": mode in ["maximum", "balanced"],
        }

    def _estimate_vram_usage(self, model_name: str, compute_type: str) -> float:
        """Estimate VRAM usage in GB."""
        base_vram = self.MODEL_VRAM_REQUIREMENTS.get(model_name, 2.0)
        multiplier = self.COMPUTE_EFFICIENCY.get(compute_type, 1.0)
        return base_vram * multiplier

    def _estimate_latency(self, model_name: str, compute_type: str, hotkey_mode: bool) -> int:
        """Estimate inference latency in milliseconds."""
        # Rough estimates
        base_latencies = {
            "tiny": 50,
            "base": 100,
            "small": 200,
            "medium": 400,
            "large-v3": 600,
        }

        latency = base_latencies.get(model_name, 200)

        # int8 is faster
        if compute_type == "int8":
            latency = int(latency * 0.8)

        # Hotkey mode optimizes further
        if hotkey_mode:
            latency = int(latency * 0.7)

        return latency

    def _generate_optimization_reason(
        self, model: str, compute: str, mode: str, vram: float
    ) -> str:
        """Generate human-readable explanation of optimizations."""
        gpu = self.profile.gpu

        if not gpu.available:
            return f"CPU-only mode: Using {model} model with {compute} for compatibility"

        if mode == "maximum":
            return f"Maximum quality: {model} on {gpu.name} ({gpu.vram_gb:.1f}GB) using {compute} (~{vram:.1f}GB VRAM)"

        if mode == "balanced":
            return f"Balanced: {model} with {compute} for best quality on {gpu.vram_gb:.1f}GB GPU"

        if mode == "speed":
            return f"Speed optimized: {model} for fastest transcription"

        if mode == "low_memory":
            return f"Memory optimized: {model} to fit in available VRAM"

        return f"Auto-optimized: {model} with {compute}"

    def get_preset_settings(self, preset_name: str) -> OptimizedSettings:
        """Get settings for a named preset."""
        presets = {
            "maximum_quality": self.generate_optimal_settings("maximum"),
            "balanced": self.generate_optimal_settings("balanced"),
            "maximum_speed": self.generate_optimal_settings("speed"),
            "low_memory": self.generate_optimal_settings("low_memory"),
            "hotkey_mode": self.generate_optimal_settings("balanced", hotkey_mode=True),
        }

        return presets.get(preset_name, presets["balanced"])


def get_recommended_settings(mode: str = "balanced", hotkey: bool = False) -> OptimizedSettings:
    """Convenience function to get recommended settings."""
    optimizer = AutoOptimizer()
    return optimizer.generate_optimal_settings(mode=mode, hotkey_mode=hotkey)
