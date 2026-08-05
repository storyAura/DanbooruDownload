"""Compatibility wrapper for the packaged booru client module."""

from booru_download.core.danbooru_client import *  # noqa: F401,F403
from booru_download.core.danbooru_client import (  # noqa: F401
    _categorize_flat_tags,
    _normalize_post,
)
