"""Image conversion helpers for downloaded static images."""

from dataclasses import dataclass
from pathlib import Path
import random
import re

from PIL import Image

DEFAULT_BACKGROUND_COLOR = "#ff4fd8"
VIVID_BACKGROUND_COLORS = (
    (255, 79, 216),
    (0, 194, 255),
    (45, 212, 191),
    (255, 204, 0),
    (255, 93, 93),
    (124, 58, 237),
)


def normalize_convert_format(value) -> str:
    fmt = str(value or "jpg").strip().lower()
    if fmt == "jpeg":
        fmt = "jpg"
    return fmt if fmt in {"jpg", "webp"} else "jpg"


def normalize_quality(value, default: int = 95) -> int:
    try:
        quality = int(value)
    except (TypeError, ValueError):
        return default
    return quality if 1 <= quality <= 100 else default


def normalize_effort(value, default: int = 6) -> int:
    try:
        effort = int(value)
    except (TypeError, ValueError):
        return default
    return effort if 0 <= effort <= 6 else default


def normalize_background_mode(value) -> str:
    mode = str(value or "color").strip().lower()
    return mode if mode in {"white", "color", "random"} else "color"


def normalize_background_color(value) -> str:
    color = str(value or DEFAULT_BACKGROUND_COLOR).strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", color):
        return color
    return DEFAULT_BACKGROUND_COLOR


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    color = normalize_background_color(value)
    return (
        int(color[1:3], 16),
        int(color[3:5], 16),
        int(color[5:7], 16),
    )


@dataclass(frozen=True)
class ImageConversionConfig:
    format: str = "jpg"
    quality: int = 95
    lossless: bool = False
    effort: int = 6
    background_mode: str = "color"
    background_color: str = DEFAULT_BACKGROUND_COLOR

    def __post_init__(self):
        object.__setattr__(self, "format", normalize_convert_format(self.format))
        object.__setattr__(self, "quality", normalize_quality(self.quality))
        object.__setattr__(self, "effort", normalize_effort(self.effort))
        object.__setattr__(
            self, "background_mode", normalize_background_mode(self.background_mode)
        )
        object.__setattr__(
            self, "background_color", normalize_background_color(self.background_color)
        )


class ImageConverter:
    """Convert downloaded images into a sibling folder named after the source folder."""

    def __init__(self, config: ImageConversionConfig | None = None):
        self.config = config or ImageConversionConfig()

    def converted_path(self, image_path: Path) -> Path:
        source_dir = image_path.parent
        converted_dir = source_dir.parent / f"{source_dir.name}_{self.config.format}"
        return converted_dir / f"{image_path.stem}.{self.config.format}"

    def convert(self, image_path: str | Path) -> Path:
        source_path = Path(image_path)
        converted_path = self.converted_path(source_path)
        tmp_path = converted_path.with_suffix(converted_path.suffix + ".tmp")
        converted_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(source_path) as image:
            if self.config.format == "jpg":
                output = self._prepare_jpg(image)
                output.save(
                    tmp_path,
                    format="JPEG",
                    quality=self.config.quality,
                    optimize=True,
                )
            else:
                output = self._prepare_webp(image)
                output.save(
                    tmp_path,
                    format="WEBP",
                    quality=self.config.quality,
                    lossless=self.config.lossless,
                    method=self.config.effort,
                )

        tmp_path.replace(converted_path)
        return converted_path

    def _prepare_jpg(self, image: Image.Image) -> Image.Image:
        if image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        ):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return image.convert("RGB")

    def _prepare_webp(self, image: Image.Image) -> Image.Image:
        if self._has_transparency(image):
            return self._flatten_with_background(image)
        return image

    def _has_transparency(self, image: Image.Image) -> bool:
        return image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        )

    def _flatten_with_background(self, image: Image.Image) -> Image.Image:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, self._background_rgb())
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background

    def _background_rgb(self) -> tuple[int, int, int]:
        if self.config.background_mode == "white":
            return (255, 255, 255)
        if self.config.background_mode == "random":
            return random.choice(VIVID_BACKGROUND_COLORS)
        return _hex_to_rgb(self.config.background_color)
