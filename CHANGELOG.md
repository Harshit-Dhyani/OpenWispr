# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-03-19

### Added
- Text transform API routes and services for transcript processing
- Hotkey transcription service for push-to-talk workflows
- User corrections service for managing transcript edits
- Skills system with 20+ specialized workflows for agents
- Comprehensive docstrings for all API modules and services
- mkdocs.yml with full documentation site configuration
- Repo-local skills in `.codex/skills/` for agent guidance
- Performance, integration, and unit test coverage updates
- Script sync infrastructure for skills

### Fixed
- Core module updates and compatibility fixes
- Electron UI module improvements
- Backend and frontend type safety enhancements
- Project configuration updates
- Test coverage for new features

### Changed
- Updated deployment guide with latest build commands
- Updated project structure documentation
- Added contributing-docs guide for documentation workflows
- Added operations guide for development workflows
- Added python-api reference documentation
- CHANGELOG and README date stamps

### Security
- Improved secret handling in CI/CD
- Brand assets protection

### Documentation
- Added 20+ specialized skills for agent workflows
- Updated docs hub and engineering docs
- Added source-of-truth skill for information verification
- Added public-doc-honesty skill for documentation accuracy

---

## [0.1.0] - 2026-01-15

### Added
- **Core Features**
  - Real-time speech-to-text transcription
  - System audio capture for meetings
  - Microphone dictation with hotkey activation
  - Floating window for live transcript display
  - Coach/Refiner for post-processing with local LLM
  
- **Audio Pipeline**
  - Multiple audio backend support (PyAudio, SoundCard)
  - Voice Activity Detection (VAD)
  - Low-latency optimized transcription
  - Silence gating and filtering
  
- **Models**
  - Faster-Whisper integration
  - Model download and preload management
  - GPU acceleration support
  - Model catalog with recommendations
  
- **Settings**
  - Comprehensive settings system
  - Per-source model selection (microphone vs system)
  - Language and quality presets
  - Export configuration
  
- **Desktop Integration**
  - System tray support
  - Global hotkeys
  - Floating window
  - Quick settings

### Platform Support
- Windows 10/11 (primary)
- macOS (experimental)
- Linux (experimental)
