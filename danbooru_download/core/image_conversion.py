"""Image conversion helpers for downloaded static images."""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


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


@dataclass(frozen=True)
class ImageConversionConfig:
    format: str = "jpg"
    quality: int = 95
    lossless: bool = False
    effort: int = 6

    def __post_init__(self):
        object.__setattr__(self, "format", normalize_convert_format(self.format))
        object.__setattr__(self, "quality", normalize_quality(self.quality))
        object.__setattr__(self, "effort", normalize_effort(self.effort))


class ImageConverter:
    """Convert downloaded images into a sibling jpg_webp folder."""

    def __init__(self, config: ImageConversionConfig | None = None):
        self.config = config or ImageConversionConfig()

    def converted_path(self, image_path: Path) -> Path:
        return image_path.parent / "jpg_webp" / f"{image_path.stem}.{self.config.format}"

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
                output = image.convert("RGBA") if image.mode == "P" else image
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
