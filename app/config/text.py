"""Centralized UI text for Transcripta.

All user-facing text should be imported from here.
This enables:
- Easy localization
- Consistent terminology
- Single source of truth
"""

from typing import Dict

# ============================================
# Model Names
# ============================================
MODEL_NAMES: Dict[str, str] = {
    "tiny": "Tiny (Fastest, Lowest Quality)",
    "base": "Base (Fast, Good Quality)",
    "small": "Small (Balanced)",
    "medium": "Medium (Best Quality, Slower)",
    "large-v3": "Large v3 (Highest Quality, Slowest)",
    "turbo": "Turbo (Fast, High Quality)",
}

# Short model names (for compact UI)
MODEL_NAMES_SHORT: Dict[str, str] = {
    "tiny": "Tiny",
    "base": "Base",
    "small": "Small",
    "medium": "Medium",
    "large-v3": "Large v3",
    "turbo": "Turbo",
}

# ============================================
# Live Mode Labels
# ============================================
LIVE_MODE_LABELS: Dict[str, str] = {
    "ultra": "Ultra (100ms chunks)",
    "realtime": "Real-Time (Ultra Low Latency)",
    "low_latency": "Low Latency",
    "balanced": "Balanced",
    "high_accuracy": "High Accuracy",
}

LIVE_MODE_DESCRIPTIONS: Dict[str, str] = {
    "ultra": "Fastest response with smallest chunks. May reduce accuracy.",
    "realtime": "Ultra low latency for real-time applications. 200ms chunks.",
    "low_latency": "Fast transcription with good accuracy. 500ms chunks.",
    "balanced": "Best balance for most use cases. 1 second chunks.",
    "high_accuracy": "Maximum accuracy with larger chunks. 2 second chunks.",
}

# ============================================
# Setting Category Labels
# ============================================
CATEGORY_LABELS: Dict[str, str] = {
    "general": "General",
    "transcription": "Transcription",
    "audio": "Audio",
    "hotkey": "Hotkey",
    "advanced": "Advanced",
    "refiner": "Refiner",
}

# ============================================
# Setting Labels
# ============================================
SETTING_LABELS: Dict[str, str] = {
    # General
    "defaultSessionTitle": "Default Session Title",
    "defaultLanguage": "Default Language",
    "exportDirectory": "Export Directory",
    "autoSaveInterval": "Auto-Save Interval",
    "theme": "Theme",
    "showNotifications": "Show Notifications",
    "minimizeToTray": "Minimize to Tray",
    "startupWithSystem": "Start with System",
    # Transcription
    "model_name": "Model",
    "default_asr_model_id": "ASR Model ID",
    "compute_type": "Compute Type",
    "chunk_duration": "Chunk Duration",
    "overlap_ratio": "Overlap Ratio",
    "live_mode": "Live Mode",
    "vad_enabled": "Enable VAD",
    "vad_threshold_db": "VAD Threshold",
    "vad_min_silence_ms": "VAD Min Silence",
    "vad_speech_pad_ms": "VAD Speech Padding",
    "confidence_threshold": "Confidence Threshold",
    "enable_filler_filter": "Filter Filler Words",
    "enable_hallucination_filter": "Filter Hallucinations",
    "min_segment_length": "Min Segment Length",
    "max_workers": "Max Workers",
    "use_parallel_processing": "Parallel Processing",
    "preload_model": "Preload Model",
    "hotkey_optimized": "Hotkey Optimized",
    "beam_size": "Beam Size",
    "best_of": "Best Of",
    "patience": "Patience",
    "temperature": "Temperature",
    "refinement_mode": "Refinement Mode",
    # Audio
    "captureMode": "Capture Mode",
    "defaultDeviceId": "Default Audio Device",
    "audio_backend": "Audio Backend",
    "sampleRate": "Sample Rate",
    "noiseFiltering": "Noise Filtering",
    "echoCancellation": "Echo Cancellation",
    "autoGainControl": "Auto Gain Control",
    # Hotkey
    "enabled": "Enable Global Hotkey",
    "key_combination": "Key Combination",
    "hold_mode": "Hold Mode",
    "auto_inject": "Auto-inject Text",
    "language": "Dictation Language",
    "device_id": "Dictation Microphone",
    "finish_mode_default": "Default Finish Action",
    "show_floating_window": "Show Floating Window",
    "floating_window_position": "Floating Window Position",
    "record_on_start": "Record on Start",
    "stop_on_release": "Stop on Release",
    "copy_to_clipboard": "Copy to Clipboard",
    # Advanced
    "debugMode": "Debug Mode",
    "logLevel": "Log Level",
    "enableMetrics": "Enable Metrics",
    "maxLogFiles": "Max Log Files",
    "experimentalStem": "Enhanced STEM Detection",
    "experimentalGpuAccel": "GPU Acceleration",
    # Refiner
    "selected_model_id": "Selected Model",
    "runtime_enabled": "Runtime Enabled",
    "engine_preference": "Engine Preference",
}

