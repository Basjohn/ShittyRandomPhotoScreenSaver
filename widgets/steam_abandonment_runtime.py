"""Presentation-neutral Steam Abandonment runtime/model owner (E1 slice 4).

``AbandonmentRuntimeService`` owns the non-pixel lifecycle for one retained
Abandonment Issues card:

- cache-first startup load;
- source refresh and explicit manual force-refresh;
- cache-backed rotation cadence and rotation work;
- request/generation admission and stale-result fencing;
- prepared semantic model + decoded dynamic-image state;
- idempotent stop/retirement independent of QWidget lifetime.

The existing ``core.steam`` cache/backend/credential/request-policy helpers
remain the source and persistence authorities.  This module does not introduce
a Steam provider singleton or share one card's selection/cadence with another
display.  Current cardinality remains one Abandonment runtime per enabled
card/display.

The retained presentation model implements a small consumer protocol:

- ``is_abandonment_consumer_alive()``
- ``on_abandonment_presentation(presentation, *, animate)``
- ``request_abandonment_fade()``
- ``on_abandonment_rotation_due()``

It retains only accepted presentation state, transition-only deferral and
semantic action routing. The service remains independent of Quick geometry,
pixels and item lifetime.
"""
from __future__ import annotations

import weakref
from typing import Any, Optional

from core.logging.logger import get_logger
from core.runtime_flags import automatic_service_updates_enabled
from core.threading.manager import ThreadManager
from widgets.overlay_timers import OverlayTimerHandle, create_overlay_timer
from widgets.steam_abandonment_preparation import (
    AbandonmentPreparedPresentation,
    AbandonmentRuntimeConfig,
    achievement_evidence_requested,
    prepare_abandonment_presentation,
)


logger = get_logger(__name__)


