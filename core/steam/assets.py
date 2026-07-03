"""Safe Steam asset cache helpers for future card artwork/avatar use."""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from core.logging.logger import get_logger
from core.steam.models import SteamResult, SteamResultStatus

logger = get_logger(__name__)

MAX_STEAM_ASSET_BYTES = 2_000_000
_ALLOWED_SUFFIX_BY_KIND = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "webp": b"RIFF",
}


@dataclass(frozen=True)
class SteamAssetRecord:
    """Cached asset reference safe for future paint code."""

    url_fingerprint: str
    path: Path
    bytes_written: int
    image_kind: str


def cache_asset_from_bytes(
    *,
    cache_dir: Path,
    url: str,
    data: bytes,
    allowed_hosts: tuple[str, ...] = ("cdn.akamai.steamstatic.com", "avatars.steamstatic.com", "shared.akamai.steamstatic.com"),
) -> SteamAssetRecord | SteamResult:
    """Validate and atomically cache an already-fetched Steam image payload."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in allowed_hosts:
        return SteamResult(status=SteamResultStatus.ASSET_INVALID, message="Steam asset host is not allowed.")
    if not data or len(data) > MAX_STEAM_ASSET_BYTES:
        return SteamResult(status=SteamResultStatus.ASSET_INVALID, message="Steam asset size is invalid.")
    kind = _detect_image_kind(data)
    if kind is None:
        return SteamResult(status=SteamResultStatus.ASSET_INVALID, message="Steam asset did not look like a supported image.")
    fingerprint = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{fingerprint}.{kind}"
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_bytes(data)
        tmp_path.replace(path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        logger.exception("[STEAM] Failed to write asset cache path=%s", path)
        raise
    return SteamAssetRecord(
        url_fingerprint=fingerprint,
        path=path,
        bytes_written=len(data),
        image_kind=kind,
    )


def fetch_and_cache_asset(
    *,
    cache_dir: Path,
    url: str,
    fetcher: Callable[[str], bytes],
    allowed_hosts: tuple[str, ...] = ("cdn.akamai.steamstatic.com", "avatars.steamstatic.com", "shared.akamai.steamstatic.com"),
) -> SteamAssetRecord | SteamResult:
    """Fetch through an injected fetcher, then validate/cache the asset."""
    try:
        data = fetcher(url)
    except Exception as exc:
        logger.warning("[STEAM] Asset fetch failed url_hash=%s error=%s", hashlib.sha256(url.encode("utf-8")).hexdigest()[:12], exc)
        return SteamResult(status=SteamResultStatus.NETWORK_ERROR, message="Steam asset fetch failed.")
    return cache_asset_from_bytes(cache_dir=cache_dir, url=url, data=data, allowed_hosts=allowed_hosts)


def prune_asset_cache(cache_dir: Path, *, max_files: int = 256) -> int:
    """Prune oldest cached Steam asset files beyond max_files."""
    if not cache_dir.exists():
        return 0
    files = [path for path in cache_dir.iterdir() if path.is_file() and not path.name.endswith(".tmp")]
    if len(files) <= max_files:
        return 0
    removed = 0
    for path in sorted(files, key=lambda item: item.stat().st_mtime)[: max(0, len(files) - max_files)]:
        try:
            path.unlink()
            removed += 1
        except Exception:
            logger.warning("[STEAM] Failed to prune asset cache file path=%s", path)
    return removed


def _detect_image_kind(data: bytes) -> str | None:
    for kind, signature in _ALLOWED_SUFFIX_BY_KIND.items():
        if data.startswith(signature):
            return "jpg" if kind == "jpeg" else kind
    return None
