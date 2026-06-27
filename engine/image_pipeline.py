"""Image Loading Pipeline - Extracted from screensaver_engine.py.

Contains image loading, prescaling, prefetching, and display coordination
logic. All functions accept the engine instance as the first parameter
to preserve the original interface.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import time

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QPixmap, QImage

from core.logging.logger import (
    get_logger,
    is_cache_logging_enabled,
    is_perf_metrics_enabled,
    is_verbose_logging,
)
from core.logging.tags import TAG_WORKER, TAG_PERF, TAG_ASYNC
from core.constants.timing import TRANSITION_STAGGER_MS
from core.process.types import WorkerType, MessageType
from core.settings import SettingsManager
from rendering.display_modes import DisplayMode
from rendering.image_processor_async import AsyncImageProcessor
from sources.base_provider import ImageMetadata

if TYPE_CHECKING:
    from engine.screensaver_engine import ScreensaverEngine

logger = get_logger(__name__)


def _cache_trace(message: str, *args: Any, level: int = logging.INFO) -> None:
    if is_cache_logging_enabled():
        logger.log(level, "[CACHE] " + message, *args)


# ------------------------------------------------------------------
# Cache helpers
# ------------------------------------------------------------------

def _normalize_display_mode(display_mode: Any) -> DisplayMode:
    if isinstance(display_mode, DisplayMode):
        return display_mode
    return DisplayMode.from_string(str(display_mode or DisplayMode.FILL.value))


def _build_scaled_cache_key(
    image_path: str,
    target_width: int,
    target_height: int,
    display_mode: DisplayMode,
    use_lanczos: bool,
    sharpen: bool,
) -> str:
    mode = _normalize_display_mode(display_mode)
    return (
        f"{image_path}|scaled:{mode.value}:{target_width}x{target_height}"
        f":l{1 if use_lanczos else 0}:s{1 if sharpen else 0}"
    )


def _ensure_cache_runtime_stats(engine: ScreensaverEngine) -> Dict[str, int]:
    stats = getattr(engine, "_cache_runtime_stats", None)
    if isinstance(stats, dict):
        return stats
    stats = {
        "raw_hits": 0,
        "raw_misses": 0,
        "scaled_hits": 0,
        "scaled_misses": 0,
        "worker_fallbacks": 0,
        "prefetch_resume_scheduled": 0,
        "prefetch_resume_runs": 0,
        "scaled_prefetch_requests": 0,
        "scaled_prefetch_completed": 0,
        "scaled_derivations": 0,
    }
    setattr(engine, "_cache_runtime_stats", stats)
    return stats


def _bump_cache_runtime_stat(engine: ScreensaverEngine, key: str, amount: int = 1) -> None:
    stats = _ensure_cache_runtime_stats(engine)
    stats[key] = int(stats.get(key, 0)) + amount


def _probe_cache(
    engine: ScreensaverEngine,
    cache_key: str,
    *,
    bucket: str,
) -> Optional[QPixmap | QImage]:
    cache = getattr(engine, "_image_cache", None)
    if cache is None or not cache_key:
        return None
    cached = cache.get(cache_key)
    if cached is None:
        _bump_cache_runtime_stat(engine, f"{bucket}_misses")
    else:
        _bump_cache_runtime_stat(engine, f"{bucket}_hits")
    return cached


def _get_display_quality_settings(engine: ScreensaverEngine) -> tuple[bool, bool]:
    use_lanczos = True
    sharpen = False
    if engine.settings_manager:
        use_lanczos = SettingsManager.to_bool(
            engine.settings_manager.get("display.use_lanczos", True),
            True,
        )
        sharpen = SettingsManager.to_bool(
            engine.settings_manager.get("display.sharpen_downscale", False),
            False,
        )
    return use_lanczos, sharpen


def _get_prefetch_target_specs(engine: ScreensaverEngine) -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []
    display_manager = getattr(engine, "display_manager", None)
    displays = getattr(display_manager, "displays", None) or []
    seen: set[tuple[int, int, str]] = set()
    for display in displays:
        try:
            if hasattr(display, "get_target_size"):
                target_size = display.get_target_size()
            else:
                dpr = getattr(display, "_device_pixel_ratio", 1.0)
                target_size = QSize(
                    int(display.width() * dpr),
                    int(display.height() * dpr),
                )
            width = int(target_size.width())
            height = int(target_size.height())
            if width <= 0 or height <= 0:
                continue
            mode = _normalize_display_mode(getattr(display, "display_mode", DisplayMode.FILL))
            signature = (width, height, mode.value)
            if signature in seen:
                continue
            seen.add(signature)
            specs.append(
                {
                    "width": width,
                    "height": height,
                    "display_mode": mode,
                }
            )
        except Exception as e:
            logger.debug("[PREFETCH] Failed to inspect display target size: %s", e)
    return specs


def _get_prefetch_target_specs_in_display_order(engine: ScreensaverEngine) -> List[Dict[str, Any]]:
    """Return ordered display target specs without cross-product fan-out."""
    specs: List[Dict[str, Any]] = []
    display_manager = getattr(engine, "display_manager", None)
    displays = getattr(display_manager, "displays", None) or []
    for display in displays:
        try:
            if hasattr(display, "get_target_size"):
                target_size = display.get_target_size()
            else:
                dpr = getattr(display, "_device_pixel_ratio", 1.0)
                target_size = QSize(
                    int(display.width() * dpr),
                    int(display.height() * dpr),
                )
            width = int(target_size.width())
            height = int(target_size.height())
            if width <= 0 or height <= 0:
                continue
            specs.append(
                {
                    "width": width,
                    "height": height,
                    "display_mode": _normalize_display_mode(getattr(display, "display_mode", DisplayMode.FILL)),
                }
            )
        except Exception as e:
            logger.debug("[PREFETCH] Failed to inspect ordered display target size: %s", e)
    return specs


def _get_prefetch_request_plan(engine: ScreensaverEngine, paths: List[str]) -> List[tuple[str, Dict[str, Any]]]:
    """Plan scaled warmup requests using the same broad image-consumption contract as runtime.

    The previous implementation built a full cross-product of preview paths and
    display target specs, which floods scaled warmup with requests that are
    unlikely to complete before the next transition. We instead prioritize the
    images the runtime will actually consume next:
    - different-images mode: map preview order onto display order in round-robin
    - same-image mode: warm the first preview image for every distinct display
      target, then keep later previews on the primary target only
    """
    if not paths:
        return []

    ordered_specs = _get_prefetch_target_specs_in_display_order(engine)
    if not ordered_specs:
        return []

    raw_same_image = True
    settings_manager = getattr(engine, "settings_manager", None)
    if settings_manager is not None:
        raw_same_image = settings_manager.get("display.same_image_all_monitors", True)
    same_image = SettingsManager.to_bool(raw_same_image, True)

    if not same_image:
        return [
            (path, ordered_specs[idx % len(ordered_specs)])
            for idx, path in enumerate(paths)
        ]

    distinct_specs: List[Dict[str, Any]] = []
    seen_signatures: set[tuple[int, int, str]] = set()
    for spec in ordered_specs:
        signature = (spec["width"], spec["height"], spec["display_mode"].value)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        distinct_specs.append(spec)

    plan: List[tuple[str, Dict[str, Any]]] = [(paths[0], spec) for spec in distinct_specs]
    primary_spec = distinct_specs[0]
    for path in paths[1:]:
        plan.append((path, primary_spec))
    return plan


def _build_prefetch_scaled_requests(
    engine: ScreensaverEngine,
    paths: List[str],
) -> List[Dict[str, Any]]:
    cache = getattr(engine, "_image_cache", None)
    if cache is None or not paths:
        return []

    use_lanczos, sharpen = _get_display_quality_settings(engine)
    requests: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for path, spec in _get_prefetch_request_plan(engine, paths):
        cache_key = _build_scaled_cache_key(
            path,
            spec["width"],
            spec["height"],
            spec["display_mode"],
            use_lanczos,
            sharpen,
        )
        if cache_key in seen_keys or cache.contains(cache_key):
            continue
        seen_keys.add(cache_key)
        requests.append(
            {
                "stats": _ensure_cache_runtime_stats(engine),
                "path": path,
                "cache_key": cache_key,
                "width": spec["width"],
                "height": spec["height"],
                "display_mode": spec["display_mode"],
                "use_lanczos": use_lanczos,
                "sharpen": sharpen,
            }
        )
    if requests:
        _cache_trace(
            "Prepared scaled warmup requests count=%d unique_paths=%d",
            len(requests),
            len(paths),
        )
    return requests


def _derive_scaled_pixmap_from_raw_cache(
    engine: ScreensaverEngine,
    image_path: str,
    source_image: Optional[QImage],
    target_size: QSize,
    display_mode: DisplayMode,
    use_lanczos: bool,
    sharpen: bool,
) -> Optional[QPixmap]:
    if source_image is None or source_image.isNull():
        return None
    scaled_qimage = AsyncImageProcessor.process_qimage(
        source_image,
        target_size,
        display_mode,
        use_lanczos=use_lanczos,
        sharpen=sharpen,
    )
    if scaled_qimage.isNull():
        return None
    scaled_pixmap = QPixmap.fromImage(scaled_qimage)
    if scaled_pixmap.isNull():
        return None
    cache = getattr(engine, "_image_cache", None)
    if cache is not None:
        scaled_key = _build_scaled_cache_key(
            image_path,
            target_size.width(),
            target_size.height(),
            display_mode,
            use_lanczos,
            sharpen,
        )
        cache.put(scaled_key, scaled_pixmap)
    _bump_cache_runtime_stat(engine, "scaled_derivations")
    _cache_trace(
        "Derived scaled variant from raw cache path=%s target=%dx%d mode=%s lanczos=%s sharpen=%s",
        image_path,
        target_size.width(),
        target_size.height(),
        display_mode.value,
        int(use_lanczos),
        int(sharpen),
    )
    return scaled_pixmap


def _describe_prefetcher_state(engine: ScreensaverEngine) -> str:
    prefetcher = getattr(engine, "_prefetcher", None)
    snapshot = None
    if prefetcher is not None:
        snapshot_state = getattr(prefetcher, "snapshot_state", None)
        if callable(snapshot_state):
            try:
                snapshot = snapshot_state()
            except Exception as exc:
                logger.debug("[CACHE] Failed to snapshot prefetcher state: %s", exc)
    if not isinstance(snapshot, dict):
        return "prefetch_state=unavailable"
    return (
        "prefetch_state="
        f"raw_inflight:{int(snapshot.get('raw_inflight', 0))},"
        f"raw_pending:{int(snapshot.get('raw_pending', 0))},"
        f"scaled_inflight:{int(snapshot.get('scaled_inflight', 0))},"
        f"scaled_pending:{int(snapshot.get('scaled_pending', 0))}"
    )


def _get_cached_pixmap_variants(
    engine: ScreensaverEngine,
    image_path: str,
    target_width: int,
    target_height: int,
    display_mode: DisplayMode,
    use_lanczos: bool,
    sharpen: bool,
) -> tuple[Optional[QPixmap], Optional[QPixmap]]:
    """Return cached processed/original pixmaps when available.

    The async display path historically ignored the pre-scaled cache variants and
    always paid ImageWorker prescale cost on image change. This helper keeps one
    cache contract for both the sync and async paths:
    - prefer the display-ready scaled cache key for the processed pixmap
    - fall back to the raw-path cached image for the original pixmap
    """
    cache = getattr(engine, "_image_cache", None)
    if cache is None or not image_path:
        return None, None

    processed_pixmap: Optional[QPixmap] = None
    original_pixmap: Optional[QPixmap] = None
    scaled_key = _build_scaled_cache_key(
        image_path,
        target_width,
        target_height,
        display_mode,
        use_lanczos,
        sharpen,
    )

    def _coerce_cached_pixmap(cache_key: str) -> Optional[QPixmap]:
        bucket = "scaled" if cache_key == scaled_key else "raw"
        cached = _probe_cache(engine, cache_key, bucket=bucket)
        if isinstance(cached, QPixmap) and not cached.isNull():
            return cached
        if isinstance(cached, QImage) and not cached.isNull():
            try:
                pm = QPixmap.fromImage(cached)
                if not pm.isNull():
                    if cache_key == scaled_key:
                        cache.put(cache_key, pm)
                    return pm
            except Exception as e:
                logger.debug("[ASYNC] Failed to convert cached QImage for %s: %s", cache_key, e)
        return None

    processed_pixmap = _coerce_cached_pixmap(scaled_key)
    original_pixmap = _coerce_cached_pixmap(image_path)

    if processed_pixmap is not None:
        _cache_trace(
            "Scaled cache hit path=%s target=%dx%d mode=%s lanczos=%s sharpen=%s",
            image_path,
            target_width,
            target_height,
            display_mode.value,
            int(use_lanczos),
            int(sharpen),
        )
    else:
        _cache_trace(
            "Scaled cache miss path=%s target=%dx%d mode=%s lanczos=%s sharpen=%s",
            image_path,
            target_width,
            target_height,
            display_mode.value,
            int(use_lanczos),
            int(sharpen),
        )

    if processed_pixmap is not None and original_pixmap is None:
        original_pixmap = processed_pixmap

    return processed_pixmap, original_pixmap


# ------------------------------------------------------------------
# ImageWorker-based loading
# ------------------------------------------------------------------

def load_image_via_worker(
    engine: ScreensaverEngine,
    image_path: str,
    target_width: int,
    target_height: int,
    display_mode: str = "fill",
    sharpen: bool = False,
    timeout_ms: int = 500,
) -> Optional[QImage]:
    """
    Load and prescale image using ImageWorker process.

    Uses the ImageWorker for decode/prescale in a separate process,
    avoiding GIL contention. Falls back to None if worker unavailable.

    Args:
        engine: ScreensaverEngine instance
        image_path: Path to image file
        target_width: Target width in pixels
        target_height: Target height in pixels
        display_mode: Display mode (fill, fit, shrink)
        sharpen: Whether to apply sharpening
        timeout_ms: Timeout for worker response

    Returns:
        QImage if successful, None if worker unavailable or failed
    """
    if not engine._process_supervisor or not engine._process_supervisor.is_running(WorkerType.IMAGE):
        return None

    try:
        # Get quality settings from settings manager
        use_lanczos = True
        if engine.settings_manager:
            use_lanczos = engine.settings_manager.get('display.use_lanczos', True)
            if isinstance(use_lanczos, str):
                use_lanczos = use_lanczos.lower() == 'true'

        response = engine._process_supervisor.send_request_and_await_response(
            WorkerType.IMAGE,
            MessageType.IMAGE_PRESCALE,
            payload={
                "path": image_path,
                "target_width": target_width,
                "target_height": target_height,
                "mode": display_mode,
                "use_lanczos": use_lanczos,
                "sharpen": sharpen,
            },
            timeout_ms=timeout_ms,
        )

        if not response:
            logger.warning(f"{TAG_WORKER} ImageWorker timeout after %dms", timeout_ms)
            return None

        if response.success:
            payload = response.payload
            width = payload.get("width", 0)
            height = payload.get("height", 0)

            if width <= 0 or height <= 0:
                logger.warning(f"{TAG_WORKER} ImageWorker returned invalid dimensions")
                return None

            # Check for shared memory response (large images)
            shm_name = payload.get("shared_memory_name")
            if shm_name:
                try:
                    from multiprocessing.shared_memory import SharedMemory
                    shm_size = payload.get("shared_memory_size", width * height * 4)
                    shm = SharedMemory(name=shm_name, create=False)
                    rgba_data = bytes(shm.buf[:shm_size])
                    shm.close()
                    # Don't unlink - worker will clean up

                    if is_perf_metrics_enabled():
                        logger.debug(
                            f"{TAG_PERF} {TAG_WORKER} ImageWorker used shared memory: %.1f MB",
                            shm_size / (1024 * 1024)
                        )
                except Exception as shm_err:
                    logger.warning(f"{TAG_WORKER} Failed to read shared memory: %s", shm_err)
                    return None
            else:
                # Queue-based transfer (smaller images)
                rgba_data = payload.get("rgba_data")

            if rgba_data and width > 0 and height > 0:
                qimage = QImage(
                    rgba_data,
                    width,
                    height,
                    width * 4,  # bytes per line
                    QImage.Format.Format_RGBA8888,
                )
                # Make a deep copy since rgba_data may be invalidated
                qimage = qimage.copy()

                if is_perf_metrics_enabled():
                    proc_time = response.processing_time_ms or 0
                    logger.info(
                        f"{TAG_PERF} {TAG_WORKER} ImageWorker prescale: %dx%d in %.1fms",
                        width, height, proc_time
                    )

                return qimage
        else:
            error = response.error or "Unknown error"
            logger.warning(f"{TAG_WORKER} ImageWorker failed: %s", error)
            return None

    except Exception as e:
        logger.warning(f"{TAG_WORKER} ImageWorker error: %s", e)
        return None


# ------------------------------------------------------------------
# Image task loading (IO thread)
# ------------------------------------------------------------------

def load_image_task(
    engine: ScreensaverEngine,
    image_meta: ImageMetadata,
    preferred_size: Optional[tuple] = None,
) -> Optional[QPixmap]:
    """
    Load image task (runs in thread pool).

    Args:
        engine: ScreensaverEngine instance
        image_meta: Image metadata
        preferred_size: Optional (width, height) tuple for preferred display size

    Returns:
        Loaded QPixmap or None if failed
    """
    try:
        # Determine path
        if image_meta.local_path:
            image_path = str(image_meta.local_path)
        elif image_meta.url:
            logger.debug(f"Loading from URL: {image_meta.url}")
            if not image_meta.local_path:
                logger.warning("[CACHE][FALLBACK] No local path for URL image")
                return None
            image_path = str(image_meta.local_path)
        else:
            logger.warning("[CACHE][FALLBACK] No path or URL for image")
            return None

        # Use cache if available (QImage decoded on IO thread)
        pixmap: Optional[QPixmap] = None
        if engine._prefetcher and engine._image_cache:
            # Prefer a pre-scaled variant for this display if present
            try:
                size = preferred_size or engine._get_primary_display_size()
                use_lanczos, sharpen = _get_display_quality_settings(engine)
                display_mode = _normalize_display_mode(
                    engine.settings_manager.get("display.mode", DisplayMode.FILL.value)
                    if engine.settings_manager
                    else DisplayMode.FILL
                )
                if size:
                    w, h = size
                    scaled_key = _build_scaled_cache_key(
                        image_path,
                        w,
                        h,
                        display_mode,
                        use_lanczos,
                        sharpen,
                    )
                    scaled_cached = engine._image_cache.get(scaled_key)
                    if isinstance(scaled_cached, QPixmap):
                        pixmap = scaled_cached
                    elif isinstance(scaled_cached, QImage) and not scaled_cached.isNull() and engine.thread_manager:
                        pm = QPixmap.fromImage(scaled_cached)
                        if not pm.isNull():
                            engine._image_cache.put(scaled_key, pm)
                            pixmap = pm
                            # Clear QImage reference to free memory (Section 1.1 fix)
                            scaled_cached = None
            except Exception as _e:
                logger.debug("[ENGINE] Exception suppressed: %s", _e)
                pixmap = None

            if pixmap is None or pixmap.isNull():
                cached = engine._image_cache.get(image_path)
                if isinstance(cached, QPixmap):
                    pixmap = cached
                elif isinstance(cached, QImage) and not cached.isNull():
                    try:
                        pm = QPixmap.fromImage(cached)
                        if not pm.isNull():
                            pixmap = pm
                            # Clear QImage reference to free memory (Section 1.1 fix)
                            cached = None
                    except Exception as e:
                        logger.debug("[ENGINE] Exception suppressed: %s", e)
                        pixmap = None
                if pixmap is None:
                    pixmap = QPixmap(image_path)
        else:
            pixmap = QPixmap(image_path)

        if pixmap.isNull():
            logger.warning("Image load failed for: %s", image_path)
            return None

        logger.debug(f"Image loaded: {image_path} ({pixmap.width()}x{pixmap.height()})")
        return pixmap

    except Exception as e:
        logger.exception(f"Image load task failed: {e}")
        return None


# ------------------------------------------------------------------
# Async image loading and display
# ------------------------------------------------------------------

def load_and_display_image_async(
    engine: ScreensaverEngine,
    image_meta: ImageMetadata,
    retry_count: int = 0,
) -> None:
    """
    Load and display image asynchronously. Processes image on background thread.

    ARCHITECTURAL NOTE: This method moves heavy image processing off the UI thread
    to eliminate frame timing spikes during image changes. The flow is:
    1. Load QImage on IO thread (or from cache)
    2. Process/scale QImage on COMPUTE thread
    3. Convert to QPixmap and display on UI thread

    For "different images on each monitor" mode, this loads separate images for
    each display from the queue.

    Args:
        engine: ScreensaverEngine instance
        image_meta: Image metadata for first display
        retry_count: Number of retries attempted (max 10)
    """
    if not engine.thread_manager or not engine.display_manager:
        # Fall back to sync path if no thread manager
        load_and_display_image(engine, image_meta, retry_count)
        return

    # Check same_image setting to determine how many images to load
    raw_same_image = engine.settings_manager.get('display.same_image_all_monitors', True)
    same_image = SettingsManager.to_bool(raw_same_image, True)

    # Build list of images to load - one per display if different images mode
    displays = engine.display_manager.displays if engine.display_manager else []
    image_metas = [image_meta]  # First display gets the provided image

    if not same_image and len(displays) > 1:
        # Load different images for each additional display
        used_paths = set()
        first_path = str(image_meta.local_path) if image_meta.local_path else (image_meta.url or "")
        used_paths.add(first_path)

        for i in range(1, len(displays)):
            next_meta = None
            for attempt in range(5):
                candidate = engine.image_queue.next() if engine.image_queue else None
                if not candidate:
                    break

                candidate_path = str(candidate.local_path) if candidate.local_path else (candidate.url or "")
                if candidate_path not in used_paths:
                    next_meta = candidate
                    used_paths.add(candidate_path)
                    break
                elif attempt < 4:
                    logger.debug(f"{TAG_ASYNC} Skipping duplicate image for display {i}, attempt {attempt + 1}")
                else:
                    next_meta = candidate
                    logger.warning(f"{TAG_ASYNC} Could not find unique image for display {i} after 5 attempts")

            if next_meta:
                image_metas.append(next_meta)
            else:
                image_metas.append(image_meta)
                logger.warning(f"{TAG_ASYNC} Queue empty, reusing first image for display {i}")

        logger.debug(f"{TAG_ASYNC} Loading {len(image_metas)} different images for {len(displays)} displays")

    def _do_load_and_process() -> Optional[Dict]:
        """Background task: load and process images for all displays."""
        try:
            processed_images = {}
            display_list = engine.display_manager.displays if engine.display_manager else []

            # Get quality settings
            use_lanczos, sharpen = _get_display_quality_settings(engine)

            for i, display in enumerate(display_list):
                meta = image_metas[i] if i < len(image_metas) else image_metas[0]
                img_path = str(meta.local_path) if meta.local_path else (meta.url or "")

                if not img_path:
                    logger.warning(f"{TAG_ASYNC} No path for display {i}")
                    continue

                # Load QImage (thread-safe)
                qimage: Optional[QImage] = None

                # Try cache first
                if engine._image_cache:
                    cached = engine._image_cache.get(img_path)
                    if isinstance(cached, QImage) and not cached.isNull():
                        qimage = cached
                    elif isinstance(cached, QPixmap) and not cached.isNull():
                        qimage = cached.toImage()

                # Validate file exists before trying worker
                if qimage is None or qimage.isNull():
                    from pathlib import Path
                    if not Path(img_path).exists():
                        logger.warning(f"{TAG_ASYNC} Image file not found: {img_path}")
                        for retry in range(3):
                            replacement = engine.image_queue.next() if engine.image_queue else None
                            if replacement and replacement.local_path:
                                replacement_path = str(replacement.local_path)
                                if Path(replacement_path).exists():
                                    img_path = replacement_path
                                    meta = replacement
                                    logger.info(f"{TAG_ASYNC} Using replacement image for display {i}: {Path(replacement_path).name}")
                                    break

                        if not Path(img_path).exists():
                            logger.warning(f"{TAG_ASYNC} No valid replacement found for display {i}")
                            continue

                try:
                    # Get target size from display
                    if hasattr(display, 'get_target_size'):
                        target_size = display.get_target_size()
                    else:
                        dpr = getattr(display, '_device_pixel_ratio', 1.0)
                        target_size = QSize(
                            int(display.width() * dpr),
                            int(display.height() * dpr)
                        )

                    # Get display mode
                    display_mode = _normalize_display_mode(getattr(display, 'display_mode', DisplayMode.FILL))
                    display_mode_str = display_mode.value

                    processed_pixmap, original_pixmap = _get_cached_pixmap_variants(
                        engine,
                        img_path,
                        target_size.width(),
                        target_size.height(),
                        display_mode,
                        use_lanczos,
                        sharpen,
                    )

                    if processed_pixmap is None or processed_pixmap.isNull():
                        processed_qimage = None
                        fallback_reason = "scaled_miss"

                        if qimage is not None and not qimage.isNull():
                            processed_pixmap = _derive_scaled_pixmap_from_raw_cache(
                                engine,
                                img_path,
                                qimage,
                                target_size,
                                display_mode,
                                use_lanczos,
                                sharpen,
                            )
                            if processed_pixmap is not None:
                                fallback_reason = "derived_from_raw_cache"

                        if processed_pixmap is None and engine._process_supervisor and engine._process_supervisor.is_running(WorkerType.IMAGE):
                            _bump_cache_runtime_stat(engine, "worker_fallbacks")
                            raw_state = "raw_cached" if qimage is not None and not qimage.isNull() else "raw_missing"
                            _cache_trace(
                                "[FALLBACK] Worker fallback display=%d reason=%s raw_state=%s %s path=%s target=%dx%d mode=%s",
                                i,
                                fallback_reason,
                                raw_state,
                                _describe_prefetcher_state(engine),
                                img_path,
                                target_size.width(),
                                target_size.height(),
                                display_mode_str,
                                level=logging.WARNING,
                            )
                            worker_qimage = load_image_via_worker(
                                engine,
                                img_path,
                                target_size.width(),
                                target_size.height(),
                                display_mode=display_mode_str,
                                sharpen=sharpen,
                                timeout_ms=3000,
                            )
                            if worker_qimage and not worker_qimage.isNull():
                                processed_qimage = worker_qimage
                                logger.debug(f"{TAG_ASYNC} Image loaded via ImageWorker for display {i}")
                            else:
                                logger.warning(f"{TAG_ASYNC} ImageWorker failed for display {i}, skipping image")
                                continue
                        elif processed_pixmap is None:
                            if qimage is not None and not qimage.isNull():
                                _cache_trace(
                                    "[FALLBACK] Compute-thread scale fallback display=%d reason=raw_available_no_worker path=%s target=%dx%d mode=%s",
                                    i,
                                    img_path,
                                    target_size.width(),
                                    target_size.height(),
                                    display_mode_str,
                                    level=logging.WARNING,
                                )
                                processed_qimage = AsyncImageProcessor.process_qimage(
                                    qimage,
                                    target_size,
                                    display_mode,
                                    use_lanczos=use_lanczos,
                                    sharpen=sharpen,
                                )
                            else:
                                logger.warning(f"{TAG_ASYNC} No ImageWorker and no cache for display {i}, skipping")
                                continue

                        if processed_pixmap is None:
                            # Convert to QPixmap on worker thread (Qt 6 allows this)
                            _conv_start = time.time()
                            processed_pixmap = QPixmap.fromImage(processed_qimage)
                            _conv_elapsed = (time.time() - _conv_start) * 1000
                            if _conv_elapsed > 50 and is_perf_metrics_enabled():
                                logger.warning(f"[PERF] [ASYNC] QPixmap.fromImage took {_conv_elapsed:.1f}ms for display {i}")
                            # Clear QImage reference to free memory (Section 1.1 fix)
                            processed_qimage = None
                            if engine._image_cache is not None and processed_pixmap is not None and not processed_pixmap.isNull():
                                scaled_key = _build_scaled_cache_key(
                                    img_path,
                                    target_size.width(),
                                    target_size.height(),
                                    display_mode,
                                    use_lanczos,
                                    sharpen,
                                )
                                engine._image_cache.put(scaled_key, processed_pixmap)
                    else:
                        logger.debug(f"{TAG_ASYNC} Using cached scaled variant for display {i}")
                        _cache_trace(
                            "Display consumed cached scaled variant display=%d path=%s target=%dx%d mode=%s",
                            i,
                            img_path,
                            target_size.width(),
                            target_size.height(),
                            display_mode_str,
                        )

                    if original_pixmap is None or original_pixmap.isNull():
                        if qimage is None or qimage.isNull():
                            original_pixmap = processed_pixmap
                        else:
                            _conv2_start = time.time()
                            original_pixmap = QPixmap.fromImage(qimage)
                            _conv2_elapsed = (time.time() - _conv2_start) * 1000
                            if _conv2_elapsed > 50 and is_perf_metrics_enabled():
                                logger.warning(f"[PERF] [ASYNC] Original QPixmap.fromImage took {_conv2_elapsed:.1f}ms for display {i}")
                            # Clear QImage reference to free memory (Section 1.1 fix)
                            qimage = None

                    processed_images[i] = {
                        'pixmap': processed_pixmap,
                        'original_pixmap': original_pixmap,
                        'target_size': target_size,
                        'path': img_path,
                    }
                except Exception as e:
                    logger.debug(f"[ASYNC] Failed to process for display {i}: {e}")

            if not processed_images:
                return None

            return {
                'processed': processed_images,
                'same_image': same_image,
            }
        except Exception as e:
            logger.exception(f"[ASYNC] Background image processing failed: {e}")
            return None

    def _on_process_complete(result) -> None:
        """UI thread callback: convert to QPixmap and display."""
        try:
            data = result.result if result and result.success else None
            if data is None:
                logger.warning(f"[ASYNC] Image processing failed, retrying (attempt {retry_count + 1}/10)")
                engine._loading_in_progress = False
                try:
                    pending = getattr(engine.display_manager, "set_transition_work_pending", None)
                    if callable(pending):
                        pending(False)
                except Exception:
                    logger.debug("[ASYNC] Failed to clear transition pending state", exc_info=True)
                if retry_count < 10 and engine.image_queue:
                    next_meta = engine.image_queue.next()
                    if next_meta:
                        load_and_display_image_async(engine, next_meta, retry_count + 1)
                return

            processed = data['processed']
            is_same_image = data.get('same_image', True)

            displays = engine.display_manager.displays if engine.display_manager else []
            for i, display in enumerate(displays):
                if i not in processed:
                    setter = getattr(display, "set_transition_work_pending", None)
                    if callable(setter):
                        setter(False)
            displayed_paths = []

            # PERF: Stagger transition starts by 100ms per display to avoid
            # simultaneous transition completions which cause 100+ms UI blocks.
            stagger_ms = TRANSITION_STAGGER_MS

            for i, display in enumerate(displays):
                if i not in processed:
                    continue

                proc_data = processed[i]
                processed_pixmap = proc_data['pixmap']
                original_pixmap = proc_data['original_pixmap']
                img_path = proc_data['path']

                if processed_pixmap.isNull():
                    logger.warning(f"[ASYNC] QPixmap is null for display {i}")
                    continue

                delay_ms = i * stagger_ms
                if delay_ms > 0:
                    def _delayed_set(d=display, pp=processed_pixmap, op=original_pixmap, ip=img_path):
                        if hasattr(d, 'set_processed_image'):
                            d.set_processed_image(pp, op, ip)
                        else:
                            d.set_image(pp, ip)
                    QTimer.singleShot(delay_ms, _delayed_set)
                else:
                    if hasattr(display, 'set_processed_image'):
                        display.set_processed_image(processed_pixmap, original_pixmap, img_path)
                    else:
                        display.set_image(processed_pixmap, img_path)

                displayed_paths.append(img_path)

            # Emit signal for first image
            if displayed_paths:
                engine.image_changed.emit(displayed_paths[0])
                if is_same_image:
                    logger.info(f"[ASYNC] Same image displayed on all monitors: {displayed_paths[0]}")
                else:
                    logger.info(f"[ASYNC] Different images displayed on {len(displayed_paths)} displays")

            # Record per-display history for previous-image support
            _record_display_history(engine, image_metas)

            schedule_prefetch(engine)
            engine._loading_in_progress = False
            try:
                if engine.display_manager and not engine.display_manager.has_transition_work_pending():
                    pending = getattr(engine.display_manager, "set_transition_work_pending", None)
                    if callable(pending):
                        pending(False)
            except Exception:
                logger.debug("[ASYNC] Failed to reconcile transition pending state", exc_info=True)

        except Exception as e:
            logger.exception(f"[ASYNC] UI callback failed: {e}")
            engine._loading_in_progress = False
            try:
                pending = getattr(engine.display_manager, "set_transition_work_pending", None)
                if callable(pending):
                    pending(False)
            except Exception:
                logger.debug("[ASYNC] Failed to clear transition pending state", exc_info=True)

    # Submit to COMPUTE pool for processing
    try:
        engine.thread_manager.submit_compute_task(
            _do_load_and_process,
            callback=lambda r: engine.thread_manager.run_on_ui_thread(lambda: _on_process_complete(r))
        )
    except Exception as e:
        logger.warning(f"[ASYNC] Failed to submit task, falling back to sync: {e}")
        load_and_display_image(engine, image_meta, retry_count)


# ------------------------------------------------------------------
# Per-display history recording
# ------------------------------------------------------------------

def _record_display_history(engine: "ScreensaverEngine", image_metas: list) -> None:
    """Push a per-display snapshot onto the engine's display history stack.

    Args:
        engine: ScreensaverEngine instance
        image_metas: List of ImageMetadata, one per display
    """
    try:
        history = engine._display_image_history
        history.append(list(image_metas))
        # Cap at 50 entries to bound memory
        while len(history) > 50:
            history.pop(0)
    except Exception as e:
        logger.debug("[HISTORY] Failed to record display history: %s", e)


# ------------------------------------------------------------------
# Async image loading with pre-resolved metas (for previous-image)
# ------------------------------------------------------------------

def load_and_display_image_async_with_metas(
    engine: "ScreensaverEngine",
    image_metas: list,
) -> None:
    """Load and display specific images on each display without advancing the queue.

    This is used by the previous-image feature to show pre-resolved
    ImageMetadata on each display.  The logic mirrors
    load_and_display_image_async but skips queue advancement.
    """
    if not engine.thread_manager or not engine.display_manager:
        # Sync fallback — show first image on all displays
        if image_metas:
            load_and_display_image(engine, image_metas[0])
        return

    displays = engine.display_manager.displays if engine.display_manager else []
    # Pad metas to match display count
    while len(image_metas) < len(displays):
        image_metas.append(image_metas[-1] if image_metas else None)

    def _do_load() -> Optional[Dict]:
        try:
            processed_images = {}
            display_list = engine.display_manager.displays if engine.display_manager else []
            sharpen = False
            use_lanczos, sharpen = _get_display_quality_settings(engine)

            for i, display in enumerate(display_list):
                meta = image_metas[i] if i < len(image_metas) else None
                if meta is None:
                    continue
                img_path = str(meta.local_path) if meta.local_path else (meta.url or "")
                if not img_path:
                    continue

                qimage: Optional[QImage] = None
                if engine._image_cache:
                    cached = engine._image_cache.get(img_path)
                    if isinstance(cached, QImage) and not cached.isNull():
                        qimage = cached
                    elif isinstance(cached, QPixmap) and not cached.isNull():
                        qimage = cached.toImage()

                if qimage is None or qimage.isNull():
                    from pathlib import Path
                    if not Path(img_path).exists():
                        continue

                try:
                    if hasattr(display, 'get_target_size'):
                        target_size = display.get_target_size()
                    else:
                        dpr = getattr(display, '_device_pixel_ratio', 1.0)
                        target_size = QSize(int(display.width() * dpr), int(display.height() * dpr))

                    display_mode = _normalize_display_mode(getattr(display, 'display_mode', DisplayMode.FILL))
                    display_mode_str = display_mode.value

                    processed_pixmap, original_pixmap = _get_cached_pixmap_variants(
                        engine,
                        img_path,
                        target_size.width(),
                        target_size.height(),
                        display_mode,
                        use_lanczos,
                        sharpen,
                    )

                    if processed_pixmap is None or processed_pixmap.isNull():
                        processed_qimage = None
                        if qimage is not None and not qimage.isNull():
                            processed_pixmap = _derive_scaled_pixmap_from_raw_cache(
                                engine,
                                img_path,
                                qimage,
                                target_size,
                                display_mode,
                                use_lanczos,
                                sharpen,
                            )
                        if processed_pixmap is None and engine._process_supervisor and engine._process_supervisor.is_running(WorkerType.IMAGE):
                            _bump_cache_runtime_stat(engine, "worker_fallbacks")
                            worker_qimage = load_image_via_worker(
                                engine, img_path, target_size.width(), target_size.height(),
                                display_mode=display_mode_str, sharpen=sharpen, timeout_ms=3000,
                            )
                            if worker_qimage and not worker_qimage.isNull():
                                processed_qimage = worker_qimage
                            else:
                                continue
                        elif processed_pixmap is None and qimage is not None and not qimage.isNull():
                            processed_qimage = AsyncImageProcessor.process_qimage(
                                qimage, target_size, display_mode, use_lanczos=use_lanczos, sharpen=sharpen,
                            )
                        elif processed_pixmap is None:
                            continue

                        if processed_pixmap is None:
                            processed_pixmap = QPixmap.fromImage(processed_qimage)
                            processed_qimage = None
                            if engine._image_cache is not None and processed_pixmap is not None and not processed_pixmap.isNull():
                                scaled_key = _build_scaled_cache_key(
                                    img_path,
                                    target_size.width(),
                                    target_size.height(),
                                    display_mode,
                                    use_lanczos,
                                    sharpen,
                                )
                                engine._image_cache.put(scaled_key, processed_pixmap)

                    if original_pixmap is None or original_pixmap.isNull():
                        original_pixmap = QPixmap.fromImage(qimage) if (qimage and not qimage.isNull()) else processed_pixmap

                    processed_images[i] = {
                        'pixmap': processed_pixmap,
                        'original_pixmap': original_pixmap,
                        'target_size': target_size,
                        'path': img_path,
                    }
                except Exception as e:
                    logger.debug("[ASYNC-PREV] Failed to process for display %d: %s", i, e)

            return {'processed': processed_images} if processed_images else None
        except Exception as e:
            logger.exception("[ASYNC-PREV] Background processing failed: %s", e)
            return None

    def _on_complete(result) -> None:
        try:
            data = result.result if result and result.success else None
            if data is None:
                engine._loading_in_progress = False
                try:
                    pending = getattr(engine.display_manager, "set_transition_work_pending", None)
                    if callable(pending):
                        pending(False)
                except Exception:
                    logger.debug("[ASYNC-PREV] Failed to clear transition pending state", exc_info=True)
                return
            processed = data['processed']
            displays_list = engine.display_manager.displays if engine.display_manager else []
            for i, display in enumerate(displays_list):
                if i not in processed:
                    setter = getattr(display, "set_transition_work_pending", None)
                    if callable(setter):
                        setter(False)
            stagger_ms = TRANSITION_STAGGER_MS
            displayed = []
            for i, display in enumerate(displays_list):
                if i not in processed:
                    continue
                proc = processed[i]
                delay_ms = i * stagger_ms
                if delay_ms > 0:
                    def _delayed(d=display, pp=proc['pixmap'], op=proc['original_pixmap'], ip=proc['path']):
                        if hasattr(d, 'set_processed_image'):
                            d.set_processed_image(pp, op, ip)
                        else:
                            d.set_image(pp, ip)
                    QTimer.singleShot(delay_ms, _delayed)
                else:
                    if hasattr(display, 'set_processed_image'):
                        display.set_processed_image(proc['pixmap'], proc['original_pixmap'], proc['path'])
                    else:
                        display.set_image(proc['pixmap'], proc['path'])
                displayed.append(proc['path'])
            if displayed:
                engine.image_changed.emit(displayed[0])
                logger.info("[ASYNC-PREV] Previous images displayed on %d displays", len(displayed))
            engine._loading_in_progress = False
            try:
                if engine.display_manager and not engine.display_manager.has_transition_work_pending():
                    pending = getattr(engine.display_manager, "set_transition_work_pending", None)
                    if callable(pending):
                        pending(False)
            except Exception:
                logger.debug("[ASYNC-PREV] Failed to reconcile transition pending state", exc_info=True)
        except Exception as e:
            logger.exception("[ASYNC-PREV] UI callback failed: %s", e)
            engine._loading_in_progress = False
            try:
                pending = getattr(engine.display_manager, "set_transition_work_pending", None)
                if callable(pending):
                    pending(False)
            except Exception:
                logger.debug("[ASYNC-PREV] Failed to clear transition pending state", exc_info=True)

    try:
        engine.thread_manager.submit_compute_task(
            _do_load,
            callback=lambda r: engine.thread_manager.run_on_ui_thread(lambda: _on_complete(r))
        )
    except Exception as e:
        logger.warning("[ASYNC-PREV] Failed to submit task: %s", e)
        if image_metas:
            load_and_display_image(engine, image_metas[0])


# ------------------------------------------------------------------
# Sync image loading and display (legacy fallback)
# ------------------------------------------------------------------

def load_and_display_image(
    engine: ScreensaverEngine,
    image_meta: ImageMetadata,
    retry_count: int = 0,
) -> bool:
    """
    Load and display image synchronously. Auto-retries with next image on failure.

    NOTE: This is the legacy sync path. For better performance, use
    load_and_display_image_async() which processes images off the UI thread.

    Args:
        engine: ScreensaverEngine instance
        image_meta: Image metadata
        retry_count: Number of retries attempted (max 10)

    Returns:
        True if successful, False otherwise
    """
    try:
        pixmap = load_image_task(engine, image_meta)

        if not pixmap:
            logger.warning(f"[CACHE][FALLBACK] Image load failed, attempting next image (retry {retry_count + 1}/10)")
            engine._loading_in_progress = False
            try:
                pending = getattr(engine.display_manager, "set_transition_work_pending", None)
                if callable(pending):
                    pending(False)
            except Exception:
                logger.warning("[CACHE][FALLBACK] Failed to clear transition pending state", exc_info=True)

            if retry_count < 10 and engine.image_queue:
                next_image = engine.image_queue.next()
                if next_image:
                    return load_and_display_image(engine, next_image, retry_count + 1)

            logger.error("[CACHE][FALLBACK] Failed to load any images after 10 attempts")
            engine.display_manager.show_error("No valid images available")
            return False

        image_path = str(image_meta.local_path) if image_meta.local_path else image_meta.url or "unknown"

        raw_same_image = engine.settings_manager.get('display.same_image_all_monitors', True)
        same_image = SettingsManager.to_bool(raw_same_image, True)
        logger.debug(
            "Same image on all monitors setting: %s (raw=%r)",
            same_image,
            raw_same_image,
        )

        if same_image:
            engine.display_manager.show_image(pixmap, image_path)
            logger.info(f"Image displayed: {image_path}")
        else:
            display_count = len(engine.display_manager.displays)
            for i in range(display_count):
                if i == 0:
                    engine.display_manager.show_image_on_screen(i, pixmap, image_path)
                else:
                    next_meta = engine.image_queue.next() if engine.image_queue else None
                    if next_meta:
                        try:
                            d = engine.display_manager.displays[i]
                            size = (d.width(), d.height())
                        except Exception as e:
                            logger.debug("[ENGINE] Exception suppressed: %s", e)
                            size = None
                        next_pixmap = load_image_task(engine, next_meta, preferred_size=size)
                        if next_pixmap:
                            next_path = str(next_meta.local_path) if next_meta.local_path else next_meta.url or "unknown"
                            engine.display_manager.show_image_on_screen(i, next_pixmap, next_path)
            logger.info(f"Different images displayed on {display_count} displays")

        engine.image_changed.emit(image_path)
        schedule_prefetch(engine)

        engine._loading_in_progress = False
        try:
            pending = getattr(engine.display_manager, "set_transition_work_pending", None)
            if callable(pending):
                pending(False)
        except Exception:
            logger.warning("[CACHE][FALLBACK] Failed to reconcile transition pending state", exc_info=True)
        return True

    except Exception as e:
        logger.exception(f"Load and display failed: {e}")
        engine._loading_in_progress = False
        try:
            pending = getattr(engine.display_manager, "set_transition_work_pending", None)
            if callable(pending):
                pending(False)
        except Exception:
            logger.warning("[CACHE][FALLBACK] Failed to clear transition pending state", exc_info=True)
        return False


# ------------------------------------------------------------------
# Prefetch scheduling
# ------------------------------------------------------------------

def _has_transition_work_pending(engine: ScreensaverEngine) -> bool:
    """Return True while any display still owns transition/image-change work."""
    try:
        if engine.display_manager and (
            engine.display_manager.has_running_transition()
            or engine.display_manager.has_transition_work_pending()
        ):
            return True
    except Exception as e:
        logger.debug("[ENGINE] Exception suppressed: %s", e)
    return False


def schedule_prefetch(engine: ScreensaverEngine) -> None:
    """Schedule prefetch of upcoming images."""
    try:
        if not engine.image_queue or not engine._prefetcher or engine._prefetch_ahead <= 0:
            return
        if _has_transition_work_pending(engine):
            if is_verbose_logging():
                logger.debug("Prefetch deferred: transition still active or pending")
            return
        preview_many = getattr(engine.image_queue, "preview_upcoming", None)
        if callable(preview_many):
            upcoming = preview_many(engine._prefetch_ahead)
            preview_source = "preview_upcoming"
        else:
            upcoming = engine.image_queue.peek_many(engine._prefetch_ahead)
            preview_source = "peek_many"

        paths: List[str] = []
        seen_paths: set[str] = set()
        for m in upcoming:
            try:
                p = str(m.local_path) if m and m.local_path else (m.url or "")
                if p and p not in seen_paths:
                    seen_paths.add(p)
                    paths.append(p)
            except Exception as _e:
                logger.debug("[ENGINE] Exception suppressed: %s", _e)
                continue
        if not paths:
            return

        engine._prefetcher.prefetch_paths(paths)
        _cache_trace(
            "Prefetch preview source=%s path_count=%d paths=%s",
            preview_source,
            len(paths),
            " | ".join(paths[:5]),
        )
        scaled_requests = _build_prefetch_scaled_requests(engine, paths)
        if scaled_requests:
            _bump_cache_runtime_stat(engine, "scaled_prefetch_requests", len(scaled_requests))
            register_scaled_requests = getattr(engine._prefetcher, "register_scaled_requests", None)
            queued_count = len(scaled_requests)
            if callable(register_scaled_requests):
                queued = register_scaled_requests(scaled_requests)
                if isinstance(queued, int):
                    queued_count = queued
            _cache_trace(
                "Queued scaled warmup request_count=%d prepared=%d preview_source=%s",
                queued_count,
                len(scaled_requests),
                preview_source,
            )

        if is_perf_metrics_enabled():
            logger.info(
                "[PERF] [PREFETCH] scheduled paths=%d scaled_requests=%d source=%s",
                len(paths),
                len(scaled_requests),
                preview_source,
            )
        elif is_verbose_logging():
            logger.debug("Prefetch scheduled for %d upcoming images", len(paths))
    except Exception as e:
        logger.debug(f"Prefetch schedule failed: {e}")


def notify_transition_complete(engine: ScreensaverEngine, screen_index: Optional[int] = None) -> None:
    """Notify the prefetch pipeline that a display transition has completed.

    This is the shared seam that makes the documented post-transition prefetch
    delay real in runtime instead of purely advisory:
    - mark transition completion on the prefetcher
    - schedule one delayed prefetch pass after the configured cool-down
    """
    prefetcher = getattr(engine, "_prefetcher", None)
    if prefetcher is None:
        return

    try:
        prefetcher.notify_transition_complete()
    except Exception as e:
        logger.debug("[PREFETCH] Failed to mark transition completion: %s", e)
        return

    scheduled = bool(getattr(engine, "_prefetch_resume_scheduled", False))
    if scheduled:
        return

    delay_ms = 0
    try:
        delay_ms = max(0, int(prefetcher.get_post_transition_delay_ms()))
    except Exception as e:
        logger.debug("[PREFETCH] Failed to read post-transition delay: %s", e)
        delay_ms = 0

    engine._prefetch_resume_scheduled = True
    _bump_cache_runtime_stat(engine, "prefetch_resume_scheduled")
    if is_perf_metrics_enabled():
        logger.info(
            "[PERF] [PREFETCH] transition_complete screen=%s delay_ms=%d",
            screen_index if screen_index is not None else "shared",
            delay_ms,
        )
    _cache_trace(
        "Transition complete prefetch resume scheduled screen=%s delay_ms=%d",
        screen_index if screen_index is not None else "shared",
        delay_ms,
    )

    def _resume_prefetch() -> None:
        try:
            if _has_transition_work_pending(engine):
                recheck_delay_ms = max(50, delay_ms)
                _cache_trace(
                    "Transition-delayed prefetch resume rearmed reason=transition_work_pending delay_ms=%d",
                    recheck_delay_ms,
                )
                QTimer.singleShot(recheck_delay_ms, _resume_prefetch)
                return

            engine._prefetch_resume_scheduled = False
            _bump_cache_runtime_stat(engine, "prefetch_resume_runs")
            _cache_trace("Transition-delayed prefetch resume running")
            schedule_prefetch(engine)
        except Exception:
            logger.debug("[PREFETCH] Deferred resume failed", exc_info=True)

    QTimer.singleShot(delay_ms, _resume_prefetch)
