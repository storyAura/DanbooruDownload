import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from danbooru_download.core.image_conversion import ImageConversionConfig, ImageConverter


def create_rgba_png(path: Path) -> None:
    image = Image.new("RGBA", (8, 8), (255, 0, 0, 128))
    image.save(path)


class ImageConverterTests(unittest.TestCase):
    def test_jpg_conversion_uses_quality_and_white_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.png"
            create_rgba_png(source)
            calls = []

            def fake_save(image, fp, format=None, **params):
                calls.append((image.mode, Path(fp), format, params))
                Path(fp).write_bytes(b"jpg")

            converter = ImageConverter(
                ImageConversionConfig(format="jpg", quality=82, effort=2)
            )
            with patch.object(Image.Image, "save", autospec=True, side_effect=fake_save):
                converted = converter.convert(source)

        self.assertEqual(converted.name, "sample.jpg")
        self.assertEqual(calls[-1][0], "RGB")
        self.assertEqual(calls[-1][2], "JPEG")
        self.assertEqual(calls[-1][3]["quality"], 82)
        self.assertTrue(calls[-1][3]["optimize"])

    def test_webp_lossy_conversion_uses_quality_and_effort(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.png"
            create_rgba_png(source)
            calls = []

            def fake_save(image, fp, format=None, **params):
                calls.append((Path(fp), format, params))
                Path(fp).write_bytes(b"webp")

            converter = ImageConverter(
                ImageConversionConfig(format="webp", quality=77, lossless=False, effort=4)
            )
            with patch.object(Image.Image, "save", autospec=True, side_effect=fake_save):
                converted = converter.convert(source)

        self.assertEqual(converted.name, "sample.webp")
        self.assertEqual(calls[-1][1], "WEBP")
        self.assertEqual(calls[-1][2]["quality"], 77)
        self.assertFalse(calls[-1][2]["lossless"])
        self.assertEqual(calls[-1][2]["method"], 4)

    def test_webp_lossless_conversion_uses_lossless_and_effort(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.png"
            create_rgba_png(source)
            calls = []

            def fake_save(image, fp, format=None, **params):
                calls.append((Path(fp), format, params))
                Path(fp).write_bytes(b"webp")

            converter = ImageConverter(
                ImageConversionConfig(format="webp", quality=50, lossless=True, effort=6)
            )
            with patch.object(Image.Image, "save", autospec=True, side_effect=fake_save):
                converter.convert(source)

        self.assertTrue(calls[-1][2]["lossless"])
        self.assertEqual(calls[-1][2]["method"], 6)


if __name__ == "__main__":
    unittest.main()
