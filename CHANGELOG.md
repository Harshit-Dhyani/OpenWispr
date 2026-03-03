# Changelog

All notable changes to Transcripta will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Project root structure reorganization for better maintainability
- Moved documentation to organized structure (`docs/architecture/`, `docs/deployment/`, `docs/operations/`)
- Moved Electron main process files to `app/electron/main/` (from `ui-electron/`)

## [0.1.0] - 2026-03-01

### Added

#### Core Transcription
- Dual transcription modes (Hotkey/Wispr and System)
- faster-whisper backend with multiple model support
- Real-time streaming transcription with partial results
- Local audio capture (microphone + system loopback via WASAPI)
- Voice Activity Detection (VAD) for speech segmentation
- Audio visualization with frequency-based levels
- Model pool for efficient GPU memory management
- Auto-optimization based on system profiling

#### Quality Features
- Filler word filtering (um, uh, like, etc.)
- Hallucination detection and filtering
- Text stabilization for partial results
- Dictation cleanup and normalization
- Confidence thresholds for transcription quality

#### Refiner Features
- Local LLM text refinement via llama.cpp
- Multiple refinement modes (off, strict, polished)
- Technical token preservation during refinement

#### Settings & Configuration
- Per-mode settings (Hotkey vs System modes)
- Bidirectional settings sync between frontend and backend
- Settings migrations for version upgrades
- Validation with pydantic models

#### API & Communication
- FastAPI REST API for backend operations
- WebSocket for real-time bidirectional updates
- SSE (Server-Sent Events) for transcription events
- Health monitoring endpoints

#### Frontend
- Electron + React + TypeScript application
- Multiple window types (main, floating, quick settings)
- Global hotkey support (Ctrl+Shift+T)
- System tray integration
- Settings UI with validation

#### Session Management
- JSONL-based session storage
- Export to multiple formats (TXT, JSON, SRT, VTT)
- STEM formula extraction and review
- Session recovery mechanisms

#### Performance
- GPU/CPU auto-fallback for hardware compatibility
- Backpressure handling for audio streaming
- Fast chunker with adaptive sizing
- Real-time performance metrics

#### Infrastructure
- Python 3.11 backend
- CTranslate2 for model inference
- PyAudioWPatch for Windows audio capture
- Model download manager
