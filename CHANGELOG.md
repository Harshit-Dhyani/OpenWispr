# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-03-15

### Added
- Provider health display in UI and backend
- Provider URL support for refiner and coach services
- Providers API route for provider management
- Local LLM provider infrastructure
- CI/CD workflows for automated testing and release
- New prompt system for audit and fix workflows
- Expanded E2E and regression test coverage
- Module reorganization for audio, core, and Electron services

### Fixed
- Settings validation improvements
- Provider base URL fields in settings dataclasses
- Database improvements
- Python import errors across audio, API, and config modules
- TypeScript type errors in floating window components
- E2E test configuration issues
- Legacy naming cleanup (Transcripta → OpenWispr)

### Changed
- Updated settings to support provider health and URL
- Reorganized audio pipeline modules into dedicated directories
- Reorganized core modules (logging, metrics, optimization, profiling, session)
- Updated backward-compatibility shims for settings

### Security
- Added security policy documentation
- Improved secret handling in CI/CD

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
