import asyncio
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from downloader import Downloader
from formatter import FilenameFormatter


POST = {
    "id": 1001,
    "tag_string_character": "hakurei_reimu",
    "tag_string_general": "solo smile",
}


def create_rgba_png(path: Path) -> None:
    image = Image.new("RGBA", (8, 8), (255, 0, 0, 128))
    image.save(path)


class DownloaderConversionTests(unittest.TestCase):
    def test_converts_image_to_sibling_jpg_folder_named_after_source_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp) / "dracaena_sunbringer"
            source = save_dir / "sample.png"
            save_dir.mkdir()
            create_rgba_png(source)
            downloader = Downloader(
                save_dir=save_dir,
                auto_convert_images=True,
                auto_convert_format="jpg",
            )

            converted = downloader._convert_image(source)

            self.assertEqual(
                converted,
                save_dir.parent / "dracaena_sunbringer_jpg" / "sample.jpg",
            )
            self.assertTrue(converted.exists())
            self.assertTrue(source.exists())

    def test_converts_image_to_sibling_webp_folder_named_after_source_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp) / "dracaena_sunbringer"
            source = save_dir / "sample.png"
            save_dir.mkdir()
            create_rgba_png(source)
            downloader = Downloader(
                save_dir=save_dir,
                auto_convert_images=True,
                auto_convert_format="webp",
            )

            converted = downloader._convert_image(source)

            self.assertEqual(
                converted,
                save_dir.parent / "dracaena_sunbringer_webp" / "sample.webp",
            )
            self.assertTrue(converted.exists())

    def test_passes_webp_background_settings_to_converter(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = Downloader(
                save_dir=Path(tmp),
                auto_convert_images=True,
                auto_convert_format="webp",
                auto_convert_background_mode="random",
                auto_convert_background_color="#00ff66",
            )

            self.assertEqual(downloader.conversion_config.background_mode, "random")
            self.assertEqual(downloader.conversion_config.background_color, "#00ff66")

    def test_tag_txt_follows_converted_image_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp) / "dracaena_sunbringer"
            converted = save_dir.parent / "dracaena_sunbringer_jpg" / "sample.jpg"
            downloader = Downloader(save_dir=save_dir, save_tag_txt=True)

            downloader._write_tag_txt(converted, POST)

            txt_path = converted.with_suffix(".txt")
            self.assertTrue(txt_path.exists())
            self.assertEqual(txt_path.read_text(encoding="utf-8").strip(), "hakurei_reimu, solo, smile")

    def test_tag_txt_stays_with_original_without_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp)
            original = save_dir / "sample.png"
            downloader = Downloader(save_dir=save_dir, save_tag_txt=True)

            downloader._write_tag_txt(original, POST)

            self.assertTrue((save_dir / "sample.txt").exists())
            self.assertFalse((save_dir.parent / f"{save_dir.name}_jpg" / "sample.txt").exists())

    def test_existing_original_is_converted_when_target_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp) / "dracaena_sunbringer"
            source = save_dir / "1001.png"
            save_dir.mkdir()
            create_rgba_png(source)
            downloader = Downloader(
                save_dir=save_dir,
                formatter=FilenameFormatter("{id}.{ext}"),
                auto_convert_images=True,
                auto_convert_format="jpg",
                save_tag_txt=True,
                on_log=lambda _msg: None,
            )

            result = asyncio.run(
                downloader._download_one(
                    client=None,
                    post={**POST, "file_url": "https://example.invalid/1001.png", "file_ext": "png"},
                    semaphore=asyncio.Semaphore(1),
                )
            )

            self.assertTrue(result)
            self.assertTrue(
                (save_dir.parent / "dracaena_sunbringer_jpg" / "1001.jpg").exists()
            )
            self.assertTrue(
                (save_dir.parent / "dracaena_sunbringer_jpg" / "1001.txt").exists()
            )


if __name__ == "__main__":
    unittest.main()
