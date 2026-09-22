"""Worker-only, once-per-cache-revision image admission for followed news.

Do not treat nonempty cache files as decodable images. Keep successful
validation memoized across source generations; no QML or GUI image probing.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=512)
def _verified_file(path: str, size: int, mtime_ns: int) -> bool:
    try:
        from PIL import Image
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError, SyntaxError):
        return False


def valid_local_artwork(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        info = path.stat()
        if 0 < info.st_size <= 2_000_000 and _verified_file(str(path), info.st_size, info.st_mtime_ns):
            return path
        # Remove only invalid entries in the existing asset-cache namespace;
        # a failed decode must not poison all future cache-first admissions.
        if len(path.stem) == 24 and all(c in "0123456789abcdef" for c in path.stem):
            path.unlink(missing_ok=True)
    except OSError:
        pass
    return None
