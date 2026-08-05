import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from booru_download.cli import main, parse_args
from booru_download.core.fs_safety import is_video_extension


class VideoExtensionHelpersTests(unittest.TestCase):
    def test_detects_video_extensions(self):
        self.assertTrue(is_video_extension("mp4"))
        self.assertTrue(is_video_extension(".WEBM"))
        self.assertTrue(is_video_extension("zip"))
        self.assertFalse(is_video_extension("jpg"))


class CliDryRunTests(unittest.TestCase):
    def test_parse_args_accepts_dry_run_and_include_video(self):
        with patch("sys.argv", ["main.py", "-t", "landscape", "--dry-run", "--include-video"]):
            args = parse_args()
        self.assertTrue(args.dry_run)
        self.assertTrue(args.include_video)

    def test_dry_run_lists_posts_without_downloading(self):
        posts = [
            {
                "id": 1,
                "file_ext": "jpg",
                "file_url": "https://example.com/1.jpg",
                "tag_string": "landscape sky",
                "tag_string_artist": "painter",
                "tag_string_general": "landscape sky",
                "md5": "a" * 32,
                "rating": "g",
                "score": 10,
                "width": 100,
                "height": 100,
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": 2,
                "file_ext": "mp4",
                "file_url": "https://example.com/2.mp4",
                "tag_string": "landscape",
                "tag_string_artist": "painter",
                "tag_string_general": "landscape",
                "md5": "b" * 32,
                "rating": "g",
                "score": 11,
                "width": 100,
                "height": 100,
                "created_at": "2024-01-01T00:00:00Z",
            },
        ]

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def search_all(self, tags="", max_posts=100, on_log=None):
                return posts

        buf = io.StringIO()
        with patch("sys.argv", ["main.py", "-t", "landscape", "-l", "5", "--dry-run"]), \
             patch("booru_download.cli.DanbooruClient", FakeClient), \
             patch("booru_download.cli.Downloader") as mock_dl, \
             redirect_stdout(buf):
            main()

        output = buf.getvalue()
        self.assertIn("dry-run", output.lower())
        self.assertIn("#1", output)
        self.assertNotIn("#2", output)  # mp4 filtered by default
        self.assertIn("Would download 1 file", output)
        mock_dl.assert_not_called()

    def test_include_video_keeps_mp4_in_dry_run(self):
        posts = [
            {
                "id": 9,
                "file_ext": "mp4",
                "file_url": "https://example.com/9.mp4",
                "tag_string": "landscape",
                "tag_string_artist": "painter",
                "tag_string_general": "landscape",
                "md5": "c" * 32,
                "rating": "g",
                "score": 1,
                "width": 10,
                "height": 10,
                "created_at": "2024-01-01T00:00:00Z",
            },
        ]

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def search_all(self, tags="", max_posts=100, on_log=None):
                return posts

        buf = io.StringIO()
        with patch(
            "sys.argv",
            ["main.py", "-t", "landscape", "--dry-run", "--include-video"],
        ), patch("booru_download.cli.DanbooruClient", FakeClient), redirect_stdout(buf):
            main()

        self.assertIn("#9", buf.getvalue())


class CliAuthGateTests(unittest.TestCase):
    def test_gelbooru_without_credentials_exits(self):
        with patch(
            "sys.argv",
            ["main.py", "-t", "1girl", "-u", "https://gelbooru.com", "--dry-run"],
        ), patch("booru_download.cli.CredentialsStore") as store_cls, \
             self.assertRaises(SystemExit) as cm:
            store = store_cls.return_value
            store.load.return_value = None
            store.apply_to_config.side_effect = lambda config, **kwargs: config
            main()
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
