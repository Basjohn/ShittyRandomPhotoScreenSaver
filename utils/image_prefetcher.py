"""
Image prefetcher built on ThreadManager and ImageCache.

- Decodes images into QImage on IO threads (thread-safe)
- Caches decoded images in an LRU cache
- Prefetches next N images ahead with limited concurrency
- Supports post-transition delay to reduce IO contention
"""
from __future__ import annotations

from typing import List, Optional, Set
import threading
import time
from PySide6.QtGui import QImage

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.threading.manager import ThreadManager, TaskPriority, ThreadPoolType
from utils.image_cache import ImageCache

logger = get_logger(__name__)


class ImagePrefetcher:
    def __init__(
        self,
        thread_manager: ThreadManager,
        cache: ImageCache,
        max_concurrent: int = 2,
        post_transition_delay_ms: float = 100.0,
    ) -> None:
        self._threads = thread_manager
        self._cache = cache
        self._max_concurrent = max(1, int(max_concurrent))
        self._inflight: Set[str] = set()
        self._lock = threading.Lock()
        # Desync: post-transition delay to reduce IO contention
        self._post_transition_delay_ms = max(0.0, float(post_transition_delay_ms))
        self._transition_end_time: float = 0.0

    def notify_transition_complete(self) -> None:
        """Notify prefetcher that a transition just completed.
        
        Prefetching will be delayed by post_transition_delay_ms to reduce
        IO contention with transition rendering.
        """
        self._transition_end_time = time.time()
        if is_perf_metrics_enabled():
            logger.debug("[PERF] ImagePrefetcher: transition complete, delaying prefetch for %.0fms",
                        self._post_transition_delay_ms)

    def _is_in_post_transition_delay(self) -> bool:
        """Check if we're still within the post-transition delay window."""
        if self._post_transition_delay_ms <= 0:
            return False
        elapsed_ms = (time.time() - self._transition_end_time) * 1000
        return elapsed_ms < self._post_transition_delay_ms

    def get_cached(self, path: str) -> Optional[QImage]:
        img = self._cache.get(path)
        if isinstance(img, QImage):
            return img
        return None
    
    def clear_inflight(self) -> None:
        """Clear the inflight set. Call when sources change to avoid stale paths."""
        with self._lock:
            self._inflight.clear()
        if is_verbose_logging():
            logger.debug("Prefetcher inflight set cleared")

    def prefetch_paths(self, paths: List[str]) -> None:
        if not paths:
            return
        # Desync: Skip prefetching during post-transition delay to reduce IO contention
        if self._is_in_post_transition_delay():
            if is_verbose_logging():
                logger.debug("ImagePrefetcher: skipping prefetch due to post-transition delay")
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
        from utils.image_loader import ImageLoader

        def _load_qimage(p: str) -> Optional[QImage]:
            return ImageLoader.load_qimage_silent(p)

        def _on_done(res) -> None:
            # res is TaskResult
            try:
                img: Optional[QImage] = res.result if res and res.success else None
                if img is not None:
                    try:
                        self._cache.put(path, img)
                        if is_verbose_logging():
                            logger.debug(f"Prefetched and cached: {path}")
                    except Exception as e:
                        logger.debug("[MISC] Exception suppressed: %s", e)
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
