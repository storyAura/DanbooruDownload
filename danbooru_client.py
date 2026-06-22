"""Danbooru API client with search, pagination, and rate limiting."""

import time
from typing import Generator, Optional

import httpx


class DanbooruClient:
    """Client for the Danbooru JSON API.

    Works with Danbooru (https://danbooru.donmai.us) and compatible mirror
    sites such as Safebooru, etc.
    """

    POSTS_PER_PAGE = 200  # Danbooru API maximum
    REQUEST_INTERVAL = 0.5  # Minimum seconds between API requests

    def __init__(
        self,
        base_url: str = "https://danbooru.donmai.us",
        username: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = None
        if username and api_key:
            self.auth = (username, api_key)

        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "DanbooruDownload/1.0"},
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

        for attempt in range(max_retries):
            try:
                self._throttle()
                resp = self._client.get(url, params=params, auth=self.auth)

                if resp.status_code == 429:
                    # Rate limited — wait and retry
                    wait = min(2 ** attempt * 2, 30)
                    print(f"  ⏳ Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                return resp.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise RuntimeError("Authentication failed. Check username and API key.") from e
                if e.response.status_code == 403:
                    raise RuntimeError("Access denied. You may need a Gold+ account for this query.") from e
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Request failed: {e}") from e

        return []

    def search(self, tags: str = "", limit: int = 200, page: int | str = 1) -> list[dict]:
        """Search for posts.

        Args:
            tags: Tag search query (supports metatags like rating:g, score:>100, order:score)
            limit: Number of results per page (max 200)
            page: Page number or cursor string like 'b12345'

        Returns:
            List of post dicts from the API
        """
        params = {
            "tags": tags,
            "limit": min(limit, self.POSTS_PER_PAGE),
            "page": page,
        }
        result = self._request("/posts.json", params)
        if isinstance(result, list):
            return result
        return []

    def search_all(
        self,
        tags: str = "",
        max_posts: int = 100,
        on_log: Optional[callable] = None,
    ) -> Generator[dict, None, None]:
        """Search and paginate through all results up to max_posts.

        Uses cursor-based pagination (page=b{id}) for efficient traversal
        that avoids the 1000-page limit.

        Yields:
            Post dicts one at a time.
        """
        fetched = 0
        page: int | str = 1
        per_page = min(max_posts, self.POSTS_PER_PAGE)
        page_num = 0

        while fetched < max_posts:
            remaining = max_posts - fetched
            limit = min(remaining, per_page)
            page_num += 1

            if on_log:
                on_log(f"  📄 Fetching page {page_num}...")

            posts = self.search(tags=tags, limit=limit, page=page)
            if not posts:
                break

            for post in posts:
                # Skip posts without downloadable files
                if not post.get("file_url") and not post.get("large_file_url"):
                    continue
                yield post
                fetched += 1
                if fetched >= max_posts:
                    break

            # Use cursor-based pagination: get posts before the last ID
            last_id = posts[-1].get("id")
            if last_id is None:
                break
            page = f"b{last_id}"

    def get_post(self, post_id: int) -> dict:
        """Get a single post by ID."""
        result = self._request(f"/posts/{post_id}.json")
        return result if isinstance(result, dict) else {}

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
