import unittest

from booru_download.ui.app import (
    COLORS,
    THEME_DARK,
    THEME_LIGHT,
    apply_theme_palette,
    normalize_ui_theme,
)


class ThemePaletteTests(unittest.TestCase):
    def test_normalize_ui_theme_defaults_invalid_values(self):
        self.assertEqual(normalize_ui_theme("dark"), "dark")
        self.assertEqual(normalize_ui_theme("LIGHT"), "light")
        self.assertEqual(normalize_ui_theme("invalid"), "light")

    def test_apply_theme_palette_switches_colors(self):
        apply_theme_palette("light")
        self.assertEqual(COLORS["app_bg"], THEME_LIGHT["app_bg"])

        apply_theme_palette("dark")
        self.assertEqual(COLORS["app_bg"], THEME_DARK["app_bg"])
        self.assertNotEqual(COLORS["panel"], THEME_LIGHT["panel"])


if __name__ == "__main__":
    unittest.main()
