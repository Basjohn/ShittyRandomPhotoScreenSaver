"""Image Loading Pipeline - Extracted from screensaver_engine.py.

Contains image loading, prescaling, prefetching, and display coordination
logic. All functions accept the engine instance as the first parameter
to preserve the original interface.
"""

from __future__ import annotations

from typing import Optional, Dict, TYPE_CHECKING
import time

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QPixmap, QImage

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.logging.tags import TAG_WORKER, TAG_PERF, TAG_ASYNC
from core.constants.timing import TRANSITION_STAGGER_MS
from core.process.types import WorkerResponse, WorkerType, MessageType
from core.settings import SettingsManager
from queue import Empty as QueueEmpty
from rendering.display_modes import DisplayMode
from rendering.image_processor_async import AsyncImageProcessor
from sources.base_provider import ImageMetadata

if TYPE_CHECKING:
    from engine.screensaver_engine import ScreensaverEngine

logger = get_logger(__name__)


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

        # Send prescale request to ImageWorker
        _correlation_id = engine._process_supervisor.send_message(
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
        )

        if not _correlation_id:
            logger.debug(f"{TAG_WORKER} Failed to send message to ImageWorker")
            return None

        # Wait for response with blocking get - more efficient than busy-polling
        start_time = time.time()
        timeout_s = timeout_ms / 1000.0

        while (time.time() - start_time) < timeout_s:
            # Use blocking get with short timeout - worker wakes us when response arrives
            try:
                resp_queue = engine._process_supervisor._response_queues.get(WorkerType.IMAGE)
                if not resp_queue:
                    return None
                # Blocking get with 50ms timeout - efficient waiting
                data = resp_queue.get(timeout=0.05)
                response = WorkerResponse.from_dict(data)

                # Handle internal messages (heartbeat, busy/idle)
                if response.msg_type in (MessageType.WORKER_BUSY, MessageType.WORKER_IDLE, MessageType.HEARTBEAT_ACK):
                    continue

                if response.correlation_id == _correlation_id:
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

            except QueueEmpty:
                # Timeout on blocking get - check if we've exceeded total timeout
                continue
            except Exception as e:
                logger.debug(f"{TAG_WORKER} Error waiting for response: %s", e)
                return None

        logger.warning(f"{TAG_WORKER} ImageWorker timeout after %dms", timeout_ms)
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
                logger.warning("[FALLBACK] No local path for URL image")
                return None
            image_path = str(image_meta.local_path)
        else:
            logger.warning("[FALLBACK] No path or URL for image")
            return None

        # Use cache if available (QImage decoded on IO thread)
        pixmap: Optional[QPixmap] = None
        if engine._prefetcher and engine._image_cache:
            # Prefer a pre-scaled variant for this display if present
            try:
                size = preferred_size or engine._get_primary_display_size()
                if size:
                    w, h = size
                    scaled_key = f"{image_path}|scaled:{w}x{h}"
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
                            engine._image_cache.put(image_path, pm)
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
            sharpen = False
            if engine.settings_manager:
                sharpen = engine.settings_manager.get('display.sharpen_downscale', False)
                if isinstance(sharpen, str):
                    sharpen = sharpen.lower() == 'true'

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
                    display_mode = getattr(display, 'display_mode', DisplayMode.FILL)
                    display_mode_str = display_mode.value if hasattr(display_mode, 'value') else str(display_mode).lower()

                    # Try ImageWorker (separate process, avoids GIL)
                    processed_qimage = None

                    if engine._process_supervisor and engine._process_supervisor.is_running(WorkerType.IMAGE):
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
                    else:
                        if qimage is not None and not qimage.isNull():
                            processed_qimage = AsyncImageProcessor.process_qimage(
                                qimage,
                                target_size,
                                display_mode,
                                use_lanczos=False,
                                sharpen=sharpen,
                            )
                        else:
                            logger.warning(f"{TAG_ASYNC} No ImageWorker and no cache for display {i}, skipping")
                            continue

                    # Convert to QPixmap on worker thread (Qt 6 allows this)
                    _conv_start = time.time()
                    processed_pixmap = QPixmap.fromImage(processed_qimage)
                    _conv_elapsed = (time.time() - _conv_start) * 1000
                    if _conv_elapsed > 50 and is_perf_metrics_enabled():
                        logger.warning(f"[PERF] [ASYNC] QPixmap.fromImage took {_conv_elapsed:.1f}ms for display {i}")
                    # Clear QImage reference to free memory (Section 1.1 fix)
                    processed_qimage = None

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
                if retry_count < 10 and engine.image_queue:
                    next_meta = engine.image_queue.next()
                    if next_meta:
                        load_and_display_image_async(engine, next_meta, retry_count + 1)
                return

            processed = data['processed']
            is_same_image = data.get('same_image', True)

            displays = engine.display_manager.displays if engine.display_manager else []
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

            schedule_prefetch(engine)
            engine._loading_in_progress = False

        except Exception as e:
            logger.exception(f"[ASYNC] UI callback failed: {e}")
            engine._loading_in_progress = False

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
            logger.warning(f"[FALLBACK] Image load failed, attempting next image (retry {retry_count + 1}/10)")
            engine._loading_in_progress = False

            if retry_count < 10 and engine.image_queue:
                next_image = engine.image_queue.next()
                if next_image:
                    return load_and_display_image(engine, next_image, retry_count + 1)

            logger.error("[FALLBACK] Failed to load any images after 10 attempts")
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
        return True

    except Exception as e:
        logger.exception(f"Load and display failed: {e}")
        engine._loading_in_progress = False
        return False


