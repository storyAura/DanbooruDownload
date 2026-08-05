import unittest

from config import Config
from danbooru_client import (
    PROFILE_DANBOORU,
    PROFILE_GELBOORU,
    PROFILE_MOEBOORU,
    PROFILE_NOZOMI,
    DanbooruClient,
    _categorize_flat_tags,
    _normalize_post,
)
from formatter import FilenameFormatter


class ConfigTagQueryTests(unittest.TestCase):
    def test_build_tags_query_preserves_space_separated_tags(self):
        config = Config(
            tags="1girl solo",
            blocked_tags="lowres -bad_anatomy",
            rating="g",
            min_score=50,
        )

        self.assertEqual(
            config.build_tags_query(),
            "1girl solo -lowres -bad_anatomy rating:g score:>=50",
        )


class ClientProfileTests(unittest.TestCase):
    def test_detects_supported_api_profiles(self):
        cases = [
            ("https://danbooru.donmai.us", PROFILE_DANBOORU),
            ("https://aibooru.online", PROFILE_DANBOORU),
            ("https://safebooru.donmai.us", PROFILE_DANBOORU),
            ("https://yande.re", PROFILE_MOEBOORU),
            ("https://konachan.com", PROFILE_MOEBOORU),
            ("https://gelbooru.com", PROFILE_GELBOORU),
            ("https://nozomi.la", PROFILE_NOZOMI),
        ]

        for base_url, expected_profile in cases:
            with self.subTest(base_url=base_url):
                client = DanbooruClient(base_url=base_url)
                try:
                    self.assertEqual(client.profile, expected_profile)
                finally:
                    client.close()


class PostNormalizationTests(unittest.TestCase):
    def test_normalizes_moebooru_post(self):
        post = _normalize_post(
            {
                "id": 123,
                "tags": "1girl solo",
                "file_url": "https://files.yande.re/image/hash/yande.re%20123%20sample.jpg",
                "width": "1600",
                "height": "900",
                "rating": "s",
                "score": "42",
                "created_at": 1_700_000_000,
            }
        )

        self.assertEqual(post["tag_string"], "1girl solo")
        self.assertEqual(post["tag_string_general"], "1girl solo")
        self.assertEqual(post["file_ext"], "jpg")
        self.assertEqual(post["image_width"], 1600)
        self.assertEqual(post["image_height"], 900)
        self.assertEqual(post["rating"], "s")
        self.assertEqual(post["score"], 42)
        self.assertIn("T", post["created_at"])

    def test_normalizes_gelbooru_post(self):
        post = _normalize_post(
            {
                "id": 456,
                "tags": "landscape sky",
                "file_url": "https://img.gelbooru.com/images/ab/cd/file.png?download=1",
                "width": 1024,
                "height": 768,
                "rating": "explicit",
                "score": "7",
            }
        )

        self.assertEqual(post["tag_string"], "landscape sky")
        self.assertEqual(post["tag_string_general"], "landscape sky")
        self.assertEqual(post["file_ext"], "png")
        self.assertEqual(post["rating"], "e")
        self.assertEqual(post["score"], 7)
        self.assertEqual(post["tag_string_artist"], "")

    def test_categorize_flat_tags_splits_character_and_meta(self):
        categorized = _categorize_flat_tags(
            "hatsune_miku_(vocaloid) 1girl highres solo"
        )
        self.assertEqual(categorized["tag_string_character"], "hatsune_miku_(vocaloid)")
        self.assertEqual(categorized["tag_string_meta"], "highres")
        self.assertEqual(categorized["tag_string_general"], "1girl solo")

    def test_flat_tag_filename_fallback_avoids_unknown_artist(self):
        post = _normalize_post(
            {
                "id": 42,
                "tags": "landscape sky highres",
                "file_url": "https://example.com/a.jpg",
            },
            profile=PROFILE_GELBOORU,
            base_url="https://gelbooru.com",
        )
        name = FilenameFormatter("{artist}_{id}.{ext}").format(post)
        self.assertEqual(name, "landscape+sky_42.jpg")
        self.assertNotIn("unknown", name)

    def test_normalizes_protocol_relative_gelbooru_url(self):
        post = _normalize_post(
            {
                "id": 789,
                "tags": "1girl",
                "file_url": "//img3.gelbooru.com/images/ab/cd/file.jpg",
            },
            profile=PROFILE_GELBOORU,
            base_url="https://gelbooru.com",
        )

        self.assertEqual(
            post["file_url"],
            "https://img3.gelbooru.com/images/ab/cd/file.jpg",
        )

    def test_builds_gelbooru_url_from_directory_and_image(self):
        post = _normalize_post(
            {
                "id": 999,
                "tags": "1girl",
                "directory": "ab/cd",
                "image": "file.jpg",
            },
            profile=PROFILE_GELBOORU,
            base_url="https://gelbooru.com",
        )

        self.assertEqual(
            post["file_url"],
            "https://img3.gelbooru.com/images/ab/cd/file.jpg",
        )


if __name__ == "__main__":
    unittest.main()
