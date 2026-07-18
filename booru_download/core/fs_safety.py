"""Filesystem safety helpers: path containment, unique temp files, atomic writes."""

from __future__ import annotations

import os
import re
import tempfile
import time
import uuid
from pathlib import Path

import yaml


# Extensions are remote-controlled data; only allow short alphanumeric tokens.
_SAFE_EXT_RE = re.compile(r"[a-z0-9]{1,10}")
_WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_UNSAFE_SEGMENT_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def normalize_file_ext(value, default: str = "jpg") -> str:
    """Whitelist a remote file extension down to a plain alphanumeric token."""
    ext = str(value or "").strip().lower().lstrip(".")
    if _SAFE_EXT_RE.fullmatch(ext):
        return ext
    return default


def sanitize_subfolder(value: str) -> str:
    """Reduce a user-supplied subfolder name to safe relative path segments.

    Rejects drive letters, rooted paths, ``..`` traversal, reserved device
    names, and strips characters invalid on Windows. Returns "" when nothing
    safe remains (caller should fall back to the root download directory).
    """
    raw = str(value or "").strip()
    if not raw:
        return ""

    segments: list[str] = []
    for segment in re.split(r"[\\/]+", raw):
        segment = _UNSAFE_SEGMENT_CHARS.sub("_", segment).strip().rstrip(". ")
        if not segment or segment in {".", ".."}:
            continue
        if segment.split(".")[0].lower() in _WINDOWS_RESERVED_NAMES:
            continue
        segments.append(segment)
    return "/".join(segments)


def safe_join(root: Path, relative: str | Path) -> Path:
    """Join *relative* onto *root*, guaranteeing the result stays inside root."""
    root = Path(root)
    candidate = (root / relative).resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        raise ValueError(
            f"path escapes the download root: {relative!r} -> {candidate}"
        ) from None
    return candidate


def is_within_directory(root: Path, target: Path) -> bool:
    """Return True when *target* resolves inside *root*."""
    try:
        Path(target).resolve(strict=False).relative_to(Path(root).resolve(strict=False))
        return True
    except ValueError:
        return False


def unique_tmp_path(target: Path) -> Path:
    """Return an unpredictable temp path in the same directory as *target*."""
    target = Path(target)
    return target.parent / f".{target.name}.{uuid.uuid4().hex}.tmp"


def atomic_write_text(path: str | Path, content: str, encoding: str = "utf-8") -> None:
    """Write text to *path* via a same-directory temp file and os.replace."""
    _atomic_write_bytes(Path(path), content.encode(encoding))


def atomic_write_yaml(path: str | Path, data) -> None:
    """Serialize *data* to YAML in memory first, then atomically replace *path*.

    Serializing before touching the target file means a dump error can never
    truncate the previous good copy.
    """
    text = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)
    _atomic_write_bytes(Path(path), text.encode("utf-8"))


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def quarantine_corrupt_file(path: Path) -> Path | None:
    """Rename a corrupt file aside so the app can start fresh; return new path."""
    path = Path(path)
    if not path.exists():
        return None
    target = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
    counter = 0
    while target.exists():
        counter += 1
        target = path.with_name(
            f"{path.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}-{counter}"
        )
    try:
        os.replace(path, target)
    except OSError:
        return None
    return target


def clamp_concurrency(value, default: int = 8, maximum: int = 64) -> int:
    """Clamp a concurrency setting to [1, maximum]; invalid input -> default."""
    try:
        concurrent = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(concurrent, 1), maximum)


def normalize_timeout(value, default: float = 30.0, maximum: float = 3600.0) -> float:
    """Return a finite positive timeout; invalid input -> default."""
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return default
    if not (timeout > 0) or timeout != timeout or timeout == float("inf"):
        return default
    return min(timeout, maximum)


def normalize_max_posts(value, default: int = 100, maximum: int = 1_000_000) -> int:
    """Clamp max posts to [1, maximum]; invalid input -> default."""
    try:
        max_posts = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(max_posts, 1), maximum)
