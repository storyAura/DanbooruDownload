"""Async image downloader with concurrency control, progress callbacks, and cancel support."""

import asyncio
import hashlib
import random
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import httpx
from tqdm import tqdm

from formatter import DEFAULT_TAG_TEXT_CATEGORIES, FilenameFormatter, TagTextFormatter


class Downloader:
    """Download images from Danbooru posts concurrently.

    Supports both CLI mode (tqdm progress bar) and GUI mode (callback-based progress).
    Features streaming downloads to reduce memory usage and download speed tracking.
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
        on_speed: Optional[Callable] = None,
        cancel_event: Optional[threading.Event] = None,
        save_tag_txt: bool = False,
        tag_txt_categories: Optional[list[str]] = None,
        tag_txt_underscore_to_space: bool = False,
        tag_txt_escape_special_chars: bool = False,
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
            on_speed: Callback(bytes_per_sec) for speed display.
            cancel_event: Threading event to signal download cancellation.
            save_tag_txt: Save a comma-separated same-name .txt tag file.
            tag_txt_categories: Tag sections to include in fixed sidebar order.
            tag_txt_underscore_to_space: Replace underscores with spaces in TXT tags.
            tag_txt_escape_special_chars: Escape prompt-control characters in TXT tags.
        """
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.formatter = formatter or FilenameFormatter()
        self.max_concurrent = max_concurrent
        self.skip_existing = skip_existing
        self.timeout = timeout
        self.on_progress = on_progress
        self.on_log = on_log
        self.on_speed = on_speed
        self.cancel_event = cancel_event
        self.save_tag_txt = save_tag_txt
        self.tag_txt_formatter = TagTextFormatter(
            tag_txt_categories or DEFAULT_TAG_TEXT_CATEGORIES,
            underscore_to_space=tag_txt_underscore_to_space,
            escape_special_chars=tag_txt_escape_special_chars,
        )

        # Stats
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.total = 0

        # Speed tracking
        self._bytes_downloaded = 0
        self._speed_lock = threading.Lock()
        self._last_speed_report = 0.0
        self._speed_window: list[tuple[float, int]] = []  # (timestamp, bytes)

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

    def _track_bytes(self, nbytes: int):
        """Track downloaded bytes for speed calculation."""
        now = time.monotonic()
        with self._speed_lock:
            self._bytes_downloaded += nbytes
            self._speed_window.append((now, nbytes))
            # Keep only last 5 seconds of data
            cutoff = now - 5.0
            self._speed_window = [(t, b) for t, b in self._speed_window if t > cutoff]

            # Report speed at most every 0.5s
            if self.on_speed and now - self._last_speed_report >= 0.5:
                self._last_speed_report = now
                if len(self._speed_window) >= 2:
                    elapsed = self._speed_window[-1][0] - self._speed_window[0][0]
                    total_bytes = sum(b for _, b in self._speed_window)
                    if elapsed > 0:
                        self.on_speed(total_bytes / elapsed)

    def _get_download_url(self, post: dict) -> Optional[str]:
        """Get the best available download URL for a post (prefer original)."""
        return post.get("file_url") or post.get("large_file_url")

    def _write_tag_txt(self, image_path: Path, post: dict) -> None:
        """Write a same-name .txt file for selected Danbooru tag categories."""
        if not self.save_tag_txt:
            return

        content = self.tag_txt_formatter.format(post)
        if not content:
            return

        txt_path = image_path.with_suffix(".txt")
        tmp_path = txt_path.with_suffix(txt_path.suffix + ".tmp")
        try:
            txt_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(content + "\n", encoding="utf-8")
            tmp_path.replace(txt_path)
        except Exception as e:
            self._log(f"  Failed TXT #{post.get('id', '?')}: {e}")
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

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
        """Download a single post's image using streaming to reduce memory."""
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
            self._write_tag_txt(filepath, post)
            self.skipped += 1
            self._log(f"  Skipped #{post.get('id', '?')}: already exists")
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
                    # Use streaming download for large files
                    async with client.stream("GET", url, follow_redirects=True) as resp:
                        resp.raise_for_status()

                        tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
                        tmp_path.parent.mkdir(parents=True, exist_ok=True)

                        with open(tmp_path, "wb") as f:
                            async for chunk in resp.aiter_bytes(chunk_size=65536):
                                if self.cancel_event and self.cancel_event.is_set():
                                    tmp_path.unlink(missing_ok=True)
                                    return False
                                f.write(chunk)
                                self._track_bytes(len(chunk))

                    tmp_path.rename(filepath)
                    self._write_tag_txt(filepath, post)

                    self.downloaded += 1
                    self._log(f"  Downloaded #{post.get('id', '?')}: {filename}")
                    if progress:
                        progress.update(1)
                    self._report_progress()
                    return True

                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    if attempt < max_retries - 1:
                        # Exponential backoff with jitter
                        base_delay = 2 ** attempt
                        jitter = random.uniform(0, base_delay * 0.5)
                        await asyncio.sleep(base_delay + jitter)
                        continue
                    self._log(f"  Failed #{post.get('id', '?')}: {e}")
                    self.failed += 1
                    if progress:
                        progress.update(1)
                    self._report_progress()
                    return False
                except Exception as e:
                    self._log(f"  Failed #{post.get('id', '?')}: {e}")
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
                max_connections=self.max_concurrent + 4,
                max_keepalive_connections=self.max_concurrent + 2,
            ),
        ) as client:
            if use_tqdm:
                with tqdm(
                    total=len(posts),
                    desc="Downloading",
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
        self._bytes_downloaded = 0
        self._speed_window = []
        self._last_speed_report = 0.0

        asyncio.run(self._download_batch_async(posts))

        return {
            "downloaded": self.downloaded,
            "skipped": self.skipped,
            "failed": self.failed,
        }