# ============================================
# Setting Descriptions
# ============================================
SETTING_DESCRIPTIONS: Dict[str, str] = {
    # General
    "defaultSessionTitle": "Default name for new transcription sessions",
    "defaultLanguage": "Primary language for transcription",
    "exportDirectory": "Default location for exported transcripts",
    "autoSaveInterval": "How often to save session progress",
    "theme": "Application color theme",
    "showNotifications": "Display desktop notifications for events",
    "minimizeToTray": "Keep running in system tray when closed",
    "startupWithSystem": "Launch automatically on Windows startup",
    # Transcription
    "model_name": "Whisper model size - larger is more accurate but slower",
    "compute_type": "Precision mode - float16 for quality, int8 for speed",
    "chunk_duration": "Audio chunk size in seconds",
    "overlap_ratio": "Audio overlap between chunks",
    "vad_enabled": "Voice Activity Detection - only transcribe when speech is detected",
    "vad_threshold_db": "Energy threshold for speech detection",
    "vad_min_silence_ms": "Minimum silence duration to consider end of speech",
    "vad_speech_pad_ms": "Padding added to speech segments",
    "confidence_threshold": "Minimum confidence for transcript segments",
    "enable_filler_filter": "Remove um, uh, etc.",
    "enable_hallucination_filter": "Remove likely incorrect segments",
    "min_segment_length": "Minimum duration for transcript segments",
    "max_workers": "Number of parallel processing workers",
    "use_parallel_processing": "Use multiple workers for faster transcription",
    "preload_model": "Keep model loaded in memory",
    "hotkey_optimized": "Optimize for quick hotkey-triggered sessions",
    "beam_size": "Beam search width for decoding",
    "best_of": "Number of candidates to consider during sampling",
    "patience": "Beam search patience factor",
    "temperature": "Sampling temperature - higher = more random",
    "refinement_mode": "Level of LLM post-processing applied to transcripts",
    # Audio
    "captureMode": "Choose between microphone dictation and system-audio capture",
    "defaultDeviceId": "Primary device for the selected capture mode",
    "audio_backend": "Low-level Windows capture backend",
    "sampleRate": "Audio sample rate - 16kHz recommended for Whisper",
    "noiseFiltering": "Reduce background noise",
    "echoCancellation": "Remove echo from speakers",
    "autoGainControl": "Automatically adjust input volume",
    # Hotkey
    "enabled": "Activate transcription from anywhere using a hotkey",
    "key_combination": "Press the button to record a new hotkey",
    "hold_mode": "Record while holding the hotkey",
    "auto_inject": "Type transcription into active window",
    "language": "Default language for hotkey dictation",
    "device_id": "Microphone used for quick dictation",
    "finish_mode_default": "What happens when dictation stops from the hotkey toggle",
    "show_floating_window": "Display overlay during transcription",
    "floating_window_position": "Where to show the transcription overlay",
    "record_on_start": "Begin recording when hotkey is activated",
    "stop_on_release": "End recording when hotkey is released",
    "copy_to_clipboard": "Automatically copy transcription to clipboard",
    # Advanced
    "debugMode": "Enable verbose logging and diagnostics",
    "logLevel": "Minimum severity for log messages",
    "enableMetrics": "Collect and report performance metrics",
    "maxLogFiles": "Number of log files to retain",
    "experimentalStem": "Advanced formula and equation recognition",
    "experimentalGpuAccel": "Use GPU for pre-processing when available",
    # Refiner
    "selected_model_id": "LLM model for transcript refinement",
    "runtime_enabled": "Enable runtime LLM refinement",
    "engine_preference": "Preferred LLM inference engine",
}

