"""Shared presentation-neutral Media runtime ownership (Phase E1 slice 6).

The configured media provider, selected GSMTC session, transport target and
accepted track/artwork snapshot are application-wide facts.  A screensaver can
have one presenter per display, but it must not create one controller, query
loop and artwork decode path per presenter.

``MediaRuntimeService`` is the per-display lease stored by that display's
``WidgetRuntimeManager``.  Production leases for the same runtime generation
join one ``_SharedMediaRuntimeOwner``.  Directly constructed ``MediaWidget``
instances use an isolated owner so tools/tests can inject a controller without
joining production state.

The shared owner contains no QWidget/QPixmap/layout/transition code.  It owns:

* controller/provider construction and retirement;
* one adaptive poll/query cadence and accepted/retained snapshot;
* runtime/request/provider/playback generations and optimistic confirmation;
* one source-resolution QImage decode per accepted artwork identity;
* first-active/last-active and last-attached consumer accounting.

Each presenter continues to own QPixmap creation, DPR/logical scaling/cropping,
transition deferral, fades, geometry, progress quantization and control feedback.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
import time
import weakref
from typing import Any, Callable, Iterable, Optional

from PySide6.QtCore import QBuffer, QByteArray
from PySide6.QtGui import QImage, QImageReader

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.media.media_controller import (
    BaseMediaController,
    MediaCommandResult,
    MediaPlaybackState,
    MediaTrackInfo,
    create_media_controller,
)
from core.media.provider_registry import (
    get_provider_failover_candidates,
    normalize_provider_id,
    preserve_provider_setting,
)
from core.threading.manager import ThreadManager
from widgets.media.runtime_state import (
    MediaWidgetRuntimeState,
    build_retained_display_info,
    cache_retained_display_info,
    mark_provider_probe_attempt,
    note_missing_session,
    should_probe_provider_failover,
)
from widgets.overlay_timers import OverlayTimerHandle, create_overlay_timer
from widgets.service_widget_runtime import stop_overlay_timer_pair

logger = get_logger(__name__)


@dataclass(frozen=True)
class PreparedMediaArtwork:
    """Source-resolution worker decode retained by the neutral owner."""

    key: tuple[int, str]
    image: QImage | None
    decode_ms: float = 0.0


@dataclass(frozen=True)
class MediaRuntimeSnapshot:
    """One coherent state revision delivered to every active presenter."""

    revision: int
    provider: str
    info: MediaTrackInfo | None
    artwork: PreparedMediaArtwork


@dataclass(frozen=True)
class _MediaQueryResult:
    info: MediaTrackInfo | None
    artwork: PreparedMediaArtwork
    selected_provider: str | None
    owner_generation: int
    request_id: int
    provider_generation: int
    playback_epoch: int
    probed_failover: bool
    worker_started: float
    worker_finished: float
    reason: str = "event"


ControllerFactory = Callable[..., BaseMediaController]


def _clone_track_info(
    info: MediaTrackInfo | None,
    *,
    state: MediaPlaybackState | None = None,
) -> MediaTrackInfo | None:
    if info is None:
        return None
    return MediaTrackInfo(
        title=info.title,
        artist=info.artist,
        album=info.album,
        album_artist=info.album_artist,
        state=state if state is not None else info.state,
        can_play_pause=info.can_play_pause,
        can_play=info.can_play,
        can_pause=info.can_pause,
        can_toggle_play_pause=info.can_toggle_play_pause,
        can_next=info.can_next,
        can_previous=info.can_previous,
        can_seek=info.can_seek,
        artwork=bytes(info.artwork) if info.artwork is not None else None,
        source_app_user_model_id=info.source_app_user_model_id,
        position_ms=info.position_ms,
        duration_ms=info.duration_ms,
    )


def compute_media_artwork_key(payload: Optional[bytes]) -> tuple[int, str]:
    """Return the stable bounded identity used by runtime and presenters."""

    if not payload:
        return (0, "")
    try:
        data = bytes(payload)
        return (len(data), hashlib.sha1(data[:4096]).hexdigest())
    except Exception as exc:
        logger.debug("[MEDIA_RUNTIME] Failed to compute artwork key: %s", exc)
        return (0, "")


def decode_media_artwork(artwork: Optional[bytes]) -> QImage | None:
    """Decode source-resolution artwork on the existing shared I/O worker."""

    if not artwork:
        return None
    try:
        data = bytes(artwork)
    except Exception as exc:
        logger.debug("[MEDIA_RUNTIME] Invalid artwork payload: %s", exc)
        return None

    header_hex = data[:16].hex() if len(data) >= 16 else data.hex()
    logger.debug(
        "[MEDIA_RUNTIME] Artwork decode: %d bytes, header=%s",
        len(data),
        header_hex,
    )
    try:
        byte_array = QByteArray(data)
        buffer = QBuffer(byte_array)
        if not buffer.open(QBuffer.OpenModeFlag.ReadOnly):
            return None
        reader = QImageReader(buffer)
        reader.setAutoTransform(True)
        image = reader.read()
        buffer.close()
    except MemoryError:
        logger.error("[MEDIA_RUNTIME] Out of memory decoding artwork", exc_info=True)
        return None
    except Exception:
        logger.debug("[MEDIA_RUNTIME] Failed to decode artwork", exc_info=True)
        return None
    if image is None or image.isNull() or image.width() <= 0 or image.height() <= 0:
        return None
    return image


def prepare_media_artwork(
    artwork: Optional[bytes],
    key: tuple[int, str],
    *,
    known_key: tuple[int, str] | None,
) -> PreparedMediaArtwork:
    """Decode a changed identity exactly once; unchanged identity is a marker."""

    if key == known_key or key == (0, ""):
        return PreparedMediaArtwork(key=key, image=None, decode_ms=0.0)
    started = time.monotonic()
    image = decode_media_artwork(artwork)
    return PreparedMediaArtwork(
        key=key,
        image=image,
        decode_ms=max(0.0, (time.monotonic() - started) * 1000.0),
    )


def _normalize_metadata(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _coalesce_partial_metadata(
    info: MediaTrackInfo | None,
    previous: MediaTrackInfo | None,
) -> MediaTrackInfo | None:
    """Retain known same-track artist/artwork through partial GSMTC snapshots."""

    if info is None or (info.artist or "").strip() or previous is None:
        return info
    if not _normalize_metadata(info.title):
        return info
    if _normalize_metadata(info.title) != _normalize_metadata(previous.title):
        return info
    if not (previous.artist or "").strip():
        return info
    try:
        return replace(
            info,
            artist=previous.artist,
            album=info.album or previous.album,
            album_artist=info.album_artist or previous.album_artist,
            artwork=info.artwork if info.artwork is not None else previous.artwork,
        )
    except Exception:
        logger.debug("[MEDIA_RUNTIME] Failed to coalesce partial metadata", exc_info=True)
        return info


_SHARED_MEDIA_OWNERS: dict[tuple[str, object], "_SharedMediaRuntimeOwner"] = {}


def _shared_owner_key(runtime_generation: Any, thread_manager: Any) -> tuple[str, object]:
    if runtime_generation is not None:
        return ("runtime", runtime_generation)
    # Standalone services never use this key.  This fallback keeps test/runtime
    # hosts without an explicit generation scoped to their actual shared pool.
    return ("thread_manager", id(thread_manager))


def _drop_shared_owner(
    key: tuple[str, object], owner: "_SharedMediaRuntimeOwner"
) -> None:
    if _SHARED_MEDIA_OWNERS.get(key) is owner:
        _SHARED_MEDIA_OWNERS.pop(key, None)


def shared_media_owner_count() -> int:
    """Read-only diagnostic used by focused cardinality regressions."""

    return len(_SHARED_MEDIA_OWNERS)


def reset_shared_media_runtime_for_tests() -> None:
    """Retire process-shared owners; intended only for isolated tests."""

    for owner in list(_SHARED_MEDIA_OWNERS.values()):
        owner.retire()
    _SHARED_MEDIA_OWNERS.clear()


class _SharedMediaRuntimeOwner:
    """One runtime-generation Media controller/query/model authority."""

    _PLAYBACK_CONFIRMATION_REFRESH_DELAY_MS = 300
    _PLAYBACK_CONFIRMATION_TIMEOUT_SEC = 3.0
    # Reconciliation / liveness watchdog interval (deep-idle scale, NOT a truth
    # cadence). Native GSMTC events are the normal truth path; this only catches
    # dropped events / provider liveness and logs [MEDIA_EVENT][MISSED_EVENT].
    _RECONCILE_INTERVAL_MS = 30000
    # Minimum spacing between timeline-only dirty refreshes. Timeline events are
    # the one class that can be chatty (position ticks); this coalescing floor
    # bounds a chatty provider while leaving seeks/track/play-pause prompt. It is
    # event-armed and single-shot (never a recurring cadence).
    _TIMELINE_COALESCE_MS = 1000

    def __init__(
        self,
        *,
        provider: str,
        thread_manager: Any,
        runtime_generation: Any,
        controller: BaseMediaController | None = None,
        controller_factory: ControllerFactory = create_media_controller,
        registry_key: tuple[str, object] | None = None,
    ) -> None:
        self._provider = preserve_provider_setting(provider)
        self._thread_manager = thread_manager
        self._runtime_generation = runtime_generation
        self._controller_factory = controller_factory
        self._controller: BaseMediaController | None = controller
        self._registry_key = registry_key

        self._leases: weakref.WeakSet[MediaRuntimeService] = weakref.WeakSet()
        self._active_leases: weakref.WeakSet[MediaRuntimeService] = weakref.WeakSet()
        self._running = False
        self._retired = False

        self._owner_generation = 0
        self._request_id = 0
        self._provider_generation = 0
        self._refresh_in_flight = False
        self._refresh_in_flight_request = 0
        self._command_refresh_pending = False
        self._event_refresh_pending = False

        # Reconciliation / liveness watchdog timer (deep-idle scale). Replaces the
        # retired 1000/2000/2500 ms active poll cadence: normal truth arrives via
        # native GSMTC events, so this single timer only reconciles/detects dropped
        # events. There is no per-display fan-out and no second cadence owner.
        self._reconcile_timer = None
        self._reconcile_timer_handle: OverlayTimerHandle | None = None

        # Native event observation state.
        self._event_observation_active = False
        self._event_observation_degraded = False
        self._last_timeline_refresh_monotonic = 0.0
        self._timeline_flush_scheduled = False
        self._timeline_flush_token = 0

        self._consecutive_none_count = 0
        self._activation_time = 0.0
        self._post_activation_grace_sec = 5.0

        # Bounded [MEDIA_EVENT] telemetry (never per-callback verbose).
        self._event_counts: dict[str, int] = {}
        self._dirty_coalesced = 0
        self._refresh_source_counts: dict[str, int] = {}
        self._stale_event_rejections = 0
        self._missed_event_count = 0

        self._runtime_state = MediaWidgetRuntimeState()
        self._current_info: MediaTrackInfo | None = None
        self._artwork = PreparedMediaArtwork((0, ""), None, 0.0)
        self._revision = 0
        self._snapshot_requires_refresh = False
        self._query_cache_info: MediaTrackInfo | None = None
        self._query_cache_ts = 0.0
        self._query_cache_ms = 500

        self._playback_epoch = 0
        self._expected_playback_state: MediaPlaybackState | None = None
        self._expected_playback_epoch: int | None = None
        self._playback_confirmation_deadline_monotonic = 0.0
        self._playback_confirmation_token = 0

        if self._controller is not None:
            self._configure_controller(self._controller)

    # ------------------------------------------------------------------
    # Consumer accounting / diagnostics
    # ------------------------------------------------------------------
    @property
    def provider(self) -> str:
        return self._provider

    @property
    def controller(self) -> BaseMediaController | None:
        return self._controller

    @property
    def owner_generation(self) -> int:
        return self._owner_generation

    @property
    def request_id(self) -> int:
        return self._request_id

    @property
    def provider_generation(self) -> int:
        return self._provider_generation

    @property
    def playback_epoch(self) -> int:
        return self._playback_epoch

    @property
    def expected_playback_state(self) -> MediaPlaybackState | None:
        return self._expected_playback_state

    @property
    def expected_playback_epoch(self) -> int | None:
        return self._expected_playback_epoch

    @property
    def playback_confirmation_deadline(self) -> float:
        return self._playback_confirmation_deadline_monotonic

    @property
    def reconcile_timer_handle(self) -> OverlayTimerHandle | None:
        return self._reconcile_timer_handle

    @property
    def refresh_in_flight(self) -> bool:
        return self._refresh_in_flight

    @property
    def event_observation_active(self) -> bool:
        return self._event_observation_active

    @property
    def event_observation_degraded(self) -> bool:
        return self._event_observation_degraded

    def event_telemetry(self) -> dict[str, Any]:
        """Bounded [MEDIA_EVENT] counters for tests and diagnostics."""

        return {
            "observation_active": self._event_observation_active,
            "observation_degraded": self._event_observation_degraded,
            "event_counts": dict(self._event_counts),
            "dirty_coalesced": self._dirty_coalesced,
            "refresh_sources": dict(self._refresh_source_counts),
            "stale_event_rejections": self._stale_event_rejections,
            "missed_events": self._missed_event_count,
        }

    def active_consumer_count(self) -> int:
        return sum(1 for lease in list(self._active_leases) if lease._consumer_alive())

    def attached_consumer_count(self) -> int:
        return sum(1 for lease in list(self._leases) if lease._consumer_alive())

    def is_running(self) -> bool:
        return self._running and not self._retired

    def is_retired(self) -> bool:
        return self._retired

    def current_info(self) -> MediaTrackInfo | None:
        return _clone_track_info(self._current_info)

    def current_snapshot(self) -> MediaRuntimeSnapshot | None:
        if self._revision <= 0 and self._current_info is None:
            return None
        return MediaRuntimeSnapshot(
            revision=self._revision,
            provider=self._provider,
            info=_clone_track_info(self._current_info),
            artwork=self._artwork,
        )

    def attach(self, lease: "MediaRuntimeService") -> None:
        if self._retired:
            raise RuntimeError("cannot attach to a retired Media owner")
        if self._thread_manager is None and lease._thread_manager is not None:
            self._thread_manager = lease._thread_manager
        elif (
            lease._thread_manager is not None
            and self._thread_manager is not None
            and lease._thread_manager is not self._thread_manager
        ):
            raise RuntimeError("shared Media consumers must use one ThreadManager")
        if (
            self._runtime_generation is not None
            and lease.runtime_generation is not None
            and lease.runtime_generation != self._runtime_generation
        ):
            raise RuntimeError("shared Media consumer runtime generation mismatch")
        self._leases.add(lease)

    def detach(self, lease: "MediaRuntimeService") -> None:
        self.deactivate(lease)
        self._leases.discard(lease)
        if not list(self._leases):
            self.retire()

    def activate(self, lease: "MediaRuntimeService") -> bool:
        if self._retired or lease not in self._leases:
            return False
        self._active_leases.add(lease)
        if self._running:
            if not self._snapshot_requires_refresh:
                snapshot = self.current_snapshot()
                if snapshot is not None:
                    lease._deliver_snapshot(snapshot)
            return True
        if self._thread_manager is None:
            logger.error("[MEDIA_RUNTIME] Cannot start without ThreadManager")
            self._active_leases.discard(lease)
            return False
        from core.media.media_native_trace import trace_media_native_stage

        trace_media_native_stage(
            component="media",
            stage="owner_activate_begin",
            generation=self._runtime_generation,
        )
        try:
            self._ensure_controller()
            self._running = True
            self._activation_time = time.monotonic()
            self._ensure_reconcile_timer()
            if self._reconcile_timer_handle is None or self._reconcile_timer is None:
                raise RuntimeError("Media reconcile heartbeat was not created")
            self._start_event_observation()
            trace_media_native_stage(
                component="media",
                stage="owner_activate_complete",
                generation=self._runtime_generation,
            )
            if not self._snapshot_requires_refresh:
                snapshot = self.current_snapshot()
                if snapshot is not None:
                    self._broadcast_snapshot(snapshot)
            self.refresh(bust_cache=True, reason="activation")
            return True
        except Exception:
            # BaseOverlayWidget treats a false start as activation failure. Keep
            # both lease and owner flags honest so reuse cannot admit a runtime
            # whose controller/timer setup only partially completed.
            self._active_leases.discard(lease)
            self.stop()
            logger.error(
                "[MEDIA_RUNTIME] Shared owner activation failed closed",
                exc_info=True,
            )
            return False

    def deactivate(self, lease: "MediaRuntimeService") -> None:
        self._active_leases.discard(lease)
        if not list(self._active_leases):
            self.stop()

    # ------------------------------------------------------------------
    # Controller/provider ownership
    # ------------------------------------------------------------------
    def _configure_controller(self, controller: BaseMediaController) -> None:
        try:
            controller.set_thread_manager(self._thread_manager)
        except Exception:
            logger.debug("[MEDIA_RUNTIME] Controller ThreadManager injection failed", exc_info=True)
        setter = getattr(controller, "set_runtime_generation", None)
        if callable(setter):
            try:
                setter(self._runtime_generation)
            except Exception:
                logger.debug("[MEDIA_RUNTIME] Controller generation injection failed", exc_info=True)
        result_setter = getattr(controller, "set_command_result_handler", None)
        if callable(result_setter):
            owner_ref = weakref.ref(self)
            owner_generation = self._owner_generation
            provider_generation = self._provider_generation
            runtime_generation = self._runtime_generation

            def _on_command_result(result: MediaCommandResult) -> None:
                def _deliver() -> None:
                    owner = owner_ref()
                    if owner is not None:
                        owner._commit_command_result(
                            controller,
                            result,
                            owner_generation=owner_generation,
                            provider_generation=provider_generation,
                        )

                _deliver._srpss_runtime_generation = runtime_generation
                ThreadManager.run_on_ui_thread(_deliver)

            _on_command_result._srpss_runtime_generation = runtime_generation
            result_setter(_on_command_result)

    def _ensure_controller(self) -> BaseMediaController:
        controller = self._controller
        if controller is None:
            controller = self._controller_factory(
                thread_manager=self._thread_manager,
                app_filter=self._provider,
            )
            self._controller = controller
        self._configure_controller(controller)
        return controller

    @staticmethod
    def _retire_controller(controller: BaseMediaController | None) -> None:
        if controller is None:
            return
        retire = getattr(controller, "retire", None)
        if callable(retire):
            try:
                retire()
            except Exception:
                logger.debug("[MEDIA_RUNTIME] Controller retirement failed", exc_info=True)

    def set_provider(
        self,
        provider: object,
        *,
        source: str,
        persist: bool = False,
        accepted_info: MediaTrackInfo | None = None,
        accepted_artwork: PreparedMediaArtwork | None = None,
    ) -> bool:
        if self._retired:
            return False
        normalized = preserve_provider_setting(provider)
        if normalized == self._provider:
            return False

        old_provider = self._provider
        old_controller = self._controller
        self._provider = normalized
        self._provider_generation += 1
        self._request_id += 1
        self._refresh_in_flight = False
        self._refresh_in_flight_request = self._request_id
        self._command_refresh_pending = False
        self._clear_query_cache()
        self._reset_playback_confirmation()
        self._runtime_state = MediaWidgetRuntimeState()
        self._current_info = _clone_track_info(accepted_info)
        if accepted_artwork is None:
            self._artwork = PreparedMediaArtwork((0, ""), None, 0.0)
        else:
            self._artwork = accepted_artwork
        self._retire_controller(old_controller)
        self._controller = None
        if self._running:
            self._ensure_controller()
            # The retired old controller detached its subscriptions; the new
            # provider's controller must observe from scratch.
            self._start_event_observation()
        self._broadcast_provider_changed(
            old_provider,
            normalized,
            source=source,
            persist=persist,
        )
        logger.info(
            "[MEDIA_RUNTIME] Provider switch: %s -> %s (source=%s)",
            old_provider,
            normalized,
            source,
        )
        if accepted_info is not None:
            cache_retained_display_info(self._runtime_state, accepted_info)
            self._publish(accepted_info)
        elif self._running:
            self.refresh(bust_cache=True)
        return True

    # ------------------------------------------------------------------
    # Presentation delivery
    # ------------------------------------------------------------------
    def _live_active_leases(self) -> list["MediaRuntimeService"]:
        live: list[MediaRuntimeService] = []
        for lease in list(self._active_leases):
            if lease._running and lease._consumer_alive():
                live.append(lease)
        return live

    def _broadcast_snapshot(self, snapshot: MediaRuntimeSnapshot) -> None:
        for lease in self._live_active_leases():
            lease._deliver_snapshot(snapshot)

    def _publish(self, info: MediaTrackInfo | None) -> None:
        self._current_info = _clone_track_info(info)
        self._revision += 1
        self._snapshot_requires_refresh = False
        self._broadcast_snapshot(
            MediaRuntimeSnapshot(
                revision=self._revision,
                provider=self._provider,
                info=_clone_track_info(info),
                artwork=self._artwork,
            )
        )

    def _broadcast_provider_changed(
        self,
        old_provider: str,
        provider: str,
        *,
        source: str,
        persist: bool,
    ) -> None:
        leases = self._live_active_leases()
        authority = leases[0] if leases else None
        for lease in leases:
            lease._deliver_provider_changed(
                old_provider,
                provider,
                source=source,
                persist=bool(persist and lease is authority),
            )

    def _broadcast_volume_target(self, provider: str, source_id: str) -> None:
        for lease in self._live_active_leases():
            lease._deliver_volume_target(provider, source_id)

    # ------------------------------------------------------------------
    # Event observation / reconcile / query ownership
    # ------------------------------------------------------------------
    def _ensure_reconcile_timer(self) -> None:
        """Arm the single deep-idle-scale reconcile/liveness heartbeat."""

        if self._retired or not self._running:
            return
        handle = self._reconcile_timer_handle
        timer = self._reconcile_timer
        if handle is not None and timer is not None:
            try:
                if timer.isActive():
                    return
            except Exception:
                pass
        handle = create_overlay_timer(
            self,
            self._RECONCILE_INTERVAL_MS,
            self._reconcile,
            description="Media reconcile heartbeat",
        )
        self._reconcile_timer_handle = handle
        self._reconcile_timer = getattr(handle, "_timer", None)

    def _stop_reconcile_timer(self) -> None:
        stop_overlay_timer_pair(
            self,
            handle_attr="_reconcile_timer_handle",
            qtimer_attr="_reconcile_timer",
            delete_qtimers=True,
        )

    def _start_event_observation(self) -> None:
        """Best-effort: subscribe native dirty edges; loud/degraded on failure."""

        controller = self._controller
        if controller is None:
            return
        try:
            supported = bool(controller.supports_event_observation())
        except Exception:
            supported = False
        if not supported:
            self._event_observation_active = False
            self._event_observation_degraded = True
            logger.warning(
                "[MEDIA_EVENT][DEGRADED] controller cannot observe native events; "
                "relying on the %ds reconcile watchdog (provider=%s). The retired "
                "1-2.5s active poll is NOT reactivated.",
                self._RECONCILE_INTERVAL_MS // 1000,
                self._provider,
            )
            return
        owner_ref = weakref.ref(self)
        owner_generation = self._owner_generation
        runtime_generation = self._runtime_generation

        def _on_dirty(reason: str) -> None:
            # Native WinRT thread -> hop to the UI thread + fence by generation.
            def _deliver() -> None:
                owner = owner_ref()
                if owner is not None:
                    owner._handle_dirty_edge(str(reason), owner_generation)

            _deliver._srpss_runtime_generation = runtime_generation
            ThreadManager.run_on_ui_thread(_deliver)

        def _on_established(ok: bool, detail: str) -> None:
            def _deliver() -> None:
                owner = owner_ref()
                if owner is not None:
                    owner._on_observation_established(
                        bool(ok), str(detail), owner_generation
                    )

            _deliver._srpss_runtime_generation = runtime_generation
            ThreadManager.run_on_ui_thread(_deliver)

        try:
            started = bool(
                controller.start_event_observation(_on_dirty, _on_established)
            )
        except Exception:
            started = False
            logger.debug("[MEDIA_EVENT] start_event_observation raised", exc_info=True)
        if not started:
            self._event_observation_active = False
            self._event_observation_degraded = True
            logger.warning(
                "[MEDIA_EVENT][DEGRADED] native observation could not start "
                "(provider=%s); relying on the reconcile watchdog.",
                self._provider,
            )

    def _stop_event_observation(self) -> None:
        controller = self._controller
        if controller is not None:
            try:
                controller.stop_event_observation()
            except Exception:
                logger.debug(
                    "[MEDIA_EVENT] controller stop_event_observation failed",
                    exc_info=True,
                )
        if self._event_observation_active or self._event_counts:
            self._log_event_summary()
        self._event_observation_active = False

    def _on_observation_established(
        self, ok: bool, detail: str, owner_generation: int
    ) -> None:
        if self._retired or not self._running or owner_generation != self._owner_generation:
            return
        self._event_observation_active = bool(ok)
        self._event_observation_degraded = not bool(ok)
        if ok:
            logger.info(
                "[MEDIA_EVENT] observation active provider=%s detail=%s",
                self._provider,
                detail,
            )
        else:
            logger.warning(
                "[MEDIA_EVENT][DEGRADED] observation failed provider=%s detail=%s",
                self._provider,
                detail,
            )

    def _handle_dirty_edge(self, reason: str, owner_generation: int) -> None:
        """Coalesce one native dirty edge into the single shared refresh path."""

        if self._retired or not self._running:
            return
        if owner_generation != self._owner_generation:
            self._stale_event_rejections += 1
            return
        self._event_counts[reason] = self._event_counts.get(reason, 0) + 1
        if not self._event_observation_active:
            # A real edge proves observation is live even before the establishment
            # callback lands.
            self._event_observation_active = True
            self._event_observation_degraded = False
        if reason == "timeline":
            now = time.monotonic()
            elapsed_ms = (now - self._last_timeline_refresh_monotonic) * 1000.0
            if elapsed_ms < self._TIMELINE_COALESCE_MS:
                self._schedule_timeline_flush(self._TIMELINE_COALESCE_MS - elapsed_ms)
                return
            self._last_timeline_refresh_monotonic = now
        self._launch_dirty_refresh()

    def _launch_dirty_refresh(self) -> None:
        if self._refresh_in_flight:
            if self._event_refresh_pending:
                # Already one pending edge: collapse this one into it.
                self._dirty_coalesced += 1
            else:
                self._event_refresh_pending = True
            return
        self.refresh(bust_cache=True, reason="event")

    def _schedule_timeline_flush(self, delay_ms: float) -> None:
        if self._timeline_flush_scheduled:
            self._dirty_coalesced += 1
            return
        self._timeline_flush_scheduled = True
        self._timeline_flush_token += 1
        token = self._timeline_flush_token
        runtime_generation = self._runtime_generation
        owner_ref = weakref.ref(self)

        def _flush() -> None:
            owner = owner_ref()
            if owner is None:
                return
            if (
                owner._retired
                or not owner._running
                or token != owner._timeline_flush_token
            ):
                return
            owner._timeline_flush_scheduled = False
            owner._last_timeline_refresh_monotonic = time.monotonic()
            owner._launch_dirty_refresh()

        _flush._srpss_runtime_generation = runtime_generation
        ThreadManager.single_shot(max(1, int(delay_ms)), _flush)

    def _reconcile(self) -> None:
        """Deep-idle-scale watchdog: reconcile and detect dropped native events."""

        if self._retired or not self._running:
            return
        self.refresh(bust_cache=True, reason="reconcile")

    def wake_from_idle(self) -> None:
        """Force one prompt reconcile refresh (external wake / interaction)."""

        if self._retired or not self._running:
            return
        self._consecutive_none_count = 0
        self.refresh(bust_cache=True, reason="wake")

    def _log_event_summary(self) -> None:
        logger.info(
            "[MEDIA_EVENT] summary provider=%s events=%s coalesced=%d refreshes=%s "
            "stale_rejected=%d missed=%d degraded=%s",
            self._provider,
            dict(self._event_counts),
            self._dirty_coalesced,
            dict(self._refresh_source_counts),
            self._stale_event_rejections,
            self._missed_event_count,
            self._event_observation_degraded,
        )

    @staticmethod
    def _state_fingerprint(
        info: MediaTrackInfo | None,
        artwork_key: tuple[int, str],
    ) -> tuple[Any, ...]:
        """Non-position identity used to spot a reconcile-discovered missed event."""

        if info is None:
            return (None, None, None, None, artwork_key)
        return (
            _normalize_metadata(info.title),
            _normalize_metadata(info.artist),
            _normalize_metadata(info.album),
            info.state,
            artwork_key,
        )

    def _clear_query_cache(self) -> None:
        self._query_cache_info = None
        self._query_cache_ts = 0.0

    def refresh(self, *, bust_cache: bool = False, reason: str = "event") -> bool:
        if self._retired or not self._running or not self._active_leases:
            return False
        if bust_cache:
            self._clear_query_cache()
        now = time.monotonic()
        if self._query_cache_info is not None and not bust_cache:
            age_ms = (now - self._query_cache_ts) * 1000.0
            if age_ms < self._query_cache_ms:
                self._publish(self._query_cache_info)
                return True
        if self._refresh_in_flight:
            return False
        tm = self._thread_manager
        if tm is None:
            logger.error("[MEDIA_RUNTIME] Refresh unavailable without ThreadManager")
            return False

        controller = self._ensure_controller()
        self._request_id += 1
        request_id = self._request_id
        owner_generation = self._owner_generation
        provider_generation = self._provider_generation
        playback_epoch = self._playback_epoch
        provider = self._provider
        fallback_artwork = (
            getattr(self._current_info, "artwork", None)
            if self._current_info is not None
            else None
        )
        known_artwork_key = self._artwork.key
        allow_failover = bool(get_provider_failover_candidates(provider)) and (
            should_probe_provider_failover(self._runtime_state)
            and not self._has_fresh_info()
        )
        fallback_providers: Iterable[str] = (
            get_provider_failover_candidates(provider) if allow_failover else ()
        )
        self._refresh_in_flight = True
        self._refresh_in_flight_request = request_id
        runtime_generation = self._runtime_generation
        owner_ref = weakref.ref(self)

        def _do_query() -> _MediaQueryResult:
            worker_started = time.monotonic()
            selected_provider: str | None = None
            info: MediaTrackInfo | None = None
            try:
                worker_query = getattr(controller, "get_current_track_from_io_worker", None)
                if callable(worker_query):
                    selected_provider, info = worker_query(fallback_providers)
                else:
                    info = controller.get_current_track()
                    if info is not None:
                        selected_provider = provider
            except Exception:
                logger.debug("[MEDIA_RUNTIME] get_current_track failed", exc_info=True)
            artwork_payload = (
                getattr(info, "artwork", None) if info is not None else fallback_artwork
            )
            artwork_key = compute_media_artwork_key(artwork_payload)
            prepared = prepare_media_artwork(
                artwork_payload,
                artwork_key,
                known_key=known_artwork_key,
            )
            return _MediaQueryResult(
                info=info,
                artwork=prepared,
                selected_provider=normalize_provider_id(selected_provider),
                owner_generation=owner_generation,
                request_id=request_id,
                provider_generation=provider_generation,
                playback_epoch=playback_epoch,
                probed_failover=allow_failover,
                worker_started=worker_started,
                worker_finished=time.monotonic(),
                reason=reason,
            )

        _do_query._srpss_runtime_generation = runtime_generation

        def _on_result(task_result: Any) -> None:
            candidate = (
                getattr(task_result, "result", None)
                if getattr(task_result, "success", False)
                else None
            )

            def _deliver() -> None:
                owner = owner_ref()
                if owner is None:
                    return
                try:
                    owner._commit_query(candidate)
                finally:
                    if owner._refresh_in_flight_request == request_id:
                        owner._refresh_in_flight = False
                        # One pending dirty edge may launch one further refresh.
                        # Command confirmations take precedence over event edges.
                        if owner._command_refresh_pending:
                            owner._command_refresh_pending = False
                            owner._event_refresh_pending = False
                            owner.refresh(bust_cache=True, reason="command")
                        elif owner._event_refresh_pending:
                            owner._event_refresh_pending = False
                            owner.refresh(bust_cache=True, reason="event")

            _deliver._srpss_runtime_generation = runtime_generation
            ThreadManager.run_on_ui_thread(_deliver)

        _on_result._srpss_runtime_generation = runtime_generation
        self._refresh_source_counts[reason] = (
            self._refresh_source_counts.get(reason, 0) + 1
        )
        try:
            tm.submit_io_task(
                _do_query,
                callback=_on_result,
                task_id=(
                    f"media_runtime_query_{runtime_generation}_{owner_generation}_"
                    f"{provider_generation}_{request_id}"
                ),
                category="media_refresh",
            )
        except TypeError:
            # Small compatibility managers used by standalone tools/tests may not
            # accept diagnostic keywords; ownership/fencing remains unchanged.
            tm.submit_io_task(_do_query, callback=_on_result)
        except Exception:
            logger.debug("[MEDIA_RUNTIME] Failed to submit refresh", exc_info=True)
            if self._refresh_in_flight_request == request_id:
                self._refresh_in_flight = False
            return False
        return True

    def _query_is_current(self, result: _MediaQueryResult) -> bool:
        return bool(
            not self._retired
            and self._running
            and result.owner_generation == self._owner_generation
            and result.request_id == self._request_id
            and result.provider_generation == self._provider_generation
        )

    def _commit_query(self, result: Any) -> None:
        if not isinstance(result, _MediaQueryResult) or not self._query_is_current(result):
            return
        prior_fingerprint = self._state_fingerprint(self._current_info, self._artwork.key)
        info = self._reconcile_playback_epoch(result.info, result.playback_epoch)
        info = _coalesce_partial_metadata(info, self._current_info)
        if result.probed_failover:
            mark_provider_probe_attempt(self._runtime_state)
        selected_provider = normalize_provider_id(result.selected_provider)
        failover_provider = (
            selected_provider
            if selected_provider is not None and selected_provider != self._provider
            else None
        )
        if failover_provider is not None:
            self._accept_artwork(info, result.artwork)
            self.set_provider(
                failover_provider,
                source="media_runtime_autofallback",
                persist=True,
                accepted_info=info,
                accepted_artwork=self._artwork,
            )
            self._broadcast_volume_target(
                failover_provider,
                getattr(info, "source_app_user_model_id", "") if info else "",
            )
            return

        display_info = self._accept_info(info)
        self._accept_artwork(display_info, result.artwork)
        self._query_cache_info = _clone_track_info(display_info)
        self._query_cache_ts = time.monotonic()
        self._broadcast_volume_target(
            self._provider,
            getattr(display_info, "source_app_user_model_id", "")
            if display_info is not None
            else "",
        )
        self._publish(display_info)
        if result.reason == "reconcile":
            new_fingerprint = self._state_fingerprint(display_info, self._artwork.key)
            if new_fingerprint != prior_fingerprint:
                self._missed_event_count += 1
                logger.warning(
                    "[MEDIA_EVENT][MISSED_EVENT] reconcile watchdog found a "
                    "non-position change no native event delivered provider=%s "
                    "missed_total=%d",
                    self._provider,
                    self._missed_event_count,
                )
        if is_perf_metrics_enabled():
            worker_ms = max(
                0.0,
                (result.worker_finished - result.worker_started) * 1000.0,
            )
            elapsed_ms = max(0.0, (time.monotonic() - result.worker_started) * 1000.0)
            if elapsed_ms >= 1000.0 or worker_ms >= 1000.0:
                logger.warning(
                    "[PERF][MEDIA_RUNTIME] slow shared refresh total_ms=%.1f "
                    "worker_ms=%.1f provider=%s",
                    elapsed_ms,
                    worker_ms,
                    self._provider,
                )

    def _has_fresh_info(self) -> bool:
        retained = self._runtime_state.retained_display_info
        if retained is None:
            return False
        return (
            time.monotonic() - self._runtime_state.retained_display_info_ts
        ) < 5.0

    def _accept_info(self, info: MediaTrackInfo | None) -> MediaTrackInfo | None:
        if info is not None:
            had_missing_session = self._consecutive_none_count > 0
            cache_retained_display_info(self._runtime_state, info)
            self._consecutive_none_count = 0
            if had_missing_session:
                # Recovery from a missing-session gap reopens the activation grace
                # window; a routine successful event does not.
                self._activation_time = time.monotonic()
            return info

        if (
            self._activation_time > 0
            and time.monotonic() - self._activation_time < self._post_activation_grace_sec
        ):
            return build_retained_display_info(self._runtime_state)

        # Missing session: retain the last accepted snapshot. Event-driven
        # observation means there is no idle poll cadence to slow down - the
        # absence of native events is itself the idle state, and the reconcile
        # watchdog remains the only (deep-idle-scale) query.
        self._consecutive_none_count += 1
        note_missing_session(self._runtime_state)
        return build_retained_display_info(self._runtime_state)

    def _accept_artwork(
        self,
        info: MediaTrackInfo | None,
        prepared: PreparedMediaArtwork,
    ) -> None:
        final_key = compute_media_artwork_key(
            getattr(info, "artwork", None) if info is not None else None
        )
        if final_key == self._artwork.key:
            return
        if prepared.key != final_key:
            # A retained/coalesced final snapshot may deliberately keep the
            # already-owned image while the raw query carried no artwork.
            if final_key == self._artwork.key:
                return
            self._artwork = PreparedMediaArtwork(final_key, None, 0.0)
            return
        self._artwork = PreparedMediaArtwork(
            key=prepared.key,
            image=prepared.image,
            decode_ms=prepared.decode_ms,
        )
        if is_perf_metrics_enabled() and prepared.key != (0, ""):
            logger.info(
                "[PERF][MEDIA_ARTWORK] event=decoded_shared key_id=%s "
                "payload_bytes=%d decode_ms=%.2f decode_ok=%s consumers=%d",
                prepared.key[1][:12],
                prepared.key[0],
                prepared.decode_ms,
                prepared.image is not None and not prepared.image.isNull(),
                self.active_consumer_count(),
            )

    # ------------------------------------------------------------------
    # Shared transport / optimistic playback ownership
    # ------------------------------------------------------------------
    def _reset_playback_confirmation(self) -> None:
        self._playback_confirmation_token += 1
        self._expected_playback_state = None
        self._expected_playback_epoch = None
        self._playback_confirmation_deadline_monotonic = 0.0

    def _commit_command_result(
        self,
        controller: BaseMediaController,
        result: MediaCommandResult,
        *,
        owner_generation: int,
        provider_generation: int,
    ) -> None:
        """Reconcile only a current controller's real provider completion."""

        if (
            self._retired
            or not self._running
            or controller is not self._controller
            or owner_generation != self._owner_generation
            or provider_generation != self._provider_generation
            or not isinstance(result, MediaCommandResult)
        ):
            return
        if result.action == "play_pause" and not result.succeeded:
            self._reset_playback_confirmation()
        self._clear_query_cache()
        if self._refresh_in_flight:
            self._command_refresh_pending = True
        else:
            self.refresh(bust_cache=True, reason="command")

    def _begin_playback_confirmation(self, state: MediaPlaybackState) -> None:
        self._reset_playback_confirmation()
        self._playback_epoch += 1
        self._expected_playback_state = state
        self._expected_playback_epoch = self._playback_epoch
        self._playback_confirmation_deadline_monotonic = (
            time.monotonic() + self._PLAYBACK_CONFIRMATION_TIMEOUT_SEC
        )
        self._clear_query_cache()
        token = self._playback_confirmation_token
        runtime_generation = self._runtime_generation
        owner_ref = weakref.ref(self)

        def _confirm_refresh() -> None:
            owner = owner_ref()
            if (
                owner is None
                or owner._retired
                or not owner._running
                or token != owner._playback_confirmation_token
            ):
                return
            owner.refresh(bust_cache=True)

        _confirm_refresh._srpss_runtime_generation = runtime_generation
        ThreadManager.single_shot(
            self._PLAYBACK_CONFIRMATION_REFRESH_DELAY_MS,
            _confirm_refresh,
        )

    def _reconcile_playback_epoch(
        self,
        info: MediaTrackInfo | None,
        refresh_epoch: int,
    ) -> MediaTrackInfo | None:
        if info is None:
            return None
        current_epoch = self._playback_epoch
        expected = self._expected_playback_state
        expected_epoch = self._expected_playback_epoch
        if refresh_epoch == current_epoch:
            if expected is None or expected_epoch != current_epoch:
                return info
            if info.state == expected:
                self._reset_playback_confirmation()
                return info
            if time.monotonic() >= self._playback_confirmation_deadline_monotonic:
                self._reset_playback_confirmation()
                return info
            state_to_preserve = expected
        else:
            current = self._current_info.state if self._current_info is not None else None
            state_to_preserve = expected if expected is not None else current
            if state_to_preserve is None:
                return info
        if info.state == state_to_preserve:
            return info
        try:
            return replace(info, state=state_to_preserve)
        except Exception:
            return info

    def play_pause(self, *, execute: bool = True) -> bool:
        if self._retired or not self._running:
            return False
        info = self._current_info
        next_state = None
        if info is not None and info.state in (
            MediaPlaybackState.PLAYING,
            MediaPlaybackState.PAUSED,
        ):
            next_state = (
                MediaPlaybackState.PAUSED
                if info.state == MediaPlaybackState.PLAYING
                else MediaPlaybackState.PLAYING
            )
        controller = self._ensure_controller()
        if execute:
            try:
                if not controller.play_pause(next_state):
                    return False
            except Exception:
                logger.debug("[MEDIA_RUNTIME] play_pause failed", exc_info=True)
                return False
        if info is not None and next_state is not None:
            optimistic = replace(info, state=next_state)
            self._begin_playback_confirmation(next_state)
            self._publish(optimistic)
        else:
            self.refresh(bust_cache=True)
        return True

    def next_track(self, *, execute: bool = True) -> bool:
        return self._transport_without_optimistic("next", execute=execute)

    def previous_track(self, *, execute: bool = True) -> bool:
        return self._transport_without_optimistic("previous", execute=execute)

    def seek_fraction(self, fraction: float, *, execute: bool = True) -> bool:
        """Route a semantic seek without projecting unaccepted timeline state."""

        if self._retired or not self._running:
            return False
        info = self._current_info
        if info is None or not info.can_seek or not info.duration_ms:
            return False
        try:
            parsed_fraction = float(fraction)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(parsed_fraction):
            return False
        bounded_fraction = max(0.0, min(1.0, parsed_fraction))
        controller = self._ensure_controller()
        if execute:
            try:
                if not controller.seek_fraction(bounded_fraction):
                    return False
            except Exception:
                logger.debug("[MEDIA_RUNTIME] seek failed", exc_info=True)
                return False
        # The accepted provider snapshot remains authoritative; seeking does
        # not optimistically rewrite the displayed position.
        if not execute:
            self.refresh(bust_cache=True)
        return True

    def _transport_without_optimistic(self, action: str, *, execute: bool) -> bool:
        if self._retired or not self._running:
            return False
        controller = self._ensure_controller()
        if execute:
            try:
                if not getattr(controller, action)():
                    return False
            except Exception:
                logger.debug("[MEDIA_RUNTIME] %s failed", action, exc_info=True)
                return False
        if not execute:
            self.refresh(bust_cache=True)
        return True

    # ------------------------------------------------------------------
    # Stop / retirement
    # ------------------------------------------------------------------
    def stop(self) -> None:
        if self._retired:
            return
        # Teardown order: close event admission, detach native subscriptions,
        # fence queued deliveries, then stop the reconcile heartbeat.
        self._running = False
        self._stop_event_observation()
        # Retain accepted data for the first fresh post-restart reconciliation,
        # but never replay it merely because a new activation began. This
        # preserves the legacy stop/start cache-retirement contract.
        self._snapshot_requires_refresh = True
        self._owner_generation += 1
        self._request_id += 1
        self._refresh_in_flight = False
        self._refresh_in_flight_request = self._request_id
        self._command_refresh_pending = False
        self._event_refresh_pending = False
        self._timeline_flush_scheduled = False
        self._timeline_flush_token += 1
        self._stop_reconcile_timer()
        self._reset_playback_confirmation()
        self._clear_query_cache()

    def retire(self) -> None:
        if self._retired:
            return
        self.stop()
        self._retired = True
        self._retire_controller(self._controller)
        self._controller = None
        self._active_leases.clear()
        self._leases.clear()
        self._current_info = None
        self._runtime_state = MediaWidgetRuntimeState()
        self._artwork = PreparedMediaArtwork((0, ""), None, 0.0)
        self._snapshot_requires_refresh = True
        self._thread_manager = None
        if self._registry_key is not None:
            _drop_shared_owner(self._registry_key, self)


