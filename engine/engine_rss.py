"""RSS Integration - Extracted from screensaver_engine.py.

Contains RSS image loading (async/sync), background refresh scheduling,
stale image eviction, and merge logic. All functions accept the engine
instance as the first parameter to preserve the original interface.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import List, Tuple, TYPE_CHECKING

from core.events import EventType
from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.logging.tags import TAG_RSS
from sources.base_provider import ImageMetadata, ImageSourceType

if TYPE_CHECKING:
    from engine.screensaver_engine import ScreensaverEngine

logger = get_logger(__name__)


# ------------------------------------------------------------------
# Dynamic RSS settings helpers
# ------------------------------------------------------------------

def get_dynamic_rss_settings(engine: ScreensaverEngine) -> Tuple[int, int]:
    """Return dynamic RSS settings based on transition interval.

    Rules based on transition interval:
        <=30s: 20 minimum, 30 min decay (slow rotation, ~1 image/min)
        >30s but <=90s: 15 minimum, 45 min decay
        >90s: 10 minimum, 60 min decay (very slow rotation)

    Decay rate is intentionally slow to avoid wasteful downloads.
    At 60s transition interval, 30 min decay = ~1 image removed per minute.
    """
    try:
        interval = 60  # default
        if engine.settings_manager:
            interval = int(engine.settings_manager.get('timing.interval'))

        if interval <= 30:
            return (20, 30)
        elif interval <= 90:
            return (15, 45)
        else:
            return (10, 60)
    except Exception as e:
        logger.debug("[ENGINE] Exception suppressed: %s", e)
        return (15, 10)  # Safe default


def get_rss_background_cap(engine: ScreensaverEngine) -> int:
    """Return the global background cap for RSS images.

    This limits how many RSS/JSON images we keep queued at any
    given time. The minimum is dynamically adjusted based on
    transition interval to ensure variety.

    Can be overridden via settings (``sources.rss_background_cap``).
    """
    try:
        # Get dynamic minimum based on transition interval
        dynamic_min, _ = get_dynamic_rss_settings(engine)

        if not engine.settings_manager:
            return max(35, dynamic_min)

        raw = engine.settings_manager.get('sources.rss_background_cap')
        cap = int(raw)

        # Ensure cap is at least the dynamic minimum
        return max(cap, dynamic_min) if cap > 0 else dynamic_min
    except Exception as e:
        logger.debug("[ENGINE] Exception suppressed: %s", e)
        return 35


def get_rss_rotating_cache_size(engine: ScreensaverEngine) -> int:
    """Return how many cached RSS images should be preloaded into the queue."""

    try:
        if not engine.settings_manager:
            return 20

        raw = engine.settings_manager.get('sources.rss_rotating_cache_size')
        rotating = int(raw)
        return max(1, rotating)
    except Exception as e:
        logger.debug("[ENGINE] Exception suppressed: %s", e)
        return 20


def get_rss_startup_target_total(engine: ScreensaverEngine) -> int:
    """Return the startup cache target for RSS source negotiation.

    Startup should not keep negotiating new source downloads once the on-disk
    RSS cache already satisfies the real runtime pool expectations. Use the
    larger of the queue cap and preload cap so startup cache authority stays
    aligned with what the engine can actually use.
    """

    try:
        return max(
            get_rss_background_cap(engine),
            get_rss_rotating_cache_size(engine),
        )
    except Exception as e:
        logger.debug("[ENGINE] Exception suppressed: %s", e)
        return 35


def get_rss_stale_minutes(engine: ScreensaverEngine) -> int:
    """Return TTL in minutes for stale RSS images.

    Dynamically adjusted based on transition interval:
        <=30s: 30 min decay (slow rotation, ~1 image/min)
        >30s but <=90s: 45 min decay
        >90s: 60 min decay

    Slow decay prevents wasteful downloads. Images only leave cache
    when new replacements are available (safe rotation).

    Can be overridden via settings (``sources.rss_stale_minutes``).
    A value <= 0 disables stale expiration.
    """
    try:
        # Get dynamic decay based on transition interval
        _, dynamic_decay = get_dynamic_rss_settings(engine)

        if not engine.settings_manager:
            return dynamic_decay

        # Check if user has explicitly set a value (non-default)
        raw = engine.settings_manager.get('sources.rss_stale_minutes')
        if raw is not None:
            minutes = int(raw)
            return minutes if minutes > 0 else 0

        return dynamic_decay
    except Exception as e:
        logger.debug("[ENGINE] Exception suppressed: %s", e)
        return 10


# ------------------------------------------------------------------
# Async / sync RSS loading
# ------------------------------------------------------------------

def drop_retired_rss_images(engine: ScreensaverEngine) -> int:
    """Remove pool images the coordinator retired (replaced or unable to fill) from the queue."""
    coordinator = getattr(engine, "rss_coordinator", None)
    if coordinator is None or not engine.image_queue:
        return 0
    removed = 0
    for path in coordinator.take_retired_paths():
        try:
            if engine.image_queue.remove_image(path):
                removed += 1
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
    if removed:
        logger.info(f"{TAG_RSS} Retired {removed} replaced RSS images from the queue")
    return removed


def load_rss_images_async(engine: ScreensaverEngine) -> None:
    """Load RSS images asynchronously via RSSCoordinator.

    Acquisition and remaining cache work run on the IO pool. Queue construction
    retains its existing synchronous disk-cache warm preload; no network runs
    there. The bounded result is merged once on IO before GUI image admission.
    """
    if not engine.rss_coordinator:
        return
    if not engine.thread_manager:
        raise RuntimeError("Wallpaper startup requires the existing IO owner")

    logger.info(f"{TAG_RSS} Starting async RSS load via RSSCoordinator...")
    coordinator = engine.rss_coordinator
    queue = engine.image_queue
    _preloaded = False  # closure flag

    def _publish_startup_completion() -> None:
        generation, display_manager = engine._capture_runtime_identity()
        def _resume_on_ui() -> None:
            if (engine._shutting_down or coordinator.is_stopped or engine.rss_coordinator is not coordinator
                    or engine.image_queue is not queue
                    or not engine._is_runtime_identity_current(generation, display_manager)
                    or not engine.is_running() or engine._display_selection_suspended()
                    or display_manager is None or display_manager.has_presented_image()
                    or engine._loading_in_progress):
                return
            if engine._replacement_watchdog_label is not None and queue.total_images() > 0:
                engine._arm_replacement_watchdog()
            if not engine._show_next_image(origin="rss_startup_completion"):
                engine._schedule_startup_first_image_retry()
        _resume_on_ui._srpss_runtime_generation = generation
        engine.thread_manager.single_shot(0, _resume_on_ui)

    def _on_new_images(new_images: List[ImageMetadata]):
        """Callback from coordinator with freshly downloaded images."""
        nonlocal _preloaded

        if (engine._shutting_down or coordinator.is_stopped or engine.rss_coordinator is not coordinator
                or engine.image_queue is not queue):
            return
        was_empty = queue.total_images() == 0
        to_merge = []

        # First call: inject cached images that warm_cache loaded from disk
        if not _preloaded:
            _preloaded = True
            cached = engine.rss_coordinator.get_cached_images()
            if cached:
                rotating = get_rss_rotating_cache_size(engine)
                if len(cached) > rotating:
                    random.shuffle(cached)
                    cached = cached[:rotating]
                to_merge.extend(cached)
        to_merge.extend(new_images)
        merge_rss_images_from_refresh(engine, to_merge, shuffle=False, retire_stale=False)
        # Replacements are in: the images they replace leave the queue.
        drop_retired_rss_images(engine)
        if was_empty:
            _publish_startup_completion()

    coordinator.load_async(on_images=_on_new_images, runtime_generation=engine._runtime_generation)


def startup_image_pending(engine: ScreensaverEngine) -> bool:
    """Derive waiting from existing queue/source state, never another state owner."""
    from sources.rss.coordinator import RSSState
    return bool(engine.image_queue is not None and engine.image_queue.total_images() == 0
                and engine.rss_coordinator is not None
                and not engine.rss_coordinator.is_stopped
                and engine.rss_coordinator.state == RSSState.LOADING)


# ------------------------------------------------------------------
# Background refresh
# ------------------------------------------------------------------

def start_rss_background_refresh_if_needed(engine: ScreensaverEngine) -> None:
    """Schedule background RSS refresh if RSS sources are present."""
    try:
        if not engine.thread_manager or engine.image_queue is None or not engine.rss_coordinator:
            return
        if engine.rss_coordinator.is_stopped or engine._display_selection_suspended():
            return
        if engine._rss_refresh_timer is not None:
            return

        cap = get_rss_background_cap(engine)
        if cap <= 0:
            return

        # Allow user override for refresh interval; default ~10min.
        interval_min = 10
        try:
            if engine.settings_manager:
                raw = engine.settings_manager.get('sources.rss_refresh_minutes')
                interval_min = int(raw)
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
            interval_min = 10

        # Desync: Add ±1 minute jitter to prevent alignment with other timers
        jitter_min = random.randint(-1, 1)
        interval_min += jitter_min

        interval_ms = max(60_000, interval_min * 60_000)
        if is_perf_metrics_enabled():
            logger.debug("[PERF] RSS background refresh: interval=%d min (jitter: %+d min)", interval_min, jitter_min)
        try:
            engine._rss_refresh_timer = engine.thread_manager.schedule_recurring(
                interval_ms,
                engine._background_refresh_rss,
            )
            logger.info(
                "Background RSS refresh enabled (interval=%dms, cap=%d)",
                interval_ms,
                cap,
            )
        except Exception as e:
            logger.debug(f"Background RSS refresh scheduling failed: {e}")
            engine._rss_refresh_timer = None
    except Exception as e:
        logger.debug(f"Background RSS refresh init failed: {e}")


def background_refresh_rss(engine: ScreensaverEngine) -> None:
    """Periodic background refresh for RSS/JSON sources.

    Runs on the UI thread via ``ThreadManager.schedule_recurring``
    and dispatches IO work to the thread pool via RSSCoordinator.
    """
    try:
        if not engine._running:
            return
        if not engine.thread_manager or engine.image_queue is None or not engine.rss_coordinator:
            return
        if engine.rss_coordinator.is_stopped or engine._display_selection_suspended():
            return

        cap = get_rss_background_cap(engine)
        if cap <= 0:
            return

        try:
            existing = engine.image_queue.get_all_images()
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
            existing = []

        current_rss = sum(
            1 for m in existing
            if getattr(m, 'source_type', None) == ImageSourceType.RSS
        )

        if current_rss >= cap:
            return

        if not engine.rss_coordinator.source_count:
            return
        logger.debug("Background RSS refresh: next bounded source opportunity")

        coordinator = engine.rss_coordinator
        queue = engine.image_queue
        generation = engine._runtime_generation

        def _refresh_task():
            try:
                images = coordinator.refresh_next_sources()
                if (engine._shutting_down or coordinator.is_stopped
                        or engine.rss_coordinator is not coordinator or engine.image_queue is not queue
                        or engine._runtime_generation != generation):
                    return
                # Publication belongs to this tracked job as well: retirement
                # must drain cache writes AND merges before source replacement.
                merge_rss_images_from_refresh(engine, images)
                drop_retired_rss_images(engine)
            except Exception as e:
                logger.warning(f"[FALLBACK] Background RSS refresh failed: {e}")

        _refresh_task._srpss_runtime_generation = generation
        try:
            engine.thread_manager.submit_io_task(
                _refresh_task,
                category="rss_background_refresh",
            )
        except Exception as e:
            logger.debug(f"Background RSS submit failed: {e}")
    except Exception as e:
        logger.debug(f"Background RSS refresh tick failed: {e}")


# ------------------------------------------------------------------
# Merge refreshed images into queue
# ------------------------------------------------------------------

def merge_rss_images_from_refresh(
    engine: ScreensaverEngine,
    images: List[ImageMetadata],
    *,
    shuffle: bool = True,
    retire_stale: bool = True,
) -> None:
    """Merge refreshed RSS images into the queue under the global cap."""
    if not images or engine.image_queue is None:
        return

    cap = get_rss_background_cap(engine)
    if cap <= 0:
        return

    with engine._rss_merge_lock:
        try:
            existing = engine.image_queue.get_all_images()
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
            existing = []

        existing_keys = set()
        current_rss = 0
        for m in existing:
            try:
                key = str(m.local_path) if m.local_path else (m.url or "")
                if key:
                    existing_keys.add(key)
                if getattr(m, 'source_type', None) == ImageSourceType.RSS:
                    current_rss += 1
            except Exception as _e:
                logger.debug("[ENGINE] Exception suppressed: %s", _e)
                continue

        remaining = cap - current_rss
        if remaining <= 0:
            return

        new_items: List[ImageMetadata] = []
        for m in images:
            try:
                if getattr(m, 'source_type', None) != ImageSourceType.RSS:
                    continue
                key = str(m.local_path) if m.local_path else (m.url or "")
                if not key or key in existing_keys:
                    continue
                existing_keys.add(key)
                new_items.append(m)
            except Exception as _e:
                logger.debug("[ENGINE] Exception suppressed: %s", _e)
                continue

        if not new_items:
            return

        if shuffle:
            try:
                random.shuffle(new_items)
            except Exception as e:
                logger.debug(f"{TAG_RSS} Failed to shuffle new items: %s", e)

        to_add = new_items[: max(0, remaining)]
        if not to_add:
            return

        added = 0
        try:
            added = engine.image_queue.add_images(to_add)
        except Exception as e:
            logger.debug(f"Background RSS queue add failed: {e}")
            return

        removed_stale = 0
        if added > 0 and retire_stale:
            stale_minutes = get_rss_stale_minutes(engine)
            if stale_minutes > 0:
                cutoff = datetime.utcnow() - timedelta(minutes=stale_minutes)

                try:
                    snapshot = engine.image_queue.get_all_images()
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    snapshot = []

                try:
                    history_paths = set(engine.image_queue.get_history(engine.image_queue.history_size))
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    history_paths = set()

                stale_paths: List[str] = []
                for m in snapshot:
                    try:
                        if getattr(m, 'source_type', None) != ImageSourceType.RSS:
                            continue
                        lp = str(m.local_path) if m.local_path else None
                        if not lp or lp in history_paths:
                            continue
                        ts = getattr(m, 'fetched_date', None) or getattr(m, 'created_date', None)
                        if ts is None or not isinstance(ts, datetime):
                            continue
                        if ts < cutoff:
                            stale_paths.append(lp)
                    except Exception as e:
                        logger.debug("[ENGINE] Exception suppressed: %s", e)
                        continue

                if stale_paths:
                    max_remove = min(len(stale_paths), added)
                    for path in stale_paths[:max_remove]:
                        try:
                            if engine.image_queue.remove_image(path):
                                removed_stale += 1
                        except Exception as e:
                            logger.debug("[ENGINE] Exception suppressed: %s", e)
                            continue

        logger.info(
            "Background RSS refresh merged %d new images (cap=%d, removed_stale=%d)",
            added,
            cap,
            removed_stale,
        )

        if engine.event_system and (added > 0 or removed_stale > 0):
            try:
                try:
                    final_existing = engine.image_queue.get_all_images()
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    final_existing = []

                total_rss = 0
                for m in final_existing:
                    try:
                        if getattr(m, 'source_type', None) == ImageSourceType.RSS:
                            total_rss += 1
                    except Exception as e:
                        logger.debug("[ENGINE] Exception suppressed: %s", e)
                        continue

                engine.event_system.publish(
                    EventType.RSS_UPDATED,
                    data={"added": added, "removed_stale": removed_stale, "total_rss": total_rss},
                    source=engine,
                )
            except Exception as e:
                logger.debug(f"{TAG_RSS} Failed to publish RSS_REFRESHED event: %s", e)
