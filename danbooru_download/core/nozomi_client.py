"""Nozomi.la API helpers for tag search and post normalization."""

from __future__ import annotations

import struct
import time
from typing import Callable, Generator, Optional
from urllib.parse import quote

import httpx

APP_USER_AGENT = "DanbooruDownload/1.3.1"


NOZOMI_ROOT = "https://nozomi.la"
NOZOMI_CDN = "gold-usergeneratedcontent.net"
NOZOMI_INDEX_HOST = "n.nozomi.la"
NOZOMI_API_HOST = f"j.{NOZOMI_CDN}"
NOZOMI_REFERER = f"{NOZOMI_ROOT}/"
NOZOMI_REQUEST_INTERVAL = 0.5
NOZOMI_RANGE_CHUNK = 256


def decode_nozomi_bytes(data: bytes) -> list[int]:
    """Decode a .nozomi binary stream into big-endian post IDs."""
    if not data:
        return []
    if len(data) % 4:
        data = data[: len(data) - (len(data) % 4)]
    count = len(data) // 4
    if count == 0:
        return []
    return list(struct.unpack(f">{count}I", data))


def sanitize_nozomi_tag(tag: str) -> str:
    return quote(tag.strip().replace(" ", "_"), safe="")


def is_nozomi_metatag(token: str) -> bool:
    lowered = token.lower()
    return (
        lowered.startswith("rating:")
        or lowered.startswith("score:")
        or lowered.startswith("order:")
        or lowered.startswith("sort:")
    )


def parse_nozomi_tags(tags_query: str) -> tuple[list[str], list[str], list[str]]:
    """Split a tag query into positive tags, negative tags, and ignored metatags."""
    positive: list[str] = []
    negative: list[str] = []
    metatags: list[str] = []

    for raw in tags_query.split():
        token = raw.strip()
        if not token:
            continue
        if token.startswith("-"):
            tag = token[1:].strip()
            if not tag:
                continue
            if is_nozomi_metatag(tag):
                metatags.append(token)
            else:
                negative.append(tag)
        elif is_nozomi_metatag(token):
            metatags.append(token)
        else:
            positive.append(token)

    return positive, negative, metatags


def post_json_url(post_id: int | str) -> str:
    pid = str(post_id)
    return f"https://{NOZOMI_API_HOST}/post/{pid[-1]}/{pid[-3:-1]}/{pid}.json"


def build_media_url(dataid: str, media_type: str, is_video: bool = False) -> tuple[str, str]:
    ext = (media_type or "webp").lower()
    if is_video:
        subdomain = "v"
    elif ext == "gif":
        subdomain = "g"
    else:
        # Nozomi's CDN serves static images only as .webp; the original type
        # reported in post metadata (jpg/png/avif) 404s on the media host.
        subdomain = "w"
        ext = "webp"
    url = f"https://{subdomain}.{NOZOMI_CDN}/{dataid[-1]}/{dataid[-3:-1]}/{dataid}.{ext}"
    return url, ext


def _list_field(value) -> str:
    if isinstance(value, list):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def normalize_nozomi_post(raw: dict, post_id: int | str) -> dict:
    """Normalize a Nozomi post JSON payload into the app's Danbooru-like shape."""
    images = raw.get("imageurls") or []
    if not images:
        return {}

    image = images[0]
    dataid = str(image.get("dataid") or "")
    if not dataid:
        return {}

    media_type = str(image.get("type") or "webp")
    is_video = bool(image.get("is_video"))
    file_url, file_ext = build_media_url(dataid, media_type, is_video)

    post = {
        "id": int(post_id),
        "file_url": file_url,
        "large_file_url": file_url,
        "file_ext": file_ext,
        "md5": dataid,
        "tag_string_artist": _list_field(raw.get("artist")),
        "tag_string_copyright": _list_field(raw.get("copyright")),
        "tag_string_character": _list_field(raw.get("character")),
        "tag_string_general": _list_field(raw.get("general")),
        "tag_string_meta": "",
        "created_at": raw.get("date", ""),
        "rating": "e",
        "score": 0,
        "width": raw.get("width", 0),
        "height": raw.get("height", 0),
    }
    return post


class NozomiClient:
    """HTTP client for Nozomi.la tag indexes and post metadata."""

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": APP_USER_AGENT,
                "Referer": NOZOMI_REFERER,
                "Origin": NOZOMI_ROOT,
            },
            follow_redirects=True,
        )
        self._last_request_time = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < NOZOMI_REQUEST_INTERVAL:
            time.sleep(NOZOMI_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    def _get(self, url: str, headers: dict | None = None) -> httpx.Response:
        self._throttle()
        response = self._client.get(url, headers=headers or {})
        response.raise_for_status()
        return response

    def _nozomi_index_url(self, tag: str) -> str:
        return f"https://{NOZOMI_INDEX_HOST}/nozomi/{sanitize_nozomi_tag(tag)}.nozomi"

    def fetch_tag_post_ids(self, tag: str) -> set[int]:
        response = self._get(self._nozomi_index_url(tag))
        return set(decode_nozomi_bytes(response.content))

    def iter_tag_post_ids(self, tag: str) -> Generator[int, None, None]:
        url = self._nozomi_index_url(tag)
        offset = 0
        while True:
            headers = {"Range": f"bytes={offset}-{offset + NOZOMI_RANGE_CHUNK - 1}"}
            self._throttle()
            response = self._client.get(url, headers=headers)
            if response.status_code == 416:
                break
            if response.status_code not in {200, 206}:
                response.raise_for_status()
            chunk = response.content
            if not chunk:
                break
            for post_id in decode_nozomi_bytes(chunk):
                yield post_id
            if len(chunk) < NOZOMI_RANGE_CHUNK:
                break
            offset += NOZOMI_RANGE_CHUNK

    def resolve_post_ids(
        self,
        tags_query: str,
        max_posts: int,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> list[int]:
        positive, negative, metatags = parse_nozomi_tags(tags_query)
        if metatags and on_log:
            on_log(
                "  Nozomi.la ignores unsupported metatags: "
                + ", ".join(metatags)
            )
        if not positive:
            if on_log:
                on_log("  Nozomi.la search requires at least one tag.")
            return []

        if len(positive) == 1 and not negative:
            ids: list[int] = []
            for post_id in self.iter_tag_post_ids(positive[0]):
                ids.append(post_id)
                if len(ids) >= max_posts:
                    break
            return ids

        result = self.fetch_tag_post_ids(positive[0])
        for tag in positive[1:]:
            result &= self.fetch_tag_post_ids(tag)
        for tag in negative:
            result -= self.fetch_tag_post_ids(tag)
        return sorted(result, reverse=True)[:max_posts]

    def fetch_post(self, post_id: int | str) -> dict:
        response = self._get(post_json_url(post_id))
        return normalize_nozomi_post(response.json(), post_id)

    def search_all(
        self,
        tags: str = "",
        max_posts: int = 100,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> Generator[dict, None, None]:
        post_ids = self.resolve_post_ids(tags, max_posts, on_log=on_log)
        if on_log:
            on_log(f"  Resolved {len(post_ids)} Nozomi post IDs")

        for index, post_id in enumerate(post_ids, start=1):
            if on_log and index % 25 == 1:
                on_log(f"  Fetching post metadata {index}/{len(post_ids)}...")
            try:
                post = self.fetch_post(post_id)
            except Exception as exc:
                if on_log:
                    on_log(f"  Skipped post {post_id}: {exc}")
                continue
            if post.get("file_url"):
                yield post
