"""Bounded speculative derivatives, decoded/scaled by the existing ImageWorker.

One admitted source batch feeds all of its planned display variants. The parent
owns intent, cooldown, cache admission and generation fencing, never Qt scaling.
"""
from __future__ import annotations

from typing import Any, Callable
import threading
import time

from PySide6.QtGui import QImage

from core.logging.logger import get_logger, is_cache_logging_enabled
from rendering.display_modes import DisplayMode
from utils.image_cache import ImageCache

logger = get_logger(__name__)
_MIB = 1024 * 1024


def _request_logical_bytes(request: dict[str, Any]) -> int:
    return int(request["width"]) * int(request["height"]) * 4


def _cache_trace(message: str, *args: Any) -> None:
    if is_cache_logging_enabled():
        logger.info("[CACHE] " + message, *args)


class ImagePrefetcher:
    def __init__(
        self,
        cache: ImageCache,
        *,
        derive: Callable[[str, list[dict[str, Any]], int, Callable], Callable[[], None]],
        max_concurrent: int = 2,
        post_transition_delay_ms: float = 100.0,
        max_pending_requests: int | None = None,
        max_pending_scaled_bytes: int | None = None,
    ) -> None:
        self._cache = cache
        self._derive = derive
        budget_slots = max(1, min(4, int(max_concurrent)))
        self._max_pending_requests = min(16, max(
            budget_slots, int(max_pending_requests or budget_slots * 4),
        ))
        cache_budget = max(1, int(getattr(cache, "max_memory_bytes", 256 * _MIB)))
        self._max_pending_scaled_bytes = min(128 * _MIB, max(
            16 * _MIB,
            int(max_pending_scaled_bytes or min(cache_budget // 2, 128 * _MIB)),
        ))
        self._pending_scaled_requests: list[dict[str, Any]] = []
        self._pending_scaled_keys: set[str] = set()
        self._pending_scaled_bytes = 0
        self._scaled_inflight: set[str] = set()
        self._active_batch: object | None = None
        self._active_path: str | None = None
        self._active_generation: int | None = None
        self._active_cancel: Callable[[], None] | None = None
        self._lock = threading.Lock()
        self._prefetch_generation = 0
        self._post_transition_delay_ms = max(0.0, float(post_transition_delay_ms))
        self._transition_end_time = 0.0

    def notify_transition_complete(self) -> None:
        self._transition_end_time = time.monotonic()

    def get_post_transition_delay_ms(self) -> int:
        return max(0, int(round(self._post_transition_delay_ms)))

    def get_remaining_post_transition_delay_ms(self) -> int:
        elapsed_ms = (time.monotonic() - self._transition_end_time) * 1000
        return max(0, int(round(self._post_transition_delay_ms - elapsed_ms)))

    def is_in_post_transition_delay(self) -> bool:
        return self.get_remaining_post_transition_delay_ms() > 0

    def snapshot_state(self) -> dict[str, int]:
        with self._lock:
            return {
                "scaled_inflight": len(self._scaled_inflight),
                "scaled_pending": len(self._pending_scaled_requests),
            }

    def snapshot_budget_state(self) -> dict[str, int]:
        with self._lock:
            return {
                "scaled_pending": len(self._pending_scaled_requests),
                "scaled_pending_bytes": self._pending_scaled_bytes,
                "max_pending_requests": self._max_pending_requests,
                "max_pending_scaled_bytes": self._max_pending_scaled_bytes,
            }

    def clear_inflight(self) -> None:
        with self._lock:
            self._prefetch_generation += 1
            self._pending_scaled_requests.clear()
            self._pending_scaled_keys.clear()
            self._pending_scaled_bytes = 0
            self._scaled_inflight.clear()
            cancel = self._active_cancel
            self._active_batch = None
            self._active_path = None
            self._active_generation = None
            self._active_cancel = None
        if cancel is not None:
            cancel()
        _cache_trace("Invalidated prefetch generation and cleared derivative intents")

    def _prune_pending_locked(self) -> None:
        retained = [
            request for request in self._pending_scaled_requests
            if request["_prefetch_generation"] == self._prefetch_generation
            and not self._cache.contains(request["cache_key"])
        ]
        self._pending_scaled_requests = retained
        self._pending_scaled_keys = {request["cache_key"] for request in retained}
        self._pending_scaled_bytes = sum(map(_request_logical_bytes, retained))

    def register_scaled_requests(self, requests: list[dict[str, Any]]) -> int:
        """Admit complete per-source groups, bounded by count and RGBA bytes."""
        groups: dict[str, list[dict[str, Any]]] = {}
        for request in requests:
            owned = dict(request)
            path, key = str(owned["path"]), str(owned["cache_key"])
            width, height = int(owned["width"]), int(owned["height"])
            mode = owned["display_mode"]
            if not isinstance(mode, DisplayMode):
                mode = DisplayMode.from_string(str(mode))
            if not path or not key or width <= 0 or height <= 0:
                raise ValueError("scaled-prefetch request has invalid path/cache/geometry")
            if not isinstance(owned["use_lanczos"], bool) or not isinstance(owned["sharpen"], bool):
                raise TypeError("scaled-prefetch quality fields must be resolved booleans")
            # Preserve the foreground quality authority. No speculative PIL or
            # parent-process fallback is admitted for these requests.
            if owned["use_lanczos"] or owned["sharpen"]:
                continue
            owned.update(path=path, cache_key=key, width=width, height=height, display_mode=mode)
            groups.setdefault(path, []).append(owned)

        queued = 0
        with self._lock:
            self._prune_pending_locked()
            for path, group in groups.items():
                # A late variant cannot cause another decode of an active source.
                # The next preview registration can admit it after retirement.
                if path == self._active_path and self._active_generation == self._prefetch_generation:
                    continue
                unique: dict[str, dict[str, Any]] = {}
                for request in group:
                    key = request["cache_key"]
                    if key not in self._pending_scaled_keys and not self._cache.contains(key):
                        unique.setdefault(key, request)
                admitted = list(unique.values())
                needed = sum(map(_request_logical_bytes, admitted))
                if (
                    len(self._pending_scaled_requests) + len(admitted) > self._max_pending_requests
                    or self._pending_scaled_bytes + needed > self._max_pending_scaled_bytes
                ):
                    _cache_trace("Skipped source batch at prefetch budget path=%s derivatives=%d bytes=%d", path, len(admitted), needed)
                    continue
                for request in admitted:
                    request["_prefetch_generation"] = self._prefetch_generation
                    self._pending_scaled_requests.append(request)
                    self._pending_scaled_keys.add(request["cache_key"])
                self._pending_scaled_bytes += needed
                queued += len(admitted)
        self._pump_scaled_prefetch()
        return queued

    def _pump_scaled_prefetch(self) -> None:
        with self._lock:
            self._prune_pending_locked()
            if self._active_batch is not None or self.is_in_post_transition_delay() or not self._pending_scaled_requests:
                return
            path = self._pending_scaled_requests[0]["path"]
            requests = [request for request in self._pending_scaled_requests if request["path"] == path]
            self._pending_scaled_requests = [request for request in self._pending_scaled_requests if request["path"] != path]
            self._prune_pending_locked()
            generation = self._prefetch_generation
            token = object()
            self._active_batch = token
            self._active_path = path
            self._active_generation = generation
            self._scaled_inflight = {request["cache_key"] for request in requests}

        def _on_done(images: dict[str, QImage], error: Exception | None = None) -> None:
            try:
                if error is not None:
                    logger.error("[PREFETCH] Worker derivative batch failed path=%s: %s", path, error)
                    return
                with self._lock:
                    if generation != self._prefetch_generation or self._active_batch is not token:
                        return
                    for request in requests:
                        key = request["cache_key"]
                        image = images.get(key)
                        if image is None:
                            continue
                        if not isinstance(image, QImage) or image.isNull():
                            raise TypeError("worker derivative must be a non-null QImage")
                        self._cache.put(key, image)
                        if self._cache.contains(key):
                            stats = request.get("stats")
                            if isinstance(stats, dict):
                                stats["scaled_prefetch_completed"] = int(stats.get("scaled_prefetch_completed", 0)) + 1
            finally:
                with self._lock:
                    if self._active_batch is token:
                        self._active_batch = None
                        self._active_path = None
                        self._active_generation = None
                        self._active_cancel = None
                        self._scaled_inflight.clear()
                self._pump_scaled_prefetch()

        try:
            cancel = self._derive(path, requests, generation, _on_done)
            if not callable(cancel):
                raise TypeError("prefetch derivative submission must return its cancellation handle")
            with self._lock:
                still_current = self._active_batch is token
                if still_current:
                    self._active_cancel = cancel
            # A clear or synchronous completion can race submission. Never
            # attach a previous correlation's handle to the next source owner.
            if not still_current:
                cancel()
        except Exception:
            with self._lock:
                if self._active_batch is token:
                    self._active_batch = None
                    self._active_path = None
                    self._active_generation = None
                    self._active_cancel = None
                    self._scaled_inflight.clear()
            logger.exception("[PREFETCH] Failed to submit worker derivative batch path=%s", path)
            raise
