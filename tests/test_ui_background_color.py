import unittest

from danbooru_download.ui.app import is_hex_background_color


class UiBackgroundColorTests(unittest.TestCase):
    def test_hex_background_color_accepts_rrggbb_values(self):
        self.assertTrue(is_hex_background_color("#ff4fd8"))
        self.assertTrue(is_hex_background_color("#00FF66"))

    def test_hex_background_color_rejects_invalid_values(self):
        self.assertFalse(is_hex_background_color("hotpink"))
        self.assertFalse(is_hex_background_color("#fff"))
        self.assertFalse(is_hex_background_color("#12345g"))


if __name__ == "__main__":
    unittest.main()
