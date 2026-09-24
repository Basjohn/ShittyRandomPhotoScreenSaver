"""RSSCache - the wallpaper-feed image pool on disk and in memory.

Responsibilities:
    - The pool: image files directly under the cache directory, newest first,
      bounded by count and bytes, with an index of each file's real pixel size,
      fetch time and origin (``state/pool.json``) so startup never probes files.
    - Retirement: a file replaced by the session rotation is hidden at once and
      deleted at the next session start, so nothing still in this session's
      history loses its file.
    - Rejected-URL memory: image URLs that cannot fill the displays (with the
      size they had) are not fetched again while that still holds.

State lives under ``state/`` so the pool's eviction sweep never touches it.
Writes are atomic; a malformed state file is replaced by an empty one, never
fatal. Copy-on-write lists keep reads lock-free for the UI thread.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Dict, Iterable, List, Optional, Set, Tuple

from sources.base_provider import ImageMetadata, ImageSourceType
from sources.rss.constants import (
    DEFAULT_MAX_CACHE_SIZE_MB,
    MAX_CACHED_IMAGES_TO_LOAD,
    MAX_REJECTED_URLS,
    MIN_CACHE_BEFORE_CLEANUP,
    REJECTED_URL_TTL_DAYS,
)
from core.logging.logger import get_logger

logger = get_logger(__name__)

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_STATE_VERSION = 1


def url_key(url: str) -> str:
    """The stable file stem / memory key for an image URL."""
    return hashlib.md5(str(url).encode("utf-8", errors="replace")).hexdigest()


@dataclass(frozen=True)
class PoolEntry:
    metadata: ImageMetadata
    width: Optional[int]
    height: Optional[int]
    fetched_at: float

    @property
    def path(self) -> Path:
        return Path(self.metadata.local_path)


class RSSCache:
    """Manages the on-disk wallpaper pool and its small persisted index."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_cache_size_mb: int = DEFAULT_MAX_CACHE_SIZE_MB,
        resource_manager=None,
    ):
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            from core.settings.storage_paths import get_rss_cache_dir
            self.cache_dir = get_rss_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir = self.cache_dir / "state"
        self.max_cache_size = max_cache_size_mb * 1024 * 1024
        self._entries: List[PoolEntry] = []
        self._index: Dict[str, dict] = {}
        self._retired: Set[str] = set()
        self._rejected: Dict[str, list] = {}
        self._resource_id: Optional[str] = None
        if resource_manager is not None:
            try:
                from core.resources.types import ResourceType
                self._resource_id = resource_manager.register(
                    self,
                    resource_type=ResourceType.IMAGE_CACHE,
                    description=f"RSSCache: {self.cache_dir}",
                )
            except Exception as e:
                logger.debug(f"[RSS_CACHE] ResourceManager registration failed: {e}")

    # ------------------------------------------------------------------
    # Pool reads (any thread)
    # ------------------------------------------------------------------

    @property
    def entries(self) -> List[PoolEntry]:
        return self._entries  # reference read is atomic under CPython

    @property
    def images(self) -> List[ImageMetadata]:
        return [entry.metadata for entry in self._entries]

    @property
    def count(self) -> int:
        return len(self._entries)

    def existing_paths(self) -> Set[str]:
        return {str(entry.path) for entry in self._entries}

    def has_url(self, image_url: str) -> bool:
        key = url_key(image_url)
        return any(entry.path.stem == key for entry in self._entries)

    # ------------------------------------------------------------------
    # Load (startup; cheap: one small JSON read plus a magic-byte check)
    # ------------------------------------------------------------------

    def load_from_disk(self, *, purge_retired: bool = True) -> int:
        """Load the pool.

        ``purge_retired`` (a new process session) deletes files retired by an
        earlier session; a settings rebuild within the same session keeps them
        on disk (they may be in this session's history) but still hidden.
        """
        try:
            self._read_state()
            if purge_retired:
                for name in sorted(self._retired):
                    self._unlink(self.cache_dir / name)
                    self._index.pop(name, None)
                self._retired.clear()
            files = [f for f in self.cache_dir.iterdir()
                     if f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS
                     and f.name not in self._retired]
            present = {f.name for f in files} | self._retired
            # Files removed outside the pool (Cache Maintenance) leave no index rows.
            self._index = {name: row for name, row in self._index.items() if name in present}
            files.sort(key=lambda f: self._fetched_at(f), reverse=True)
            pending: List[PoolEntry] = []
            removed = 0
            for cache_file in files[:MAX_CACHED_IMAGES_TO_LOAD]:
                try:
                    size = cache_file.stat().st_size
                    if size < 100 or not self._validate_image_header(cache_file):
                        self._unlink(cache_file)
                        self._index.pop(cache_file.name, None)
                        removed += 1
                        continue
                    pending.append(self._entry_for(cache_file, size))
                except OSError as e:
                    logger.debug(f"[RSS_CACHE] Skipping {cache_file.name}: {e}")
            self._entries = pending
            if removed:
                logger.info(f"[RSS_CACHE] Removed {removed} corrupt cached images")
            self._write_state()
            logger.info(f"[RSS_CACHE] Loaded {len(pending)} cached images from disk")
            return len(pending)
        except Exception as e:
            logger.error(f"[RSS_CACHE] Failed to load cached images: {e}")
            return 0

    def _fetched_at(self, path: Path) -> float:
        row = self._index.get(path.name) or {}
        value = row.get("fetched")
        if type(value) in {int, float}:
            return float(value)
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    def _entry_for(self, path: Path, file_size: int) -> PoolEntry:
        row = self._index.get(path.name) or {}
        width = row.get("w") if type(row.get("w")) is int else None
        height = row.get("h") if type(row.get("h")) is int else None
        fetched = self._fetched_at(path)
        metadata = ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id=str(row.get("source") or "cached"),
            image_id=path.name,
            local_path=path,
            url=str(row.get("url") or "") or None,
            title=str(row.get("title") or path.stem),
            width=width,
            height=height,
            fetched_date=datetime.fromtimestamp(fetched, tz=timezone.utc).replace(tzinfo=None),
            file_size=file_size,
            format=path.suffix[1:].upper(),
        )
        return PoolEntry(metadata, width, height, fetched)

    # ------------------------------------------------------------------
    # Pool writes (IO worker)
    # ------------------------------------------------------------------

    def add(self, path: Path, *, width: int, height: int, url: str, source: str, title: str,
            fetched_at: Optional[float] = None) -> PoolEntry:
        stamp = time.time() if fetched_at is None else float(fetched_at)
        self._index[path.name] = {"w": int(width), "h": int(height), "fetched": stamp,
                                  "url": str(url)[:4096], "source": str(source)[:4096],
                                  "title": str(title)[:300]}
        entry = self._entry_for(path, path.stat().st_size)
        self._entries = [*self._entries, entry]
        return entry

    def record_size(self, entry: PoolEntry, width: int, height: int) -> PoolEntry:
        """Index a legacy file's measured size (first session after the rebuild)."""
        row = self._index.setdefault(entry.path.name, {})
        row.update({"w": int(width), "h": int(height), "fetched": entry.fetched_at})
        updated = self._entry_for(entry.path, entry.metadata.file_size or 0)
        self._entries = [updated if e.path == entry.path else e for e in self._entries]
        return updated

    def retire(self, entries: Iterable[PoolEntry]) -> List[str]:
        """Hide entries now; their files are deleted at the next session start."""
        names = {entry.path.name for entry in entries}
        if not names:
            return []
        self._retired |= names
        self._entries = [e for e in self._entries if e.path.name not in names]
        return [str(self.cache_dir / name) for name in sorted(names)]

    def remember_rejected(self, image_url: str, size: Optional[Tuple[int, int]]) -> None:
        self._rejected[url_key(image_url)] = [
            int(size[0]) if size else 0, int(size[1]) if size else 0, time.time()]
        if len(self._rejected) > MAX_REJECTED_URLS:
            oldest = sorted(self._rejected, key=lambda k: self._rejected[k][2])
            for key in oldest[: len(self._rejected) - MAX_REJECTED_URLS]:
                del self._rejected[key]

    def is_rejected(self, image_url: str, required: Tuple[int, int]) -> bool:
        """Known not to fill displays of at least ``required`` (or not an image at all)."""
        row = self._rejected.get(url_key(image_url))
        if not row:
            return False
        width, height, stamp = row
        if time.time() - float(stamp) > REJECTED_URL_TTL_DAYS * 86400:
            return False
        if not width or not height:
            return True
        return not (width >= required[0] and height >= required[1])

    def save_state(self) -> None:
        self._write_state()

    # ------------------------------------------------------------------
    # Eviction (bounded; never touches state/ or retired-but-listed files)
    # ------------------------------------------------------------------

    def cleanup(self, min_keep: int = MIN_CACHE_BEFORE_CLEANUP) -> None:
        """Evict the oldest image files when the pool exceeds its count or byte bounds."""
        try:
            in_pool = {entry.path.name for entry in self._entries}
            files = []
            total = 0
            for f in self.cache_dir.iterdir():
                # Retired files stay until the next session start (they may be in
                # this session's history); they are deleted by load_from_disk.
                if f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS and f.name not in self._retired:
                    size = f.stat().st_size
                    files.append((f, size, self._fetched_at(f)))
                    total += size
            max_files = max(min_keep * 2, MAX_CACHED_IMAGES_TO_LOAD)
            if total <= self.max_cache_size and len(files) <= max_files:
                return
            files.sort(key=lambda row: (row[0].name in in_pool, row[2]))  # outside the pool, oldest first
            removable = max(0, len(files) - min_keep)
            removed = 0
            for path, size, _ in files[:removable]:
                if total <= self.max_cache_size * 0.8 and len(files) - removed <= max_files:
                    break
                if path.name in in_pool:
                    self._entries = [e for e in self._entries if e.path.name != path.name]
                self._unlink(path)
                self._index.pop(path.name, None)
                removed += 1
                total -= size
            if removed:
                logger.info(f"[RSS_CACHE] Evicted {removed} files, kept {len(files) - removed}")
            self._write_state()
        except Exception as e:
            logger.error(f"[RSS_CACHE] Cleanup failed: {e}")

    def clear_all(self) -> int:
        """Remove every cached image file (Cache Maintenance). Returns count removed."""
        removed = 0
        for f in list(self.cache_dir.iterdir()):
            if f.is_file():
                self._unlink(f)
                removed += 1
        self._entries = []
        self._index.clear()
        self._retired.clear()
        self._write_state()
        return removed

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @property
    def _state_file(self) -> Path:
        return self.state_dir / "pool.json"

    def _read_state(self) -> None:
        self._index, self._retired, self._rejected = {}, set(), {}
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            logger.warning("[RSS_CACHE] Unreadable pool index replaced")
            return
        if not isinstance(payload, dict) or payload.get("version") != _STATE_VERSION:
            return
        index = payload.get("entries")
        if isinstance(index, dict):
            self._index = {str(k): v for k, v in index.items() if isinstance(v, dict)}
        retired = payload.get("retired")
        if isinstance(retired, list):
            self._retired = {str(name) for name in retired if isinstance(name, str) and "/" not in name
                             and "\\" not in name}
        rejected = payload.get("rejected")
        if isinstance(rejected, dict):
            self._rejected = {str(k): list(v) for k, v in rejected.items()
                              if isinstance(v, list) and len(v) == 3}

    def _write_state(self) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            payload = {"version": _STATE_VERSION, "entries": self._index,
                       "retired": sorted(self._retired), "rejected": self._rejected}
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.state_dir,
                                             prefix=".pool.", suffix=".tmp", delete=False) as handle:
                json.dump(payload, handle, separators=(",", ":"))
                temp = Path(handle.name)
            os.replace(temp, self._state_file)
        except OSError as e:
            logger.warning(f"[RSS_CACHE] Pool index write failed: {e}")

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _validate_image_header(path: Path) -> bool:
        """Quick validation via magic bytes."""
        try:
            with open(path, "rb") as f:
                header = f.read(16)
            return (
                header[:2] == b"\xff\xd8"
                or header[:8] == b"\x89PNG\r\n\x1a\n"
                or header[:4] == b"RIFF"
                or header[:6] in (b"GIF87a", b"GIF89a")
            )
        except OSError:
            return False
