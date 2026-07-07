import tempfile
import unittest
from pathlib import Path

from downloader import Downloader


class DownloaderValidationTests(unittest.TestCase):
    def test_zero_byte_existing_file_is_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp)
            filepath = save_dir / "sample.jpg"
            filepath.write_bytes(b"")
            downloader = Downloader(save_dir=save_dir, skip_existing=True)
            self.assertFalse(downloader._already_exists(filepath, {"md5": "abc"}))

    def test_valid_existing_file_is_skipped_without_md5(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp)
            filepath = save_dir / "sample.jpg"
            filepath.write_bytes(b"\xff\xd8\xff\xd9")
            downloader = Downloader(save_dir=save_dir, skip_existing=True)
            self.assertTrue(downloader._already_exists(filepath, {}))

    def test_detects_image_magic_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp)
            png_path = save_dir / "sample.png"
            png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
            downloader = Downloader(save_dir=save_dir)
            self.assertTrue(downloader._looks_like_image(png_path))


if __name__ == "__main__":
    unittest.main()
