[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PySide6](https://img.shields.io/badge/PySide6-6.7+-green.svg)](https://pyside.org/)

---

# Qt/PySide UI (Legacy Fallback)

> ⚠️ **Work in Progress** - This project is not finished. See main [README](../../../README.md) for status.
>
> **Last Updated:** March 13, 2026

---

This directory contains the Qt-based UI implementation using PySide6. It serves as a functional fallback when the Electron UI is unavailable.

---

## Status

**⚠️ Legacy/Fallback Status**

This UI is functional but **secondary** to the Electron-based distribution. It is maintained as a fallback for:
- Development and debugging purposes
- Emergency fallback if Electron issues arise
- Environments where Electron is not suitable

---

## Active UI

The **primary and actively maintained UI** is the Electron app located at:
- `app/electron/` - Electron-based desktop application

---

## Files

- `main_window.py` - Main Qt window implementation with PySide6
- `__init__.py` - Module exports

---

## Qt UI Capabilities

The Qt UI provides basic functionality:
- **Basic transcription** - Record and transcribe audio
- **Settings management** - Configure transcription settings
- **Session management** - Save and review past transcriptions
- **Audio capture** - Microphone recording support

---

## Limitations vs Electron

The Qt UI has the following limitations:
- **No floating window** - Cannot be used as an overlay
- **No system tray** - Cannot minimize to system tray
- **No global hotkeys** - Qt hotkeys only work when the window is focused
- **Simpler UI** - Less polished interface

**Note:** Settings and session data **are compatible** between both UIs.

---

## Usage

To run the Qt UI instead of Electron:

```python
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.core.config import AppSettings

app = QApplication([])
settings = AppSettings()
window = MainWindow(settings=settings)
window.show()
app.exec()
```

Or via command line:

```bash
python -c "from PySide6.QtWidgets import QApplication; from app.ui.main_window import MainWindow; from app.core.config import AppSettings; app = QApplication([]); settings = AppSettings(); window = MainWindow(settings=settings); window.show(); app.exec()"
```

---

## Migration Notes

- All new UI development should happen in `app/electron/`
- The Qt UI does not have feature parity with the Electron UI
- Settings and session data are compatible between both UIs

---

## Future Plans

- Maintained as a fallback/debugging tool
- May be used for environments where Electron is unavailable
- No active feature development planned
