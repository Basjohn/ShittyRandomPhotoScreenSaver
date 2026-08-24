"""Presentation-neutral Weather runtime-data service (Phase E1 slice 3).

``WeatherRuntimeService`` owns the non-pixel behavior required to obtain and
maintain Weather data, extracted out of ``WeatherWidget`` presentation ownership:

- provider construction/use (``OpenMeteoProvider``);
- detached network fetch + preparation on the shared I/O pool;
- startup cache load and cache persistence;
- automatic refresh cadence + retry scheduling that exist solely to maintain data;
- current-request / stale-result generation authority (request ids + location key)
  so retired or superseded work cannot commit;
- clean retirement/cancellation of family-exclusive timer/poll/in-flight ownership.

It holds no QWidget/pixel state. It drives a *consumer* (the ``WeatherWidget``)
through a small callback protocol so prepared Weather state / refresh / error
events reach presentation without this owner importing presentation logic:

    WeatherRuntimeService  ->  prepared state + refresh/error events  ->  consumer

Consumer protocol (see ``WeatherWidget``):

- ``is_weather_consumer_alive() -> bool``
- ``on_weather_state(data, *, from_cache: bool) -> None``
- ``apply_weather_data(data) -> None``
- ``on_weather_error(error: str) -> None``
- ``weather_pending_first_show() -> bool``

The production ``WeatherRuntimeService`` is built/owned through
``WidgetRuntimeManager`` (via the neutral ``widget_runtime_services`` registry);
the production ``WeatherWidget`` defers to it and does not construct its own
provider/timer. A directly constructed ``WeatherWidget`` may build a convenience
service for standalone use.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import random
import weakref
from typing import Any, Dict, Optional

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.threading.manager import ThreadManager
from core.runtime_flags import automatic_service_updates_enabled
from core.weather_preparation import (
    PreparedWeatherFetch,
    PreparedWeatherSample,
    PreparedWeatherStartup,
    load_weather_startup_snapshot,
    normalize_weather_location_key as _normalize_weather_location_key,
    prepare_weather_sample,
    write_weather_provider_cache,
    write_weather_widget_cache,
)
import weather.open_meteo_provider as open_meteo_provider_module
from weather.open_meteo_provider import OpenMeteoProvider
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
from widgets.service_widget_runtime import (
    get_automatic_startup_refresh_decision,
    stop_overlay_timer_pair,
)

logger = get_logger(__name__)

# Optional test/profile override; canonical path is resolved by an I/O task so
# constructing the service never touches the filesystem.
_CACHE_FILE: Optional[Path] = None
_LEGACY_CACHE_FILE = Path.home() / ".srpss_last_weather.json"


class WeatherRuntimeService:
    """Presentation-neutral owner of the Weather runtime-data lifecycle."""

    def __init__(self, *, runtime_generation: Any = None) -> None:
        self._consumer_ref: Optional[weakref.ref] = None
        self._thread_manager: Any = None
        self._location: str = ""
        self._runtime_generation = runtime_generation

        self._cached_data: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=30)

        self._startup_cache_request_id = 0
        self._fetch_request_id = 0
        self._startup_refresh_token = 0
        self._retry_token = 0
        self._retry_pending = False

        self._update_timer = None
        self._update_timer_handle: Optional[OverlayTimerHandle] = None

        self._running = False
        self._retired = False

    # ------------------------------------------------------------------ #
    # Consumer / configuration                                            #
    # ------------------------------------------------------------------ #
    def attach_consumer(self, consumer: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot attach a consumer to a retired Weather runtime service")
        self._consumer_ref = weakref.ref(consumer)
        gen = getattr(consumer, "_runtime_generation", None)
        if gen is None:
            try:
                parent = consumer.parent()
            except Exception:
                parent = None
            gen = getattr(parent, "_runtime_generation", None)
        if gen is not None:
            self._runtime_generation = gen

    def detach_consumer(self, consumer: Any = None) -> None:
        """Detach the current presentation consumer without retiring the owner."""
        current = self._consumer()
        if consumer is None or current is consumer:
            self._consumer_ref = None

    def _consumer(self) -> Any:
        return self._consumer_ref() if self._consumer_ref is not None else None

    def _consumer_alive(self) -> bool:
        consumer = self._consumer()
        if consumer is None:
            return False
        try:
            return bool(consumer.is_weather_consumer_alive())
        except Exception:
            return False

    def set_thread_manager(self, thread_manager: Any) -> None:
        self._thread_manager = thread_manager

    def set_location(self, location: str) -> None:
        """Update the current location; invalidate stale work + cache on change."""
        next_location = str(location or "").strip()
        if _normalize_weather_location_key(next_location) != _normalize_weather_location_key(self._location):
            self._invalidate_async_results()
            self._startup_refresh_token += 1
            self._retry_token += 1
            self._retry_pending = False
        self._location = next_location
        self._cached_data = None
        self._cache_time = None
        if not next_location and self._running:
            self.stop()

    def set_running(self, running: bool) -> None:
        if running:
            if not self._retired:
                self._running = True
            return
        self.stop()

    @property
    def location(self) -> str:
        return self._location

    @property
    def runtime_generation(self) -> Any:
        return self._runtime_generation

    def is_running(self) -> bool:
        return self._running and not self._retired

    def is_retired(self) -> bool:
        return self._retired

    def is_cache_valid(self) -> bool:
        """Return True if any cached data exists (age ignored for display)."""
        return bool(self._cached_data)

    def has_cached_data(self) -> bool:
        return bool(self._cached_data)

    def get_cached_data(self) -> Optional[Dict[str, Any]]:
        return self._cached_data

    # ------------------------------------------------------------------ #
    # Delivery to the consumer                                            #
    # ------------------------------------------------------------------ #
    def _deliver_state(self, data: Dict[str, Any], *, from_cache: bool) -> None:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_weather_state(data, from_cache=from_cache)
        except Exception:
            logger.debug("[WEATHER_RT] on_weather_state delivery failed", exc_info=True)

    def _deliver_apply(self, data: Dict[str, Any]) -> None:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        try:
            consumer.apply_weather_data(data)
        except Exception:
            logger.debug("[WEATHER_RT] apply_weather_data delivery failed", exc_info=True)

    def _deliver_error(self, error: str) -> None:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_weather_error(error)
        except Exception:
            logger.debug("[WEATHER_RT] on_weather_error delivery failed", exc_info=True)

    def _consumer_pending_first_show(self) -> bool:
        consumer = self._consumer()
        if consumer is None:
            return False
        try:
            return bool(consumer.weather_pending_first_show())
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Generation authority                                                #
    # ------------------------------------------------------------------ #
    def _invalidate_async_results(self) -> None:
        """Close admission for startup and provider results already in flight."""
        self._startup_cache_request_id += 1
        self._fetch_request_id += 1

    # ------------------------------------------------------------------ #
    # Startup cache load                                                  #
    # ------------------------------------------------------------------ #
    def start(self, *, immediate_refresh_on_miss: bool = False) -> bool:
        """Start the Weather data lifecycle without taking pixel ownership."""
        if self._retired or not self._location:
            return False
        if self._thread_manager is None:
            logger.error("[WEATHER] Weather runtime start unavailable: ThreadManager is not configured")
            return False

        self._running = True
        if self.has_cached_data():
            self._deliver_state(self._cached_data, from_cache=True)
            self.schedule_refresh_cycle()
            return True

        self.begin_startup_cache_load(
            immediate_refresh_on_miss=immediate_refresh_on_miss
        )
        return True

    def begin_startup_cache_load(self, *, immediate_refresh_on_miss: bool = False) -> None:
        """Load widget/provider startup state once on the shared I/O pool."""
        if self._retired or not self._running:
            return
        tm = self._thread_manager
        if tm is None:
            logger.error("[WEATHER] Startup cache load unavailable: ThreadManager is not configured")
            return

        self._startup_cache_request_id += 1
        request_id = self._startup_cache_request_id
        location = self._location
        location_key = _normalize_weather_location_key(location)
        widget_cache_override = _CACHE_FILE
        provider_cache_override = open_meteo_provider_module._WEATHER_CACHE_FILE
        legacy_cache_path = _LEGACY_CACHE_FILE
        runtime_generation = self._runtime_generation
        self_ref = weakref.ref(self)

        def _load_snapshot() -> PreparedWeatherStartup:
            return load_weather_startup_snapshot(
                location,
                widget_cache_path_override=widget_cache_override,
                provider_cache_path_override=provider_cache_override,
                legacy_widget_cache_path=legacy_cache_path,
            )

        _load_snapshot._srpss_runtime_generation = runtime_generation

        def _on_result(result) -> None:
            snapshot = None
            error = None
            if getattr(result, "success", False):
                candidate = getattr(result, "result", None)
                if isinstance(candidate, PreparedWeatherStartup):
                    snapshot = candidate
                else:
                    error = "No Weather startup snapshot returned"
            else:
                error = str(getattr(result, "error", None) or "Weather startup cache load failed")

            def _deliver() -> None:
                owner = self_ref()
                if owner is None:
                    return
                if snapshot is not None:
                    owner._commit_startup_cache(
                        request_id,
                        location_key,
                        snapshot,
                        immediate_refresh_on_miss=immediate_refresh_on_miss,
                    )
                else:
                    owner._on_startup_cache_error(
                        request_id,
                        location_key,
                        str(error),
                        immediate_refresh_on_miss=immediate_refresh_on_miss,
                    )

            _deliver._srpss_runtime_generation = runtime_generation
            ThreadManager.run_on_ui_thread(_deliver)

        _on_result._srpss_runtime_generation = runtime_generation

        try:
            tm.submit_io_task(
                _load_snapshot,
                callback=_on_result,
                category="weather_startup_cache",
            )
        except Exception as exc:
            self._on_startup_cache_error(
                request_id,
                location_key,
                str(exc),
                immediate_refresh_on_miss=immediate_refresh_on_miss,
            )

    def _commit_startup_cache(
        self,
        request_id: int,
        location_key: str,
        snapshot: PreparedWeatherStartup,
        *,
        immediate_refresh_on_miss: bool = False,
    ) -> None:
        """Commit the current detached startup snapshot, then schedule refresh."""
        if (
            self._retired
            or request_id != self._startup_cache_request_id
            or location_key != _normalize_weather_location_key(self._location)
        ):
            return

        if snapshot.sample is not None:
            data = snapshot.sample.to_display_dict()
            self._cached_data = data
            self._cache_time = snapshot.cache_time
            self._deliver_state(data, from_cache=True)
        elif immediate_refresh_on_miss and automatic_service_updates_enabled():
            self.fetch_weather()
        self.schedule_refresh_cycle()

    def _on_startup_cache_error(
        self,
        request_id: int,
        location_key: str,
        error: str,
        *,
        immediate_refresh_on_miss: bool = False,
    ) -> None:
        if (
            self._retired
            or request_id != self._startup_cache_request_id
            or location_key != _normalize_weather_location_key(self._location)
        ):
            return
        logger.warning("[CACHE][WEATHER] Startup cache snapshot failed: %s", error)
        if immediate_refresh_on_miss and automatic_service_updates_enabled():
            self.fetch_weather()
        self.schedule_refresh_cycle()

    # ------------------------------------------------------------------ #
    # Refresh cadence / retry                                             #
    # ------------------------------------------------------------------ #
    def _stop_refresh_timers(self, *, delete_qtimers: bool) -> None:
        self._startup_refresh_token += 1
        stop_overlay_timer_pair(
            self,
            handle_attr="_update_timer_handle",
            qtimer_attr="_update_timer",
            delete_qtimers=delete_qtimers,
        )

    def _stop_runtime_timers(self, *, delete_qtimers: bool) -> None:
        self._stop_refresh_timers(delete_qtimers=delete_qtimers)
        # Retry is token-fenced (ThreadManager.single_shot); invalidate pending.
        self._retry_token += 1
        self._retry_pending = False

    def schedule_refresh_cycle(self) -> None:
        """Schedule startup and steady-state refresh timers (one canonical policy)."""
        if self._retired or not self._running:
            return
        # Re-scheduling replaces the prior cadence; one service owns at most one
        # startup callback and one periodic handle.
        self._stop_refresh_timers(delete_qtimers=True)
        if not automatic_service_updates_enabled():
            logger.info("[WEATHER] Automatic updates disabled via --noupdates; manual refresh only")
            return
        self._schedule_startup_refresh()
        self._start_periodic_refresh_timer()

    def _schedule_startup_refresh(self) -> None:
        decision = get_automatic_startup_refresh_decision(cache_timestamp=self._cache_time)
        if not decision.run:
            logger.info(
                "[CACHE][WEATHER] Startup timer skipped (%s%s)",
                decision.reason,
                f", cache_age_s={decision.age.total_seconds():.1f}" if decision.age is not None else "",
            )
            return
        self._startup_refresh_token += 1
        token = self._startup_refresh_token
        runtime_generation = self._runtime_generation
        self_ref = weakref.ref(self)

        def _fire() -> None:
            owner = self_ref()
            if owner is not None:
                owner._on_startup_refresh_timeout(token)

        _fire._srpss_runtime_generation = runtime_generation
        ThreadManager.single_shot(30 * 1000, _fire)
        logger.info(
            "[CACHE][WEATHER] Startup timer scheduled in 30s (%s%s)",
            decision.reason,
            f", cache_age_s={decision.age.total_seconds():.1f}" if decision.age is not None else "",
        )

    def _on_startup_refresh_timeout(self, token: int) -> None:
        if (
            self._retired
            or not self._running
            or token != self._startup_refresh_token
        ):
            return
        self.fetch_weather()

    def _start_periodic_refresh_timer(self) -> None:
        base_interval_ms = 30 * 60 * 1000  # 30 minutes
        jitter_ms = random.randint(-2 * 60 * 1000, 2 * 60 * 1000)
        interval_ms = base_interval_ms + jitter_ms
        if is_perf_metrics_enabled():
            logger.debug(
                "[PERF] WeatherRuntimeService: refresh interval %.1f min (jitter: %+.1f min)",
                interval_ms / 60000,
                jitter_ms / 60000,
            )
        handle = create_overlay_timer(
            self,
            interval_ms,
            self._on_periodic_refresh_timeout,
            description="Weather runtime refresh",
        )
        self._update_timer_handle = handle
        try:
            self._update_timer = getattr(handle, "_timer", None)
        except Exception as e:
            logger.debug("[WEATHER] Exception suppressed: %s", e)
            self._update_timer = None

    def _on_periodic_refresh_timeout(self) -> None:
        if self._retired or not self._running:
            return
        self.fetch_weather()

    def schedule_retry(self, delay_ms: int = 5 * 60 * 1000) -> None:
        """Schedule one token-fenced retry fetch (no QWidget timer ownership)."""
        if self._retired or not self._running:
            return
        if self._retry_pending:
            return
        self._retry_token += 1
        token = self._retry_token
        self._retry_pending = True
        runtime_generation = self._runtime_generation
        self_ref = weakref.ref(self)

        def _fire() -> None:
            owner = self_ref()
            if owner is None:
                return
            owner._on_retry_timeout(token)

        _fire._srpss_runtime_generation = runtime_generation
        ThreadManager.single_shot(delay_ms, _fire)

    def _on_retry_timeout(self, token: int) -> None:
        if self._retired or token != self._retry_token:
            return
        self._retry_pending = False
        if self._running:
            self.fetch_weather()

    # ------------------------------------------------------------------ #
    # Fetch                                                               #
    # ------------------------------------------------------------------ #
    def fetch_weather(self) -> None:
        """Fetch weather data (always attempts a background refresh)."""
        if self._retired or not self._location:
            return
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Weather fetch initiated for %s", self._location)
        else:
            logger.debug("Fetching fresh weather data")

        if self._thread_manager is None:
            logger.error("[THREAD_MANAGER] Weather fetch aborted: no ThreadManager available")
            return

        self._fetch_request_id += 1
        request_id = self._fetch_request_id
        location = self._location
        self._fetch_via_thread_manager(request_id, location)

    def _fetch_via_thread_manager(self, request_id: int, location: str) -> None:
        tm = self._thread_manager
        if tm is None:
            return
        location_key = _normalize_weather_location_key(location)
        runtime_generation = self._runtime_generation
        self_ref = weakref.ref(self)

        def _do_fetch() -> PreparedWeatherFetch:
            import time

            start_time = time.perf_counter()
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Weather API call starting for %s", location)
            else:
                logger.debug("[ThreadManager] Fetching weather for %s", location)
            provider = OpenMeteoProvider(timeout=10, persist_results=False)
            result = provider.get_current_weather(location)
            if is_perf_metrics_enabled():
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.debug("[PERF] Weather API call completed in %.2fms for %s", elapsed_ms, location)
            if not isinstance(result, dict):
                raise RuntimeError("No weather data returned")
            return PreparedWeatherFetch(
                sample=prepare_weather_sample(
                    result,
                    fallback_location=location,
                    observed_at=datetime.now(),
                ),
                persist_provider=provider.last_result_was_network,
            )

        _do_fetch._srpss_runtime_generation = runtime_generation

        def _on_result(result) -> None:
            sample = None
            error = None
            if getattr(result, "success", False):
                candidate = getattr(result, "result", None)
                if isinstance(candidate, PreparedWeatherFetch):
                    sample = candidate
                else:
                    error = "No weather data returned"
            else:
                error = str(getattr(result, "error", None) or "No weather data returned")

            def _deliver() -> None:
                owner = self_ref()
                if owner is None:
                    return
                if sample is not None:
                    owner.commit_weather_fetch(request_id, location_key, sample)
                else:
                    owner._commit_weather_fetch_error(request_id, location_key, str(error))

            _deliver._srpss_runtime_generation = runtime_generation
            ThreadManager.run_on_ui_thread(_deliver)

        _on_result._srpss_runtime_generation = runtime_generation

        try:
            tm.submit_io_task(
                _do_fetch,
                callback=_on_result,
                category="weather_fetch",
            )
        except Exception as e:
            logger.exception("ThreadManager IO task submission failed for weather fetch: %s", e)
            self._commit_weather_fetch_error(request_id, location_key, str(e))

    def commit_weather_fetch(
        self,
        request_id: int,
        location_key: str,
        prepared: PreparedWeatherFetch,
    ) -> None:
        """Accept only the newest current-location provider result."""
        if (
            self._retired
            or request_id != self._fetch_request_id
            or location_key != _normalize_weather_location_key(self._location)
        ):
            return
        # A live provider sample is authoritative over a still-pending startup
        # snapshot, but failed/deferred work must not discard that fallback.
        self._startup_cache_request_id += 1
        needs_refresh_cycle = (
            self._consumer_pending_first_show() and self._update_timer_handle is None
        )
        self._install_weather_data(
            prepared.sample.to_display_dict(),
            prepared.sample,
            persist_provider=prepared.persist_provider,
        )
        if needs_refresh_cycle:
            self.schedule_refresh_cycle()

    def _commit_weather_fetch_error(
        self,
        request_id: int,
        location_key: str,
        error: str,
    ) -> None:
        if (
            self._retired
            or request_id != self._fetch_request_id
            or location_key != _normalize_weather_location_key(self._location)
        ):
            return
        self.on_fetch_error(error)

    def on_weather_fetched(self, data: Dict[str, Any]) -> None:
        """Compatibility seam for an already-fetched Weather dictionary."""
        if self._retired:
            return
        sample = prepare_weather_sample(
            data,
            fallback_location=self._location,
            observed_at=datetime.now(),
        )
        self._startup_cache_request_id += 1
        self._install_weather_data(dict(data), sample)

    def _install_weather_data(
        self,
        data: Dict[str, Any],
        sample: PreparedWeatherSample,
        *,
        persist_provider: bool = False,
    ) -> None:
        """Install visible state on the consumer, then enqueue persistence."""
        self._cached_data = data
        self._cache_time = sample.observed_at
        self._deliver_state(data, from_cache=False)
        self._queue_weather_cache_persistence(sample, persist_provider=persist_provider)

    def _queue_weather_cache_persistence(
        self,
        sample: PreparedWeatherSample,
        *,
        persist_provider: bool,
    ) -> None:
        tm = self._thread_manager
        if tm is None:
            logger.debug("[CACHE][WEATHER] Persistence skipped: ThreadManager is not configured")
            return
        cache_override = _CACHE_FILE
        provider_cache_override = open_meteo_provider_module._WEATHER_CACHE_FILE
        runtime_generation = self._runtime_generation

        def _persist() -> bool:
            widget_written = write_weather_widget_cache(
                sample,
                cache_path_override=cache_override,
            )
            provider_written = True
            if persist_provider:
                provider_written = write_weather_provider_cache(
                    sample,
                    cache_path_override=provider_cache_override,
                )
            return widget_written and provider_written

        _persist._srpss_runtime_generation = runtime_generation
        try:
            tm.submit_io_task(_persist, category="weather_cache_persist")
        except Exception:
            logger.warning("[CACHE][WEATHER] Failed to submit widget-cache persistence", exc_info=True)

    def on_fetch_error(self, error: str) -> None:
        """Handle a fetch error: keep cached display, emit error, retry if needed."""
        if self._cached_data:
            logger.warning("Fetch failed, using cached data: %s", error)
            self._deliver_apply(self._cached_data)
        else:
            logger.error("Fetch failed with no cache: %s", error)

        if not self._cached_data and self._running:
            self.schedule_retry()

        self._deliver_error(error)

    # ------------------------------------------------------------------ #
    # Lifecycle                                                           #
    # ------------------------------------------------------------------ #
    def stop(self) -> None:
        """Stop refresh/retry and fence in-flight results (reusable)."""
        self._invalidate_async_results()
        self._stop_runtime_timers(delete_qtimers=True)
        self._running = False

    def retire(self) -> None:
        """Terminal retirement of Weather runtime-data ownership (idempotent)."""
        if self._retired:
            return
        self._retired = True
        self.stop()
        self._cached_data = None
        self._cache_time = None
        self._consumer_ref = None
        self._thread_manager = None