# ============================================
# Theme Labels
# ============================================
THEME_LABELS: Dict[str, str] = {
    "light": "Light (Lawn)",
    "dark": "Dark (Night)",
    "cyber": "Cyberpunk",
    "dracula": "Dracula",
}

# ============================================
# Compute Type Labels
# ============================================
COMPUTE_TYPE_LABELS: Dict[str, str] = {
    "float16": "Float16 (Best Quality)",
    "float32": "Float32 (Maximum Quality)",
    "int8": "Int8 (Fast, Low VRAM)",
    "int8_float16": "Int8_Float16 (Balanced)",
}

# ============================================
# Capture Mode Labels
# ============================================
CAPTURE_MODE_LABELS: Dict[str, str] = {
    "system": "System Audio",
    "microphone": "Microphone",
}

# ============================================
# Audio Backend Labels
# ============================================
AUDIO_BACKEND_LABELS: Dict[str, str] = {
    "auto": "Auto (PyAudio first)",
    "pyaudio": "PyAudio WASAPI",
    "soundcard": "Soundcard (Legacy)",
}

# ============================================
# Sample Rate Labels
# ============================================
SAMPLE_RATE_LABELS: Dict[str, str] = {
    "8000": "8 kHz",
    "16000": "16 kHz (Recommended)",
    "22050": "22.05 kHz",
    "44100": "44.1 kHz",
    "48000": "48 kHz",
}

# ============================================
# Finish Action Labels
# ============================================
FINISH_ACTION_LABELS: Dict[str, str] = {
    "finish": "Finish Only",
    "finish_and_paste": "Finish & Paste",
}

# ============================================
# Floating Window Position Labels
# ============================================
FLOATING_POSITION_LABELS: Dict[str, str] = {
    "top-left": "Top Left",
    "top-right": "Top Right",
    "bottom-left": "Bottom Left",
    "bottom-right": "Bottom Right",
    "center": "Center",
}

# ============================================
# Log Level Labels
# ============================================
LOG_LEVEL_LABELS: Dict[str, str] = {
    "DEBUG": "Debug (Most Verbose)",
    "INFO": "Info",
    "WARN": "Warning",
    "ERROR": "Error (Least Verbose)",
}

# ============================================
# Optimization Preset Labels
# ============================================
OPTIMIZATION_PRESET_LABELS: Dict[str, str] = {
    "maximum": "Maximum Quality",
    "balanced": "Balanced",
    "fast": "Maximum Speed",
    "low_memory": "Low Memory",
}

PRESET_DESCRIPTIONS: Dict[str, str] = {
    "maximum": "Best accuracy, needs 10GB+ GPU",
    "balanced": "Best balance for most systems",
    "fast": "Fastest transcription",
    "low_memory": "Fits in limited VRAM",
}

# ============================================
# Refinement Mode Labels
# ============================================
REFINEMENT_MODE_LABELS: Dict[str, str] = {
    "off": "Off (No refinement)",
    "strict": "Strict (Minor corrections)",
    "polished": "Polished (Full rewrite)",
}

# ============================================
# Refiner Engine Labels
# ============================================
REFINER_ENGINE_LABELS: Dict[str, str] = {
    "llamacpp": "Llama.cpp (Local)",
    "ollama": "Ollama (Local)",
}

# ============================================
# Tab Labels
# ============================================
TAB_LABELS: Dict[str, str] = {
    "presets": "Presets",
    "manual": "Manual",
    "hotkey": "Hotkey",
    "general": "General",
    "transcription": "Transcription",
    "audio": "Audio",
    "advanced": "Advanced",
}

# ============================================
# Button Labels
# ============================================
BUTTON_LABELS: Dict[str, str] = {
    "apply": "Apply",
    "cancel": "Cancel",
    "close": "Close",
    "save": "Save",
    "reset": "Reset",
    "start": "Start",
    "stop": "Stop",
    "pause": "Pause",
    "resume": "Resume",
    "export": "Export",
    "import": "Import",
    "delete": "Delete",
    "edit": "Edit",
    "create": "Create",
    "refresh": "Refresh",
    "search": "Search",
    "clear": "Clear",
    "copy": "Copy",
    "paste": "Paste",
    "applyOptimizedSettings": "Apply Optimized Settings",
    "applyManualSettings": "Apply Manual Settings",
    "recommended": "Recommended",
}

