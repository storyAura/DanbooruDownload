"""Configuration management for DanbooruDownload."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


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
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_yaml(self, path: str | Path) -> None:
        """Save current config to a YAML file."""
        from dataclasses import asdict
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(asdict(self), f, default_flow_style=False, allow_unicode=True)
