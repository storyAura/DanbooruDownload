import struct
import unittest
from unittest.mock import MagicMock, patch

from danbooru_download.core.nozomi_client import (
    NozomiClient,
    build_media_url,
    decode_nozomi_bytes,
    is_nozomi_metatag,
    normalize_nozomi_post,
    parse_nozomi_tags,
    post_json_url,
    sanitize_nozomi_tag,
)


class NozomiBinaryTests(unittest.TestCase):
    def test_decode_nozomi_bytes_parses_big_endian_ids(self):
        data = struct.pack(">III", 100, 200, 300)
        self.assertEqual(decode_nozomi_bytes(data), [100, 200, 300])

    def test_decode_nozomi_bytes_trims_incomplete_tail(self):
        data = struct.pack(">II", 10, 20) + b"\x00\x01"
        self.assertEqual(decode_nozomi_bytes(data), [10, 20])


class NozomiTagParsingTests(unittest.TestCase):
    def test_parse_nozomi_tags_splits_positive_negative_and_metatags(self):
        positive, negative, metatags = parse_nozomi_tags(
            "1girl solo -lowres rating:safe score:>=10 order:id"
        )
        self.assertEqual(positive, ["1girl", "solo"])
        self.assertEqual(negative, ["lowres"])
        self.assertEqual(metatags, ["rating:safe", "score:>=10", "order:id"])

    def test_is_nozomi_metatag(self):
        self.assertTrue(is_nozomi_metatag("rating:g"))
        self.assertTrue(is_nozomi_metatag("score:>=50"))
        self.assertFalse(is_nozomi_metatag("1girl"))


class NozomiUrlTests(unittest.TestCase):
    def test_sanitize_nozomi_tag(self):
        self.assertEqual(sanitize_nozomi_tag("hatsune miku"), "hatsune_miku")

    def test_post_json_url(self):
        self.assertEqual(
            post_json_url(123456789),
            "https://j.gold-usergeneratedcontent.net/post/9/78/123456789.json",
        )

    def test_build_media_url_for_static_image(self):
        url, ext = build_media_url("abcdef0123456789", "webp", is_video=False)
        self.assertEqual(ext, "webp")
        self.assertIn("w.gold-usergeneratedcontent.net", url)
        self.assertTrue(url.endswith(".webp"))

    def test_build_media_url_for_video(self):
        url, ext = build_media_url("abcdef0123456789", "webm", is_video=True)
        self.assertIn("v.gold-usergeneratedcontent.net", url)
        self.assertTrue(url.endswith(".webm"))

    def test_build_media_url_for_gif(self):
        url, ext = build_media_url("abcdef0123456789", "gif", is_video=False)
        self.assertIn("g.gold-usergeneratedcontent.net", url)
        self.assertEqual(ext, "gif")


class NozomiNormalizationTests(unittest.TestCase):
    def test_normalize_nozomi_post(self):
        raw = {
            "date": "2024-01-01",
            "width": 800,
            "height": 600,
            "artist": ["artist_tag"],
            "copyright": ["series"],
            "character": ["char"],
            "general": ["1girl", "solo"],
            "imageurls": [
                {
                    "dataid": "abcdef0123456789",
                    "type": "webp",
                    "is_video": False,
                }
            ],
        }
        post = normalize_nozomi_post(raw, 123456789)
        self.assertEqual(post["id"], 123456789)
        self.assertEqual(post["md5"], "abcdef0123456789")
        self.assertIn("w.gold-usergeneratedcontent.net", post["file_url"])
        self.assertEqual(post["tag_string_artist"], "artist_tag")
        self.assertEqual(post["tag_string_general"], "1girl solo")


class NozomiClientTests(unittest.TestCase):
    def test_resolve_post_ids_intersects_multiple_tags(self):
        client = NozomiClient()
        try:
            with patch.object(client, "fetch_tag_post_ids") as fetch_ids:
                fetch_ids.side_effect = [
                    {10, 20, 30},
                    {20, 30, 40},
                ]
                ids = client.resolve_post_ids("1girl solo", max_posts=10)
            self.assertEqual(ids, [30, 20])
        finally:
            client.close()

    def test_resolve_post_ids_subtracts_negative_tags(self):
        client = NozomiClient()
        try:
            with patch.object(client, "fetch_tag_post_ids") as fetch_ids:
                fetch_ids.side_effect = [
                    {10, 20, 30},
                    {20},
                ]
                ids = client.resolve_post_ids("1girl -lowres", max_posts=10)
            self.assertEqual(ids, [30, 10])
        finally:
            client.close()

    def test_resolve_post_ids_logs_ignored_metatags(self):
        client = NozomiClient()
        logs: list[str] = []
        try:
            with patch.object(client, "iter_tag_post_ids", return_value=iter([99])):
                ids = client.resolve_post_ids(
                    "1girl rating:safe score:>=10",
                    max_posts=5,
                    on_log=logs.append,
                )
            self.assertEqual(ids, [99])
            self.assertTrue(any("ignores unsupported metatags" in line for line in logs))
        finally:
            client.close()

    def test_search_all_yields_posts_with_media(self):
        client = NozomiClient()
        try:
            post_json = {
                "date": "2024-01-01",
                "imageurls": [{"dataid": "abc1234567890123", "type": "webp"}],
            }
            with patch.object(client, "resolve_post_ids", return_value=[42]):
                with patch.object(client, "_get") as mock_get:
                    response = MagicMock()
                    response.json.return_value = post_json
                    mock_get.return_value = response
                    posts = list(client.search_all("1girl", max_posts=1))
            self.assertEqual(len(posts), 1)
            self.assertIn("file_url", posts[0])
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
