---

# OpenWispr

> ⚠️ **Work in Progress** - This is an active development project. Not all features are implemented, there are known bugs, and the API may change.
>
> **Last Updated:** March 13, 2026

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)
[![Windows 11](https://img.shields.io/badge/windows-11-0078D6.svg)](https://www.microsoft.com/windows/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Privacy-first, local desktop transcription for Windows 11**

---

## ⚠️ Status: In Development

This project is **not finished**. Here's what that means:

- **Known Bugs**: There are 150+ documented bugs in `reports/`
- **Missing Features**: Some settings are marked as "Coming Soon"
- **API Changes**: Settings and interfaces may change
- **Not Production Ready**: Do not use for critical transcription jobs
- **Documentation Gaps**: Some areas lack complete documentation

See [reports/](reports/) for detailed audit findings.

---

## ✨ Key Features

### 🔥 Hotkey Mode - Quick Dictation

Press a hotkey to start instant recording from your microphone. Text appears in real-time as you speak and automatically pastes at your cursor position. Perfect for quick notes, emails, and chat messages.

### 🎙️ System Mode - Full Sessions

Transcribe system audio from videos, podcasts, meetings, and any playback. Supports multi-hour sessions with automatic silence detection, session history, and export to TXT, JSON, SRT, and VTT formats.

### 🔒 Privacy First

All transcription runs 100% locally on your machine—never sends audio or text to the cloud. Works completely offline. You own all your transcripts and data.

---

## ⚠️ Known Issues

See [reports/](reports/) for comprehensive audit of:

- Security issues
- Performance bottlenecks  
- Settings inconsistencies
- Missing error handling

---

## 🚀 Quick Start

```powershell
# Clone and enter directory
git clone <repo-url>
cd OpenWispr

# Create virtual environment
python -m venv .venv
. .venv\Scripts\Activate.ps1

# Install dependencies
pip install -e .[dev]
cd app/electron && pnpm install && cd ..

# Start the app
pnpm run dev
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/) | Full usage instructions |
| [Configuration](docs/configuration.md) | Settings and presets |
| [Models](docs/models.md) | Whisper model selection |
| [Troubleshooting](docs/troubleshooting.md) | Common issues |
| [Reports](reports/) | Development audit findings |

---

## 💻 System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **OS** | Windows 11 | Windows 11 |
| **Python** | 3.11+ | 3.11+ |
| **RAM** | 8GB | 16GB |
| **Storage** | 2GB + model space | 5GB + model space |
| **GPU** | None | NVIDIA 2GB+ VRAM |

---

## 🤝 Contributing

Contributions welcome! Please note:

- This is a complex project with many moving parts
- Check the [reports/](reports/) for areas needing work
- Run `python scripts/validate/validate.py` before submitting

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.
