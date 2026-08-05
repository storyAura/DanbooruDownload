import unittest
from unittest.mock import MagicMock, patch

from booru_download.core.config import Config
from booru_download.core.credentials import get_auth_profile, validate_credentials


class AuthGateLogicTests(unittest.TestCase):
    def test_gelbooru_auth_required_without_credentials(self):
        auth = get_auth_profile("https://gelbooru.com")
        self.assertTrue(auth.auth_required)
        errors = validate_credentials("https://gelbooru.com", "", "")
        self.assertIn("auth_required", errors)

    def test_danbooru_auth_optional(self):
        auth = get_auth_profile("https://danbooru.donmai.us")
        self.assertFalse(auth.auth_required)
        self.assertEqual(
            validate_credentials("https://danbooru.donmai.us", "", ""),
            [],
        )

    def test_gui_ensure_auth_ready_blocks_gelbooru(self):
        from booru_download.ui.app import BooruDownloadGUI

        with patch.object(BooruDownloadGUI, "__init__", lambda self: None):
            gui = BooruDownloadGUI()
            gui.t = {
                "auth_required_title": "Need auth",
                "auth_required_msg": "Open settings?",
            }
            gui._open_settings = MagicMock()
            config = Config(base_url="https://gelbooru.com", username="", api_key="")

            with patch("booru_download.ui.app.messagebox.askyesno", return_value=True) as ask:
                ready = BooruDownloadGUI._ensure_auth_ready(gui, config)

            self.assertFalse(ready)
            ask.assert_called_once()
            gui._open_settings.assert_called_once()


if __name__ == "__main__":
    unittest.main()