# ============================================
# Status Labels
# ============================================
STATUS_LABELS: Dict[str, str] = {
    "idle": "Idle",
    "recording": "Recording",
    "processing": "Processing",
    "paused": "Paused",
    "error": "Error",
    "loading": "Loading",
    "initializing": "Initializing",
    "ready": "Ready",
    "stopping": "Stopping",
    "saving": "Saving",
}

# ============================================
# Section Headers
# ============================================
SECTION_HEADERS: Dict[str, str] = {
    "systemProfile": "System Profile",
    "optimizationResults": "Optimization Results",
    "modelSettings": "Model Settings",
    "audioPipeline": "Audio Pipeline",
    "qualityFiltering": "Quality Filtering",
    "performance": "Performance",
    "liveModes": "Live Modes",
    "advancedSettings": "Advanced Settings",
    "generalSettings": "General Settings",
    "transcriptionSettings": "Transcription Settings",
    "audioSettings": "Audio Settings",
    "hotkeySettings": "Hotkey Settings",
}

# ============================================
# Error Messages
# ============================================
ERROR_MESSAGES: Dict[str, str] = {
    "backend_unavailable": "Cannot connect to backend. Please restart the application.",
    "device_not_found": "Selected audio device not found. Please check your microphone.",
    "model_load_failed": "Failed to load model. Check your GPU memory and try a smaller model.",
    "invalid_settings": "Invalid settings provided. Please check your configuration.",
    "session_save_failed": "Failed to save session. Check disk space and permissions.",
    "export_failed": "Failed to export transcript. Check the export directory.",
    "hotkey_register_failed": "Failed to register hotkey. It may be in use by another application.",
    "audio_capture_failed": "Audio capture failed. Check your audio device settings.",
    "transcription_error": "Transcription error occurred. Check logs for details.",
    "network_error": "Network error. Check your connection.",
    "timeout_error": "Operation timed out. Please try again.",
    "unknown_error": "An unknown error occurred. Please restart the application.",
    "failed_to_load_settings": "Failed to load settings",
    "failed_to_load_profile": "Failed to load system profile",
    "failed_to_optimize": "Failed to load optimized settings",
}

# ============================================
# Tooltips
# ============================================
TOOLTIPS: Dict[str, str] = {
    "hotkey_record": "Press this key combination to start/stop recording",
    "vad_threshold": "Lower values detect more quiet speech",
    "chunk_duration": "Smaller chunks = lower latency, larger = better accuracy",
    "overlap_ratio": "Higher overlap improves accuracy at boundaries but uses more resources",
    "beam_size": "Larger values improve accuracy but slow down transcription",
    "temperature": "Higher values make output more random, lower more deterministic",
    "confidence_threshold": "Segments below this confidence will be flagged for review",
    "auto_save_interval": "How often session data is saved to disk",
    "tradeoffs": "Trade-offs made for this optimization preset",
}

# ============================================
# Unit Labels
# ============================================
UNIT_LABELS: Dict[str, str] = {
    "seconds": "s",
    "milliseconds": "ms",
    "percentage": "%",
    "decibels": "dB",
    "gigabytes": "GB",
    "megabytes": "MB",
    "hertz": "Hz",
    "kilohertz": "kHz",
    "cores": "Cores",
}

# ============================================
# Hardware Labels
# ============================================
HARDWARE_LABELS: Dict[str, str] = {
    "gpu": "GPU",
    "cpu": "CPU",
    "vram": "VRAM",
    "ram": "RAM",
    "storage": "Storage",
    "ssd": "SSD",
    "hdd": "HDD",
    "available": "Available",
    "not_available": "Not Available",
    "cores": "Cores",
    "free_space": "Free Space",
}

# ============================================
# Metric Labels
# ============================================
METRIC_LABELS: Dict[str, str] = {
    "quality_level": "Quality Level",
    "vram_usage": "VRAM Usage",
    "latency": "Latency",
    "tradeoffs": "Trade-offs",
    "processing_time": "Processing Time",
    "confidence": "Confidence",
}

