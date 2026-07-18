"""Regression tests for the I/O hardening fixes (unique tmp, MD5, os.replace)."""

import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from booru_download.core.config import Config
from booru_download.core.credentials import CredentialsStore
from booru_download.core.downloader import Downloader
from booru_download.core.formatter import FilenameFormatter

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"payload-bytes" + b"\xff\xd9"
JPEG_MD5 = hashlib.md5(JPEG_BYTES).hexdigest()


async def _no_sleep(_delay):
    return None


def _run_single_download(downloader: Downloader, post: dict, content: bytes) -> bool:
    """Drive one _download_one call through a mock HTTP transport."""

    def handler(request):
        return httpx.Response(200, content=content)

    async def runner():
        transport = httpx.MockTransport(handler)
        semaphore = asyncio.Semaphore(downloader.max_concurrent)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch("asyncio.sleep", _no_sleep):
                return await downloader._download_one(client, post, semaphore)

    return asyncio.run(runner())


class DownloadIntegrityTests(unittest.TestCase):
    def _make_downloader(self, save_dir, **kwargs) -> Downloader:
        return Downloader(
            save_dir=save_dir,
            formatter=FilenameFormatter("{id}.{ext}"),
            skip_existing=kwargs.pop("skip_existing", True),
            **kwargs,
        )

    def test_md5_verified_download_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            dl = self._make_downloader(tmp)
            post = {
                "id": 1,
                "file_url": "https://example.com/a.jpg",
                "file_ext": "jpg",
                "md5": JPEG_MD5,
            }
            self.assertTrue(_run_single_download(dl, post, JPEG_BYTES))
            self.assertEqual((Path(tmp) / "1.jpg").read_bytes(), JPEG_BYTES)
            self.assertEqual(dl.downloaded, 1)

    def test_md5_mismatch_counts_as_failure_and_leaves_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dl = self._make_downloader(tmp)
            post = {
                "id": 2,
                "file_url": "https://example.com/a.jpg",
                "file_ext": "jpg",
                "md5": "0" * 32,
            }
            self.assertFalse(_run_single_download(dl, post, JPEG_BYTES))
            self.assertEqual(dl.failed, 1)
            self.assertFalse((Path(tmp) / "2.jpg").exists())
            leftovers = list(Path(tmp).glob("*.tmp"))
            self.assertEqual(leftovers, [])

    def test_corrupt_existing_file_is_healed_on_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "3.jpg"
            target.write_bytes(b"corrupt old content")
            dl = self._make_downloader(tmp)
            post = {
                "id": 3,
                "file_url": "https://example.com/a.jpg",
                "file_ext": "jpg",
                "md5": JPEG_MD5,
            }
            self.assertTrue(_run_single_download(dl, post, JPEG_BYTES))
            self.assertEqual(target.read_bytes(), JPEG_BYTES)
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_no_skip_redownload_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "4.jpg"
            target.write_bytes(JPEG_BYTES)
            dl = self._make_downloader(tmp, skip_existing=False)
            new_content = b"\xff\xd8\xff\xe1" + b"newer" + b"\xff\xd9"
            post = {
                "id": 4,
                "file_url": "https://example.com/a.jpg",
                "file_ext": "jpg",
                "md5": hashlib.md5(new_content).hexdigest(),
            }
            self.assertTrue(_run_single_download(dl, post, new_content))
            self.assertEqual(target.read_bytes(), new_content)

    def test_invalid_media_without_md5_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            dl = self._make_downloader(tmp)
            post = {"id": 5, "file_url": "https://example.com/a.jpg", "file_ext": "jpg"}
            self.assertFalse(_run_single_download(dl, post, b"<html>error page</html>"))
            self.assertEqual(dl.failed, 1)
            self.assertFalse((Path(tmp) / "5.jpg").exists())

    def test_webm_video_download_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            dl = self._make_downloader(tmp)
            webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 32
            post = {
                "id": 6,
                "file_url": "https://example.com/a.webm",
                "file_ext": "webm",
                "md5": hashlib.md5(webm).hexdigest(),
            }
            self.assertTrue(_run_single_download(dl, post, webm))

    def test_duplicate_targets_do_not_collide(self):
        with tempfile.TemporaryDirectory() as tmp:
            dl = self._make_downloader(tmp)
            posts = [
                {
                    "id": 7,
                    "file_url": "https://example.com/a.jpg",
                    "file_ext": "jpg",
                    "md5": JPEG_MD5,
                }
                for _ in range(2)
            ]

            def handler(request):
                return httpx.Response(200, content=JPEG_BYTES)

            async def runner():
                transport = httpx.MockTransport(handler)
                semaphore = asyncio.Semaphore(dl.max_concurrent)
                async with httpx.AsyncClient(transport=transport) as client:
                    return await asyncio.gather(
                        *(dl._download_one(client, p, semaphore) for p in posts)
                    )

            results = asyncio.run(runner())
            self.assertEqual(sorted(results), [True, True])
            self.assertEqual(dl.failed, 0)
            self.assertEqual(dl.downloaded + dl.skipped, 2)
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])


