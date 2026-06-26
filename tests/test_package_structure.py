import unittest
from pathlib import Path


class PackageStructureTests(unittest.TestCase):
    def test_package_modules_are_importable(self):
        from danbooru_download.core.config import Config
        from danbooru_download.core.downloader import Downloader
        from danbooru_download.ui.app import DanbooruGUI

        self.assertIsNotNone(Config)
        self.assertIsNotNone(Downloader)
        self.assertIsNotNone(DanbooruGUI)

    def test_root_gui_is_thin_wrapper_without_details_button(self):
        root_gui = Path("gui.py").read_text(encoding="utf-8")
        self.assertNotIn("class DanbooruGUI", root_gui)
        self.assertNotIn("SoftwareDetailsDialog", root_gui)
        self.assertNotIn("btn_about", root_gui)


if __name__ == "__main__":
    unittest.main()
