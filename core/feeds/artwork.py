"""F3 worker-only local artwork cache, independent of Qt and feed scheduling.

The existing family owner invokes ``warm`` only from an event-admitted source
IO job. Cache lookup never schedules network work, and this module owns no Qt,
QML, provider refresh or independent download worker. Only accepted local files
may be projected into retained presentation.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import ipaddress
import logging
import os
import tempfile
from typing import Callable, Iterable, Mapping

from core.logging.logger import is_feeds_logging_enabled
from core.logging.tags import LOG_FAMILY_FEEDS, LOG_FAMILY_FIELD
from urllib.parse import urlsplit

from .models import FeedItem
from .projection import ranked_image_candidates

logger = logging.getLogger(__name__)

# Hard upper bounds, independent of the document's declared dimensions or a
# malicious Content-Length.  Conversion is worker-only and contains no Qt path.
MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
MAX_SOURCE_PIXELS = 16_000_000
MAX_STORED_EDGE = 640
MAX_IMAGES_PER_WARM = 4
CACHE_MAX_FILES = 256
CACHE_MAX_BYTES = 128 * 1024 * 1024


class ArtworkCancelled(RuntimeError):
    """A retired generation must not write its optional image result."""


def safe_artwork_url(value: object) -> str:
    """Reject obvious unsafe/proprietary image targets before any network work.

    DNS-boundary checks are still necessary in the eventual live transport;
    recognizing a syntactically safe candidate is NOT authorization to fetch it.
    """
    if type(value) is not str or not 0 < len(value) <= 4096:
        return ""
    try:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").strip(".").lower()
        port = parsed.port  # Reject malformed network ports.
    except ValueError:
        return ""
    if (parsed.scheme.lower() not in {"http", "https"} or not hostname
        or parsed.username is not None or parsed.password is not None
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
        or "\\" in value or hostname in {"localhost", "localhost.localdomain"}
        or hostname.endswith((".localhost", ".local", ".internal"))
        or (port is not None and port not in {80, 443})):
        return ""
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if not address.is_global:
            return ""
    return value


def _key(url: str) -> str:
    # Signed media query strings are never copied into filenames or logs.
    return sha256(url.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ArtworkWarmResult:
    """Completed worker batch; no per-image notification or render authority."""
    local_by_item: Mapping[str, str]
    attempts: int
    newly_cached: int


class FeedArtworkCache:
    """Cache-first worker transaction with caller-owned fetch and cancellation.

    ``fetch_bytes`` must be a *bounded*, redirect-vetted image transport.  The
    eventual owner must inject an implementation that checks redirect targets
    and resolved IP addresses before making requests.  No default fetcher is
    provided, preventing this preparatory cache from accidentally becoming an
    unsupervised second feed network owner.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def _file(self, url: str) -> Path:
        return self.directory / (_key(url) + ".png")

    @staticmethod
    def _valid(path: Path) -> bool:
        if not path.is_file() or path.is_symlink():
            return False
        try:
            stat = path.stat()
            if not 0 < stat.st_size <= MAX_DOWNLOAD_BYTES:
                return False
            from PIL import Image
            with Image.open(path) as image:
                valid = (image.format == "PNG" and image.width > 0 and image.height > 0
                         and image.width <= MAX_STORED_EDGE and image.height <= MAX_STORED_EDGE)
                if valid:
                    image.verify()  # Reject a truncated/corrupt file, not just its header.
                return valid
        except (OSError, ValueError, SyntaxError):
            return False

    def cached(self, url: str) -> str:
        """Validate an existing local file; never open a transport or write."""
        if not safe_artwork_url(url):
            return ""
        path = self._file(url)
        return path.as_uri() if self._valid(path) else ""

    @staticmethod
    def _normalize_image(payload: bytes) -> bytes:
        if not 0 < len(payload) <= MAX_DOWNLOAD_BYTES:
            raise ValueError("image payload exceeds bound or is empty")
        from PIL import Image, ImageOps, UnidentifiedImageError
        DecompressionBombError = Image.DecompressionBombError
        try:
            with Image.open(BytesIO(payload)) as original:
                width, height = original.size
                if width <= 0 or height <= 0 or width * height > MAX_SOURCE_PIXELS:
                    raise ValueError("image dimensions exceed bound")
                if original.format not in {"PNG", "JPEG", "WEBP", "GIF"}:
                    raise ValueError("unsupported image format")
                # First frame only; never render/process a provider GIF timeline.
                first = ImageOps.exif_transpose(original)
                first.thumbnail((MAX_STORED_EDGE, MAX_STORED_EDGE), Image.Resampling.LANCZOS)
                rgb = first.convert("RGBA") if "A" in first.getbands() else first.convert("RGB")
                output = BytesIO()
                rgb.save(output, format="PNG", optimize=False)
                result = output.getvalue()
                if not 0 < len(result) <= MAX_DOWNLOAD_BYTES:
                    raise ValueError("normalized image exceeds cache bound")
                return result
        except (OSError, UnidentifiedImageError, OverflowError, DecompressionBombError) as exc:
            raise ValueError("unusable image payload") from exc

    def _write(self, url: str, content: bytes, *, still_needed: Callable[[], bool]) -> str:
        if not still_needed():
            raise ArtworkCancelled()
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._file(url)
        if self._valid(path):
            return path.as_uri()
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.directory, prefix=".feed-art-", suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if not still_needed():
                raise ArtworkCancelled()
            temporary.replace(path)
            temporary = None
            return path.as_uri()
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def prune(self, *, protected: Iterable[str] = ()) -> int:
        """One bounded worker-only eviction after writes, never on render/read."""
        if not self.directory.is_dir():
            return 0
        protected_names = {Path(urlsplit(source).path).name for source in protected}
        entries = []
        for path in self.directory.iterdir():
            if path.is_symlink() or not path.is_file() or path.suffix != ".png":
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append((stat.st_mtime_ns, path, stat.st_size))
        count, size, removed = len(entries), sum(row[2] for row in entries), 0
        for _, path, weight in sorted(entries):
            if count <= CACHE_MAX_FILES and size <= CACHE_MAX_BYTES:
                break
            if path.name in protected_names:
                continue
            try:
                path.unlink()
            except OSError:
                continue
            removed += 1
            count -= 1
            size -= weight
        return removed

    def warm(
        self, items: Iterable[FeedItem], *,
        fetch_bytes: Callable[[str], bytes],
        still_needed: Callable[[], bool],
        max_new: int = MAX_IMAGES_PER_WARM,
        protected_sources: Iterable[str] = (),
    ) -> ArtworkWarmResult:
        """Cache hits for all items; bounded missing-image work for this batch.

        An unavailable image is optional.  Work cancellation, unlike an image
        failure, propagates to the owner, which must fence the entire batch.
        """
        local: dict[str, str] = {}
        attempts = created = 0
        attempted_urls: set[str] = set()
        batch_budget = max(0, min(MAX_IMAGES_PER_WARM, int(max_new)))
        item_rows = tuple(items)

        # A surprisingly common RSS pattern advertises one feed/site hero as a
        # high-resolution media candidate on *every* entry while the actual
        # per-article image sits lower in content/thumbnail metadata. Ranking
        # each item in isolation makes that shared chrome win every card. Count
        # candidate ownership once for this accepted document and prefer URLs
        # unique to an item before any cross-item candidate. This is pure worker
        # selection: no page scraping, extra scheduler or render-time work.
        candidates_by_item: dict[str, tuple[str, ...]] = {}
        candidate_users: dict[str, int] = {}
        for item in item_rows:
            candidates = tuple(dict.fromkeys(filter(None, (
                safe_artwork_url(candidate) for candidate in ranked_image_candidates(item)))))
            candidates_by_item[item.item_id] = candidates
            for candidate in candidates:
                candidate_users[candidate] = candidate_users.get(candidate, 0) + 1

        for item in item_rows:
            if not still_needed():
                raise ArtworkCancelled()
            ranked = candidates_by_item.get(item.item_id, ())
            # A URL advertised by more than one distinct article is not useful
            # article identity for a multi-row widget. Treat it as feed/site
            # chrome and suppress it instead of painting the same hero on every
            # story. A one-item document naturally has count==1 and is unchanged.
            candidates = tuple(candidate for candidate in ranked
                               if candidate_users.get(candidate, 0) == 1)
            if not candidates:
                continue
            # Prefer any already-established usable local image, even when a
            # newer/nominally higher-resolution candidate is unavailable.
            cached = next((source for candidate in candidates
                           if (source := self.cached(candidate))), "")
            if cached:
                local[item.item_id] = cached
                continue
            for candidate in candidates:
                if attempts >= batch_budget:
                    break
                if candidate in attempted_urls:
                    continue
                attempted_urls.add(candidate)
                attempts += 1
                try:
                    payload = fetch_bytes(candidate)
                    normalized = self._normalize_image(payload)
                    local[item.item_id] = self._write(candidate, normalized, still_needed=still_needed)
                    created += 1
                    break
                except ArtworkCancelled:
                    raise
                except (OSError, ValueError, TypeError):
                    continue
        if created:
            if not still_needed():
                raise ArtworkCancelled()
            self.prune(protected=(*local.values(), *protected_sources))
        shared_candidates = sum(1 for count in candidate_users.values() if count > 1)
        if is_feeds_logging_enabled():
            logger.info(
                "[FEEDS][ARTWORK] items=%d distinct_candidates=%d shared_candidates=%d "
                "attempts=%d newly_cached=%d local_items=%d unique_local_files=%d",
                len(item_rows), len(candidate_users), shared_candidates, attempts, created,
                len(local), len(set(local.values())),
                extra={LOG_FAMILY_FIELD: (LOG_FAMILY_FEEDS,)},
            )
        return ArtworkWarmResult(local, attempts, created)
