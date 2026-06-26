import tempfile
import unittest
from pathlib import Path

from config import Config


class ConfigConversionTests(unittest.TestCase):
    def test_conversion_defaults_are_disabled_jpg(self):
        config = Config()

        self.assertFalse(config.auto_convert_images)
        self.assertEqual(config.auto_convert_format, "jpg")
        self.assertEqual(config.auto_convert_quality, 95)
        self.assertFalse(config.auto_convert_lossless)
        self.assertEqual(config.auto_convert_effort, 6)
        self.assertEqual(config.auto_convert_background_mode, "color")
        self.assertEqual(config.auto_convert_background_color, "#ff4fd8")

    def test_yaml_round_trips_conversion_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            Config(
                auto_convert_images=True,
                auto_convert_format="webp",
                auto_convert_background_mode="white",
                auto_convert_background_color="#00ff66",
            ).to_yaml(path)

            loaded = Config.from_yaml(path)

        self.assertTrue(loaded.auto_convert_images)
        self.assertEqual(loaded.auto_convert_format, "webp")
        self.assertEqual(loaded.auto_convert_quality, 95)
        self.assertFalse(loaded.auto_convert_lossless)
        self.assertEqual(loaded.auto_convert_effort, 6)
        self.assertEqual(loaded.auto_convert_background_mode, "white")
        self.assertEqual(loaded.auto_convert_background_color, "#00ff66")

    def test_invalid_conversion_options_fall_back_to_safe_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "\n".join(
                    [
                        "auto_convert_images: true",
                        "auto_convert_format: bmp",
                        "auto_convert_quality: 500",
                        "auto_convert_lossless: yes",
                        "auto_convert_effort: 99",
                        "auto_convert_background_mode: stripes",
                        "auto_convert_background_color: hotpink",
                    ]
                ),
                encoding="utf-8",
            )

            loaded = Config.from_yaml(path)

        self.assertTrue(loaded.auto_convert_images)
        self.assertEqual(loaded.auto_convert_format, "jpg")
        self.assertEqual(loaded.auto_convert_quality, 95)
        self.assertTrue(loaded.auto_convert_lossless)
        self.assertEqual(loaded.auto_convert_effort, 6)
        self.assertEqual(loaded.auto_convert_background_mode, "color")
        self.assertEqual(loaded.auto_convert_background_color, "#ff4fd8")


if __name__ == "__main__":
    unittest.main()