class MediaRuntimeService:
    """Per-display neutral lease/projection to a Media family runtime owner."""

    def __init__(
        self,
        *,
        provider: str = "spotify",
        shared: bool = True,
        controller: BaseMediaController | None = None,
        controller_factory: ControllerFactory = create_media_controller,
        runtime_generation: Any = None,
    ) -> None:
        if shared and controller is not None:
            raise ValueError("controller injection is isolated-standalone only")
        self._configured_provider = preserve_provider_setting(provider)
        self._shared = bool(shared)
        self._controller = controller
        self._controller_factory = controller_factory
        self._runtime_generation = runtime_generation
        self._thread_manager: Any = None
        self._consumer_ref: weakref.ReferenceType | None = None
        self._owner: _SharedMediaRuntimeOwner | None = None
        self._running = False
        self._retired = False

    @property
    def runtime_generation(self) -> Any:
        return self._runtime_generation

    @property
    def provider(self) -> str:
        owner = self._owner
        return owner.provider if owner is not None else self._configured_provider

    @property
    def shared_owner(self) -> _SharedMediaRuntimeOwner | None:
        return self._owner

    def current_info(self) -> MediaTrackInfo | None:
        owner = self._owner
        return owner.current_info() if owner is not None else None

    def current_snapshot(self) -> MediaRuntimeSnapshot | None:
        owner = self._owner
        return owner.current_snapshot() if owner is not None else None

    def is_running(self) -> bool:
        return bool(
            self._running
            and not self._retired
            and self._owner is not None
            and self._owner.is_running()
        )

    def is_retired(self) -> bool:
        return self._retired

    def set_thread_manager(self, thread_manager: Any) -> None:
        self._thread_manager = thread_manager
        owner = self._owner
        if owner is not None:
            if owner._thread_manager is None:
                owner._thread_manager = thread_manager
            elif thread_manager is not None and owner._thread_manager is not thread_manager:
                raise RuntimeError("shared Media lease cannot replace ThreadManager")

    def attach_consumer(self, consumer: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot attach consumer to retired Media service")
        current_consumer = self._consumer()
        if current_consumer is not None and current_consumer is not consumer:
            raise RuntimeError("Media lease already belongs to another consumer")
        if self._owner is not None:
            if current_consumer is consumer:
                return
            raise RuntimeError("Media lease already has an owner")
        self._consumer_ref = weakref.ref(consumer)
        generation = getattr(consumer, "_runtime_generation", None)
        if generation is None:
            try:
                generation = getattr(consumer.parent(), "_runtime_generation", None)
            except Exception:
                generation = None
        if generation is not None:
            self._runtime_generation = generation
        if self._thread_manager is None:
            self._thread_manager = getattr(consumer, "_thread_manager", None)

        if self._shared:
            if self._runtime_generation is None and self._thread_manager is None:
                self._consumer_ref = None
                raise RuntimeError(
                    "shared Media lease requires runtime generation or ThreadManager"
                )
            key = _shared_owner_key(self._runtime_generation, self._thread_manager)
            owner = _SHARED_MEDIA_OWNERS.get(key)
            owner_created = False
            if owner is None or owner.is_retired():
                owner = _SharedMediaRuntimeOwner(
                    provider=self._configured_provider,
                    thread_manager=self._thread_manager,
                    runtime_generation=self._runtime_generation,
                    controller_factory=self._controller_factory,
                    registry_key=key,
                )
                _SHARED_MEDIA_OWNERS[key] = owner
                owner_created = True
            elif owner.provider != self._configured_provider:
                logger.warning(
                    "[MEDIA_RUNTIME] Joining live shared provider %s with stale configured value %s",
                    owner.provider,
                    self._configured_provider,
                )
        else:
            owner = _SharedMediaRuntimeOwner(
                provider=self._configured_provider,
                thread_manager=self._thread_manager,
                runtime_generation=self._runtime_generation,
                controller=self._controller,
                controller_factory=self._controller_factory,
            )
            owner_created = True
        try:
            owner.attach(self)
        except Exception:
            self._consumer_ref = None
            if owner_created:
                owner.retire()
            raise
        self._owner = owner

    def detach_consumer(self, consumer: Any = None) -> None:
        current = self._consumer()
        if consumer is not None and current is not consumer:
            return
        owner = self._owner
        if owner is not None:
            owner.detach(self)
        self._owner = None
        self._consumer_ref = None
        self._running = False

    def _consumer(self) -> Any:
        return self._consumer_ref() if self._consumer_ref is not None else None

    def _consumer_alive(self) -> bool:
        consumer = self._consumer()
        if consumer is None:
            return False
        try:
            return bool(consumer.is_media_consumer_alive())
        except Exception:
            return False

    def _deliver_snapshot(self, snapshot: MediaRuntimeSnapshot) -> None:
        consumer = self._consumer()
        if not self._running or consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_media_runtime_snapshot(snapshot)
        except Exception:
            logger.debug("[MEDIA_RUNTIME] Snapshot delivery failed", exc_info=True)

    def _deliver_provider_changed(
        self,
        old_provider: str,
        provider: str,
        *,
        source: str,
        persist: bool,
    ) -> None:
        consumer = self._consumer()
        if not self._running or consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_media_runtime_provider_changed(
                old_provider,
                provider,
                source=source,
                persist=persist,
            )
        except Exception:
            logger.debug("[MEDIA_RUNTIME] Provider delivery failed", exc_info=True)

    def _deliver_volume_target(self, provider: str, source_id: str) -> None:
        consumer = self._consumer()
        if not self._running or consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_media_runtime_volume_target(provider, source_id)
        except Exception:
            logger.debug("[MEDIA_RUNTIME] Volume-target delivery failed", exc_info=True)

    def start(self) -> bool:
        if self._retired or self._owner is None:
            return False
        if self._running:
            return True
        self._running = True
        try:
            activated = self._owner.activate(self)
        except Exception:
            logger.error(
                "[MEDIA_RUNTIME] Lease activation failed closed",
                exc_info=True,
            )
            activated = False
        if not activated:
            self._running = False
            return False
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._owner is not None:
            self._owner.deactivate(self)

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self.detach_consumer()
        self._thread_manager = None

    def set_provider_runtime(self, provider: object, *, source: str = "settings") -> bool:
        owner = self._owner
        if owner is None:
            normalized = preserve_provider_setting(provider)
            changed = normalized != self._configured_provider
            self._configured_provider = normalized
            return changed
        changed = owner.set_provider(provider, source=source, persist=False)
        self._configured_provider = owner.provider
        return changed

    def refresh(self, *, bust_cache: bool = False) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.refresh(bust_cache=bust_cache))

    def wake_from_idle(self) -> None:
        if self._owner is not None:
            self._owner.wake_from_idle()

    def play_pause(self, *, execute: bool = True) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.play_pause(execute=execute))

    def next_track(self, *, execute: bool = True) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.next_track(execute=execute))

    def previous_track(self, *, execute: bool = True) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.previous_track(execute=execute))

    def seek_fraction(self, fraction: float, *, execute: bool = True) -> bool:
        owner = self._owner
        return bool(
            owner is not None
            and owner.seek_fraction(fraction, execute=execute)
        )
