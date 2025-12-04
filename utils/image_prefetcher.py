"""
Image prefetcher built on ThreadManager and ImageCache.

- Decodes images into QImage on IO threads (thread-safe)
- Caches decoded images in an LRU cache
- Prefetches next N images ahead with limited concurrency
"""
from __future__ import annotations

from typing import List, Optional, Set
import threading
from PySide6.QtGui import QImage

from core.logging.logger import get_logger, is_verbose_logging
from core.threading.manager import ThreadManager, TaskPriority, ThreadPoolType
from utils.image_cache import ImageCache

logger = get_logger(__name__)


class ImagePrefetcher:
    def __init__(
        self,
        thread_manager: ThreadManager,
        cache: ImageCache,
        max_concurrent: int = 2,
    ) -> None:
        self._threads = thread_manager
        self._cache = cache
        self._max_concurrent = max(1, int(max_concurrent))
        self._inflight: Set[str] = set()
        self._lock = threading.Lock()

    def get_cached(self, path: str) -> Optional[QImage]:
        img = self._cache.get(path)
        if isinstance(img, QImage):
            return img
        return None

    def prefetch_paths(self, paths: List[str]) -> None:
        if not paths:
            return
        # Submit up to max_concurrent new loads that are not already cached or in-flight
        submitted = 0
        for p in paths:
            if not p:
                continue
            if self._cache.contains(p):
                continue
            with self._lock:
                if p in self._inflight:
                    continue
                if submitted >= self._max_concurrent:
                    break
                self._inflight.add(p)
            self._submit_load(p)
            submitted += 1

    def _submit_load(self, path: str) -> None:
        # inflight is already marked by caller under lock

        def _load_qimage(p: str) -> Optional[QImage]:
            try:
                img = QImage(p)
                if img.isNull():
                    logger.warning(f"Prefetch decode failed for: {p}")
                    return None
                return img
            except Exception as e:
                logger.exception(f"Prefetch load failed for {p}: {e}")
                return None

        def _on_done(res) -> None:
            # res is TaskResult
            try:
                img: Optional[QImage] = res.result if res and res.success else None
                if img is not None:
                    try:
                        self._cache.put(path, img)
                        if is_verbose_logging():
                            logger.debug(f"Prefetched and cached: {path}")
                    except Exception:
                        pass
            finally:
                with self._lock:
                    self._inflight.discard(path)

        try:
            self._threads.submit_task(
                ThreadPoolType.IO,
                _load_qimage,
                path,
                priority=TaskPriority.LOW,
                callback=_on_done,
            )
        except Exception as e:
            logger.debug(f"Prefetch submit failed for {path}: {e}")
            with self._lock:
                self._inflight.discard(path)
