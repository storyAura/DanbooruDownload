"""Filename formatting engine for Danbooru posts."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from booru_download.core.fs_safety import normalize_file_ext


# Characters not allowed in filenames on Windows
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_FILENAME_LEN = 200
TAG_TEXT_CATEGORY_ORDER = ("artist", "copyright", "character", "general", "meta")
DEFAULT_TAG_TEXT_CATEGORIES = ("character", "general")
_TAG_TEXT_ESCAPE_RE = re.compile(r"([\\()\[\]{}])")


def _sanitize(text: str) -> str:
    """Remove characters unsafe for filenames and trim length."""
    text = _UNSAFE_CHARS.sub("_", text)
    # Collapse consecutive underscores
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:_MAX_FILENAME_LEN]


def _extract_tags_by_category(post: dict, category_key: str) -> str:
    """Extract tags string from a Danbooru post for a given category.

    Danbooru API returns tags in fields like 'tag_string_artist',
    'tag_string_character', 'tag_string_copyright', 'tag_string_general'.
    """
    return post.get(f"tag_string_{category_key}", "")


def normalize_tag_text_categories(categories: Iterable[str] | str | None) -> list[str]:
    """Return valid tag categories in the fixed Danbooru sidebar order."""
    if categories is None:
        categories = DEFAULT_TAG_TEXT_CATEGORIES
    elif isinstance(categories, str):
        categories = categories.replace(",", " ").split()

    wanted = {str(category).strip().lower() for category in categories if str(category).strip()}
    return [category for category in TAG_TEXT_CATEGORY_ORDER if category in wanted]


class TagTextFormatter:
    """Format Danbooru tag categories into LoRA-style comma-separated txt tags."""

    def __init__(
        self,
        categories: Iterable[str] | str | None = None,
        underscore_to_space: bool = False,
        escape_special_chars: bool = False,
    ):
        self.categories = normalize_tag_text_categories(categories)
        self.underscore_to_space = underscore_to_space
        self.escape_special_chars = escape_special_chars

    def _format_tag(self, tag: str) -> str:
        if self.underscore_to_space:
            tag = tag.replace("_", " ")
        if self.escape_special_chars:
            tag = _TAG_TEXT_ESCAPE_RE.sub(r"\\\1", tag)
        return tag

    def format(self, post: dict) -> str:
        tags: list[str] = []
        seen: set[str] = set()

        for category in self.categories:
            raw_tags = _extract_tags_by_category(post, category)
            for tag in raw_tags.split():
                if tag and tag not in seen:
                    tags.append(self._format_tag(tag))
                    seen.add(tag)

        return ", ".join(tags)


class FilenameFormatter:
    """Format filenames from Danbooru post metadata.

    Supported placeholders:
        {id}        - Post ID
        {md5}       - File MD5 hash
        {artist}    - Artist tag(s)
        {character} - Character tag(s)
        {copyright} - Copyright/series tag(s)
        {general}   - General tags (first 5, to avoid overly long names)
        {tags}      - All tags (first 10)
        {rating}    - Rating (g/s/q/e)
        {score}     - Post score
        {date}      - Upload date (YYYY-MM-DD)
        {width}     - Image width
        {height}    - Image height
        {ext}       - File extension
    """

    def __init__(self, template: str = "{id}_{artist}_{md5}.{ext}"):
        self.template = template

    def format(self, post: dict) -> str:
        """Generate a sanitized filename from a post dict using the template."""
        # Determine extension from file_url or file_ext
        ext = post.get("file_ext", "")
        if not ext:
            file_url = post.get("file_url", "") or post.get("large_file_url", "")
            if file_url:
                ext = Path(file_url).suffix.lstrip(".")
        # The extension is remote data; force it down to a plain token so it
        # can never smuggle path separators into the final filename.
        ext = normalize_file_ext(ext)

        # Extract date
        created = post.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                date_str = "unknown"
        else:
            date_str = "unknown"

        # All tags (first 10) — also used as filename fallback on flat-tag sites.
        all_tags_raw = post.get("tag_string", "") or ""
        all_tags = [t for t in all_tags_raw.split() if t][:10]
        tags_str = "+".join(all_tags) if all_tags else ""
        tag_fallback = "+".join(all_tags[:2]) if all_tags else "unknown"

        # Build artist string (take first 3 artists max)
        artist_raw = _extract_tags_by_category(post, "artist")
        artists = [a for a in artist_raw.split() if a][:3]
        artist_str = "+".join(artists) if artists else tag_fallback

        # Character
        char_raw = _extract_tags_by_category(post, "character")
        chars = [c for c in char_raw.split() if c][:3]
        char_str = "+".join(chars) if chars else tag_fallback

        # Copyright
        copy_raw = _extract_tags_by_category(post, "copyright")
        copies = [c for c in copy_raw.split() if c][:3]
        copy_str = "+".join(copies) if copies else tag_fallback

        # General tags (first 5)
        gen_raw = _extract_tags_by_category(post, "general")
        gens = [g for g in gen_raw.split() if g][:5]
        gen_str = "+".join(gens) if gens else ""

        # Rating map
        rating_map = {"g": "general", "s": "sensitive", "q": "questionable", "e": "explicit"}
        rating = post.get("rating", "g") or "g"

        values = {
            "id": str(post.get("id", "0")),
            "md5": post.get("md5", "unknown") or "unknown",
            "artist": artist_str,
            "character": char_str,
            "copyright": copy_str,
            "general": gen_str,
            "tags": tags_str,
            "rating": rating,
            "score": str(post.get("score", 0)),
            "date": date_str,
            "width": str(post.get("image_width", 0)),
            "height": str(post.get("image_height", 0)),
            "ext": ext,
        }

        # Format and sanitize
        try:
            # Split extension from the rest so we can sanitize them separately
            if ".{ext}" in self.template:
                name_part = self.template.replace(".{ext}", "")
                name = _sanitize(name_part.format(**values))
                filename = f"{name}.{ext}"
            else:
                filename = _sanitize(self.template.format(**values))
        except KeyError as e:
            # Fallback to safe name
            filename = f"{post.get('id', 'unknown')}_{post.get('md5', 'unknown')}.{ext}"

        return filename