# ------------------------------------------------------------------
# Prefetch scheduling
# ------------------------------------------------------------------

def schedule_prefetch(engine: ScreensaverEngine) -> None:
    """Schedule prefetch of upcoming images."""
    try:
        if not engine.image_queue or not engine._prefetcher or engine._prefetch_ahead <= 0:
            return
        upcoming = engine.image_queue.peek_many(engine._prefetch_ahead)
        paths = []
        for m in upcoming:
            try:
                p = str(m.local_path) if m and m.local_path else (m.url or "")
                if p:
                    paths.append(p)
            except Exception as _e:
                logger.debug("[ENGINE] Exception suppressed: %s", _e)
                continue
        engine._prefetcher.prefetch_paths(paths)
        if paths and is_verbose_logging():
            logger.debug(f"Prefetch scheduled for {len(paths)} upcoming images")
            # Avoid heavy UI-side conversions while transitions are active.
            skip_heavy_ui_work = False
            try:
                if engine.display_manager and hasattr(engine.display_manager, "has_running_transition"):
                    skip_heavy_ui_work = engine.display_manager.has_running_transition()
            except Exception as _e:
                logger.debug("[ENGINE] Exception suppressed: %s", _e)
                skip_heavy_ui_work = False
            # UI warmup: convert first cached QImage to QPixmap to reduce on-demand conversion
            # PERFORMANCE FIX: Move QPixmap.fromImage to compute pool (Qt 6 allows this)
            try:
                if not skip_heavy_ui_work and engine.thread_manager and engine._image_cache:
                    first = paths[0]
                    def _compute_convert():
                        """Compute pool: Convert QImage to QPixmap (Qt 6 thread-safe)"""
                        try:
                            cached = engine._image_cache.get(first)
                            if isinstance(cached, QImage):
                                pm = QPixmap.fromImage(cached)
                                if not pm.isNull():
                                    # Clear QImage reference to free memory (Section 1.1 fix)
                                    cached = None
                                    return (first, pm)
                        except Exception as e:
                            logger.debug(f"Prefetch convert failed for {first}: {e}")
                        return None

                    def _ui_cache(result):
                        """UI thread: Store result in cache"""
                        try:
                            if result and result.success and result.result:
                                path, pixmap = result.result
                                engine._image_cache.put(path, pixmap)
                                logger.debug(f"Prefetch warmup: cached QPixmap for {path}")
                        except Exception as e:
                            logger.debug(f"Prefetch cache failed: {e}")

                    engine.thread_manager.submit_compute_task(
                        _compute_convert,
                        callback=lambda r: engine.thread_manager.run_on_ui_thread(lambda: _ui_cache(r))
                    )
            except Exception as e:
                logger.debug("[PREFETCH] UI warmup failed: %s", e)
            # Pre-scale proposal: safely compute scaled QImages for distinct display sizes
            try:
                if not skip_heavy_ui_work and engine.thread_manager and engine._image_cache:
                    first_path = paths[0]
                    sizes = engine._get_distinct_display_sizes()
                    for (w, h) in sizes:
                        scaled_key = f"{first_path}|scaled:{w}x{h}"
                        try:
                            if engine._image_cache.contains(scaled_key):
                                continue
                        except Exception as e:
                            logger.debug("[ENGINE] Exception suppressed: %s", e)
                        def _compute_prescale_wh(width=w, height=h, src_path=first_path, cache_key=scaled_key):
                            """Compute-task: scale cached QImage to a target size and store in cache."""
                            try:
                                base = engine._image_cache.get(src_path)
                                if isinstance(base, QImage) and not base.isNull():
                                    scaled = AsyncImageProcessor._scale_image(
                                        base,
                                        width,
                                        height,
                                        use_lanczos=False,
                                        sharpen=False,
                                    )
                                    if not scaled.isNull():
                                        engine._image_cache.put(cache_key, scaled)
                            except Exception as e:
                                logger.debug(f"Pre-scale compute failed ({width}x{height}): {e}")
                        try:
                            submit = getattr(engine.thread_manager, 'submit_compute_task', None)
                            if callable(submit):
                                submit(_compute_prescale_wh)
                        except Exception as e:
                            logger.debug("[ENGINE] Exception suppressed: %s", e)
            except Exception as _e:
                logger.debug("[ENGINE] Exception suppressed: %s", _e)
    except Exception as e:
        logger.debug(f"Prefetch schedule failed: {e}")
