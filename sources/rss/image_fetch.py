"""Wallpaper image acquisition: one vetted stream per image, judged by its real pixels.

Wallpapers are judged against the connected displays in fill mode (the default
and best mode): an image is admitted only when it can fill every display
without upscaling. Larger is always fine; the crop is not judged in advance.

The image streams through the shared public image path
(``core.feeds.artwork_transport.iter_public_image``: bounded DNS, a pinned
public address, validated redirects, byte and time caps) straight into a
temporary file. Its real pixel size is read from the header as it arrives, at a
few growing checkpoints, so an image that is too small costs a few kilobytes
instead of a whole download. Nothing here schedules work or owns a thread; the
caller's worker job and cancellation fence bound it.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import time
from typing import Callable
import uuid

MAX_WALLPAPER_BYTES = 80 * 1024 * 1024
WALLPAPER_FETCH_SECONDS = 120.0
WALLPAPER_USER_AGENT = "SRPSS/WallpaperFeeds"
# Header checkpoints (bytes received). JPEG/PNG/WebP headers normally resolve at
# the first; large embedded ICC/EXIF blocks may push the frame header later.
_PROBE_POINTS = (16 * 1024, 64 * 1024, 256 * 1024, 1024 * 1024, 2 * 1024 * 1024)
# Formats the RSS cache loader recognises by magic bytes.
_EXTENSIONS = {b"jpeg": ".jpg", b"jpg": ".jpg", b"png": ".png", b"webp": ".webp"}


class WallpaperRejected(ValueError):
    """The URL did not yield an admissible wallpaper (too small, or not an image)."""

    def __init__(self, reason: str, size: tuple[int, int] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.size = size


@dataclass(frozen=True)
class WallpaperFile:
    path: Path
    width: int
    height: int


def fills_displays(width: int, height: int, required: tuple[int, int]) -> bool:
    """True when the image fills every display in fill mode without upscaling."""
    return width >= required[0] and height >= required[1]


def _reader(source):
    from PySide6.QtGui import QImageReader

    return QImageReader(source)


def image_size_from_prefix(data: bytes) -> tuple[tuple[int, int], bytes] | None:
    """``((width, height), format)`` read from an image's first bytes, or ``None``."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice

    buffer = QBuffer()
    buffer.setData(QByteArray(bytes(data)))
    if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
        return None
    reader = _reader(buffer)
    size = reader.size()
    if not size.isValid() or size.width() <= 0 or size.height() <= 0:
        return None
    return (size.width(), size.height()), bytes(reader.format()).lower()


def image_size_of_file(path: Path) -> tuple[tuple[int, int], bytes] | None:
    reader = _reader(str(path))
    size = reader.size()
    if not size.isValid() or size.width() <= 0 or size.height() <= 0:
        return None
    return (size.width(), size.height()), bytes(reader.format()).lower()


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def fetch_wallpaper(
    url: str,
    directory: Path,
    *,
    file_stem: str,
    still_needed: Callable[[], bool],
    required: tuple[int, int],
    resolve: Callable[..., object] | None = None,
    max_bytes: int = MAX_WALLPAPER_BYTES,
    max_seconds: float = WALLPAPER_FETCH_SECONDS,
) -> WallpaperFile:
    """Download one wallpaper into ``directory`` as ``file_stem`` + its real format's extension.

    Raises ``WallpaperRejected`` for an image that cannot fill the displays or
    is not a supported image, and the transport's ``ArtworkFetchError`` /
    ``ArtworkCancelled`` for network, bound and cancellation failures. A
    partial file never survives any failure.
    """
    from core.feeds.artwork_transport import iter_public_image

    directory.mkdir(parents=True, exist_ok=True)
    temp = directory / f".tmp.{file_stem}.{uuid.uuid4().hex[:8]}"
    probe = bytearray()
    known: tuple[tuple[int, int], bytes] | None = None
    checkpoints = list(_PROBE_POINTS)
    received = 0
    stream = iter_public_image(
        url,
        still_needed=still_needed,
        max_bytes=max_bytes,
        max_seconds=max_seconds,
        resolve=resolve,
        user_agent=WALLPAPER_USER_AGENT,
        accept="image/jpeg,image/png,image/webp;q=0.9,image/*;q=0.5",
        chunk_size=64 * 1024,
    )
    try:
        with open(temp, "wb") as handle:
            for chunk in stream:
                handle.write(chunk)
                received += len(chunk)
                if known is None and checkpoints:
                    probe.extend(chunk)
                    if received >= checkpoints[0]:
                        while checkpoints and received >= checkpoints[0]:
                            checkpoints.pop(0)
                        known = image_size_from_prefix(bytes(probe))
                        if known is not None:
                            probe = bytearray()
                            if not fills_displays(*known[0], required):
                                raise WallpaperRejected("too small", known[0])
                        elif not checkpoints:
                            probe = bytearray()
        if known is None:
            known = image_size_of_file(temp)
        if known is None:
            raise WallpaperRejected("not a readable image")
        (width, height), fmt = known
        if not fills_displays(width, height, required):
            raise WallpaperRejected("too small", (width, height))
        extension = _EXTENSIONS.get(fmt)
        if extension is None:
            raise WallpaperRejected(f"unsupported format {fmt.decode(errors='replace') or '?'}", (width, height))
        final = directory / f"{file_stem}{extension}"
        for attempt in range(4):
            try:
                os.replace(temp, final)
                break
            except OSError:
                # Antivirus/indexers can hold a just-closed file briefly on Windows.
                if attempt == 3:
                    raise
                time.sleep(0.05 * (attempt + 1))
        return WallpaperFile(final, width, height)
    finally:
        stream.close()
        _unlink(temp)


__all__ = [
    "MAX_WALLPAPER_BYTES",
    "WallpaperFile",
    "WallpaperRejected",
    "fetch_wallpaper",
    "fills_displays",
    "image_size_from_prefix",
    "image_size_of_file",
]
