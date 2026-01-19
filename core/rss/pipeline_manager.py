"""
Centralized coordinator for RSS cache paths, deduplication, and cache hygiene.

The manager is a lightweight singleton that holds shared state for the RSS
pipeline so all entry points (engine, sources, UI) interact with the same cache
directory and deduplication policy.
"""
from __future__ import annotations

import tempfile
from collections import defaultdict
from pathlib import Path
from threading import RLock
from typing import Dict, Iterable, Optional, Sequence, Set
from core.logging.logger import get_logger
from sources.base_provider import ImageMetadata

logger = get_logger(__name__)


class RssPipelineManager:
    """Coordinates RSS cache paths, deduplication, and cache clears."""

    _instance: Optional["RssPipelineManager"] = None

    def __init__(self) -> None:
        self._lock = RLock()
        self._cache_dir = self._resolve_default_cache_dir()
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._thread_manager = None
        self._resource_manager = None
        self._settings_manager = None
        self._image_cache = None

        self._dedupe_keys: Dict[str, Set[str]] = defaultdict(set)

    @classmethod
    def get_instance(cls) -> "RssPipelineManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------ setup #
    def initialize(
        self,
        *,
        thread_manager=None,
        resource_manager=None,
        settings_manager=None,
    ) -> None:
        """Attach core managers so the pipeline can follow global policies."""
        with self._lock:
            if settings_manager is not None and settings_manager is not self._settings_manager:
                self._settings_manager = settings_manager
                self._refresh_cache_dir_from_settings()

            if thread_manager is not None:
                self._thread_manager = thread_manager

            if resource_manager is not None:
                self._resource_manager = resource_manager

    def attach_image_cache(self, image_cache) -> None:
        with self._lock:
            self._image_cache = image_cache

    # -------------------------------------------------------------- cache dir #
    def _resolve_default_cache_dir(self) -> Path:
        return Path(tempfile.gettempdir()) / "screensaver_rss_cache"

    def _refresh_cache_dir_from_settings(self) -> None:
        """Refresh the cache directory if settings provide an override."""
        if not self._settings_manager:
            return
        try:
            override = self._settings_manager.get("sources.rss_cache_directory", "").strip()
            if not override:
                return
            override_path = Path(override)
            override_path.mkdir(parents=True, exist_ok=True)
            self._cache_dir = override_path
            logger.info("RssPipelineManager cache dir overridden via settings: %s", override_path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to apply rss_cache_directory override: %s", exc)

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    # ------------------------------------------------------------- dedup keys #
    def rebuild_dedupe_index(self, image_queue, *, namespace: Optional[str] = None) -> None:
        """Rebuild dedupe keys from the current queue snapshot."""
        try:
            snapshot = image_queue.get_all_images()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("[RSS PIPELINE] Failed to snapshot queue for dedupe rebuild: %s", exc)
            return

        keys: Set[str] = set()
        for image in snapshot:
            key = self.build_image_key(image)
            if key:
                keys.add(key)

        with self._lock:
            ns = self._ns(namespace)
            self._dedupe_keys[ns].clear()
            self._dedupe_keys[ns].update(keys)

    def clear_dedupe(self, namespace: Optional[str] = None) -> None:
        with self._lock:
            ns = self._ns(namespace)
            self._dedupe_keys.pop(ns, None)

    def has_key(self, key: str, *, namespace: Optional[str] = None) -> bool:
        with self._lock:
            return key in self._dedupe_keys[self._ns(namespace)]

    def record_images(self, images: Iterable[ImageMetadata], *, namespace: Optional[str] = None) -> None:
        with self._lock:
            ns = self._ns(namespace)
            for image in images:
                key = self.build_image_key(image)
                if key:
                    self._dedupe_keys[ns].add(key)

    def record_image(self, image: ImageMetadata, *, namespace: Optional[str] = None) -> None:
        self.record_images([image], namespace=namespace)

    def record_keys(self, keys: Sequence[str], *, namespace: Optional[str] = None) -> None:
        ns = self._ns(namespace)
        with self._lock:
            self._dedupe_keys[ns].update(key for key in keys if key)

    def build_url_key(self, url: Optional[str]) -> str:
        if not url:
            return ""
        return f"url:{url}"

    def build_image_key(
        self,
        image: Optional[ImageMetadata],
    ) -> str:
        if image is None:
            return ""
        if image.url:
            return self.build_url_key(image.url)
        if image.image_id:
            return f"id:{image.source_id}:{image.image_id}"
        if image.local_path:
            return f"path:{image.local_path}"
        return f"obj:{id(image)}"

    # ---------------------------------------------------------- cache hygiene #
    def count_disk_cache_files(self) -> int:
        if not self._cache_dir.exists():
            return 0
        try:
            return sum(1 for file in self._cache_dir.iterdir() if file.is_file())
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("[RSS PIPELINE] Failed counting cache files: %s", exc)
            return 0

    def clear_cache(
        self,
        *,
        clear_disk: bool = True,
        clear_memory: bool = False,
        image_queue=None,
        namespace: Optional[str] = None,
    ) -> dict:
        """Clear disk and/or in-memory caches and optionally rebuild dedupe keys."""
        files_removed = 0
        memory_cleared = 0

        if clear_disk:
            files_removed = self._clear_disk_cache()
            self.clear_dedupe(namespace=namespace)

        if clear_memory and self._image_cache is not None:
            try:
                memory_cleared = self._image_cache.size()
                self._image_cache.clear()
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("[RSS PIPELINE] Failed clearing ImageCache: %s", exc)

        if image_queue is not None:
            self.rebuild_dedupe_index(image_queue)

        return {
            "disk_files_removed": files_removed,
            "memory_entries_cleared": memory_cleared,
        }

    def _clear_disk_cache(self) -> int:
        if not self._cache_dir.exists():
            return 0

        removed = 0
        for entry in self._cache_dir.glob("*"):
            if not entry.is_file():
                continue
            try:
                entry.unlink()
                removed += 1
            except Exception as exc:
                logger.warning("[RSS PIPELINE] Failed to remove cache file %s: %s", entry, exc)
        logger.info("[RSS PIPELINE] Cleared %d cached RSS files", removed)
        return removed

    # ------------------------------------------------------------ utilities ###
    def _ns(self, namespace: Optional[str]) -> str:
        return namespace or "__global__"

    def is_duplicate(
        self,
        image: Optional[ImageMetadata],
        *,
        pending_keys: Optional[Set[str]] = None,
        namespace: Optional[str] = None,
    ) -> bool:
        key = self.build_image_key(image)
        if not key:
            return False
        if pending_keys and key in pending_keys:
            return True
        return self.has_key(key, namespace=namespace)


def get_rss_pipeline_manager() -> RssPipelineManager:
    """Helper accessor for call sites outside the engine (UI/tests)."""
    return RssPipelineManager.get_instance()
