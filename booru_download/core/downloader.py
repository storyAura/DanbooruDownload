"""Async image downloader with concurrency control, progress callbacks, and cancel support."""

import asyncio
import hashlib
import os
import random
import re
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import httpx
from tqdm import tqdm

from booru_download.core.formatter import (
    DEFAULT_TAG_TEXT_CATEGORIES,
    FilenameFormatter,
    TagTextFormatter,
)
from booru_download.core.fs_safety import (
    clamp_concurrency,
    normalize_timeout,
    safe_join,
    unique_tmp_path,
)
from booru_download.core.image_conversion import (
    ImageConversionConfig,
    ImageConverter,
    normalize_convert_format,
)


APP_USER_AGENT = "BooruDownload/1.4.0"
IMAGE_MAGIC_PREFIXES = (
    b"\xff\xd8\xff",
    b"\x89PNG\r\n\x1a\n",
    b"GIF87a",
    b"GIF89a",
    b"RIFF",
    b"\x00\x00\x00\x18ftyp",
    b"\x00\x00\x00\x20ftyp",
)
# Container formats that are valid downloads but not still images
MEDIA_MAGIC_PREFIXES = (
    b"\x1a\x45\xdf\xa3",  # EBML: webm / mkv
    b"PK\x03\x04",        # zip (ugoira)
    b"RIFF",
)
# Extensions we insist on verifying with magic bytes
STRICT_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
_MD5_HEX_RE = re.compile(r"[0-9a-f]{32}")


class _RetryableDownloadError(RuntimeError):
    """Download produced invalid data; safe to retry."""


