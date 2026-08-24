"""Presentation-neutral Steam Achievement Pulse runtime owner (E1 slice 5).

``AchievementPulseRuntimeService`` owns one enabled card/display's cache-first
load, source/manual refresh, request admission, semantic model, decoded app/icon
artwork state and retirement. Existing ``core.steam`` cache locks, request
coalescing, backoff, credentials, backend and asset helpers remain authoritative.

The temporary QWidget consumer owns only geometry, QPainter pixels, fade and
transition deferral, hit routing, styles/logo and DPR-specific scaled-image
caches. No recurring cadence is introduced for Achievement Pulse.
"""
from __future__ import annotations

import hashlib
import weakref
from dataclasses import replace
from typing import Any, Optional

from PySide6.QtGui import QImage

from core.logging.logger import get_logger
from core.runtime_flags import automatic_service_updates_enabled
from core.threading.manager import ThreadManager
from widgets.steam_achievement_preparation import (
    AchievementPulsePreparedPresentation,
    AchievementPulseRuntimeConfig,
    prepare_achievement_artwork,
    prepare_achievement_model,
    prepare_latest_achievement_artwork,
)


logger = get_logger(__name__)


class AchievementPulseRuntimeService:
    """Own one Achievement Pulse card's source/model/artwork lifecycle."""

    def __init__(
        self,
        *,
        config: Optional[AchievementPulseRuntimeConfig] = None,
        runtime_generation: Any = None,
    ) -> None:
        self._consumer_ref: Optional[weakref.ref] = None
        self._thread_manager: Any = None
        self._runtime_generation = runtime_generation
        self._task_owner_token = id(self)
        self._config = self._normalize_config(
            config or AchievementPulseRuntimeConfig()
        )

        self._current_presentation: Optional[
            AchievementPulsePreparedPresentation
        ] = None
        self._current_profile_key = ""
        self._activation_cache_preloaded = False
        self._activation_has_metadata = False
        self._activation_cache_age_seconds: Optional[float] = None
        self._activation_refresh_scheduled = False
        self._start_fade_after_cache_load = False

        self._cache_load_started = False
        self._refresh_in_progress = False
        self._artwork_inflight_key = ""
        self._latest_artwork_inflight_key = ""

        self._owner_generation = 0
        self._state_request_id = 0
        self._cache_request_id = 0
        self._refresh_request_id = 0
        self._artwork_request_id = 0
        self._latest_artwork_request_id = 0

        self._running = False
        self._retired = False

    # ------------------------------------------------------------------
    # Configuration / consumer bridge
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_config(
        config: AchievementPulseRuntimeConfig,
    ) -> AchievementPulseRuntimeConfig:
        artwork_shape = str(config.artwork_shape or "portrait").strip().lower()
        if artwork_shape not in {"wide", "square", "portrait"}:
            artwork_shape = "portrait"
        return AchievementPulseRuntimeConfig(
            selection=config.selection,
            field_visibility={
                str(key): bool(value)
                for key, value in config.field_visibility.items()
            },
            latest_unlock_count=max(1, min(5, int(config.latest_unlock_count))),
            show_latest_artwork=bool(config.show_latest_artwork),
            show_artwork=bool(config.show_artwork),
            artwork_shape=artwork_shape,
            refresh_minutes=max(5, int(config.refresh_minutes)),
            show_connection_info_icon=bool(config.show_connection_info_icon),
        )

    def configure(self, config: AchievementPulseRuntimeConfig) -> None:
        if self._retired:
            raise RuntimeError("cannot configure a retired Achievement Pulse service")
        normalized = self._normalize_config(config)
        if normalized == self._config:
            return
        if self._running:
            raise RuntimeError("Achievement Pulse configuration is immutable while running")
        self._config = normalized
        self._invalidate_async_results()
        self._current_presentation = None
        self._current_profile_key = ""
        self._activation_cache_preloaded = False
        self._activation_has_metadata = False
        self._activation_cache_age_seconds = None
        self._cache_load_started = False
        self._artwork_inflight_key = ""
        self._latest_artwork_inflight_key = ""

    def attach_consumer(self, consumer: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot attach a consumer to a retired Achievement Pulse service")
        generation = getattr(consumer, "_runtime_generation", None)
        if generation is None:
            try:
                parent = consumer.parent()
            except Exception:
                parent = None
            generation = getattr(parent, "_runtime_generation", None)

        if generation is not None and generation != self._runtime_generation:
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
            return bool(consumer.is_achievement_consumer_alive())
        except Exception:
            return False

    def _deliver_presentation(
        self,
        presentation: AchievementPulsePreparedPresentation,
        *,
        animate: bool,
    ) -> None:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_achievement_presentation(presentation, animate=animate)
        except Exception:
            logger.debug(
                "[STEAM] Achievement Pulse presentation delivery failed",
                exc_info=True,
            )

    def _request_consumer_fade(self) -> None:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        try:
            consumer.request_achievement_fade()
        except Exception:
            logger.debug("[STEAM] Achievement Pulse fade request failed", exc_info=True)

    def set_thread_manager(self, thread_manager: Any) -> None:
        self._thread_manager = thread_manager

    @property
    def runtime_generation(self) -> Any:
        return self._runtime_generation

    @property
    def current_presentation(
        self,
    ) -> Optional[AchievementPulsePreparedPresentation]:
        return self._current_presentation

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
        self._artwork_request_id += 1
        self._latest_artwork_request_id += 1

    def _owner_is_current(self, owner_generation: int) -> bool:
        return bool(
            not self._retired
            and self._running
            and owner_generation == self._owner_generation
        )

    def _state_is_current(
        self,
        owner_generation: int,
        state_request_id: int,
    ) -> bool:
        return bool(
            self._owner_is_current(owner_generation)
            and state_request_id == self._state_request_id
        )

    @staticmethod
    def _tag_runtime_callable(func: Any, runtime_generation: Any) -> Any:
        func._srpss_runtime_generation = runtime_generation
        return func

    # ------------------------------------------------------------------
    # Startup / cache-first lifecycle
    # ------------------------------------------------------------------
    def start(self, *, start_fade_after_load: bool = False) -> bool:
        if self._retired:
            return False
        if self._thread_manager is None:
            logger.error(
                "[STEAM] Achievement Pulse start unavailable: ThreadManager is not configured"
            )
            return False
        self._running = True

        if self._current_presentation is not None:
            self._deliver_presentation(self._current_presentation, animate=False)
            self._activation_cache_preloaded = True
            self._activation_has_metadata = bool(self._current_profile_key)
            self._activation_cache_age_seconds = (
                self._current_presentation.model.cache_age_seconds
            )
            self._cache_load_started = True
            self._schedule_current_artwork()
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

        started = self._begin_cache_load(
            start_fade_after_load=start_fade_after_load
        )
        if not started:
            self._running = False
        return started

    def on_presentation_fade_complete(self) -> None:
        if not self.is_running() or not self._activation_has_metadata:
            return
        if self._activation_refresh_scheduled:
            return
        self._activation_refresh_scheduled = True
        self.refresh(
            cache_age_seconds=self._activation_cache_age_seconds,
            force=False,
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
        owner_ref = weakref.ref(self)

        def _load_snapshot() -> Any:
            from core.steam.achievement_pulse_cache import (
                load_achievement_pulse_cache_snapshot,
            )
            from core.steam.credentials import read_credential_metadata

            metadata = read_credential_metadata()
            if metadata is None:
                return None, None, None
            snapshot = load_achievement_pulse_cache_snapshot(
                profile_key=metadata.profile_cache_key,
                selection=config.selection,
            )
            model = (
                prepare_achievement_model(config, snapshot)
                if snapshot.has_usable_cache
                else None
            )
            return metadata, snapshot, model

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

            AchievementPulseRuntimeService._tag_runtime_callable(
                _apply_result,
                runtime_generation,
            )
            ThreadManager.run_on_ui_thread(_apply_result)

        self._tag_runtime_callable(_finished, runtime_generation)

        try:
            self._thread_manager.submit_io_task(
                _load_snapshot,
                task_id=(
                    "steam_achievement_cache_load_"
                    f"{self._task_owner_token}_{owner_generation}_{request_id}"
                ),
                callback=_finished,
                category="steam_achievement_cache_load",
            )
        except Exception:
            self._cache_load_started = False
            logger.warning(
                "[STEAM] Could not submit Achievement Pulse cache load",
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
        metadata, snapshot, model = payload
        cache_age_seconds = None
        if (
            state_request_id == self._state_request_id
            and metadata is not None
            and snapshot is not None
            and model is not None
        ):
            cache_age_seconds = snapshot.cache_age_seconds
            self._accept_model(
                model,
                profile_key=metadata.profile_cache_key,
                animate=False,
            )
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
        return self.refresh(cache_age_seconds=None, force=True)

    def refresh(
        self,
        *,
        cache_age_seconds: Optional[float],
        force: bool = False,
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
            logger.error(
                "[STEAM] Achievement Pulse refresh unavailable: ThreadManager is not configured"
            )
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
            from core.steam.achievement_pulse_cache import (
                AchievementPulseRefreshOutcome,
                load_achievement_pulse_cache_snapshot,
                refresh_achievement_pulse_cache,
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
                snapshot = load_achievement_pulse_cache_snapshot(
                    profile_key=metadata.profile_cache_key,
                    selection=config.selection,
                )
                outcome = AchievementPulseRefreshOutcome(
                    snapshot=snapshot,
                    connection_needs_attention=True,
                )
                model = prepare_achievement_model(
                    config,
                    snapshot,
                    connection_needs_attention=True,
                )
                return metadata.profile_cache_key, outcome, model
            if credential is None:
                return None
            outcome = refresh_achievement_pulse_cache(
                credential=credential,
                selection=config.selection,
                force=force,
                source_fresh_seconds=config.refresh_minutes * 60,
            )
            profile_key = derive_profile_cache_key(credential.profile_identifier)
            model = prepare_achievement_model(
                config,
                outcome.snapshot,
                connection_needs_attention=bool(
                    outcome.connection_needs_attention
                ),
            )
            return profile_key, outcome, model

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
                )

            AchievementPulseRuntimeService._tag_runtime_callable(
                _apply_result,
                runtime_generation,
            )
            ThreadManager.run_on_ui_thread(_apply_result)

        self._tag_runtime_callable(_finished, runtime_generation)

        try:
            self._thread_manager.submit_io_task(
                _refresh_snapshot,
                task_id=(
                    "steam_achievement_refresh_"
                    f"{self._task_owner_token}_{owner_generation}_{request_id}"
                ),
                callback=_finished,
                category="steam_achievement_refresh",
            )
        except Exception:
            self._refresh_in_progress = False
            logger.warning(
                "[STEAM] Could not submit Achievement Pulse refresh",
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
        profile_key, _outcome, model = result
        self._accept_model(model, profile_key=profile_key, animate=True)

    # ------------------------------------------------------------------
    # Accepted model / independent artwork streams
    # ------------------------------------------------------------------
    def _accept_model(
        self,
        model: Any,
        *,
        profile_key: str,
        animate: bool,
    ) -> None:
        artwork_key = (
            f"{model.appid}:{self._config.artwork_shape}"
            if self._config.show_artwork and model.appid is not None
            else ""
        )
        latest_key = (
            str(model.latest_unlock_icon_url or "").strip()
            if self._config.show_latest_artwork
            else ""
        )
        previous = self._current_presentation
        preserve_artwork = previous is not None and previous.artwork_key == artwork_key
        preserve_latest = (
            previous is not None and previous.latest_artwork_key == latest_key
        )
        self._current_presentation = AchievementPulsePreparedPresentation(
            model=model,
            artwork=(QImage(previous.artwork) if preserve_artwork else QImage()),
            artwork_identity=(
                previous.artwork_identity if preserve_artwork else ""
            ),
            artwork_key=artwork_key,
            latest_artwork=(
                QImage(previous.latest_artwork) if preserve_latest else QImage()
            ),
            latest_artwork_identity=(
                previous.latest_artwork_identity if preserve_latest else ""
            ),
            latest_artwork_key=latest_key,
        )
        self._current_profile_key = str(profile_key or "")
        self._deliver_presentation(self._current_presentation, animate=animate)
        self._schedule_current_artwork()

    def _schedule_current_artwork(self) -> None:
        presentation = self._current_presentation
        profile_key = self._current_profile_key
        if not self.is_running() or presentation is None or not profile_key:
            return
        if presentation.artwork_key and presentation.artwork.isNull():
            self._begin_artwork_load(
                presentation.artwork_key,
                profile_key=profile_key,
                appid=int(presentation.model.appid),
            )
        if presentation.latest_artwork_key and presentation.latest_artwork.isNull():
            self._begin_latest_artwork_load(
                presentation.latest_artwork_key,
                profile_key=profile_key,
            )

    def _begin_artwork_load(
        self,
        artwork_key: str,
        *,
        profile_key: str,
        appid: int,
    ) -> bool:
        if not self.is_running() or self._thread_manager is None:
            return False
        if self._artwork_inflight_key == artwork_key:
            return True
        self._artwork_inflight_key = artwork_key
        self._artwork_request_id += 1
        request_id = self._artwork_request_id
        owner_generation = self._owner_generation
        runtime_generation = self._runtime_generation
        artwork_shape = self._config.artwork_shape
        owner_ref = weakref.ref(self)

        def _load_artwork() -> Any:
            return prepare_achievement_artwork(
                profile_key=profile_key,
                appid=appid,
                artwork_shape=artwork_shape,
            )

        self._tag_runtime_callable(_load_artwork, runtime_generation)

        def _finished(task_result: Any) -> None:
            result = (
                task_result.result if getattr(task_result, "success", False) else None
            )

            def _apply_result() -> None:
                owner = owner_ref()
                if owner is None:
                    return
                owner._commit_artwork(
                    owner_generation,
                    request_id,
                    artwork_key,
                    result,
                )

            AchievementPulseRuntimeService._tag_runtime_callable(
                _apply_result,
                runtime_generation,
            )
            ThreadManager.run_on_ui_thread(_apply_result)

        self._tag_runtime_callable(_finished, runtime_generation)

        try:
            self._thread_manager.submit_io_task(
                _load_artwork,
                task_id=(
                    "steam_achievement_artwork_"
                    f"{self._task_owner_token}_{owner_generation}_{request_id}"
                ),
                callback=_finished,
                category="steam_achievement_artwork",
            )
        except Exception:
            self._artwork_inflight_key = ""
            logger.warning(
                "[STEAM] Could not submit Achievement Pulse artwork load",
                exc_info=True,
            )
            return False
        return True

    def _commit_artwork(
        self,
        owner_generation: int,
        request_id: int,
        artwork_key: str,
        result: Any,
    ) -> None:
        if not self._owner_is_current(owner_generation):
            return
        if request_id != self._artwork_request_id:
            return
        self._artwork_inflight_key = ""
        presentation = self._current_presentation
        if presentation is None or presentation.artwork_key != artwork_key:
            return
        if result is None:
            return
        image, identity = result
        if image is None or image.isNull():
            return
        self._current_presentation = replace(
            presentation,
            artwork=QImage(image),
            artwork_identity=str(identity or ""),
        )
        self._deliver_presentation(self._current_presentation, animate=False)

    def _begin_latest_artwork_load(
        self,
        icon_url: str,
        *,
        profile_key: str,
    ) -> bool:
        if not self.is_running() or self._thread_manager is None:
            return False
        if self._latest_artwork_inflight_key == icon_url:
            return True
        self._latest_artwork_inflight_key = icon_url
        self._latest_artwork_request_id += 1
        request_id = self._latest_artwork_request_id
        owner_generation = self._owner_generation
        runtime_generation = self._runtime_generation
        owner_ref = weakref.ref(self)

        def _load_artwork() -> Any:
            return prepare_latest_achievement_artwork(
                profile_key=profile_key,
                icon_url=icon_url,
            )

        self._tag_runtime_callable(_load_artwork, runtime_generation)

        def _finished(task_result: Any) -> None:
            result = (
                task_result.result if getattr(task_result, "success", False) else None
            )

            def _apply_result() -> None:
                owner = owner_ref()
                if owner is None:
                    return
                owner._commit_latest_artwork(
                    owner_generation,
                    request_id,
                    icon_url,
                    result,
                )

            AchievementPulseRuntimeService._tag_runtime_callable(
                _apply_result,
                runtime_generation,
            )
            ThreadManager.run_on_ui_thread(_apply_result)

        self._tag_runtime_callable(_finished, runtime_generation)

        try:
            url_fingerprint = hashlib.sha256(icon_url.encode("utf-8")).hexdigest()[:12]
            self._thread_manager.submit_io_task(
                _load_artwork,
                task_id=(
                    "steam_achievement_latest_artwork_"
                    f"{url_fingerprint}_{self._task_owner_token}_"
                    f"{owner_generation}_{request_id}"
                ),
                callback=_finished,
                category="steam_achievement_latest_artwork",
            )
        except Exception:
            self._latest_artwork_inflight_key = ""
            logger.warning(
                "[STEAM] Could not submit latest Achievement Pulse artwork",
                exc_info=True,
            )
            return False
        return True

    def _commit_latest_artwork(
        self,
        owner_generation: int,
        request_id: int,
        icon_url: str,
        result: Any,
    ) -> None:
        if not self._owner_is_current(owner_generation):
            return
        if request_id != self._latest_artwork_request_id:
            return
        self._latest_artwork_inflight_key = ""
        presentation = self._current_presentation
        if presentation is None or presentation.latest_artwork_key != icon_url:
            return
        if result is None:
            return
        image, identity = result
        if image is None or image.isNull():
            return
        self._current_presentation = replace(
            presentation,
            latest_artwork=QImage(image),
            latest_artwork_identity=str(identity or ""),
        )
        self._deliver_presentation(self._current_presentation, animate=False)

    # ------------------------------------------------------------------
    # Stop / retirement
    # ------------------------------------------------------------------
    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._invalidate_async_results()
        self._refresh_in_progress = False
        self._artwork_inflight_key = ""
        self._latest_artwork_inflight_key = ""
        self._start_fade_after_cache_load = False
        self._activation_refresh_scheduled = False
        self._cache_load_started = self._current_presentation is not None
        self._activation_cache_preloaded = self._current_presentation is not None

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._running = False
        self._invalidate_async_results()
        self._refresh_in_progress = False
        self._artwork_inflight_key = ""
        self._latest_artwork_inflight_key = ""
        self._cache_load_started = False
        self._start_fade_after_cache_load = False
        self._activation_refresh_scheduled = False
        self._consumer_ref = None
        self._current_profile_key = ""
        self._current_presentation = None
