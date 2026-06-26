"""Configuration management for DanbooruDownload."""

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

import yaml

from danbooru_download.core.formatter import (
    DEFAULT_TAG_TEXT_CATEGORIES,
    normalize_tag_text_categories,
)
from danbooru_download.core.image_conversion import (
    normalize_background_color,
    normalize_background_mode,
    normalize_convert_format,
    normalize_effort,
    normalize_quality,
)


def _as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass
class QueueTaskConfig:
    """Serializable queue task settings."""

    tags: str = ""
    folder_name: str = ""
    max_posts: int = 100

    @classmethod
    def from_dict(cls, data: dict) -> "QueueTaskConfig":
        """Build a queue task config from arbitrary YAML data."""
        if not isinstance(data, dict):
            return cls()

        try:
            max_posts = int(data.get("max_posts", 100) or 100)
        except (TypeError, ValueError):
            max_posts = 100

        return cls(
            tags=str(data.get("tags", "") or ""),
            folder_name=str(data.get("folder_name", "") or ""),
            max_posts=max_posts,
        )


@dataclass
class Config:
    """Configuration for the Danbooru downloader."""

    # Site settings
    base_url: str = "https://danbooru.donmai.us"
    username: Optional[str] = None
    api_key: Optional[str] = None

    # Search settings
    tags: str = ""
    blocked_tags: str = ""              # Space-separated tags to exclude
    rating: Optional[str] = None       # g(eneral), s(ensitive), q(uestionable), e(xplicit)
    min_score: Optional[int] = None

    # Download settings
    save_dir: str = "./Download"
    filename_format: str = "{artist}_{id}.{ext}"
    max_posts: int = 100
    concurrent_downloads: int = 8
    skip_existing: bool = True
    timeout: float = 30.0
    queue_tasks: list[QueueTaskConfig] = field(default_factory=list)
    save_tag_txt: bool = False
    tag_txt_categories: list[str] = field(
        default_factory=lambda: list(DEFAULT_TAG_TEXT_CATEGORIES)
    )
    tag_txt_underscore_to_space: bool = True
    tag_txt_escape_special_chars: bool = True
    auto_convert_images: bool = False
    auto_convert_format: str = "jpg"
    auto_convert_quality: int = 95
    auto_convert_lossless: bool = False
    auto_convert_effort: int = 6
    auto_convert_background_mode: str = "color"
    auto_convert_background_color: str = "#ff4fd8"

    def build_tags_query(self) -> str:
        """Build the final tags query string including rating, score, and blocked tags."""
        parts = []
        if self.tags:
            parts.append(self.tags)
        if self.blocked_tags:
            for tag in self.blocked_tags.split():
                tag = tag.strip()
                if tag and not tag.startswith("-"):
                    parts.append(f"-{tag}")
                elif tag:
                    parts.append(tag)
        if self.rating:
            parts.append(f"rating:{self.rating}")
        if self.min_score is not None:
            parts.append(f"score:>={self.min_score}")
        return " ".join(parts)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Load config from a YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        queue_data = data.get("queue_tasks", data.get("queue_items", []))
        if isinstance(queue_data, list):
            data["queue_tasks"] = [QueueTaskConfig.from_dict(item) for item in queue_data]
        else:
            data["queue_tasks"] = []
        data["tag_txt_categories"] = normalize_tag_text_categories(
            data.get("tag_txt_categories", DEFAULT_TAG_TEXT_CATEGORIES)
        )
        data["save_tag_txt"] = _as_bool(data.get("save_tag_txt"), default=False)
        data["tag_txt_underscore_to_space"] = _as_bool(
            data.get("tag_txt_underscore_to_space"), default=True
        )
        data["tag_txt_escape_special_chars"] = _as_bool(
            data.get("tag_txt_escape_special_chars"), default=True
        )
        data["auto_convert_images"] = _as_bool(
            data.get("auto_convert_images"), default=False
        )
        data["auto_convert_format"] = normalize_convert_format(
            data.get("auto_convert_format")
        )
        data["auto_convert_quality"] = normalize_quality(
            data.get("auto_convert_quality"), default=95
        )
        data["auto_convert_lossless"] = _as_bool(
            data.get("auto_convert_lossless"), default=False
        )
        data["auto_convert_effort"] = normalize_effort(
            data.get("auto_convert_effort"), default=6
        )
        data["auto_convert_background_mode"] = normalize_background_mode(
            data.get("auto_convert_background_mode")
        )
        data["auto_convert_background_color"] = normalize_background_color(
            data.get("auto_convert_background_color")
        )
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_yaml(self, path: str | Path) -> None:
        """Save current config to a YAML file."""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(asdict(self), f, default_flow_style=False, allow_unicode=True)
