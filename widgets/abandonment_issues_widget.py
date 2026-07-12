"""Production Steam Abandonment Issues overlay."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from core.logging.logger import get_logger
from core.steam.abandonment_issues import AbandonmentSelection
from widgets.overlay_timers import OverlayTimerHandle, create_overlay_timer
from widgets.steam_abandonment_components import (
    ABANDONMENT_ACCENT_RGBA,
    ABANDONMENT_ARTWORK_SIZE_DEFAULT,
    AbandonmentCardLayout,
    abandonment_authored_size,
    build_abandonment_view_model,
    layout_abandonment_card,
    normalize_abandonment_artwork_size,
    render_abandonment_card,
)
from widgets.steam_card_widget import SteamCardDefinition, SteamCardWidget
from widgets.steam_components import SteamCardViewModel


logger = get_logger(__name__)


class AbandonmentIssuesWidget(SteamCardWidget):
    """Cache-first archival rediscovery card with cache-only rotation."""

    def __init__(
        self,
        parent=None,
        *,
        definition: SteamCardDefinition,
        position,
        initial_view_model: SteamCardViewModel,
        selection: AbandonmentSelection = AbandonmentSelection(),
        field_visibility: Mapping[str, bool] | None = None,
        show_artwork: bool = True,
        artwork_shape: str = "square",
        artwork_size: int = ABANDONMENT_ARTWORK_SIZE_DEFAULT,
        accent_color: QColor | None = None,
        guilt_desaturater: bool = False,
        guilt_desaturation_strength: int = 55,
        rotation_interval_minutes: int = 30,
        refresh_minutes: int = 10,
        show_connection_info_icon: bool = True,
    ) -> None:
        self._abandonment_selection = selection
        self._abandonment_field_visibility = dict(field_visibility or {})
        self._abandonment_show_artwork = bool(show_artwork)
        self._abandonment_artwork_shape = (
            "square" if str(artwork_shape).strip().lower() == "square" else "wide"
        )
        self._abandonment_artwork_size = normalize_abandonment_artwork_size(artwork_size)
        self._abandonment_accent_color = QColor(
            accent_color or QColor(*ABANDONMENT_ACCENT_RGBA)
        )
        self._abandonment_guilt_desaturater = bool(guilt_desaturater)
        self._abandonment_guilt_desaturation_strength = max(
            0,
            min(100, int(guilt_desaturation_strength)),
        )
        self._abandonment_rotation_interval_minutes = max(
            5,
            min(24 * 60, int(rotation_interval_minutes)),
        )
        self._abandonment_show_connection_info_icon = bool(show_connection_info_icon)
        self._abandonment_artwork = QImage()
        self._abandonment_scaled_artwork = QImage()
        self._abandonment_scaled_artwork_key: tuple[int, int, int, float] | None = None
        self._abandonment_rotation_timer: OverlayTimerHandle | None = None
        super().__init__(
            parent=parent,
            definition=definition,
            position=position,
            initial_view_model=initial_view_model,
            achievement_show_artwork=False,
            refresh_minutes=refresh_minutes,
        )

    def _authored_content_size(self):
        return abandonment_authored_size(
            show_artwork=self._abandonment_show_artwork,
            artwork_shape=self._abandonment_artwork_shape,
            artwork_size=self._abandonment_artwork_size,
        )

    def _calculate_content_size(self) -> QSize:
        authored = self._authored_content_size()
        return QSize(
            max(int(math.ceil(authored.width())), self.minimumWidth()),
            max(int(math.ceil(authored.height())), self.minimumHeight()),
        )

    def last_layout(self) -> AbandonmentCardLayout | None:
        return self._last_layout

    def handle_double_click(self, _local_pos) -> bool:
        return self.request_manual_refresh()

    def _activate_impl(self) -> None:
        if not self._load_abandonment_cache(start_fade_after_load=True):
            self._request_coordinated_fade()

    def on_fade_complete(self) -> None:
        super().on_fade_complete()
        if not getattr(self, "_abandonment_activation_has_metadata", False):
            return
        self._start_rotation_timer()
        if not getattr(self, "_abandonment_activation_refresh_scheduled", False):
            self._abandonment_activation_refresh_scheduled = True
            self._refresh_abandonment_cache(
                cache_age_seconds=getattr(
                    self,
                    "_abandonment_activation_cache_age_seconds",
                    None,
                )
            )

    def _deactivate_impl(self) -> None:
        self._stop_rotation_timer()
        super()._deactivate_impl()

    def _cleanup_impl(self) -> None:
        self._stop_rotation_timer()
        super()._cleanup_impl()

    def _start_rotation_timer(self) -> None:
        if self._abandonment_selection.mode == "pinned_game":
            return
        if self._abandonment_rotation_timer is not None and self._abandonment_rotation_timer.is_active():
            return
        try:
            self._abandonment_rotation_timer = create_overlay_timer(
                self,
                self._abandonment_rotation_interval_minutes * 60 * 1_000,
                self._request_cache_only_rotation,
                description="Abandonment Issues cache-only rotation",
            )
        except Exception:
            logger.warning("[STEAM] Could not start Abandonment Issues rotation", exc_info=True)

    def _stop_rotation_timer(self) -> None:
        handle = self._abandonment_rotation_timer
        self._abandonment_rotation_timer = None
        if handle is not None:
            handle.stop()

    def _load_abandonment_cache(self, *, start_fade_after_load: bool = False) -> bool:
        if getattr(self, "_abandonment_cache_load_started", False):
            if start_fade_after_load:
                if getattr(self, "_abandonment_activation_cache_preloaded", False):
                    self._request_coordinated_fade()
                else:
                    self._abandonment_start_fade_after_cache_load = True
            return True
        if not self._ensure_thread_manager("Abandonment Issues cache load"):
            return False
        self._abandonment_cache_load_started = True
        self._abandonment_start_fade_after_cache_load = bool(start_fade_after_load)
        generation = self._next_abandonment_generation()

        def _load_snapshot():
            from core.steam.abandonment_cache import load_abandonment_cache_snapshot
            from core.steam.credentials import read_credential_metadata

            metadata = read_credential_metadata()
            if metadata is None:
                return None, None, None
            snapshot = load_abandonment_cache_snapshot(
                profile_key=metadata.profile_cache_key,
                selection=self._abandonment_selection,
                rotation_interval_minutes=self._abandonment_rotation_interval_minutes,
            )
            return (
                metadata,
                snapshot,
                self._prepare_presentation(
                    snapshot,
                    profile_key=metadata.profile_cache_key,
                    allow_asset_network=False,
                ),
            )

        def _finished(task_result) -> None:
            from core.threading.manager import ThreadManager

            def _apply_result() -> None:
                if generation != getattr(self, "_abandonment_generation", None):
                    return
                metadata, snapshot, presentation = (
                    task_result.result
                    if task_result.success and task_result.result
                    else (None, None, None)
                )
                cache_age_seconds = None
                if snapshot is not None and presentation is not None:
                    cache_age_seconds = snapshot.cache_age_seconds
                    self._apply_prepared_presentation(presentation, animate=False)
                self._abandonment_activation_cache_preloaded = True
                self._abandonment_activation_has_metadata = metadata is not None
                self._abandonment_activation_cache_age_seconds = cache_age_seconds
                if getattr(self, "_abandonment_start_fade_after_cache_load", False):
                    self._request_coordinated_fade()

            ThreadManager.run_on_ui_thread(_apply_result)

        try:
            self._thread_manager.submit_io_task(
                _load_snapshot,
                task_id=f"steam_abandonment_cache_load_{generation}",
                callback=_finished,
            )
        except Exception:
            self._abandonment_cache_load_started = False
            logger.warning("[STEAM] Could not submit Abandonment Issues cache load", exc_info=True)
            return False
        return True

    def _refresh_abandonment_cache(
        self,
        *,
        cache_age_seconds: float | None,
        force: bool = False,
    ) -> bool:
        from core.runtime_flags import automatic_service_updates_enabled

        if not force and not automatic_service_updates_enabled():
            return False
        if not force and cache_age_seconds is not None and cache_age_seconds < self._refresh_minutes * 60:
            return False
        if getattr(self, "_abandonment_refresh_in_progress", False):
            return True
        if not self._ensure_thread_manager("Abandonment Issues refresh"):
            return False
        self._abandonment_refresh_in_progress = True
        generation = self._next_abandonment_generation()

        def _refresh_snapshot():
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
                    selection=self._abandonment_selection,
                    rotation_interval_minutes=self._abandonment_rotation_interval_minutes,
                )
                outcome = AbandonmentRefreshOutcome(
                    snapshot=snapshot,
                    connection_needs_attention=True,
                )
                return outcome, self._prepare_presentation(
                    snapshot,
                    profile_key=metadata.profile_cache_key,
                    allow_asset_network=False,
                    connection_needs_attention=True,
                )
            if credential is None:
                return None
            outcome = refresh_abandonment_cache(
                credential=credential,
                selection=self._abandonment_selection,
                force=force,
                rotation_interval_minutes=self._abandonment_rotation_interval_minutes,
            )
            profile_key = derive_profile_cache_key(credential.profile_identifier)
            return outcome, self._prepare_presentation(
                outcome.snapshot,
                profile_key=profile_key,
                allow_asset_network=outcome.snapshot.resolved.ok,
                connection_needs_attention=outcome.connection_needs_attention,
            )

        def _finished(task_result) -> None:
            from core.threading.manager import ThreadManager

            def _apply_result() -> None:
                if generation != getattr(self, "_abandonment_generation", None):
                    return
                self._abandonment_refresh_in_progress = False
                result = task_result.result if task_result.success else None
                if result is not None:
                    _outcome, presentation = result
                    self._apply_prepared_presentation(presentation, animate=True)

            ThreadManager.run_on_ui_thread(_apply_result)

        try:
            self._thread_manager.submit_io_task(
                _refresh_snapshot,
                task_id=f"steam_abandonment_refresh_{generation}",
                callback=_finished,
            )
        except Exception:
            self._abandonment_refresh_in_progress = False
            logger.warning("[STEAM] Could not submit Abandonment Issues refresh", exc_info=True)
            return False
        return True

    def request_manual_refresh(self) -> bool:
        from widgets.service_widget_runtime import defer_refresh_if_transition

        if defer_refresh_if_transition(
            self,
            pending_attr="_pending_abandonment_manual_refresh",
            schedule_callback=self._schedule_deferred_manual_refresh,
            logger=logger,
            log_message="[STEAM] Deferred manual Abandonment Issues refresh during parent transition",
        ):
            return True
        return self._refresh_abandonment_cache(cache_age_seconds=None, force=True)

    def _schedule_deferred_manual_refresh(self) -> None:
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(250, self._run_deferred_manual_refresh)

    def _run_deferred_manual_refresh(self) -> None:
        from widgets.service_widget_runtime import parent_transition_running

        if not getattr(self, "_pending_abandonment_manual_refresh", False):
            return
        if parent_transition_running(self):
            self._schedule_deferred_manual_refresh()
            return
        self._pending_abandonment_manual_refresh = False
        self._refresh_abandonment_cache(cache_age_seconds=None, force=True)

    def _request_cache_only_rotation(self) -> bool:
        from widgets.service_widget_runtime import parent_transition_running

        if self._abandonment_selection.mode == "pinned_game":
            return False
        if parent_transition_running(self):
            return False
        if getattr(self, "_abandonment_rotation_in_progress", False):
            return True
        if not self._ensure_thread_manager("Abandonment Issues cache-only rotation"):
            return False
        self._abandonment_rotation_in_progress = True
        generation = self._next_abandonment_generation()

        def _rotate_snapshot():
            from core.steam.abandonment_cache import load_abandonment_cache_snapshot
            from core.steam.credentials import read_credential_metadata

            metadata = read_credential_metadata()
            if metadata is None:
                return None
            snapshot = load_abandonment_cache_snapshot(
                profile_key=metadata.profile_cache_key,
                selection=self._abandonment_selection,
                advance_rotation=True,
                rotation_interval_minutes=self._abandonment_rotation_interval_minutes,
            )
            return self._prepare_presentation(
                snapshot,
                profile_key=metadata.profile_cache_key,
                allow_asset_network=False,
            )

        def _finished(task_result) -> None:
            from core.threading.manager import ThreadManager

            def _apply_result() -> None:
                if generation != getattr(self, "_abandonment_generation", None):
                    return
                self._abandonment_rotation_in_progress = False
                presentation = task_result.result if task_result.success else None
                if presentation is not None:
                    self._apply_prepared_presentation(presentation, animate=True)

            ThreadManager.run_on_ui_thread(_apply_result)

        try:
            self._thread_manager.submit_io_task(
                _rotate_snapshot,
                task_id=f"steam_abandonment_rotation_{generation}",
                callback=_finished,
            )
        except Exception:
            self._abandonment_rotation_in_progress = False
            logger.warning("[STEAM] Could not submit cache-only Abandonment rotation", exc_info=True)
            return False
        return True

    def _prepare_presentation(
        self,
        snapshot,
        *,
        profile_key: str,
        allow_asset_network: bool,
        connection_needs_attention: bool = False,
    ) -> tuple[SteamCardViewModel, str, int]:
        from core.settings.storage_paths import get_steam_cache_dir
        from core.steam.assets import (
            SteamAssetRecord,
            abandonment_desaturation_bucket,
            fetch_steam_app_artwork,
            find_cached_steam_app_artwork,
            prepare_desaturated_steam_artwork,
        )

        model = build_abandonment_view_model(
            snapshot.resolved,
            cache_age_seconds=snapshot.cache_age_seconds,
            connection_needs_attention=connection_needs_attention,
            show_connection_info_icon=self._abandonment_show_connection_info_icon,
            field_visibility=self._abandonment_field_visibility,
        )
        asset_path: Path | None = None
        bucket = 0
        if self._abandonment_show_artwork and model.appid is not None:
            asset_dir = get_steam_cache_dir(profile_key=profile_key) / "assets"
            if allow_asset_network:
                asset = fetch_steam_app_artwork(
                    cache_dir=asset_dir,
                    appid=model.appid,
                    artwork_shape=self._abandonment_artwork_shape,
                )
                if isinstance(asset, SteamAssetRecord):
                    asset_path = asset.path
            else:
                asset_path = find_cached_steam_app_artwork(
                    cache_dir=asset_dir,
                    appid=model.appid,
                    artwork_shape=self._abandonment_artwork_shape,
                )
            if asset_path is not None:
                bucket = abandonment_desaturation_bucket(
                    inactivity_days=snapshot.resolved.inactivity_days,
                    enabled=(
                        self._abandonment_guilt_desaturater
                        and snapshot.resolved.last_played_confidence == "verified"
                    ),
                    maximum_percent=self._abandonment_guilt_desaturation_strength,
                    threshold_days=self._abandonment_selection.minimum_inactivity_days,
                )
                asset_path = prepare_desaturated_steam_artwork(
                    source_path=asset_path,
                    cache_dir=asset_dir,
                    desaturation_percent=bucket,
                )
        return model, str(asset_path or ""), bucket

    def _apply_prepared_presentation(
        self,
        presentation: tuple[SteamCardViewModel, str, int],
        *,
        animate: bool,
    ) -> None:
        from widgets.service_widget_runtime import defer_value_if_transition

        if defer_value_if_transition(
            self,
            attr_name="_deferred_abandonment_presentation",
            value=(presentation, animate),
            clear_attrs=(),
            schedule_callback=self._schedule_deferred_presentation,
            logger=logger,
            log_message="[STEAM] Deferred Abandonment Issues presentation during parent transition",
        ):
            return
        self._commit_prepared_presentation(presentation, animate=animate)

    def _schedule_deferred_presentation(self) -> None:
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(250, self._apply_deferred_presentation)

    def _apply_deferred_presentation(self) -> None:
        from widgets.service_widget_runtime import parent_transition_running

        deferred = getattr(self, "_deferred_abandonment_presentation", None)
        if deferred is None:
            return
        if parent_transition_running(self):
            self._schedule_deferred_presentation()
            return
        self._deferred_abandonment_presentation = None
        presentation, animate = deferred
        self._commit_prepared_presentation(presentation, animate=bool(animate))

    def _commit_prepared_presentation(
        self,
        presentation: tuple[SteamCardViewModel, str, int],
        *,
        animate: bool,
    ) -> None:
        model, asset_path, bucket = presentation
        image = QImage(asset_path) if asset_path else QImage()
        transition_key = (model.state, model.appid, asset_path, bucket)

        def _commit() -> None:
            self._view_model = model
            self._abandonment_artwork = image
            self._abandonment_scaled_artwork = QImage()
            self._abandonment_scaled_artwork_key = None
            self._has_displayed_valid_data = True

        self.apply_content_transition(transition_key, _commit, animate=animate)

    def _next_abandonment_generation(self) -> int:
        generation = int(getattr(self, "_abandonment_generation", 0)) + 1
        self._abandonment_generation = generation
        return generation

    def _scaled_artwork_for(self, rect: QRectF, dpr: float) -> QImage:
        if self._abandonment_artwork.isNull() or rect.isNull():
            return QImage()
        scale_dpr = max(1.0, float(dpr))
        target_w = max(1, int(round(rect.width() * scale_dpr)))
        target_h = max(1, int(round(rect.height() * scale_dpr)))
        key = (int(self._abandonment_artwork.cacheKey()), target_w, target_h, scale_dpr)
        if key == self._abandonment_scaled_artwork_key and not self._abandonment_scaled_artwork.isNull():
            return self._abandonment_scaled_artwork
        scaled = self._abandonment_artwork.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        crop_x = max(0, (scaled.width() - target_w) // 2)
        crop_y = max(0, (scaled.height() - target_h) // 2)
        prepared = scaled.copy(crop_x, crop_y, target_w, target_h)
        prepared.setDevicePixelRatio(scale_dpr)
        self._abandonment_scaled_artwork = prepared
        self._abandonment_scaled_artwork_key = key
        return prepared

    def _paint_before_native_text(self) -> None:
        painter = None
        try:
            painter = QPainter(self)
            shrink_r, shrink_b = self.painted_frame_shadow_card_shrink()
            target = QRectF(
                0.0,
                0.0,
                max(1.0, float(self.width() - shrink_r)),
                max(1.0, float(self.height() - shrink_b)),
            )
            layout = layout_abandonment_card(
                self._view_model,
                target,
                show_artwork=self._abandonment_show_artwork,
                artwork_shape=self._abandonment_artwork_shape,
                artwork_size=self._abandonment_artwork_size,
            )
            artwork = self._scaled_artwork_for(layout.art_rect, self.devicePixelRatioF())
            self._last_layout = render_abandonment_card(
                painter,
                self._view_model,
                target,
                font_family=self.get_font_family(),
                font_size=self.get_font_size(),
                text_color=self.get_text_color(),
                logo_pixmap=self._steam_logo,
                artwork_image=artwork,
                show_artwork=self._abandonment_show_artwork,
                artwork_shape=self._abandonment_artwork_shape,
                artwork_size=self._abandonment_artwork_size,
                accent_color=self._abandonment_accent_color,
                content_opacity=self.content_opacity(),
            )
        finally:
            if painter is not None:
                painter.end()
