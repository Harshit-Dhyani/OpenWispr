# Qt/PySide UI (Legacy Fallback)

This directory contains the legacy Qt-based UI implementation using PySide6.

## Status

**⚠️ Legacy/Fallback Only**

This UI is **not actively used** in the current Electron-based distribution. It is kept as a fallback option for:
- Development and debugging purposes
- Future headless/server deployments where Electron is not suitable
- Emergency fallback if Electron issues arise

## Active UI

The **primary and actively maintained UI** is the Electron app located at:
- `app/electron/` - Electron-based desktop application

## Files

- `main_window.py` - Main Qt window implementation with PySide6
- `__init__.py` - Module exports

## Usage (Development Only)

To use the Qt UI instead of Electron:

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

## Migration Notes

- All new UI development should happen in `app/electron/`
- The Qt UI does not have feature parity with the Electron UI
- Settings and session data are compatible between both UIs

## Future Plans

- Potential use for server/headless deployments
- May be removed if Electron proves stable long-term
- Could be revived for Linux native look-and-feel if needed
