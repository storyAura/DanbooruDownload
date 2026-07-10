"""Booru API client with search, pagination, and rate limiting."""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Generator, Optional
from urllib.parse import unquote, urlparse

import httpx


APP_USER_AGENT = "DanbooruDownload/1.3.1"
PROFILE_DANBOORU = "danbooru"
PROFILE_MOEBOORU = "moebooru"
PROFILE_GELBOORU = "gelbooru"
PROFILE_NOZOMI = "nozomi"


def _detect_profile(base_url: str) -> str:
    """Return the API profile for a supported booru host."""
    host = urlparse(base_url).netloc.lower()
    if "nozomi.la" in host:
        return PROFILE_NOZOMI
    if "gelbooru.com" in host:
        return PROFILE_GELBOORU
    if "yande.re" in host or "konachan.com" in host:
        return PROFILE_MOEBOORU
    return PROFILE_DANBOORU


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_tags(raw_tags) -> str:
    if isinstance(raw_tags, list):
        return " ".join(str(tag).strip() for tag in raw_tags if str(tag).strip())
    return str(raw_tags or "").strip()


def _file_ext_from_url(url: str) -> str:
    path = unquote(urlparse(url or "").path)
    return Path(path).suffix.lstrip(".").lower()


def _normalize_rating(value) -> str:
    rating = str(value or "").strip().lower()
    rating_map = {
        "g": "g",
        "general": "g",
        "safe": "g",
        "s": "s",
        "sensitive": "s",
        "q": "q",
        "questionable": "q",
        "e": "e",
        "explicit": "e",
    }
    return rating_map.get(rating, rating[:1] or "g")


