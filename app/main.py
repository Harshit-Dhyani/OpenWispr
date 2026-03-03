from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.config import AppSettings
from app.ui.main_window import MainWindow


def main() -> int:
    settings = AppSettings()
    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    window = MainWindow(settings=settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
