"""
Image prefetcher built on ThreadManager and ImageCache.

- Decodes images into QImage on IO threads (thread-safe)
- Caches decoded images in an LRU cache
- Prefetches next N images ahead with limited concurrency
- Supports post-transition delay to reduce IO contention
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
import threading
import time
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QPixmap

from core.logging.logger import (
    get_logger,
    is_cache_logging_enabled,
    is_perf_metrics_enabled,
    is_verbose_logging,
)
from core.threading.manager import ThreadManager, TaskPriority, ThreadPoolType
from rendering.display_modes import DisplayMode
from rendering.image_processor_async import AsyncImageProcessor
from utils.image_cache import ImageCache

logger = get_logger(__name__)


def _cache_trace(message: str, *args: Any) -> None:
    if is_cache_logging_enabled():
        logger.info("[CACHE] " + message, *args)


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
        self._scaled_inflight: Set[str] = set()
        self._pending_scaled_requests: List[Dict[str, Any]] = []
        self._pending_scaled_keys: Set[str] = set()
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
        _cache_trace(
            "Prefetcher transition cool-down armed delay_ms=%d",
            self.get_post_transition_delay_ms(),
        )

    def _is_in_post_transition_delay(self) -> bool:
        """Check if we're still within the post-transition delay window."""
        if self._post_transition_delay_ms <= 0:
            return False
        elapsed_ms = (time.time() - self._transition_end_time) * 1000
        return elapsed_ms < self._post_transition_delay_ms

    def get_post_transition_delay_ms(self) -> int:
        """Return the configured post-transition delay in whole milliseconds."""
        return max(0, int(round(self._post_transition_delay_ms)))

    def get_cached(self, path: str) -> Optional[QImage]:
        img = self._cache.get(path)
        if isinstance(img, QImage):
            return img
        return None
    
    def clear_inflight(self) -> None:
        """Clear the inflight set. Call when sources change to avoid stale paths."""
        with self._lock:
            self._inflight.clear()
            self._scaled_inflight.clear()
            self._pending_scaled_requests.clear()
            self._pending_scaled_keys.clear()
        if is_verbose_logging():
            logger.debug("Prefetcher inflight set cleared")
        _cache_trace("Cleared inflight and pending scaled-prefetch state")

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

    def register_scaled_requests(self, requests: List[Dict[str, Any]]) -> None:
        """Queue scaled-variant warmup requests and process them with bounded concurrency."""
        if not requests:
            return

        queued_any = False
        with self._lock:
            for request in requests:
                cache_key = str(request.get("cache_key") or "")
                raw_path = str(request.get("path") or "")
                if not cache_key or not raw_path:
                    continue
                if self._cache.contains(cache_key):
                    continue
                if cache_key in self._scaled_inflight or cache_key in self._pending_scaled_keys:
                    continue
                self._pending_scaled_requests.append(dict(request))
                self._pending_scaled_keys.add(cache_key)
                queued_any = True

        if queued_any:
            with self._lock:
                pending_total = len(self._pending_scaled_requests)
            _cache_trace("Registered scaled prefetch requests pending=%d", pending_total)
            self._pump_scaled_prefetch()

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
                        self._pump_scaled_prefetch(preferred_path=path)
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

    def _pump_scaled_prefetch(self, preferred_path: Optional[str] = None) -> None:
        if self._is_in_post_transition_delay():
            return

        requests_to_submit: List[Dict[str, Any]] = []
        with self._lock:
            available_slots = self._max_concurrent - len(self._scaled_inflight)
            if available_slots <= 0 or not self._pending_scaled_requests:
                return

            selected_indices: List[int] = []
            if preferred_path:
                for idx, pending in enumerate(self._pending_scaled_requests):
                    if len(selected_indices) >= available_slots:
                        break
                    if pending.get("path") == preferred_path and self._cache.contains(str(pending.get("path") or "")):
                        selected_indices.append(idx)

            for idx, pending in enumerate(self._pending_scaled_requests):
                if len(selected_indices) >= available_slots:
                    break
                if idx in selected_indices:
                    continue
                if self._cache.contains(str(pending.get("path") or "")):
                    selected_indices.append(idx)

            if not selected_indices:
                return

            for idx in reversed(selected_indices):
                request = self._pending_scaled_requests.pop(idx)
                cache_key = str(request.get("cache_key") or "")
                self._pending_scaled_keys.discard(cache_key)
                self._scaled_inflight.add(cache_key)
                requests_to_submit.append(request)

            requests_to_submit.reverse()

        for request in requests_to_submit:
            _cache_trace(
                "Dispatching scaled prefetch path=%s key=%s pending_remaining=%d",
                request.get("path"),
                request.get("cache_key"),
                len(self._pending_scaled_requests),
            )
            self._submit_scaled_request(request)

    def _submit_scaled_request(self, request: Dict[str, Any]) -> None:
        raw_path = str(request.get("path") or "")
        cache_key = str(request.get("cache_key") or "")
        width = int(request.get("width") or 0)
        height = int(request.get("height") or 0)
        display_mode = request.get("display_mode", DisplayMode.FILL)
        if not isinstance(display_mode, DisplayMode):
            display_mode = DisplayMode.from_string(str(display_mode))
        use_lanczos = bool(request.get("use_lanczos", False))
        sharpen = bool(request.get("sharpen", False))

        def _compute_scaled_variant() -> Optional[tuple[str, QPixmap]]:
            try:
                base = self._cache.get(raw_path)
                if isinstance(base, QPixmap) and not base.isNull():
                    base = base.toImage()
                if not isinstance(base, QImage) or base.isNull():
                    return None
                scaled = AsyncImageProcessor.process_qimage(
                    base,
                    QSize(width, height),
                    display_mode,
                    use_lanczos=use_lanczos,
                    sharpen=sharpen,
                )
                if scaled.isNull():
                    return None
                pixmap = QPixmap.fromImage(scaled)
                if pixmap.isNull():
                    return None
                return cache_key, pixmap
            except Exception as e:
                logger.debug("Scaled prefetch compute failed for %s: %s", cache_key, e)
                return None

        def _on_done(res) -> None:
            try:
                payload = res.result if res and res.success else None
                if payload:
                    key, pixmap = payload
                    self._cache.put(key, pixmap)
                    stats = request.get("stats")
                    if isinstance(stats, dict):
                        stats["scaled_prefetch_completed"] = int(stats.get("scaled_prefetch_completed", 0)) + 1
                    if is_perf_metrics_enabled():
                        logger.info(
                            "[PERF] [PREFETCH] Cached scaled variant %s (%dx%d, mode=%s)",
                            key,
                            width,
                            height,
                            display_mode.value,
                        )
                    _cache_trace(
                        "Scaled prefetch completed key=%s target=%dx%d mode=%s",
                        key,
                        width,
                        height,
                        display_mode.value,
                    )
            finally:
                with self._lock:
                    self._scaled_inflight.discard(cache_key)
                self._pump_scaled_prefetch()

        try:
            self._threads.submit_compute_task(
                _compute_scaled_variant,
                priority=TaskPriority.LOW,
                callback=_on_done,
            )
        except Exception as e:
            logger.debug("Scaled prefetch submit failed for %s: %s", cache_key, e)
            with self._lock:
                self._scaled_inflight.discard(cache_key)
            self._pump_scaled_prefetch()
