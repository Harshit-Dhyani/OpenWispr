import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config.constants import AppConstants
from app.core.settings.config import AppSettings, default_download_root, is_legacy_download_root


class DownloadRootSettingsTests(unittest.TestCase):
    def test_default_download_root_uses_windows_appdata(self) -> None:
        with (
            patch("app.core.settings.config.sys.platform", "win32"),
            patch.dict(os.environ, {"APPDATA": r"C:\Users\tester\AppData\Roaming"}, clear=False),
        ):
            expected = Path(r"C:\Users\tester\AppData\Roaming") / AppConstants.APP_NAME / "models"
            self.assertEqual(default_download_root(), expected)

    def test_legacy_env_download_root_is_upgraded(self) -> None:
        with (
            patch("app.core.settings.config.sys.platform", "win32"),
            patch.dict(
                os.environ,
                {
                    "APPDATA": r"C:\Users\tester\AppData\Roaming",
                    "OPENWISPR_DOWNLOAD_ROOT": "./models",
                },
                clear=False,
            ),
        ):
            expected = Path(r"C:\Users\tester\AppData\Roaming") / AppConstants.APP_NAME / "models"
            self.assertTrue(is_legacy_download_root("./models"))
            self.assertEqual(AppSettings().download_root, expected)

    def test_custom_download_root_is_preserved(self) -> None:
        with (
            patch("app.core.settings.config.sys.platform", "win32"),
            patch.dict(
                os.environ,
                {
                    "APPDATA": r"C:\Users\tester\AppData\Roaming",
                    "OPENWISPR_DOWNLOAD_ROOT": r"D:\Custom\Models",
                },
                clear=False,
            ),
        ):
            self.assertEqual(AppSettings().download_root, Path(r"D:\Custom\Models"))


if __name__ == "__main__":
    unittest.main()