class PathEscapeTests(unittest.TestCase):
    def test_malicious_extension_cannot_escape_save_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "save"
            root.mkdir()
            formatter = FilenameFormatter("{id}.{ext}")
            filename = formatter.format(
                {"id": 99, "file_ext": r"x\..\..\..\escaped\payload.bin"}
            )
            self.assertNotIn("\\", filename)
            self.assertNotIn("..", filename)
            resolved = (root / filename).resolve()
            self.assertTrue(str(resolved).startswith(str(root.resolve())))

    def test_unsafe_filename_counts_failed_not_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "save"
            root.mkdir()

            class EvilFormatter:
                def format(self, post):
                    return r"..\evil.jpg"

            dl = Downloader(save_dir=root, formatter=EvilFormatter())
            post = {"id": 8, "file_url": "https://example.com/a.jpg"}
            self.assertFalse(_run_single_download(dl, post, JPEG_BYTES))
            self.assertEqual(dl.failed, 1)
            self.assertFalse((Path(tmp) / "evil.jpg").exists())


class SkipValidationTests(unittest.TestCase):
    def test_non_image_leftover_without_md5_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "sample.jpg"
            filepath.write_bytes(b"definitely not an image")
            dl = Downloader(save_dir=tmp, skip_existing=True)
            self.assertFalse(dl._already_exists(filepath, {}))

    def test_valid_image_without_md5_still_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "sample.jpg"
            filepath.write_bytes(JPEG_BYTES)
            dl = Downloader(save_dir=tmp, skip_existing=True)
            self.assertTrue(dl._already_exists(filepath, {}))


class ConcurrencyClampTests(unittest.TestCase):
    def test_zero_and_negative_concurrency_clamped(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(Downloader(save_dir=tmp, max_concurrent=0).max_concurrent, 1)
            self.assertEqual(Downloader(save_dir=tmp, max_concurrent=-4).max_concurrent, 1)

    def test_bad_timeout_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertGreater(Downloader(save_dir=tmp, timeout=0).timeout, 0)
            self.assertGreater(Downloader(save_dir=tmp, timeout=float("nan")).timeout, 0)


class ConfigPersistenceTests(unittest.TestCase):
    def test_save_config_never_writes_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            config = Config(username="demo-user", api_key="DEMO_SECRET")
            config.to_yaml(path)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("demo-user", text)
            self.assertNotIn("DEMO_SECRET", text)
            self.assertNotIn("username", text)
            self.assertNotIn("api_key", text)

    def test_from_yaml_clamps_dangerous_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "concurrent_downloads: 0\ntimeout: -5\nmax_posts: 0\n",
                encoding="utf-8",
            )
            config = Config.from_yaml(path)
            self.assertGreaterEqual(config.concurrent_downloads, 1)
            self.assertGreater(config.timeout, 0)
            self.assertGreaterEqual(config.max_posts, 1)


class CredentialsRecoveryTests(unittest.TestCase):
    def test_corrupt_credentials_file_is_quarantined_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "api_credentials.yaml"
            path.write_text('credentials: {"unclosed: [', encoding="utf-8")
            store = CredentialsStore(path)
            store.load()  # must not raise
            self.assertIsNotNone(store.load_error)
            self.assertFalse(path.exists())
            quarantined = list(Path(tmp).glob("*.corrupt-*"))
            self.assertEqual(len(quarantined), 1)

    def test_non_dict_root_is_quarantined(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "api_credentials.yaml"
            path.write_text("- just\n- a\n- list\n", encoding="utf-8")
            store = CredentialsStore(path)
            store.load()
            self.assertIsNotNone(store.load_error)

    def test_atomic_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "api_credentials.yaml"
            store = CredentialsStore(path)
            store.set_for_preset("Danbooru", "user", "key")
            store.save()
            fresh = CredentialsStore(path)
            fresh.load()
            cred = fresh.get_for_preset("Danbooru")
            self.assertEqual((cred.username, cred.api_key), ("user", "key"))


if __name__ == "__main__":
    unittest.main()
