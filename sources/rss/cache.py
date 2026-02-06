"""
RSSCache - Disk cache with ResourceManager integration.

Responsibilities:
    - Load cached images from disk on startup (up to MAX_CACHED_IMAGES_TO_LOAD)
    - Validate image integrity (header bytes, minimum size)
    - Track cached image metadata (ImageMetadata list)
    - Evict oldest images when size or count limits are exceeded
    - Register with ResourceManager for deterministic cleanup
    - Report current cached count for dynamic download budget
"""
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Set
from urllib.parse import urlparse

from sources.base_provider import ImageMetadata, ImageSourceType
from sources.rss.constants import (
    MAX_CACHED_IMAGES_TO_LOAD,
    MIN_CACHE_BEFORE_CLEANUP,
    DEFAULT_MAX_CACHE_SIZE_MB,
)
from core.logging.logger import get_logger

logger = get_logger(__name__)


class RSSCache:
    """Manages the on-disk RSS image cache and in-memory metadata list."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_cache_size_mb: int = DEFAULT_MAX_CACHE_SIZE_MB,
        resource_manager=None,
    ):
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(tempfile.gettempdir()) / "screensaver_rss_cache"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size = max_cache_size_mb * 1024 * 1024

        # Copy-on-write: IO thread creates new list on add(), UI thread
        # reads the reference atomically.  No locks needed.
        self._images: List[ImageMetadata] = []
        self._cached_urls: Set[str] = set()
        self._resource_id: Optional[str] = None

        # Register cache directory with ResourceManager
        if resource_manager is not None:
            try:
                from core.resources.types import ResourceType
                self._resource_id = resource_manager.register(
                    self,
                    resource_type=ResourceType.CACHE,
                    description=f"RSSCache: {self.cache_dir}",
                )
                logger.debug(f"[RSS_CACHE] Registered with ResourceManager: {self._resource_id}")
            except Exception as e:
                logger.debug(f"[RSS_CACHE] ResourceManager registration failed: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def images(self) -> List[ImageMetadata]:
        """Return a snapshot (safe to read from any thread)."""
        return self._images  # reference read is atomic under CPython

    @property
    def count(self) -> int:
        return len(self._images)

    def existing_paths(self) -> Set[str]:
        """Return set of local_path strings for duplicate detection."""
        return {str(img.local_path) for img in self._images if img.local_path}

    def add(self, metadata: ImageMetadata) -> None:
        """Add a single image via copy-on-write (thread-safe, lock-free)."""
        new_list = list(self._images)
        new_list.append(metadata)
        self._images = new_list  # atomic reference swap

    def load_from_disk(self) -> int:
        """Load cached images from disk for instant startup availability.

        Validates each file and returns the number of valid images loaded.
        """
        try:
            if not self.cache_dir.exists():
                return 0

            pending: List[ImageMetadata] = []
            image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
            cached_files = [
                f for f in self.cache_dir.glob("*")
                if f.is_file() and f.suffix.lower() in image_extensions
            ]

            if not cached_files:
                return 0

            # Newest first for freshness
            cached_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            cached_files = cached_files[:MAX_CACHED_IMAGES_TO_LOAD]

            valid = 0
            removed = 0

            for cache_file in cached_files:
                try:
                    file_size = cache_file.stat().st_size
                    if file_size < 100:
                        cache_file.unlink()
                        removed += 1
                        continue

                    if not self._validate_image_header(cache_file):
                        cache_file.unlink()
                        removed += 1
                        continue

                    meta = ImageMetadata(
                        source_type=ImageSourceType.RSS,
                        source_id="cached",
                        image_id=cache_file.name,
                        local_path=cache_file,
                        title=cache_file.stem,
                        fetched_date=datetime.utcfromtimestamp(cache_file.stat().st_mtime),
                        file_size=file_size,
                        format=cache_file.suffix[1:].upper(),
                    )
                    pending.append(meta)
                    self._cached_urls.add(cache_file.stem)
                    valid += 1

                except Exception as e:
                    logger.debug(f"[RSS_CACHE] Skipping {cache_file.name}: {e}")

            # Atomic swap - all cached images appear at once
            if pending:
                self._images = pending

            if removed:
                logger.info(f"[RSS_CACHE] Removed {removed} corrupt cached images")
            logger.info(f"[RSS_CACHE] Loaded {valid} cached images from disk")
            return valid

        except Exception as e:
            logger.error(f"[RSS_CACHE] Failed to load cached images: {e}")
            return 0

    def get_cache_path(self, image_url: str) -> Path:
        """Return expected cache path for a URL (does not download)."""
        url_hash = hashlib.md5(image_url.encode()).hexdigest()
        parsed = urlparse(image_url)
        ext = Path(parsed.path).suffix or ".jpg"
        return self.cache_dir / f"{url_hash}{ext}"

    def is_cached(self, image_url: str) -> bool:
        url_hash = hashlib.md5(image_url.encode()).hexdigest()
        return url_hash in self._cached_urls

    def mark_cached(self, image_url: str) -> None:
        url_hash = hashlib.md5(image_url.encode()).hexdigest()
        self._cached_urls.add(url_hash)

    def cleanup(self, min_keep: int = MIN_CACHE_BEFORE_CLEANUP) -> None:
        """Evict oldest files when cache exceeds size or count limits."""
        try:
            cache_files = []
            total_size = 0

            for f in self.cache_dir.glob("*"):
                if f.is_file() and not f.name.startswith(".tmp."):
                    size = f.stat().st_size
                    mtime = f.stat().st_mtime
                    cache_files.append((f, size, mtime))
                    total_size += size

            max_files = max(min_keep * 2, MAX_CACHED_IMAGES_TO_LOAD)
            size_ok = total_size <= self.max_cache_size
            count_ok = len(cache_files) <= max_files

            if size_ok and count_ok:
                return

            cache_files.sort(key=lambda x: x[2])  # oldest first
            max_removable = max(0, len(cache_files) - min_keep)
            removed_count = 0
            removed_size = 0
            current_count = len(cache_files)

            for i, (file, size, _) in enumerate(cache_files):
                if i >= max_removable:
                    break
                if (total_size - removed_size) <= self.max_cache_size * 0.8 and \
                   (current_count - removed_count) <= max_files:
                    break
                try:
                    file.unlink()
                    removed_count += 1
                    removed_size += size
                except Exception as e:
                    logger.warning(f"[RSS_CACHE] Failed to remove {file}: {e}")

            if removed_count:
                logger.info(
                    f"[RSS_CACHE] Evicted {removed_count} files "
                    f"({removed_size / 1024 / 1024:.1f}MB), "
                    f"kept {len(cache_files) - removed_count}"
                )

        except Exception as e:
            logger.error(f"[RSS_CACHE] Cleanup failed: {e}")

    def clear_all(self) -> int:
        """Remove every cached file. Returns count removed."""
        removed = 0
        try:
            for f in self.cache_dir.glob("*"):
                if f.is_file():
                    f.unlink()
                    removed += 1
        except Exception as e:
            logger.error(f"[RSS_CACHE] clear_all failed: {e}")
        self._images.clear()
        self._cached_urls.clear()
        return removed

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_image_header(path: Path) -> bool:
        """Quick validation via magic bytes."""
        try:
            with open(path, "rb") as f:
                header = f.read(16)
            return (
                header[:2] == b"\xff\xd8"              # JPEG
                or header[:8] == b"\x89PNG\r\n\x1a\n"  # PNG
                or header[:4] == b"RIFF"                # WebP
                or header[:6] in (b"GIF87a", b"GIF89a") # GIF
            )
        except Exception:
            return False