def _normalize_created_at(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    return value or ""


def _absolute_url(url: str, base_url: str = "") -> str:
    """Normalize protocol-relative and site-relative media URLs."""
    url = str(url or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/") and base_url:
        return f"{base_url.rstrip('/')}{url}"
    return url


def _gelbooru_directory(post: dict) -> str:
    directory = str(post.get("directory") or "").strip()
    if directory:
        return directory
    md5 = str(post.get("md5") or post.get("hash") or "").strip()
    if len(md5) >= 4:
        return f"{md5[:2]}/{md5[2:4]}"
    return ""


def _resolve_media_url(post: dict, profile: str, base_url: str) -> str:
    """Resolve the best absolute download URL for a booru post."""
    for key in ("file_url", "jpeg_url", "sample_url", "large_file_url"):
        url = _absolute_url(post.get(key, ""), base_url)
        if url:
            return url

    if profile == PROFILE_GELBOORU:
        directory = _gelbooru_directory(post)
        image = str(post.get("image") or "").strip()
        if directory and image:
            return f"https://img3.gelbooru.com/images/{directory}/{image}"

    return ""


def _extract_result_posts(result) -> list[dict]:
    """Extract a post list from common booru JSON response shapes."""
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if not isinstance(result, dict):
        return []

    posts = result.get("post", [])
    if isinstance(posts, list):
        return [item for item in posts if isinstance(item, dict)]
    if isinstance(posts, dict):
        return [posts]
    return []


def _normalize_post(
    post: dict,
    profile: str = PROFILE_DANBOORU,
    base_url: str = "",
) -> dict:
    """Normalize supported booru post fields to the app's Danbooru-like shape."""
    normalized = dict(post)
    raw_tags = normalized.get("tag_string") or normalized.get("tags") or ""
    tag_string = _coerce_tags(raw_tags)

    file_url = _resolve_media_url(normalized, profile, base_url)
    large_file_url = _absolute_url(
        normalized.get("large_file_url") or normalized.get("jpeg_url") or "",
        base_url,
    ) or file_url
    file_ext = normalized.get("file_ext") or _file_ext_from_url(file_url) or _file_ext_from_url(large_file_url)
    width = _coerce_int(normalized.get("image_width", normalized.get("width")), 0)
    height = _coerce_int(normalized.get("image_height", normalized.get("height")), 0)

    normalized.update(
        {
            "file_url": file_url,
            "large_file_url": large_file_url,
            "file_ext": str(file_ext or "jpg").lower(),
            "md5": normalized.get("md5", "") or "",
            "rating": _normalize_rating(normalized.get("rating")),
            "score": _coerce_int(normalized.get("score"), 0),
            "width": width,
            "height": height,
            "image_width": width,
            "image_height": height,
            "tag_string": tag_string,
            "tag_string_artist": normalized.get("tag_string_artist", "") or "",
            "tag_string_copyright": normalized.get("tag_string_copyright", "") or "",
            "tag_string_character": normalized.get("tag_string_character", "") or "",
            "tag_string_general": normalized.get("tag_string_general", "") or "",
            "tag_string_meta": normalized.get("tag_string_meta", "") or "",
            "created_at": _normalize_created_at(normalized.get("created_at")),
        }
    )
    return normalized


class DanbooruClient:
    """Client for Danbooru, Moebooru, and Gelbooru JSON APIs.

    The public interface stays Danbooru-like while site-specific endpoint and
    response differences are handled internally.
    """

    POSTS_PER_PAGE = 200
    MOEBOORU_POSTS_PER_PAGE = 100
    GELBOORU_POSTS_PER_PAGE = 100
    REQUEST_INTERVAL = 0.5

    def __init__(
        self,
        base_url: str = "https://danbooru.donmai.us",
        username: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.profile = _detect_profile(self.base_url)
        self.timeout = timeout
        self.username = username
        self.api_key = api_key
        self.auth = None
        if self.profile != PROFILE_GELBOORU and username and api_key:
            self.auth = (username, api_key)

        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": APP_USER_AGENT},
            follow_redirects=True,
        )
        self._last_request_time: float = 0.0

    def _throttle(self):
        """Enforce minimum interval between requests to avoid 429."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.REQUEST_INTERVAL:
            time.sleep(self.REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    def _request(self, endpoint: str, params: dict | None = None) -> list | dict:
        """Make a GET request to the API with retry logic and throttling."""
        url = f"{self.base_url}{endpoint}"
        max_retries = 3
        request_params = dict(params or {})
        if self.profile == PROFILE_GELBOORU:
            if self.username:
                request_params["user_id"] = self.username
            if self.api_key:
                request_params["api_key"] = self.api_key

        for attempt in range(max_retries):
            try:
                self._throttle()
                resp = self._client.get(url, params=request_params, auth=self.auth)

                if resp.status_code == 429:
                    wait = min(2**attempt * 2, 30)
                    print(f"  Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError as e:
                    text = resp.text.lower()
                    if "cloudflare" in text or "just a moment" in text:
                        raise RuntimeError(
                            "The site returned a Cloudflare challenge instead of JSON. "
                            "Please try again later or use another supported mirror."
                        ) from e
                    raise RuntimeError("The site returned an invalid JSON response.") from e

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status == 401:
                    if self.profile == PROFILE_GELBOORU:
                        raise RuntimeError(
                            "Gelbooru authentication failed. Open Settings -> API Credentials, "
                            "enter your numeric User ID and API Key from the Gelbooru account Options page."
                        ) from e
                    raise RuntimeError("Authentication failed. Check username and API key.") from e
                if status == 403:
                    raise RuntimeError(
                        "Access denied by the site. The request may require authentication, "
                        "or the site may be blocking API clients with a Cloudflare challenge."
                    ) from e
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"Request failed: {e}") from e

        return []

    def _max_page_limit(self) -> int:
        if self.profile == PROFILE_GELBOORU:
            return self.GELBOORU_POSTS_PER_PAGE
        if self.profile == PROFILE_MOEBOORU:
            return self.MOEBOORU_POSTS_PER_PAGE
        return self.POSTS_PER_PAGE

    def search(self, tags: str = "", limit: int = 200, page: int | str = 1) -> list[dict]:
        """Search for posts.

        Args:
            tags: Tag search query.
            limit: Number of results per page.
            page: Page number, Danbooru cursor string like 'b12345', or Gelbooru pid.

        Returns:
            List of normalized post dicts from the API.
        """
        if self.profile == PROFILE_NOZOMI:
            from danbooru_download.core.nozomi_client import NozomiClient

            with NozomiClient(timeout=self.timeout) as nozomi:
                return [
                    _normalize_post(post, self.profile, self.base_url)
                    for post in nozomi.search_all(tags=tags, max_posts=limit, on_log=None)
                ]

        if self.profile == PROFILE_GELBOORU:
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": "1",
                "tags": tags,
                "limit": min(limit, self._max_page_limit()),
                "pid": _coerce_int(page, 0),
            }
            result = self._request("/index.php", params)
        elif self.profile == PROFILE_MOEBOORU:
            params = {
                "tags": tags,
                "limit": min(limit, self._max_page_limit()),
                "page": page,
            }
            result = self._request("/post.json", params)
        else:
            params = {
                "tags": tags,
                "limit": min(limit, self._max_page_limit()),
                "page": page,
            }
            result = self._request("/posts.json", params)

        return [
            _normalize_post(post, self.profile, self.base_url)
            for post in _extract_result_posts(result)
        ]

    def search_all(
        self,
        tags: str = "",
        max_posts: int = 100,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> Generator[dict, None, None]:
        """Search and paginate through all results up to max_posts."""
        if self.profile == PROFILE_NOZOMI:
            from danbooru_download.core.nozomi_client import NozomiClient

            with NozomiClient(timeout=self.timeout) as nozomi:
                for post in nozomi.search_all(tags=tags, max_posts=max_posts, on_log=on_log):
                    yield _normalize_post(post, self.profile, self.base_url)
            return

        fetched = 0
        page: int | str = 0 if self.profile == PROFILE_GELBOORU else 1
        per_page = min(max_posts, self._max_page_limit())
        page_num = 0

        while fetched < max_posts:
            remaining = max_posts - fetched
            limit = min(remaining, per_page)
            page_num += 1

            if on_log:
                on_log(f"  Fetching page {page_num}...")

            posts = self.search(tags=tags, limit=limit, page=page)
            if not posts:
                break

            for post in posts:
                if not post.get("file_url") and not post.get("large_file_url"):
                    continue
                yield post
                fetched += 1
                if fetched >= max_posts:
                    break

            if self.profile == PROFILE_DANBOORU:
                last_id = posts[-1].get("id")
                if last_id is None:
                    break
                page = f"b{last_id}"
            else:
                page = _coerce_int(page, 0) + 1

    def get_post(self, post_id: int) -> dict:
        """Get a single post by ID."""
        if self.profile == PROFILE_NOZOMI:
            from danbooru_download.core.nozomi_client import NozomiClient

            with NozomiClient(timeout=self.timeout) as nozomi:
                post = nozomi.fetch_post(post_id)
                return _normalize_post(post, self.profile, self.base_url) if post else {}

        if self.profile == PROFILE_GELBOORU:
            result = self._request(
                "/index.php",
                {"page": "dapi", "s": "post", "q": "index", "json": "1", "id": post_id},
            )
            posts = _extract_result_posts(result)
            return _normalize_post(posts[0], self.profile, self.base_url) if posts else {}
        if self.profile == PROFILE_MOEBOORU:
            result = self._request("/post/show.json", {"id": post_id})
        else:
            result = self._request(f"/posts/{post_id}.json")
        return (
            _normalize_post(result, self.profile, self.base_url)
            if isinstance(result, dict)
            else {}
        )

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