# ============================================
# Settings Section UI Copy
# ============================================
SETTINGS_SECTION_TEXT: Dict[str, Dict[str, str]] = {
    "audio": {
        "title": "Audio Settings",
        "description": "Configure audio capture, VAD, and noise filtering",
        "default_capture_source_title": "Default Capture Source",
        "default_capture_source_description": "Choose which source Transcripta should preselect. You can still switch it instantly from the main screen.",
        "default_audio_device_title": "Default Audio Device",
        "default_audio_device_description": "Primary device for the default capture source",
        "audio_backend_title": "Audio Backend",
        "audio_backend_description": "Choose which Windows capture backend Transcripta should prefer",
        "sample_rate_title": "Sample Rate",
        "sample_rate_description": "Audio sample rate - 16kHz is recommended for speech recognition",
        "vad_group_title": "Voice Activity Detection",
        "vad_toggle_title": "Enable VAD",
        "vad_toggle_description": "Automatically detect speech vs silence",
        "vad_threshold_title": "VAD Threshold",
        "vad_threshold_description": "Energy threshold for speech detection (dB)",
        "processing_group_title": "Audio Processing",
        "noise_filtering_title": "Noise Filtering",
        "noise_filtering_description": "Reduce background noise",
        "echo_cancellation_title": "Echo Cancellation",
        "echo_cancellation_description": "Remove echo from speakers",
        "auto_gain_control_title": "Auto Gain Control",
        "auto_gain_control_description": "Automatically adjust input volume",
        "coming_soon": "Coming Soon",
    },
    "transcription": {
        "title": "Transcription Settings",
        "description": "Configure model selection, quality, and performance parameters",
        "quick_presets_title": "Quick Presets",
        "microphone_asr_title": "Microphone ASR Model",
        "microphone_asr_description": "Used automatically when the active capture source is set to Microphone.",
        "system_asr_title": "System Audio ASR Model",
        "system_asr_description": "Used automatically when the active capture source is set to System Audio.",
        "fallback_asr_title": "Fallback ASR Model",
        "fallback_asr_description": "Used only when a source-specific ASR model is missing.",
        "compute_type_title": "Compute Type",
        "compute_type_description": "Precision mode - float16 for quality, int8 for speed",
        "chunk_duration_title": "Chunk Duration",
        "chunk_duration_description": "Audio chunk size in seconds",
        "overlap_ratio_title": "Overlap Ratio",
        "overlap_ratio_description": "Audio overlap between chunks",
        "min_segment_length_title": "Min Segment Length",
        "min_segment_length_description": "Minimum duration for a valid segment",
        "beam_group_title": "Beam Search Parameters",
        "beam_size_label": "Beam Size",
        "best_of_label": "Best Of",
        "patience_label": "Patience",
        "temperature_label": "Temperature",
        "quality_group_title": "Quality Filters",
        "confidence_threshold_title": "Confidence Threshold",
        "confidence_threshold_description": "Minimum confidence score for transcription segments",
        "filler_filter_title": "Filter Filler Words",
        "filler_filter_description": "Remove um, uh, and other filler words",
        "hallucination_filter_title": "Filter Hallucinations",
        "hallucination_filter_description": "Suppress likely model hallucinations",
        "performance_group_title": "Performance Options",
        "parallel_processing_title": "Parallel Processing",
        "parallel_processing_description": "Use multiple workers for faster transcription",
        "preload_model_title": "Preload Model",
        "preload_model_description": "Keep model loaded in memory for faster startup",
        "hotkey_optimized_title": "Hotkey Optimized",
        "hotkey_optimized_description": "Optimize for quick hotkey-triggered sessions",
        "max_workers_title": "Max Workers",
        "max_workers_description": "Number of parallel transcription workers",
        "not_installed_suffix": " (not installed)",
    },
    "models": {
        "title": "Model Manager",
        "description": "Install, verify, and choose speech-to-text and transcript refiner models.",
        "asr_title": "Speech-to-Text",
        "asr_description": "Choose the default ASR model for new sessions. Session Setup still lets you override the current run.",
        "refiner_title": "Transcript Refiner",
        "refiner_description": "Choose a local cleanup/refiner model. Enable llama.cpp runtime to apply Strict or Polished cleanup after final text is produced.",
        "runtime_title": "Enable Local Refiner Runtime",
        "runtime_description": "Uses llama.cpp with the selected installed GGUF model for final-text cleanup. When disabled, Transcripta uses built-in cleanup only.",
        "runtime_hint": "Applies only to final text, not live partials.",
        "refinement_mode_title": "Refinement Mode",
        "refinement_mode_description": "Off disables cleanup beyond built-in heuristics. Strict preserves meaning. Polished allows minor rephrasing.",
    },
}