class _DownloadCancelled(Exception):
    """Cooperative cancellation; not a failure."""


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
        auto_convert_images: bool = False,
        auto_convert_format: str = "jpg",
        auto_convert_quality: int = 95,
        auto_convert_lossless: bool = False,
        auto_convert_effort: int = 6,
        auto_convert_background_mode: str = "color",
        auto_convert_background_color: str = "#ff4fd8",
        auto_convert_keep_original: bool = True,
        referer_base: str = "",
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
            auto_convert_images: Convert downloaded static images to JPG/WebP.
            auto_convert_format: Target image format, either jpg or webp.
            auto_convert_quality: Target quality from 1 to 100.
            auto_convert_lossless: Use WebP lossless mode.
            auto_convert_effort: Compression effort from 0 to 6.
            auto_convert_background_mode: WebP transparency background mode.
            auto_convert_background_color: WebP fixed background color as #RRGGBB.
            auto_convert_keep_original: Keep the original image after conversion.
            referer_base: Site base URL used as Referer when downloading media files.
        """
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.referer_base = referer_base.rstrip("/") if referer_base else ""
        self.formatter = formatter or FilenameFormatter()
        # Semaphore(0) waits forever and negative values raise; clamp defensively.
        self.max_concurrent = clamp_concurrency(max_concurrent)
        self.skip_existing = skip_existing
        self.timeout = normalize_timeout(timeout, default=60.0)
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
        self.auto_convert_images = auto_convert_images
        self.auto_convert_keep_original = auto_convert_keep_original
        self.conversion_config = ImageConversionConfig(
            format=auto_convert_format,
            quality=auto_convert_quality,
            lossless=auto_convert_lossless,
            effort=auto_convert_effort,
            background_mode=auto_convert_background_mode,
            background_color=auto_convert_background_color,
        )
        self.auto_convert_format = self.conversion_config.format
        self.image_converter = ImageConverter(self.conversion_config)

        # Stats
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.total = 0

        # Serialize tasks that resolve to the same target file (Windows is
        # case-insensitive, so key on the casefolded resolved path).
        self._path_locks: dict[str, asyncio.Lock] = {}

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

    def _normalize_convert_format(self, value: str) -> str:
        return normalize_convert_format(value)

    def _converted_path(self, image_path: Path) -> Path:
        """Return the converted image path in the source folder's sibling output folder."""
        return self.image_converter.converted_path(image_path)

    def _convert_image(self, image_path: Path) -> Path:
        """Convert a downloaded static image to the configured target format."""
        return self.image_converter.convert(image_path)

    def _finalize_converted(self, filepath: Path) -> Path:
        """Convert a downloaded image and optionally remove the original file."""
        final_path = self._convert_image(filepath)
        if not self.auto_convert_keep_original:
            filepath.unlink(missing_ok=True)
            self._log(f"  Removed original: {filepath.name}")
        return final_path

    def _write_tag_txt(self, image_path: Path, post: dict) -> None:
        """Write a same-name .txt file for selected Danbooru tag categories."""
        if not self.save_tag_txt:
            return

        content = self.tag_txt_formatter.format(post)
        if not content:
            return

        txt_path = image_path.with_suffix(".txt")
        tmp_path = unique_tmp_path(txt_path)
        try:
            txt_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(content + "\n", encoding="utf-8")
            os.replace(tmp_path, txt_path)
        except Exception as e:
            self._log(f"  Failed TXT #{post.get('id', '?')}: {e}")
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _looks_like_image(self, filepath: Path) -> bool:
        """Return True when the file header looks like a supported image."""
        try:
            with open(filepath, "rb") as f:
                header = f.read(16)
        except OSError:
            return False
        if not header:
            return False
        return any(header.startswith(prefix) for prefix in IMAGE_MAGIC_PREFIXES) or (
            b"ftyp" in header[:16]
        )

    def _valid_media_file(self, filepath: Path, ext: Optional[str] = None) -> bool:
        """Extension-aware structural check for a downloaded media file."""
        try:
            if filepath.stat().st_size == 0:
                return False
            with open(filepath, "rb") as f:
                header = f.read(16)
        except OSError:
            return False
        if not header:
            return False

        if ext is None:
            ext = filepath.suffix.lstrip(".").lower()
        if ext in STRICT_IMAGE_EXTENSIONS:
            return self._looks_like_image(filepath)
        # Videos / archives: accept known container magics or any non-empty
        # payload for extensions we do not know how to validate.
        return (
            any(header.startswith(prefix) for prefix in MEDIA_MAGIC_PREFIXES)
            or b"ftyp" in header[:16]
            or self._looks_like_image(filepath)
            or ext not in {"mp4", "webm", "zip", "mkv"}
        )

    @staticmethod
    def _expected_md5(post: dict) -> Optional[str]:
        """Return the post's MD5 when it looks like a real 32-char hex digest."""
        raw = str(post.get("md5") or "").strip().lower()
        return raw if _MD5_HEX_RE.fullmatch(raw) else None

    @staticmethod
    def _file_md5(filepath: Path) -> str:
        md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def _already_exists(self, filepath: Path, post: dict) -> bool:
        """Check if file already exists and passes integrity checks."""
        if not self.skip_existing:
            return False
        if not filepath.is_file():
            return False
        if filepath.stat().st_size == 0:
            return False

        expected_md5 = self._expected_md5(post)
        if expected_md5:
            return self._file_md5(filepath) == expected_md5
        # Without an MD5 we at least require a structurally plausible file so
        # corrupt leftovers do not get skipped forever.
        return self._valid_media_file(filepath)

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
        try:
            # Refuse any formatted name that would land outside the save root.
            filepath = safe_join(self.save_dir, filename)
        except ValueError as e:
            self._log(f"  Failed #{post.get('id', '?')}: unsafe filename ({e})")
            self.failed += 1
            if progress:
                progress.update(1)
            self._report_progress()
            return False
        final_path = self._converted_path(filepath) if self.auto_convert_images else filepath

        lock = self._path_locks.setdefault(str(filepath).casefold(), asyncio.Lock())
        async with lock:
            return await self._download_one_locked(
                client, post, semaphore, progress, filepath, final_path
            )

    async def _download_one_locked(
        self,
        client: httpx.AsyncClient,
        post: dict,
        semaphore: asyncio.Semaphore,
        progress: Optional[tqdm],
        filepath: Path,
        final_path: Path,
    ) -> bool:
        filename = filepath.name
        url = self._get_download_url(post)

        if (
            self.auto_convert_images
            and self.skip_existing
            and final_path.is_file()
            and final_path.stat().st_size > 0
        ):
            self._write_tag_txt(final_path, post)
            self.skipped += 1
            self._log(f"  Skipped #{post.get('id', '?')}: converted file already exists")
            if progress:
                progress.update(1)
            self._report_progress()
            return True

        if self.auto_convert_images and not self.auto_convert_keep_original:
            if self._already_exists(filepath, post) and self.skip_existing:
                if not final_path.exists():
                    self._finalize_converted(filepath)
                else:
                    filepath.unlink(missing_ok=True)
                self._write_tag_txt(final_path, post)
                self.skipped += 1
                self._log(f"  Skipped #{post.get('id', '?')}: already exists")
                if progress:
                    progress.update(1)
                self._report_progress()
                return True
        elif self._already_exists(filepath, post):
            if self.auto_convert_images and not final_path.exists():
                final_path = self._finalize_converted(filepath)
            self._write_tag_txt(final_path, post)
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
                    await self._stream_to_file(client, url, filepath, post)

                    if self.auto_convert_images:
                        final_path = self._finalize_converted(filepath)
                    self._write_tag_txt(final_path, post)

                    self.downloaded += 1
                    if self.auto_convert_images:
                        self._log(
                            f"  Downloaded #{post.get('id', '?')}: {filename} -> {final_path.name}"
                        )
                    else:
                        self._log(f"  Downloaded #{post.get('id', '?')}: {filename}")
                    if progress:
                        progress.update(1)
                    self._report_progress()
                    return True

                except _DownloadCancelled:
                    # Cooperative cancel is not a failure.
                    return False
                except (
                    httpx.HTTPStatusError,
                    httpx.RequestError,
                    _RetryableDownloadError,
                ) as e:
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

    async def _stream_to_file(
        self,
        client: httpx.AsyncClient,
        url: str,
        filepath: Path,
        post: dict,
    ) -> None:
        """Stream *url* into a unique temp file, verify it, atomically replace.

        Raises _DownloadCancelled on cancel, _RetryableDownloadError on
        invalid data. The temp file is always removed on any failure and the
        file handle is closed before any unlink (Windows requirement).
        """
        tmp_path = unique_tmp_path(filepath)
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        md5 = hashlib.md5()
        bytes_written = 0
        cancelled = False

        try:
            async with client.stream("GET", url, follow_redirects=True) as resp:
                resp.raise_for_status()
                content_length = resp.headers.get("Content-Length")

                with open(tmp_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        if self.cancel_event and self.cancel_event.is_set():
                            cancelled = True
                            break
                        f.write(chunk)
                        md5.update(chunk)
                        bytes_written += len(chunk)
                        self._track_bytes(len(chunk))
                    if not cancelled:
                        f.flush()
                        os.fsync(f.fileno())

            if cancelled:
                raise _DownloadCancelled()

            if bytes_written == 0:
                raise _RetryableDownloadError("Downloaded file is empty")

            if content_length is not None:
                try:
                    expected_len = int(content_length)
                except ValueError:
                    expected_len = None
                if expected_len is not None and expected_len != bytes_written:
                    raise _RetryableDownloadError(
                        f"Truncated download: got {bytes_written} of {expected_len} bytes"
                    )

            expected_md5 = self._expected_md5(post)
            if expected_md5 and md5.hexdigest() != expected_md5:
                raise _RetryableDownloadError(
                    f"MD5 mismatch: expected {expected_md5}, got {md5.hexdigest()}"
                )

            if not expected_md5 and not self._valid_media_file(
                tmp_path, ext=filepath.suffix.lstrip(".").lower()
            ):
                raise _RetryableDownloadError("Downloaded file is not valid media")

            # os.replace overwrites existing targets on Windows too, so a
            # corrupt old file or --no-skip re-download can actually heal.
            os.replace(tmp_path, filepath)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    async def _download_batch_async(self, posts: list[dict]) -> None:
        """Internal async batch download."""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        use_tqdm = self.on_progress is None  # Use tqdm only in CLI mode

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "User-Agent": APP_USER_AGENT,
                **({"Referer": f"{self.referer_base}/"} if self.referer_base else {}),
            },
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
        # asyncio primitives bind to one event loop; never reuse across runs.
        self._path_locks = {}

        asyncio.run(self._download_batch_async(posts))

        return {
            "downloaded": self.downloaded,
            "skipped": self.skipped,
            "failed": self.failed,
        }
