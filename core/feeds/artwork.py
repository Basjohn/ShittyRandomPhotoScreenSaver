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
MAX_CANDIDATE_ATTEMPTS_PER_WARM = 8
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


def _candidate_identity(url: str) -> str:
    """Stable cross-item media identity that ignores tracking/signature query data.

    The original URL remains the fetch/cache key because its query can be
    required for authorization.  Identity comparison is deliberately narrower:
    two stories advertising the same public host/path with different query or
    fragment decorations still describe the same image candidate.
    """
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if not scheme or not host:
        return url
    port = parsed.port
    authority = host if port is None else f"{host}:{port}"
    return f"{scheme}://{authority}{parsed.path or '/'}"


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

    def _cached_path(self, url: str) -> Path | None:
        if not safe_artwork_url(url):
            return None
        path = self._file(url)
        return path if self._valid(path) else None

    def cached(self, url: str) -> str:
        """Validate an existing local file; never open a transport or write."""
        path = self._cached_path(url)
        return path.as_uri() if path is not None else ""

    @staticmethod
    def _content_digest(path: Path) -> bytes:
        return sha256(path.read_bytes()).digest()

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
        """Resolve local article art with bounded fallback and content identity.

        URL identity alone is insufficient: many publishers advertise one site
        hero through per-entry CDN URLs.  Selection therefore rejects exact URLs
        shared by multiple stories *and* detects identical normalized image bytes
        across otherwise-distinct URLs.  A duplicate-content discovery revokes the
        earlier claim and lets both stories try their next feed-advertised candidate.
        Work remains source-event-owned and bounded; no article-page scraping,
        presentation-time hashing, timer or second worker is introduced.
        """
        local: dict[str, str] = {}
        selected_url: dict[str, str] = {}
        attempts = created = 0
        network_owned: set[str] = set()
        content_duplicates = 0
        attempted_urls: set[str] = set()
        rejected_urls: set[str] = set()
        shared_digests: set[bytes] = set()
        digest_owner: dict[bytes, str] = {}
        digest_url: dict[bytes, str] = {}
        batch_budget = max(0, min(MAX_IMAGES_PER_WARM, int(max_new)))
        attempt_budget = min(MAX_CANDIDATE_ATTEMPTS_PER_WARM, batch_budget * 2)
        item_rows = tuple(items)
        item_by_id = {item.item_id: item for item in item_rows}

        candidates_by_item: dict[str, tuple[str, ...]] = {}
        candidate_users: dict[str, int] = {}
        candidate_identities: dict[str, str] = {}
        distinct_candidate_urls: set[str] = set()
        for item in item_rows:
            candidates = tuple(dict.fromkeys(filter(None, (
                safe_artwork_url(candidate) for candidate in ranked_image_candidates(item)))))
            candidates_by_item[item.item_id] = candidates
            # Count each stable media identity at most once per story. A common
            # publisher hero with per-entry tracking/signature query strings is
            # still common chrome and must not masquerade as distinct artwork.
            item_identities: set[str] = set()
            for candidate in candidates:
                distinct_candidate_urls.add(candidate)
                identity = _candidate_identity(candidate)
                candidate_identities[candidate] = identity
                if identity in item_identities:
                    continue
                item_identities.add(identity)
                candidate_users[identity] = candidate_users.get(identity, 0) + 1

        # Cross-item media identities are feed/site chrome, not article identity.
        for item in item_rows:
            candidates_by_item[item.item_id] = tuple(
                candidate for candidate in candidates_by_item[item.item_id]
                if candidate_users.get(candidate_identities[candidate], 0) == 1
            )

        next_index = {item.item_id: 0 for item in item_rows}
        pending = [item.item_id for item in item_rows]
        queued = set(pending)

        def requeue(item_id: str) -> None:
            if item_id in item_by_id and item_id not in queued:
                pending.append(item_id)
                queued.add(item_id)

        def reject_duplicate(item_id: str, candidate: str, digest: bytes) -> bool:
            nonlocal content_duplicates
            if digest in shared_digests:
                rejected_urls.add(candidate)
                return True
            previous = digest_owner.get(digest)
            if previous is None or previous == item_id:
                return False
            content_duplicates += 1
            shared_digests.add(digest)
            rejected_urls.add(candidate)
            previous_url = digest_url.pop(digest, "")
            if previous_url:
                rejected_urls.add(previous_url)
            digest_owner.pop(digest, None)
            local.pop(previous, None)
            selected_url.pop(previous, None)
            network_owned.discard(previous)
            requeue(previous)
            return True

        while pending:
            if not still_needed():
                raise ArtworkCancelled()
            item_id = pending.pop(0)
            queued.discard(item_id)
            if item_id in local:
                continue
            candidates = candidates_by_item.get(item_id, ())
            index = next_index[item_id]

            # Cache-first means *all* already-local fallbacks outrank a new
            # network attempt.  A previously failed preferred candidate must not
            # be retried every ordinary feed refresh when a valid lower-ranked
            # candidate is already durable on disk.  This scan is bounded by the
            # accepted per-item candidate list and performs no network work.
            cached_selected = False
            for cached_index in range(index, len(candidates)):
                candidate = candidates[cached_index]
                if candidate in rejected_urls:
                    continue
                path = self._cached_path(candidate)
                if path is None:
                    continue
                try:
                    digest = self._content_digest(path)
                except OSError:
                    continue
                next_index[item_id] = cached_index + 1
                if reject_duplicate(item_id, candidate, digest):
                    continue
                digest_owner[digest] = item_id
                digest_url[digest] = candidate
                selected_url[item_id] = candidate
                local[item_id] = path.as_uri()
                cached_selected = True
                break
            if cached_selected:
                continue

            index = next_index[item_id]
            while index < len(candidates):
                candidate = candidates[index]
                index += 1
                next_index[item_id] = index
                if candidate in rejected_urls:
                    continue
                # Cached candidates were exhausted above. A file could appear
                # only through another writer racing this worker; re-check once
                # before opening the bounded transport and accept it if valid.
                path = self._cached_path(candidate)
                if path is not None:
                    try:
                        digest = self._content_digest(path)
                    except OSError:
                        continue
                    if reject_duplicate(item_id, candidate, digest):
                        continue
                    digest_owner[digest] = item_id
                    digest_url[digest] = candidate
                    selected_url[item_id] = candidate
                    local[item_id] = path.as_uri()
                    break

                if len(network_owned) >= batch_budget or attempts >= attempt_budget:
                    break
                if candidate in attempted_urls:
                    continue
                attempted_urls.add(candidate)
                attempts += 1
                try:
                    payload = fetch_bytes(candidate)
                    normalized = self._normalize_image(payload)
                    digest = sha256(normalized).digest()
                    if reject_duplicate(item_id, candidate, digest):
                        continue
                    source = self._write(candidate, normalized, still_needed=still_needed)
                    local[item_id] = source
                    selected_url[item_id] = candidate
                    digest_owner[digest] = item_id
                    digest_url[digest] = candidate
                    network_owned.add(item_id)
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
                "content_duplicates=%d attempts=%d newly_cached=%d local_items=%d "
                "unique_local_files=%d",
                len(item_rows), len(distinct_candidate_urls), shared_candidates, content_duplicates,
                attempts, created, len(local), len(set(local.values())),
                extra={LOG_FAMILY_FIELD: (LOG_FAMILY_FEEDS,)},
            )
        return ArtworkWarmResult(local, attempts, created)
