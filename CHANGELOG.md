# Changelog

All notable changes to Transcripta will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Project root structure reorganization for better maintainability
- Centralized configuration package (`config/`)
- Documentation organization into `docs/architecture/`, `docs/deployment/`, `docs/operations/`
- Electron main process files organized under `app/desktop/main/` (moved from `ui-electron/`)

### Changed

- Moved `docs/ARCHITECTURE_PLAN.md` → `docs/architecture/ARCHITECTURE_PLAN.md`
- Moved `docs/DEPLOYMENT.md` → `docs/deployment/DEPLOYMENT.md`
- Moved `docs/OPERATIONS.md` → `docs/operations/OPERATIONS.md`
- Moved `ui-electron/` → `app/desktop/` for better project organization

## [0.1.0] - 2026-03-01

### Added

- Initial release with core transcription functionality
- Real-time speech-to-text using faster-whisper
- System audio capture via WASAPI loopback
- Electron desktop shell
- Session-based transcript management
- STEM formula detection and review
- Quality filtering (filler words, hallucinations)
- Global hotkey support (Ctrl+Shift+T)
- Floating transcription window
- Model download manager
- Auto-optimization based on PC specs
- GPU/CPU execution modes
- Export to multiple formats (JSON, TXT, Markdown)

### Features

- **Live Transcription**: Real-time transcription with configurable latency modes
- **Privacy-First**: All processing local, no cloud dependencies
- **STEM-Aware**: Detects and flags mathematical/scientific content for review
- **Quality Controls**: Confidence thresholds, filler word filtering
- **Session Management**: Automatic saving and organization of transcripts
- **Hardware Optimization**: Automatic GPU detection and optimization

### Technical

- Python 3.11 backend with FastAPI
- Electron frontend with React
- faster-whisper for STT
- CTranslate2 for inference
- PyAudioWPatch for audio capture
- Windows 11 primary support