class AbandonmentRuntimeService:
    """Own one Abandonment card's cache/source/model/rotation lifecycle."""

    def __init__(
        self,
        *,
        config: Optional[AbandonmentRuntimeConfig] = None,
        runtime_generation: Any = None,
    ) -> None:
        self._consumer_ref: Optional[weakref.ref] = None
        self._thread_manager: Any = None
        self._runtime_generation = runtime_generation
        self._task_owner_token = id(self)
        self._config = self._normalize_config(config or AbandonmentRuntimeConfig())

        self._current_presentation: Optional[AbandonmentPreparedPresentation] = None
        self._activation_cache_preloaded = False
        self._activation_has_metadata = False
        self._activation_cache_age_seconds: Optional[float] = None
        self._activation_rotation_due_seconds: Optional[float] = None
        self._activation_refresh_scheduled = False
        self._start_fade_after_cache_load = False

        self._cache_load_started = False
        self._refresh_in_progress = False
        self._rotation_in_progress = False

        self._owner_generation = 0
        self._state_request_id = 0
        self._cache_request_id = 0
        self._refresh_request_id = 0
        self._rotation_request_id = 0

        self._rotation_timer: Optional[OverlayTimerHandle] = None
        self._rotation_initial_delay = False

        self._running = False
        self._retired = False

    # ------------------------------------------------------------------
    # Configuration / consumer bridge
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_config(config: AbandonmentRuntimeConfig) -> AbandonmentRuntimeConfig:
        return AbandonmentRuntimeConfig(
            selection=config.selection,
            field_visibility={
                str(key): bool(value) for key, value in config.field_visibility.items()
            },
            show_artwork=bool(config.show_artwork),
            artwork_shape=str(config.artwork_shape or "portrait"),
            guilt_desaturater=bool(config.guilt_desaturater),
            guilt_desaturation_strength=max(
                0, min(100, int(config.guilt_desaturation_strength))
            ),
            refresh_minutes=max(1, int(config.refresh_minutes)),
            show_connection_info_icon=bool(config.show_connection_info_icon),
            show_rediscovery_message=bool(config.show_rediscovery_message),
        )

    def configure(self, config: AbandonmentRuntimeConfig) -> None:
        if self._retired:
            raise RuntimeError("cannot configure a retired Abandonment runtime service")
        normalized = self._normalize_config(config)
        if normalized == self._config:
            return
        if self._running:
            raise RuntimeError("Abandonment runtime configuration is immutable while running")
        self._config = normalized
        self._invalidate_async_results()
        self._current_presentation = None
        self._activation_cache_preloaded = False
        self._activation_has_metadata = False
        self._activation_cache_age_seconds = None
        self._activation_rotation_due_seconds = None
        self._cache_load_started = False
        logger.info(
            "[STEAM][ABANDONMENT_CADENCE] shared_refresh_minutes=%s "
            "rotation_minutes=%s authority=widgets.steam.refresh_minutes",
            normalized.refresh_minutes,
            normalized.refresh_minutes,
        )

    def attach_consumer(self, consumer: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot attach a consumer to a retired Abandonment runtime service")
        generation = getattr(consumer, "_runtime_generation", None)
        if generation is None:
            try:
                parent = consumer.parent()
            except Exception:
                parent = None
            generation = getattr(parent, "_runtime_generation", None)

        generation_changed = (
            generation is not None and generation != self._runtime_generation
        )
        if generation_changed:
            # A registry-owned service may outlive one retained presentation
            # consumer. A new display generation must never admit work submitted
            # for the previous generation, even when the service is rebound.
            if self._running:
                self.stop()
            else:
                self._invalidate_async_results()
            self._runtime_generation = generation

        self._consumer_ref = weakref.ref(consumer)
        if self._current_presentation is not None:
            self._deliver_presentation(self._current_presentation, animate=False)

    def detach_consumer(self, consumer: Any = None) -> None:
        current = self._consumer()
        if consumer is None or current is consumer:
            # Detachment is a runtime boundary, not merely a weak-reference
            # update.  Stop cadence and invalidate late task completions before
            # the presentation edge disappears.
            if self._running:
                self.stop()
            self._consumer_ref = None

    def _consumer(self) -> Any:
        return self._consumer_ref() if self._consumer_ref is not None else None

    def _consumer_alive(self) -> bool:
        consumer = self._consumer()
        if consumer is None:
            return False
        try:
            return bool(consumer.is_abandonment_consumer_alive())
        except Exception:
            return False

    def _deliver_presentation(
        self,
        presentation: AbandonmentPreparedPresentation,
        *,
        animate: bool,
    ) -> None:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_abandonment_presentation(presentation, animate=animate)
        except Exception:
            logger.debug("[STEAM] Abandonment presentation delivery failed", exc_info=True)

    def _request_consumer_fade(self) -> None:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        try:
            consumer.request_abandonment_fade()
        except Exception:
            logger.debug("[STEAM] Abandonment fade request failed", exc_info=True)

    def _request_consumer_rotation(self) -> bool:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return False
        try:
            return bool(consumer.on_abandonment_rotation_due())
        except Exception:
            logger.debug("[STEAM] Abandonment rotation delivery failed", exc_info=True)
            return False

    def set_thread_manager(self, thread_manager: Any) -> None:
        self._thread_manager = thread_manager

    @property
    def runtime_generation(self) -> Any:
        return self._runtime_generation

    @property
    def current_presentation(self) -> Optional[AbandonmentPreparedPresentation]:
        return self._current_presentation

    @property
    def rotation_timer(self) -> Optional[OverlayTimerHandle]:
        return self._rotation_timer

    @property
    def owner_generation(self) -> int:
        return self._owner_generation

    def is_running(self) -> bool:
        return self._running and not self._retired

    def is_retired(self) -> bool:
        return self._retired

    # ------------------------------------------------------------------
    # Generation / request admission
    # ------------------------------------------------------------------
    def _invalidate_async_results(self) -> None:
        self._owner_generation += 1
        self._state_request_id += 1
        self._cache_request_id += 1
        self._refresh_request_id += 1
        self._rotation_request_id += 1

    def _owner_is_current(self, owner_generation: int) -> bool:
        return bool(
            not self._retired
            and self._running
            and owner_generation == self._owner_generation
        )

    def _state_is_current(self, owner_generation: int, state_request_id: int) -> bool:
        return bool(
            self._owner_is_current(owner_generation)
            and state_request_id == self._state_request_id
        )

    @staticmethod
    def _tag_runtime_callable(func: Any, runtime_generation: Any) -> Any:
        func._srpss_runtime_generation = runtime_generation
        return func

    # ------------------------------------------------------------------
    # Startup / presentation lifecycle
    # ------------------------------------------------------------------
    def start(self, *, start_fade_after_load: bool = False) -> bool:
        if self._retired:
            return False
        if self._thread_manager is None:
            logger.error(
                "[STEAM] Abandonment runtime start unavailable: ThreadManager is not configured"
            )
            return False
        self._running = True

        if self._current_presentation is not None:
            self._deliver_presentation(self._current_presentation, animate=False)
            self._activation_cache_preloaded = True
            self._cache_load_started = True
            if start_fade_after_load:
                self._request_consumer_fade()
            return True

        if self._cache_load_started:
            if start_fade_after_load:
                if self._activation_cache_preloaded:
                    self._request_consumer_fade()
                else:
                    self._start_fade_after_cache_load = True
            return True

        started = self._begin_cache_load(start_fade_after_load=start_fade_after_load)
        if not started:
            self._running = False
        return started

    def on_presentation_fade_complete(self) -> None:
        if not self.is_running() or not self._activation_has_metadata:
            return
        self.start_rotation_timer()
        if self._activation_refresh_scheduled:
            return
        self._activation_refresh_scheduled = True
        self.refresh(
            cache_age_seconds=self._activation_cache_age_seconds,
            force=False,
            force_rotation=False,
        )

    def _begin_cache_load(self, *, start_fade_after_load: bool) -> bool:
        if not self.is_running() or self._thread_manager is None:
            return False
        self._cache_load_started = True
        self._start_fade_after_cache_load = bool(start_fade_after_load)
        self._state_request_id += 1
        state_request_id = self._state_request_id
        self._cache_request_id += 1
        request_id = self._cache_request_id
        owner_generation = self._owner_generation
        runtime_generation = self._runtime_generation
        config = self._config
        allow_asset_network = automatic_service_updates_enabled()
        owner_ref = weakref.ref(self)

        def _load_snapshot() -> Any:
            from core.steam.abandonment_cache import load_abandonment_cache_snapshot
            from core.steam.credentials import read_credential_metadata

            metadata = read_credential_metadata()
            if metadata is None:
                return None, None, None
            snapshot = load_abandonment_cache_snapshot(
                profile_key=metadata.profile_cache_key,
                selection=config.selection,
                advance_rotation=True,
                refresh_interval_minutes=config.refresh_minutes,
            )
            presentation = prepare_abandonment_presentation(
                config,
                snapshot,
                profile_key=metadata.profile_cache_key,
                allow_asset_network=allow_asset_network,
            )
            return metadata, snapshot, presentation

        self._tag_runtime_callable(_load_snapshot, runtime_generation)

        def _finished(task_result: Any) -> None:
            payload = (
                task_result.result
                if getattr(task_result, "success", False) and task_result.result
                else (None, None, None)
            )

            def _apply_result() -> None:
                owner = owner_ref()
                if owner is None:
                    return
                owner._commit_cache_load(
                    owner_generation,
                    state_request_id,
                    request_id,
                    payload,
                )

            AbandonmentRuntimeService._tag_runtime_callable(
                _apply_result,
                runtime_generation,
            )
            ThreadManager.run_on_ui_thread(_apply_result)

        self._tag_runtime_callable(_finished, runtime_generation)

        try:
            self._thread_manager.submit_io_task(
                _load_snapshot,
                task_id=(
                    "steam_abandonment_cache_load_"
                    f"{self._task_owner_token}_{owner_generation}_{request_id}"
                ),
                callback=_finished,
                category="steam_abandonment_cache_load",
            )
        except Exception:
            self._cache_load_started = False
            logger.warning(
                "[STEAM] Could not submit Abandonment Issues cache load",
                exc_info=True,
            )
            return False
        return True

    def _commit_cache_load(
        self,
        owner_generation: int,
        state_request_id: int,
        request_id: int,
        payload: Any,
    ) -> None:
        if not self._owner_is_current(owner_generation):
            return
        if request_id != self._cache_request_id:
            return
        metadata, snapshot, presentation = payload
        cache_age_seconds = None
        if (
            state_request_id == self._state_request_id
            and snapshot is not None
            and presentation is not None
        ):
            cache_age_seconds = snapshot.cache_age_seconds
            self._activation_rotation_due_seconds = snapshot.rotation_due_seconds
            self._current_presentation = presentation
            self._deliver_presentation(presentation, animate=False)
        self._activation_cache_preloaded = True
        self._activation_has_metadata = metadata is not None
        self._activation_cache_age_seconds = cache_age_seconds
        if self._start_fade_after_cache_load:
            self._start_fade_after_cache_load = False
            self._request_consumer_fade()

    # ------------------------------------------------------------------
    # Source refresh / explicit manual refresh
    # ------------------------------------------------------------------
    def request_manual_refresh(self) -> bool:
        return self.refresh(
            cache_age_seconds=None,
            force=True,
            force_rotation=True,
        )

    def refresh(
        self,
        *,
        cache_age_seconds: Optional[float],
        force: bool = False,
        force_rotation: bool = False,
    ) -> bool:
        if not self.is_running():
            return False
        if not force and not automatic_service_updates_enabled():
            return False
        if (
            not force
            and cache_age_seconds is not None
            and cache_age_seconds < self._config.refresh_minutes * 60
        ):
            return False
        if self._refresh_in_progress:
            return True
        if self._thread_manager is None:
            logger.error("[STEAM] Abandonment refresh unavailable: ThreadManager is not configured")
            return False

        self._refresh_in_progress = True
        self._state_request_id += 1
        state_request_id = self._state_request_id
        self._refresh_request_id += 1
        request_id = self._refresh_request_id
        owner_generation = self._owner_generation
        runtime_generation = self._runtime_generation
        config = self._config
        owner_ref = weakref.ref(self)

        def _refresh_snapshot() -> Any:
            from core.steam.abandonment_cache import (
                AbandonmentRefreshOutcome,
                load_abandonment_cache_snapshot,
                refresh_abandonment_cache,
            )
            from core.steam.credentials import (
                SteamCredentialError,
                derive_profile_cache_key,
                load_credentials,
                read_credential_metadata,
            )

            try:
                credential = load_credentials()
            except SteamCredentialError:
                metadata = read_credential_metadata()
                if metadata is None:
                    return None
                snapshot = load_abandonment_cache_snapshot(
                    profile_key=metadata.profile_cache_key,
                    selection=config.selection,
                    force_rotation=force_rotation,
                    refresh_interval_minutes=config.refresh_minutes,
                )
                outcome = AbandonmentRefreshOutcome(
                    snapshot=snapshot,
                    connection_needs_attention=True,
                )
                presentation = prepare_abandonment_presentation(
                    config,
                    snapshot,
                    profile_key=metadata.profile_cache_key,
                    allow_asset_network=False,
                    connection_needs_attention=True,
                )
                return outcome, presentation
            if credential is None:
                return None
            outcome = refresh_abandonment_cache(
                credential=credential,
                selection=config.selection,
                force=force,
                force_rotation=force_rotation,
                refresh_interval_minutes=config.refresh_minutes,
                recent_fresh_seconds=config.refresh_minutes * 60,
                hydrate_achievement_evidence=achievement_evidence_requested(
                    config.field_visibility
                ),
            )
            profile_key = derive_profile_cache_key(credential.profile_identifier)
            presentation = prepare_abandonment_presentation(
                config,
                outcome.snapshot,
                profile_key=profile_key,
                allow_asset_network=outcome.snapshot.resolved.ok,
                connection_needs_attention=outcome.connection_needs_attention,
            )
            return outcome, presentation

        self._tag_runtime_callable(_refresh_snapshot, runtime_generation)

        def _finished(task_result: Any) -> None:
            result = (
                task_result.result if getattr(task_result, "success", False) else None
            )

            def _apply_result() -> None:
                owner = owner_ref()
                if owner is None:
                    return
                owner._commit_refresh(
                    owner_generation,
                    state_request_id,
                    request_id,
                    result,
                    force_rotation=force_rotation,
                )

            AbandonmentRuntimeService._tag_runtime_callable(
                _apply_result,
                runtime_generation,
            )
            ThreadManager.run_on_ui_thread(_apply_result)

        self._tag_runtime_callable(_finished, runtime_generation)

        try:
            self._thread_manager.submit_io_task(
                _refresh_snapshot,
                task_id=(
                    "steam_abandonment_refresh_"
                    f"{self._task_owner_token}_{owner_generation}_{request_id}"
                ),
                callback=_finished,
                category="steam_abandonment_refresh",
            )
        except Exception:
            self._refresh_in_progress = False
            logger.warning(
                "[STEAM] Could not submit Abandonment Issues refresh",
                exc_info=True,
            )
            return False
        return True

    def _commit_refresh(
        self,
        owner_generation: int,
        state_request_id: int,
        request_id: int,
        result: Any,
        *,
        force_rotation: bool,
    ) -> None:
        if not self._owner_is_current(owner_generation):
            return
        if request_id != self._refresh_request_id:
            return
        self._refresh_in_progress = False
        if not self._state_is_current(owner_generation, state_request_id):
            return
        if result is None:
            return
        _outcome, presentation = result
        self._current_presentation = presentation
        self._deliver_presentation(presentation, animate=True)
        if force_rotation:
            self.restart_rotation_timer_full_interval()

    # ------------------------------------------------------------------
    # Cache-backed rotation
    # ------------------------------------------------------------------
    def request_cache_rotation(self) -> bool:
        if not self.is_running() or self._config.selection.mode == "pinned_game":
            return False
        if self._rotation_in_progress:
            return True
        if self._thread_manager is None:
            logger.error(
                "[STEAM] Abandonment cache rotation unavailable: ThreadManager is not configured"
            )
            return False

        self._rotation_in_progress = True
        self._state_request_id += 1
        state_request_id = self._state_request_id
        self._rotation_request_id += 1
        request_id = self._rotation_request_id
        owner_generation = self._owner_generation
        runtime_generation = self._runtime_generation
        config = self._config
        allow_asset_network = automatic_service_updates_enabled()
        owner_ref = weakref.ref(self)

        def _rotate_snapshot() -> Any:
            from core.steam.abandonment_cache import (
                hydrate_selected_achievement_evidence,
                load_abandonment_cache_snapshot,
            )
            from core.steam.credentials import (
                SteamCredentialError,
                load_credentials,
                read_credential_metadata,
            )
            from core.steam.models import SteamResultStatus

            metadata = read_credential_metadata()
            if metadata is None:
                return None
            snapshot = load_abandonment_cache_snapshot(
                profile_key=metadata.profile_cache_key,
                selection=config.selection,
                advance_rotation=True,
                refresh_interval_minutes=config.refresh_minutes,
            )
            connection_needs_attention = False
            if allow_asset_network and achievement_evidence_requested(
                config.field_visibility
            ):
                try:
                    credential = load_credentials()
                except SteamCredentialError:
                    credential = None
                    connection_needs_attention = True
                if credential is not None:
                    snapshot, achievement_result = hydrate_selected_achievement_evidence(
                        snapshot=snapshot,
                        credential=credential,
                        profile_key=metadata.profile_cache_key,
                    )
                    connection_needs_attention = bool(
                        achievement_result is not None
                        and achievement_result.status == SteamResultStatus.UNAUTHORIZED
                    )
            return prepare_abandonment_presentation(
                config,
                snapshot,
                profile_key=metadata.profile_cache_key,
                allow_asset_network=allow_asset_network,
                connection_needs_attention=connection_needs_attention,
            )

        self._tag_runtime_callable(_rotate_snapshot, runtime_generation)

        def _finished(task_result: Any) -> None:
            presentation = (
                task_result.result if getattr(task_result, "success", False) else None
            )

            def _apply_result() -> None:
                owner = owner_ref()
                if owner is None:
                    return
                owner._commit_rotation(
                    owner_generation,
                    state_request_id,
                    request_id,
                    presentation,
                )

            AbandonmentRuntimeService._tag_runtime_callable(
                _apply_result,
                runtime_generation,
            )
            ThreadManager.run_on_ui_thread(_apply_result)

        self._tag_runtime_callable(_finished, runtime_generation)

        try:
            self._thread_manager.submit_io_task(
                _rotate_snapshot,
                task_id=(
                    "steam_abandonment_rotation_"
                    f"{self._task_owner_token}_{owner_generation}_{request_id}"
                ),
                callback=_finished,
                category="steam_abandonment_rotation",
            )
        except Exception:
            self._rotation_in_progress = False
            logger.warning(
                "[STEAM] Could not submit cache-only Abandonment rotation",
                exc_info=True,
            )
            return False
        return True

    def _commit_rotation(
        self,
        owner_generation: int,
        state_request_id: int,
        request_id: int,
        presentation: Optional[AbandonmentPreparedPresentation],
    ) -> None:
        if not self._owner_is_current(owner_generation):
            return
        if request_id != self._rotation_request_id:
            return
        self._rotation_in_progress = False
        if not self._state_is_current(owner_generation, state_request_id):
            return
        if presentation is None:
            return
        self._current_presentation = presentation
        self._deliver_presentation(presentation, animate=True)

    # ------------------------------------------------------------------
    # Recurring cadence
    # ------------------------------------------------------------------
    def start_rotation_timer(self, *, delay_seconds: Optional[float] = None) -> None:
        if not self.is_running() or self._config.selection.mode == "pinned_game":
            return
        if self._rotation_timer is not None and self._rotation_timer.is_active():
            return
        full_interval_ms = self._config.refresh_minutes * 60 * 1_000
        if delay_seconds is None:
            delay_seconds = (
                self._activation_rotation_due_seconds
                if self._activation_rotation_due_seconds is not None
                else full_interval_ms / 1_000.0
            )
        interval_ms = max(
            1_000,
            min(full_interval_ms, int(round(float(delay_seconds) * 1_000))),
        )
        self._rotation_initial_delay = interval_ms < full_interval_ms
        try:
            self._rotation_timer = create_overlay_timer(
                self,
                interval_ms,
                self._on_rotation_timer,
                description="Abandonment Issues cache-backed rotation",
            )
        except Exception:
            self._rotation_initial_delay = False
            logger.warning(
                "[STEAM] Could not start Abandonment Issues rotation",
                exc_info=True,
            )

    def _on_rotation_timer(self) -> bool:
        if not self.is_running():
            return False
        if self._rotation_initial_delay:
            handle = self._rotation_timer
            self._rotation_timer = None
            self._rotation_initial_delay = False
            if handle is not None:
                handle.stop()
            self.start_rotation_timer(
                delay_seconds=float(self._config.refresh_minutes * 60)
            )
        return self._request_consumer_rotation()

    def restart_rotation_timer_full_interval(self) -> None:
        self.stop_rotation_timer()
        if self.is_running():
            self.start_rotation_timer(
                delay_seconds=float(self._config.refresh_minutes * 60)
            )

    def stop_rotation_timer(self) -> None:
        self._rotation_initial_delay = False
        handle = self._rotation_timer
        self._rotation_timer = None
        if handle is not None:
            handle.stop()

    # ------------------------------------------------------------------
    # Stop / retirement
    # ------------------------------------------------------------------
    def stop(self) -> None:
        if not self._running:
            # Defensive cleanup without advancing generations repeatedly.
            self.stop_rotation_timer()
            return
        self._running = False
        self._invalidate_async_results()
        self.stop_rotation_timer()
        self._refresh_in_progress = False
        self._rotation_in_progress = False
        self._start_fade_after_cache_load = False
        self._activation_refresh_scheduled = False
        # A current prepared model may be replayed after presentation recreation.
        # If no accepted model exists, a later start must submit a fresh cache load.
        self._cache_load_started = self._current_presentation is not None
        self._activation_cache_preloaded = self._current_presentation is not None

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._running = False
        self._invalidate_async_results()
        self.stop_rotation_timer()
        self._refresh_in_progress = False
        self._rotation_in_progress = False
        self._cache_load_started = False
        self._start_fade_after_cache_load = False
        self._activation_refresh_scheduled = False
        self._consumer_ref = None
        self._current_presentation = None
