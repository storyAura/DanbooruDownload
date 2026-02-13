"""Async image downloader with concurrency control, progress callbacks, and cancel support."""

import asyncio
import hashlib
import threading
from pathlib import Path
from typing import Callable, Optional

import httpx
from tqdm import tqdm

from formatter import FilenameFormatter


class Downloader:
    """Download images from Danbooru posts concurrently.

    Supports both CLI mode (tqdm progress bar) and GUI mode (callback-based progress).
    """

    def __init__(
        self,
        save_dir: str | Path = "./downloads",
        formatter: Optional[FilenameFormatter] = None,
        max_concurrent: int = 8,
        skip_existing: bool = True,
        timeout: float = 60.0,
        on_progress: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
        cancel_event: Optional[threading.Event] = None,
    ):
        """
        Args:
            save_dir: Directory to save downloaded images.
            formatter: Filename formatter instance.
            max_concurrent: Maximum concurrent downloads.
            skip_existing: Skip files that already exist (MD5 verified).
            timeout: HTTP request timeout.
            on_progress: Callback(downloaded, skipped, failed, total) for GUI updates.
            on_log: Callback(message) for log messages.
            cancel_event: Threading event to signal download cancellation.
        """
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.formatter = formatter or FilenameFormatter()
        self.max_concurrent = max_concurrent
        self.skip_existing = skip_existing
        self.timeout = timeout
        self.on_progress = on_progress
        self.on_log = on_log
        self.cancel_event = cancel_event

        # Stats
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.total = 0

    def _log(self, msg: str):
        """Send a log message to callback or tqdm."""
        if self.on_log:
            self.on_log(msg)
        else:
            tqdm.write(msg)

    def _report_progress(self):
        """Report progress via callback if available."""
        if self.on_progress:
            self.on_progress(self.downloaded, self.skipped, self.failed, self.total)

    def _get_download_url(self, post: dict) -> Optional[str]:
        """Get the best available download URL for a post (prefer original)."""
        return post.get("file_url") or post.get("large_file_url")

    def _already_exists(self, filepath: Path, post: dict) -> bool:
        """Check if file already exists and matches the expected MD5."""
        if not filepath.exists():
            return False
        if not self.skip_existing:
            return False

        expected_md5 = post.get("md5")
        if expected_md5:
            md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    md5.update(chunk)
            return md5.hexdigest() == expected_md5
        return True

    async def _download_one(
        self,
        client: httpx.AsyncClient,
        post: dict,
        semaphore: asyncio.Semaphore,
        progress: Optional[tqdm] = None,
    ) -> bool:
        """Download a single post's image."""
        # Check cancel
        if self.cancel_event and self.cancel_event.is_set():
            return False

        url = self._get_download_url(post)
        if not url:
            self.failed += 1
            if progress:
                progress.update(1)
            self._report_progress()
            return False

        filename = self.formatter.format(post)
        filepath = self.save_dir / filename

        if self._already_exists(filepath, post):
            self.skipped += 1
            self._log(f"  ⏭ Skipped #{post.get('id', '?')}: already exists")
            if progress:
                progress.update(1)
            self._report_progress()
            return True

        async with semaphore:
            if self.cancel_event and self.cancel_event.is_set():
                return False

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    resp = await client.get(url, follow_redirects=True)
                    resp.raise_for_status()

                    tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
                    tmp_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp_path.write_bytes(resp.content)
                    tmp_path.rename(filepath)

                    self.downloaded += 1
                    self._log(f"  ✅ Downloaded #{post.get('id', '?')}: {filename}")
                    if progress:
                        progress.update(1)
                    self._report_progress()
                    return True

                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    self._log(f"  ❌ Failed #{post.get('id', '?')}: {e}")
                    self.failed += 1
                    if progress:
                        progress.update(1)
                    self._report_progress()
                    return False
                except Exception as e:
                    self._log(f"  ❌ Failed #{post.get('id', '?')}: {e}")
                    self.failed += 1
                    if progress:
                        progress.update(1)
                    self._report_progress()
                    return False

        return False

    async def _download_batch_async(self, posts: list[dict]) -> None:
        """Internal async batch download."""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        use_tqdm = self.on_progress is None  # Use tqdm only in CLI mode

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": "DanbooruDownload/1.0"},
            limits=httpx.Limits(
                max_connections=self.max_concurrent + 2,
                max_keepalive_connections=self.max_concurrent,
            ),
        ) as client:
            if use_tqdm:
                with tqdm(
                    total=len(posts),
                    desc="📥 Downloading",
                    unit="img",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
                ) as progress:
                    tasks = [
                        self._download_one(client, post, semaphore, progress)
                        for post in posts
                    ]
                    await asyncio.gather(*tasks)
            else:
                tasks = [
                    self._download_one(client, post, semaphore, None)
                    for post in posts
                ]
                await asyncio.gather(*tasks)

    def download_batch(self, posts: list[dict]) -> dict:
        """Download a batch of posts synchronously (runs async loop internally).

        Args:
            posts: List of Danbooru post dicts.

        Returns:
            Stats dict with downloaded, skipped, failed counts.
        """
        if not posts:
            return {"downloaded": 0, "skipped": 0, "failed": 0}

        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.total = len(posts)

        asyncio.run(self._download_batch_async(posts))

        return {
            "downloaded": self.downloaded,
            "skipped": self.skipped,
            "failed": self.failed,
        }
