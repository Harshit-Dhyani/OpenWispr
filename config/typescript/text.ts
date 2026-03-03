// Auto-generated from config/python/text.py
// Do not edit manually - run `python config/generate_ts.py` to regenerate

export const ModelNames: Record<string, string> = {
  "tiny": "Tiny (fastest, lowest accuracy)",
  "small": "Small (recommended)",
  "medium": "Medium (slower, better accuracy)",
  "large-v3": "Large v3 (slowest, best accuracy)",
  "turbo": "Turbo (balanced)"
};

export const LiveModeLabels: Record<string, string> = {
  "ultra": "Ultra (100ms)",
  "realtime": "Realtime (200ms)",
  "low_latency": "Low Latency (500ms)",
  "balanced": "Balanced (1s)",
  "high_accuracy": "High Accuracy (2s)"
};

export const LiveModeDescriptions: Record<string, string> = {
  "ultra": "Fastest response but may sacrifice accuracy. Good for rapid interaction.",
  "realtime": "Near-instant transcription with acceptable accuracy.",
  "low_latency": "Good balance for live captioning scenarios.",
  "balanced": "Default mode. Good accuracy with reasonable latency.",
  "high_accuracy": "Best accuracy for recording and post-processing."
};

export const SettingLabels: Record<string, string> = {
  "model": "Transcription Model",
  "live_mode": "Live Mode",
  "execution_mode": "Execution Mode",
  "language": "Language",
  "audio_device": "Audio Device",
  "theme": "Theme",
  "hotkey": "Global Hotkey",
  "confidence_threshold": "Confidence Threshold",
  "enable_filler_filter": "Filter Filler Words",
  "enable_hallucination_filter": "Filter Hallucinations",
  "floating_position": "Floating Window Position",
  "auto_hide_floating": "Auto-hide Floating Window"
};

export const SettingDescriptions: Record<string, string> = {
  "model": "Choose the Whisper model size. Larger models are more accurate but slower.",
  "live_mode": "Controls the trade-off between speed and accuracy.",
  "execution_mode": "GPU is faster but requires CUDA. CPU works on all systems.",
  "language": "Primary language for transcription. 'Auto' detects automatically.",
  "audio_device": "Select the audio input or system output to capture.",
  "theme": "Application color theme.",
  "hotkey": "Global keyboard shortcut to toggle recording.",
  "confidence_threshold": "Minimum confidence score for transcription segments.",
  "enable_filler_filter": "Remove filler words like 'um' and 'uh'.",
  "enable_hallucination_filter": "Filter out common Whisper hallucinations.",
  "floating_position": "Where the floating transcription window appears.",
  "auto_hide_floating": "Automatically hide floating window when not recording."
};

export const ButtonLabels: Record<string, string> = {
  "start_recording": "Start Recording",
  "stop_recording": "Stop Recording",
  "pause": "Pause",
  "resume": "Resume",
  "save": "Save",
  "export": "Export",
  "settings": "Settings",
  "close": "Close",
  "cancel": "Cancel",
  "apply": "Apply",
  "reset": "Reset to Defaults"
};

export const StatusLabels: Record<string, string> = {
  "ready": "Ready",
  "recording": "Recording...",
  "paused": "Paused",
  "processing": "Processing...",
  "saving": "Saving...",
  "error": "Error",
  "loading_model": "Loading model...",
  "initializing": "Initializing..."
};

export const ErrorMessages: Record<string, string> = {
  "model_load_failed": "Failed to load the transcription model. Please try a smaller model or check your GPU drivers.",
  "audio_device_not_found": "The selected audio device is not available. Please check your audio settings.",
  "backend_not_running": "The transcription backend is not running. Please restart the application.",
  "export_failed": "Failed to export the transcript. Please check the file path and try again.",
  "permission_denied": "Permission denied. Please run the application with appropriate permissions.",
  "unknown_error": "An unexpected error occurred. Please check the logs for details."
};

export const Tooltips: Record<string, string> = {
  "stem_indicator": "STEM content detected. Click to review formulas and technical terms.",
  "confidence_low": "Low confidence - please review this segment.",
  "confidence_high": "High confidence transcription.",
  "gpu_active": "GPU acceleration active",
  "cpu_active": "Running on CPU",
  "hotkey_config": "Click to configure the global hotkey"
};
