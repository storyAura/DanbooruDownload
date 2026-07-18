import os
import unittest

import httpx

from booru_download.core.credentials import SITE_PRESET_URLS
from booru_download.core.danbooru_client import APP_USER_AGENT, DanbooruClient
from booru_download.core.nozomi_client import NOZOMI_INDEX_HOST, NozomiClient


RUN_SITE_SMOKE = os.environ.get("RUN_SITE_SMOKE") == "1"
GELBOORU_USER_ID = os.environ.get("GELBOORU_USER_ID", "").strip()
GELBOORU_API_KEY = os.environ.get("GELBOORU_API_KEY", "").strip()
SMOKE_HEADERS = {"User-Agent": APP_USER_AGENT}


def _skip_unless_smoke():
    if not RUN_SITE_SMOKE:
        raise unittest.SkipTest("Set RUN_SITE_SMOKE=1 to run live site smoke tests")


def _skip_if_site_blocked(exc: Exception, site: str) -> None:
    message = str(exc)
    if any(token in message for token in ("403", "Cloudflare", "Access denied", "429")):
        raise unittest.SkipTest(f"{site} blocked this client: {message}") from exc


def _search_one(base_url: str, tags: str = "landscape") -> list[dict]:
    with DanbooruClient(base_url=base_url, timeout=30.0) as client:
        return client.search(tags=tags, limit=1)


def _smoke_client() -> httpx.Client:
    return httpx.Client(timeout=30.0, follow_redirects=True, headers=SMOKE_HEADERS)


class SiteSmokeTests(unittest.TestCase):
    def test_danbooru_posts_json(self):
        _skip_unless_smoke()
        try:
            posts = _search_one("https://danbooru.donmai.us", tags="1girl")
        except RuntimeError as exc:
            _skip_if_site_blocked(exc, "Danbooru")
            raise
        self.assertTrue(isinstance(posts, list))

    def test_aibooru_posts_json(self):
        _skip_unless_smoke()
        try:
            posts = _search_one("https://aibooru.online")
        except RuntimeError as exc:
            _skip_if_site_blocked(exc, "AIBooru")
            raise
        self.assertTrue(isinstance(posts, list))

    def test_safebooru_posts_json(self):
        _skip_unless_smoke()
        try:
            posts = _search_one("https://safebooru.donmai.us")
        except RuntimeError as exc:
            _skip_if_site_blocked(exc, "Safebooru")
            raise
        self.assertTrue(isinstance(posts, list))

    def test_gelbooru_dapi(self):
        _skip_unless_smoke()
        if not GELBOORU_USER_ID or not GELBOORU_API_KEY:
            raise unittest.SkipTest("Set GELBOORU_USER_ID and GELBOORU_API_KEY for Gelbooru smoke test")
        with _smoke_client() as client:
            response = client.get(
                "https://gelbooru.com/index.php",
                params={
                    "page": "dapi",
                    "s": "post",
                    "q": "index",
                    "json": "1",
                    "limit": 1,
                    "pid": 0,
                    "user_id": GELBOORU_USER_ID,
                    "api_key": GELBOORU_API_KEY,
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("post", payload)

    def test_yandere_post_json(self):
        _skip_unless_smoke()
        try:
            posts = _search_one("https://yande.re")
        except RuntimeError as exc:
            _skip_if_site_blocked(exc, "Yande.re")
            raise
        self.assertTrue(isinstance(posts, list))

    def test_nozomi_index_range(self):
        _skip_unless_smoke()
        with _smoke_client() as client:
            response = client.get(
                f"https://{NOZOMI_INDEX_HOST}/nozomi/1girl.nozomi",
                headers={
                    **SMOKE_HEADERS,
                    "Referer": "https://nozomi.la/",
                    "Origin": "https://nozomi.la",
                    "Range": "bytes=0-255",
                },
            )
        self.assertIn(response.status_code, {200, 206})
        self.assertGreater(len(response.content), 0)

    def test_nozomi_client_search_one_post(self):
        _skip_unless_smoke()
        with NozomiClient(timeout=30.0) as client:
            posts = list(client.search_all("1girl", max_posts=1))
        self.assertEqual(len(posts), 1)
        self.assertTrue(posts[0].get("file_url"))

    def test_all_presets_detect_profile(self):
        for label, base_url in SITE_PRESET_URLS.items():
            with self.subTest(label=label):
                client = DanbooruClient(base_url=base_url)
                try:
                    self.assertIsNotNone(client.profile)
                finally:
                    client.close()


if __name__ == "__main__":
    unittest.main()
