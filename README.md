# OpenWispr

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)
[![Windows 11](https://img.shields.io/badge/windows-11-0078D6.svg)](https://www.microsoft.com/windows/)

**Privacy-first, local desktop transcription for Windows 11**

> **Last Updated:** March 5, 2026

OpenWispr is a production-grade desktop application for real-time speech-to-text transcription. It runs entirely on your local machine with no cloud dependencies, keeping your audio and transcripts private.

## Key Features

### Dual Transcription Modes

**Hotkey Mode (Wispr)** - Quick Dictation
- Press `Ctrl+Shift+T` to start/stop instant recording
- Optimized for low latency (<500ms first-word)
- Microphone or system audio capture
- Auto-paste transcription at cursor position
- Floating window with real-time visual feedback
- 36-bar frequency audio visualizer
- Memory-only operation (no disk I/O during recording)
- Partial text stabilization with draft/commit model
- Perfect for quick notes, emails, chat messages

**System Mode** - Full Sessions
- Transcribe system audio, videos, podcasts, meetings
- Loopback audio capture from any playback device
- Support for multi-hour sessions
- Automatic segmentation on silence
- Export to TXT, JSON, SRT, VTT formats
- Session history with notes and highlights
- STEM formula extraction for technical content
- Per-session audio backend selection
- Perfect for content creation, accessibility, documentation

### Advanced Audio Pipeline

- **16kHz sample rate** with configurable chunk sizes
- **Multiple backends**: soundcard, PyAudioWPatch with auto-fallback
- **LoopbackAudioSource** for system audio capture
- **Optimized VAD** (Voice Activity Detection) per mode
- **FastChunker** with adaptive sizing based on speech density
- Real-time audio level monitoring with frequency analysis
- Automatic device switching and recovery
- Multi-channel to mono mixing
- Backpressure handling with queue management

### STT Engine (faster-whisper)

- **FastTranscriber** with streaming transcription
- **Model Pool** for efficient model caching and reuse
- **FastChunker** with 100-400ms adaptive sizing
- **Quality filtering**: filler words, hallucinations, low-confidence detection
- **Dictation cleanup** and text stabilization
- **Partial stabilizer** for streaming results with revision tracking
- Language-specific optimizations for Hindi/English
- Language detection with fingerprint caching

### Model Management

| Model | Size | VRAM | Speed | Quality | Runtime |
|-------|------|------|-------|---------|---------|
| tiny | 80 MB | 0 GB | Fastest | Basic | enabled |
| small | 460 MB | 2 GB | Fast | Good | enabled |
| medium | 1.5 GB | 5 GB | Balanced | Better | enabled (default) |
| large-v3 | 3.1 GB | 10 GB | Slower | Excellent | enabled |
| turbo | 1.6 GB | 6 GB | Fast | Very Good | disabled |

*Sizes and VRAM from `app/core/model_catalog.py`*

- **On-demand model loading** - Only download what you use
- **Smart GPU/CPU fallback** - Automatic OOM recovery with cascade
- **INT8 quantization** - 2x faster on CPU
- **Auto-optimization** - System profiler recommends optimal settings
- Model catalog at `app/core/model_catalog.py`

### Real-Time Features

- **Streaming transcription** - Words appear as you speak
- **Partial results** - See text before it's finalized
- **Audio visualization** - 36-bar frequency level meters
- **Confidence indicators** - Quality labels (ok/weak/junk)
- **Segment boundaries** - Clear separation between thoughts
- **Backpressure monitoring** - Queue depth and drop tracking

### Refiner Service (Local LLM)

- **llama.cpp backend** for local text refinement
- **Modes**: off, strict, polished
- **Available models**: Qwen2.5 3B/7B, Mistral 7B, Phi-3 Mini
- Protects technical tokens (formulas, code)
- Automatic fallback on refiner failure
- Per-mode configuration (hotkey vs system)

### Settings System

- **Bidirectional sync** - Changes apply instantly via WebSocket
- **Settings migrations** - Versioned schema upgrades
- **Validation** - Pydantic-based with bounds checking
- **Per-mode configuration** - Different settings for hotkey/system modes
- **Offline support** - Works without internet
- Auto-generated TypeScript constants from Python

### Session Management

- **JSONL format** for structured transcript storage
- **Export formats**: TXT, JSON, SRT, VTT
- **Formula extraction** - STEM content detection and extraction
- **Session recovery** - Crash recovery with data preservation
- **Incremental output rebuild** - Efficient note generation
- **Document context** - PDF attachment for enhanced transcription

### English Coach (AI-Powered Refinement)

- **LLM-powered transcript improvement** - Local AI refines dictation output
- **Prompt templates** - Customizable coaching instructions
- **Privacy modes** - `local_only` (offline) or `allow_llm` (cloud)
- **Technical content protection** - Preserves formulas, code, hotkeys
- **Refinement profiles** - `standard` or `code_logs` for technical text
- **Floating window results** - Shows suggestions without interrupting flow
- **Cache system** - LRU cache for repeated phrases (500 entries)

### Dual Hotkey System

- **Microphone hotkey** - `Ctrl+Shift+T` (customizable) for mic dictation
- **System audio hotkey** - `Ctrl+Shift+Y` (customizable) for system audio
- **Separate model selection** - Different ASR models per source (microphone vs system)
- **Independent settings** - Per-source VAD, beam size, latency targets

### Advanced Configuration

- **Transcription presets** - `wispr` (low latency) or `system` (high quality) modes
- **Refinement modes** - `off`, `strict`, `polished` for different use cases
- **Settings import/export** - JSON-based portability between installations
- **Debug mode** - Detailed logging for troubleshooting
- **Metrics collection** - Optional anonymous performance data

### Production-Grade Features

- **Comprehensive error handling** - Structured error types with recovery
- **Automatic recovery** - Device disconnects, OOM, network issues
- **Performance monitoring** - Latency, throughput, resource usage
- **Health monitoring** - Real-time session health metrics
- **Extensive logging** - JSON-structured logs per session
- **100+ tests** - Unit, integration, and E2E coverage

## System Requirements

- **OS**: Windows 11
- **Python**: 3.11+
- **Node.js**: 20.x+ (for development)
- **GPU**: NVIDIA with 2GB+ VRAM (recommended) or CPU
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 2GB for app + model space

## Quick Start

### Installation

```powershell
# Clone repository
git clone <repo-url>
cd OpenWispr

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install Python dependencies
python -m pip install --upgrade pip setuptools wheel
pip install -e .[dev]

# Install Node dependencies (project uses pnpm)
cd app/electron
pnpm install
cd ..

# Start development
pnpm run dev
```

### GPU Verification

```powershell
# Check CUDA availability
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"

# Test faster-whisper on GPU
python -c "from faster_whisper import WhisperModel; m = WhisperModel('small', device='cuda', compute_type='float16'); print('GPU OK')"
```

## Usage

### Hotkey Mode (Quick Dictation)

Two independent hotkeys for different audio sources:

**Microphone Dictation** - `Ctrl+Shift+T` (default)
1. Press to start recording from microphone
2. Speak naturally - text appears in real-time in floating window
3. Press again to stop
4. Text automatically pasted at cursor position

**System Audio Dictation** - `Ctrl+Shift+Y` (default)
1. Press to capture system audio (videos, meetings, etc.)
2. Transcribes any playing audio in real-time
3. Press again to stop

**Pro tip:** Use `tiny` or `small` model for fastest response. Configure separate models for microphone vs system audio in Settings > Models.

### System Mode

1. Click "Start Session" in the main window
2. Select audio source (system audio or microphone)
3. Transcription builds up in real-time
4. Click "Stop Session" when done
5. Export to your preferred format (TXT, JSON, SRT, VTT)

**Pro tip:** Use `medium` or `large-v3` model for best accuracy on long content.

## Configuration

### Live Mode Profiles

| Profile | Chunk Size | Overlap | Use Case |
|---------|------------|---------|----------|
| ultra | 100ms | 20ms | Minimal latency |
| realtime | 200ms | 40ms | Fast response |
| low_latency | 500ms | 100ms | Balanced speed |
| balanced | 1s | 200ms | Default (recommended) |
| high_accuracy | 2s | 400ms | Best quality |

### Environment Variables

```powershell
# Force specific model
$env:TRANSCRIPTA_DEFAULT_MODEL='medium'

# Force compute type
$env:TRANSCRIPTA_COMPUTE_TYPE='float16'  # or 'int8' for CPU

# Specify capture device
$env:TRANSCRIPTA_CAPTURE_DEVICE_ID='<device-id>'

# Set log level
$env:TRANSCRIPTA_LOG_LEVEL='DEBUG'  # DEBUG, INFO, WARN, ERROR
```

### Settings File

User settings stored in:
```
%APPDATA%\OpenWispr\settings.json
```

Or project root:
```
user_settings.json
```

## Model Storage

Downloaded models stored in:
```
%APPDATA%\OpenWispr\models\
├── asr\
│   ├── faster-whisper-tiny\
│   ├── faster-whisper-small\
│   ├── faster-whisper-medium\
│   └── faster-whisper-large-v3
└── refiner\
    ├── qwen2.5-3b-instruct-q4_k_m.gguf
    └── qwen2.5-7b-instruct-q4_k_m.gguf
```

## Session Artifacts

Each system mode session creates:
```
sessions\<session-name>\
├── transcript.jsonl      # Structured transcript
├── transcript.txt        # Plain text export
├── notes.md              # Generated notes
├── formulas.json         # STEM formulas
├── highlights.txt        # Key highlights
├── session.json          # Session metadata
└── logs\app.log          # Debug logs
```

## Testing

### Run All Tests

```powershell
# Backend tests
pytest tests -q

# Frontend tests
cd app/electron/frontend
npm test

# E2E tests
pytest e2e -q

# Linting
ruff check .
cd app/electron && pnpm run lint
```

### Test Coverage

- Backend: >85% coverage
- Frontend: >80% coverage
- Critical paths: 100% coverage

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Electron Frontend (React/TS)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │   Main UI    │  │FloatingWindow│  │QuickSettings │  │  Tray    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │ WebSocket/SSE
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │Audio Pipeline│  │   STT Engine │  │   Session    │  │ Refiner  │ │
│  │  - Capture   │  │  - ModelPool │  │   Manager    │  │ Service  │ │
│  │  - Chunker   │  │  - Streaming │  │  - Storage   │  │(llamacpp)│ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Module Structure

```
app/
├── api/              # FastAPI server, WebSocket, settings sync
├── audio/            # Audio capture, backends (soundcard, PyAudio)
├── core/             # Settings, sessions, models, error handling
├── electron/         # Electron shell, React frontend
├── stt/              # Speech-to-text engine, chunker, quality
├── storage/          # Session storage, document store
└── stem/             # STEM formula extraction
```

## Performance Targets

| Mode | First-Word Latency | Real-Time Factor | Target |
|------|-------------------|------------------|--------|
| Hotkey (tiny) | <500ms | 0.3x | <300ms inference |
| Hotkey (small) | <800ms | 0.5x | <500ms inference |
| System (medium) | <1s | 0.5x | Balanced quality |
| System (large) | <2s | 0.7x | Best accuracy |

## Troubleshooting

### No Audio Captured

1. Check Windows playback device is correct
2. Disable exclusive mode: `Sound > Playback > Properties > Advanced`
3. Verify audio is playing through selected device
4. Run audio diagnostic: `python tools/diagnostics/check-audio.py`

### GPU Not Detected

1. Verify NVIDIA drivers installed
2. Check CUDA: `python -c "import torch; print(torch.cuda.is_available())"`
3. App falls back to CPU automatically with INT8 quantization
4. Check logs for GPU fallback messages

### Transcription Slow

1. Use smaller model (tiny, base, small)
2. Enable GPU: Settings > Execution Mode > GPU
3. Close other GPU-heavy apps
4. Use CPU with `int8` quantization for stability

### Poor Quality

1. Reduce desktop audio distortion/clipping
2. Disable spatial audio enhancements
3. Try larger model (medium, large-v3)
4. Check quality indicators - review low-confidence segments
5. Enable refiner service for post-processing

### Hotkey Not Working

1. Check if hotkey is registered: View logs for "global hotkey registered"
2. Try different hotkey combination in settings
3. Run as administrator if blocked by other apps
4. Check antivirus software isn't blocking input simulation

## Privacy & Legal

- **100% Local Processing** - No cloud upload, ever
- **No Telemetry** - Optional crash reports only
- **Your Data** - You control all transcripts and models
- **Offline Capable** - Works without internet connection
- **Important:** Only use where you have legal right to record audio

## Development

### Project Structure

```
OpenWispr/
├── app/
│   ├── api/           # REST API, WebSocket, settings sync
│   ├── audio/         # Audio capture, processing, backends
│   ├── core/          # Settings, models, error handling
│   ├── electron/      # Desktop shell, React UI
│   ├── stt/           # Speech-to-text engine
│   ├── storage/       # Session persistence
│   └── stem/          # STEM content processing
├── tests/             # Backend tests
├── e2e/               # End-to-end tests
├── tools/             # Diagnostics, scripts
├── scripts/           # Build scripts
├── pyproject.toml     # Python dependencies
└── package.json       # Node.js dependencies
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest tests -q && npm test`
4. Submit a pull request

### License

MIT License - See [LICENSE](LICENSE) for details.

---

**OpenWispr** - Local-first transcription for Windows 11

