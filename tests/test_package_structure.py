import unittest
from pathlib import Path


class PackageStructureTests(unittest.TestCase):
    def test_package_modules_are_importable(self):
        from booru_download.core.config import Config
        from booru_download.core.downloader import Downloader
        from booru_download.ui.app import BooruDownloadGUI

        self.assertIsNotNone(Config)
        self.assertIsNotNone(Downloader)
        self.assertIsNotNone(BooruDownloadGUI)

    def test_root_gui_is_thin_wrapper_without_details_button(self):
        root_gui = Path("gui.py").read_text(encoding="utf-8")
        self.assertNotIn("class BooruDownloadGUI", root_gui)
        self.assertNotIn("SoftwareDetailsDialog", root_gui)
        self.assertNotIn("btn_about", root_gui)


if __name__ == "__main__":
    unittest.main()
