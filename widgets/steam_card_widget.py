"""Dev-gated mock Steam card overlays.

These cards intentionally avoid provider, cache, credential, and timer work so
the Steam family can prove descriptor, factory, settings, Custom-layout, and
shared visual contracts before production data is wired.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from widgets.shadow_utils import ShadowFadeProfile

from core.logging.logger import get_logger
from core.steam.achievement_pulse import AchievementPulseSelection
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.steam_components import (
    ACHIEVEMENT_PULSE_AUTHORED_SIZE,
    STEAM_CARD_AUTHORED_SIZE,
    SteamCardLayout,
    SteamCardViewModel,
    build_mock_steam_view_model,
    build_steam_connect_required_view_model,
    layout_steam_card,
    render_steam_card,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class SteamCardDefinition:
    """Static presentation metadata for one Steam card scaffold."""

    widget_id: str
    title: str
    subtitle: str


STEAM_CARD_DEFINITIONS: dict[str, SteamCardDefinition] = {
    "steam_progress": SteamCardDefinition(
        widget_id="steam_progress",
        title="Steam Progress",
        subtitle="Dev-gated update card scaffold",
    ),
    "achievement_pulse": SteamCardDefinition(
        widget_id="achievement_pulse",
        title="Achievement Pulse",
        subtitle="Dev-gated achievement card scaffold",
    ),
    "abandonment_issues": SteamCardDefinition(
        widget_id="abandonment_issues",
        title="Abandonment Issues",
        subtitle="Dev-gated library return card scaffold",
    ),
    "friend_pulse": SteamCardDefinition(
        widget_id="friend_pulse",
        title="Friend Pulse",
        subtitle="Dev-gated friend activity card scaffold",
    ),
}


class SteamCardWidget(BaseOverlayWidget):
    """Framed dev-gated Steam card with cache-first presentation support."""

    settings_requested = Signal(str)

    def __init__(
        self,
        parent=None,
        *,
        definition: SteamCardDefinition,
        position: OverlayPosition = OverlayPosition.TOP_RIGHT,
        initial_view_model: SteamCardViewModel | None = None,
        achievement_selection: AchievementPulseSelection = AchievementPulseSelection(),
        achievement_field_visibility: Mapping[str, bool] | None = None,
        achievement_latest_unlock_count: int = 1,
        achievement_show_artwork: bool = True,
        achievement_artwork_shape: str = "wide",
        refresh_minutes: int = 10,
    ) -> None:
        super().__init__(parent=parent, position=position, overlay_name=definition.widget_id)
        self.definition = definition
        self._achievement_selection = achievement_selection
        self._achievement_field_visibility = dict(achievement_field_visibility or {})
        self._achievement_latest_unlock_count = max(1, min(3, int(achievement_latest_unlock_count)))
        self._achievement_show_artwork = bool(achievement_show_artwork)
        self._achievement_artwork_shape = (
            "square" if str(achievement_artwork_shape).strip().lower() == "square" else "wide"
        )
        self._refresh_minutes = max(5, int(refresh_minutes))
        self._achievement_artwork = QImage()
        self._achievement_scaled_artwork_cache = QImage()
        self._achievement_scaled_artwork_cache_key: tuple[int, int, int, float] | None = None
        self._defer_visibility_for_fade_sync = True
        self._view_model: SteamCardViewModel = initial_view_model or build_mock_steam_view_model(definition.widget_id)
        self._last_layout: SteamCardLayout | None = None
        self._steam_logo = self._load_steam_logo()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText("")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setWordWrap(False)
        authored_size = (
            ACHIEVEMENT_PULSE_AUTHORED_SIZE
            if definition.widget_id == "achievement_pulse"
            else STEAM_CARD_AUTHORED_SIZE
        )
        self.setMinimumSize(QSize(int(authored_size.width()), int(authored_size.height())))
        self._apply_base_styling()
        self._update_content()

    @staticmethod
    def _load_steam_logo() -> QPixmap:
        logo_path = Path(__file__).resolve().parent.parent / "images" / "Steam_Logo.png"
        pixmap = QPixmap(str(logo_path))
        if pixmap.isNull():
            return QPixmap()
        try:
            from widgets.steam_components import _crop_logo_pixmap_to_alpha_bounds

            cropped = _crop_logo_pixmap_to_alpha_bounds(pixmap, str(logo_path))
            return cropped if not cropped.isNull() else pixmap
        except Exception:
            return pixmap

    def _update_content(self) -> None:
        self.setToolTip(f"Steam card: {self.definition.title}")

    def _calculate_content_size(self) -> QSize:
        authored_size = (
            ACHIEVEMENT_PULSE_AUTHORED_SIZE
            if self.definition.widget_id == "achievement_pulse"
            else STEAM_CARD_AUTHORED_SIZE
        )
        return QSize(
            max(int(authored_size.width()), self.minimumWidth()),
            max(int(authored_size.height()), self.minimumHeight()),
        )

    def set_text_color(self, color: QColor) -> None:
        super().set_text_color(color)
        self.update()

    def set_view_model(self, view_model: SteamCardViewModel) -> None:
        """Apply an already-resolved view model without provider/cache work."""

        self._view_model = view_model
        self.update()

    def set_achievement_selection(self, selection: AchievementPulseSelection) -> None:
        """Set persisted non-secret app selection before an activation refresh."""
        self._achievement_selection = selection

    def set_achievement_field_visibility(self, visibility: Mapping[str, bool]) -> None:
        """Apply persisted field preferences to later cache-derived card models."""
        self._achievement_field_visibility = {str(key): bool(value) for key, value in visibility.items()}

    def last_layout(self) -> SteamCardLayout | None:
        """Return the most recent layout metrics, primarily for bars/tests."""

        return self._last_layout

    def settings_action_at(self, pos: QPoint) -> str | None:
        """Return a settings target for a click point in the last painted layout."""

        layout = self._last_layout
        if layout is None:
            return None
        point = pos
        for target, rect in layout.action_rects:
            if rect.contains(point):
                return target
        if layout.info_rect is not None and layout.info_rect.contains(point):
            return self._view_model.connection_info_target or None
        return None

    def handle_click(self, local_pos: QPoint) -> bool:
        """Consume Steam card affordance clicks without opening private routes."""

        target = self.settings_action_at(local_pos)
        if not target:
            return False
        self.settings_requested.emit(target)
        return True

    def handle_double_click(self, _local_pos: QPoint) -> bool:
        """Use a blank-card double click as the explicit Achievement Pulse refresh action."""
        if self.definition.widget_id != "achievement_pulse":
            return False
        return self.request_manual_refresh()

    def _activate_impl(self) -> None:
        """Apply cached Achievement Pulse content before the coordinated fade."""

        if self.definition.widget_id == "achievement_pulse":
            if self._load_achievement_pulse_cache(start_fade_after_load=True):
                return
        self._request_coordinated_fade()

    def _request_coordinated_fade(self) -> None:
        """Request the normal overlay fade after any cache-first preload."""

        parent = self.parent()

        def _starter() -> None:
            self._start_widget_fade_in()

        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                parent.request_overlay_fade_sync(self.get_overlay_name(), _starter)
                return
            except Exception:
                # The card is dev-gated, but a fade-sync failure is still a lifecycle fallback.
                logger.warning(
                    "[LIFECYCLE][FALLBACK] Steam card fade-sync failed; using direct fade",
                    exc_info=True,
                )
        _starter()

    def _handle_fade_complete(self) -> None:
        self._has_faded_in = True
        self.on_fade_complete()

    def on_fade_complete(self) -> None:
        """Refresh stale Steam data only after cached content has faded in."""
        super().on_fade_complete()
        if self.definition.widget_id != "achievement_pulse":
            return
        if not getattr(self, "_achievement_activation_cache_preloaded", False):
            self._load_achievement_pulse_cache()
            return
        if (
            getattr(self, "_achievement_activation_has_metadata", False)
            and not getattr(self, "_achievement_activation_refresh_scheduled", False)
        ):
            self._achievement_activation_refresh_scheduled = True
            self._refresh_achievement_pulse_cache(
                cache_age_seconds=getattr(self, "_achievement_activation_cache_age_seconds", None)
            )

    def _load_achievement_pulse_cache(self, *, start_fade_after_load: bool = False) -> bool:
        """Load a cached card model off-thread, optionally before first visibility."""
        if getattr(self, "_achievement_cache_load_started", False):
            if start_fade_after_load:
                if getattr(self, "_achievement_activation_cache_preloaded", False):
                    self._request_coordinated_fade()
                else:
                    self._achievement_start_fade_after_cache_load = True
            return True
        if not self._ensure_thread_manager("Achievement Pulse cache load"):
            return False
        self._achievement_cache_load_started = True
        self._achievement_start_fade_after_cache_load = bool(start_fade_after_load)
        generation = int(getattr(self, "_achievement_cache_generation", 0)) + 1
        self._achievement_cache_generation = generation

        def _load_snapshot():
            from core.steam.achievement_pulse_cache import load_achievement_pulse_cache_snapshot
            from core.steam.credentials import read_credential_metadata

            metadata = read_credential_metadata()
            if metadata is None:
                return None, None
            return metadata, load_achievement_pulse_cache_snapshot(
                profile_key=metadata.profile_cache_key,
                selection=self._achievement_selection,
            )

        def _finished(task_result) -> None:
            from core.threading.manager import ThreadManager

            def _apply_result() -> None:
                if getattr(self, "_achievement_cache_generation", None) != generation:
                    return
                metadata, snapshot = task_result.result if task_result.success else (None, None)
                cache_age_seconds = None
                if snapshot is not None and snapshot.has_usable_cache:
                    cache_age_seconds = snapshot.cache_age_seconds
                    self._apply_achievement_pulse_snapshot(snapshot)
                self._achievement_activation_cache_preloaded = True
                self._achievement_activation_has_metadata = metadata is not None
                self._achievement_activation_cache_age_seconds = cache_age_seconds
                if getattr(self, "_achievement_start_fade_after_cache_load", False):
                    self._request_coordinated_fade()
                elif metadata is not None:
                    self._achievement_activation_refresh_scheduled = True
                    self._refresh_achievement_pulse_cache(cache_age_seconds=cache_age_seconds)

            ThreadManager.run_on_ui_thread(_apply_result)

        try:
            self._thread_manager.submit_io_task(
                _load_snapshot,
                task_id=f"steam_achievement_cache_load_{generation}",
                callback=_finished,
            )
        except Exception:
            self._achievement_cache_load_started = False
            logger.warning("[STEAM] Could not submit Achievement Pulse cache load", exc_info=True)
            return False
        return True

    def _refresh_achievement_pulse_cache(
        self,
        *,
        cache_age_seconds: float | None,
        force: bool = False,
    ) -> bool:
        """Submit one startup refresh through the shared ThreadManager only."""
        from core.runtime_flags import automatic_service_updates_enabled

        if not force and not automatic_service_updates_enabled():
            return False
        if not force and cache_age_seconds is not None and cache_age_seconds < self._refresh_minutes * 60:
            return False
        if getattr(self, "_achievement_refresh_in_progress", False):
            return True
        if not self._ensure_thread_manager("Achievement Pulse refresh"):
            return False
        self._achievement_refresh_in_progress = True
        generation = int(getattr(self, "_achievement_cache_generation", 0)) + 1
        self._achievement_cache_generation = generation

        def _refresh_snapshot():
            from core.steam.achievement_pulse_cache import (
                AchievementPulseRefreshOutcome,
                load_achievement_pulse_cache_snapshot,
                refresh_achievement_pulse_cache,
            )
            from core.steam.credentials import SteamCredentialError, load_credentials, read_credential_metadata

            try:
                credential = load_credentials()
            except SteamCredentialError:
                metadata = read_credential_metadata()
                if metadata is None:
                    return None
                return AchievementPulseRefreshOutcome(
                    snapshot=load_achievement_pulse_cache_snapshot(
                        profile_key=metadata.profile_cache_key,
                        selection=self._achievement_selection,
                    ),
                    connection_needs_attention=True,
                )
            if credential is None:
                return None
            return refresh_achievement_pulse_cache(
                credential=credential,
                selection=self._achievement_selection,
                force=force,
            )

        def _finished(task_result) -> None:
            from core.threading.manager import ThreadManager

            def _apply_result() -> None:
                if getattr(self, "_achievement_cache_generation", None) != generation:
                    return
                self._achievement_refresh_in_progress = False
                outcome = task_result.result if task_result.success else None
                if outcome is not None and getattr(outcome, "snapshot", None) is not None:
                    self._apply_achievement_pulse_snapshot(
                        outcome.snapshot,
                        connection_needs_attention=bool(outcome.connection_needs_attention),
                    )

            ThreadManager.run_on_ui_thread(_apply_result)

        try:
            self._thread_manager.submit_io_task(
                _refresh_snapshot,
                task_id=f"steam_achievement_refresh_{generation}",
                callback=_finished,
            )
        except Exception:
            self._achievement_refresh_in_progress = False
            logger.warning("[STEAM] Could not submit Achievement Pulse refresh", exc_info=True)
            return False
        return True

    def request_manual_refresh(self) -> bool:
        """Request a user-initiated refresh without bypassing provider backoff/dedupe."""
        if self.definition.widget_id != "achievement_pulse":
            return False
        from widgets.service_widget_runtime import defer_refresh_if_transition

        if defer_refresh_if_transition(
            self,
            pending_attr="_pending_achievement_manual_refresh",
            schedule_callback=self._schedule_deferred_manual_refresh,
            logger=logger,
            log_message="[STEAM] Deferred manual Achievement Pulse refresh during parent transition",
        ):
            return True
        return self._refresh_achievement_pulse_cache(cache_age_seconds=None, force=True)

    def _schedule_deferred_manual_refresh(self) -> None:
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(250, self._run_deferred_manual_refresh)

    def _run_deferred_manual_refresh(self) -> None:
        from widgets.service_widget_runtime import parent_transition_running

        if not getattr(self, "_pending_achievement_manual_refresh", False):
            return
        if parent_transition_running(self):
            self._schedule_deferred_manual_refresh()
            return
        self._pending_achievement_manual_refresh = False
        self._refresh_achievement_pulse_cache(cache_age_seconds=None, force=True)

    def _apply_achievement_pulse_snapshot(self, snapshot, *, connection_needs_attention: bool = False) -> None:
        """Apply a cache snapshot without repaint churn or transition interruption."""
        from widgets.service_widget_runtime import defer_value_if_transition
        from widgets.steam_components import build_achievement_pulse_view_model

        model = build_achievement_pulse_view_model(
            snapshot.resolved,
            cache_age_seconds=snapshot.cache_age_seconds,
            connection_needs_attention=connection_needs_attention,
            field_visibility=self._achievement_field_visibility,
            latest_unlock_count=self._achievement_latest_unlock_count,
        )
        if defer_value_if_transition(
            self,
            attr_name="_deferred_achievement_view_model",
            value=model,
            clear_attrs=(),
            schedule_callback=self._schedule_deferred_achievement_apply,
            logger=logger,
            log_message="[STEAM] Deferred Achievement Pulse result during parent transition",
        ):
            return
        self._apply_achievement_pulse_view_model(model)

    def _schedule_deferred_achievement_apply(self) -> None:
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(250, self._apply_deferred_achievement_view_model)

    def _apply_deferred_achievement_view_model(self) -> None:
        from widgets.service_widget_runtime import parent_transition_running

        model = getattr(self, "_deferred_achievement_view_model", None)
        if model is None:
            return
        if parent_transition_running(self):
            self._schedule_deferred_achievement_apply()
            return
        self._deferred_achievement_view_model = None
        self._apply_achievement_pulse_view_model(model)

    def _apply_achievement_pulse_view_model(self, model: SteamCardViewModel) -> None:
        if model.content_fingerprint() != self._view_model.content_fingerprint():
            self.set_view_model(model)
        if self._achievement_show_artwork and model.appid is not None:
            self._load_achievement_artwork(model.appid)
        self._has_displayed_valid_data = True

    def _load_achievement_artwork(self, appid: int) -> None:
        """Load one cached-or-public app header after resolved content reaches the card."""
        if getattr(self, "_achievement_artwork_appid", None) == appid:
            return
        if not self._ensure_thread_manager("Achievement Pulse artwork"):
            return
        self._achievement_artwork_appid = appid
        generation = int(getattr(self, "_achievement_artwork_generation", 0)) + 1
        self._achievement_artwork_generation = generation

        def _load_artwork():
            from core.settings.storage_paths import get_steam_cache_dir
            from core.steam.assets import SteamAssetRecord, fetch_steam_app_header
            from core.steam.credentials import read_credential_metadata

            metadata = read_credential_metadata()
            if metadata is None:
                return None
            asset = fetch_steam_app_header(
                cache_dir=get_steam_cache_dir(profile_key=metadata.profile_cache_key) / "assets",
                appid=appid,
            )
            return asset.path if isinstance(asset, SteamAssetRecord) else None

        def _finished(task_result) -> None:
            from core.threading.manager import ThreadManager

            def _apply_result() -> None:
                if getattr(self, "_achievement_artwork_generation", None) != generation:
                    return
                asset_path = task_result.result if task_result.success else None
                image = QImage(str(asset_path)) if asset_path else QImage()
                if not image.isNull():
                    self._achievement_artwork = image
                    self._achievement_scaled_artwork_cache = QImage()
                    self._achievement_scaled_artwork_cache_key = None
                    self.update()

            ThreadManager.run_on_ui_thread(_apply_result)

        try:
            self._thread_manager.submit_io_task(
                _load_artwork,
                task_id=f"steam_achievement_artwork_{appid}_{generation}",
                callback=_finished,
            )
        except Exception:
            logger.warning("[STEAM] Could not submit Achievement Pulse artwork load", exc_info=True)

    def _scaled_achievement_artwork(self, art_rect: QRectF, dpr: float) -> QImage:
        """Return a cached DPR-aware cover crop using Media's quality policy."""

        if self._achievement_artwork.isNull() or art_rect.isNull():
            return QImage()
        scale_dpr = max(1.0, float(dpr))
        target_w = max(1, int(round(art_rect.width() * scale_dpr)))
        target_h = max(1, int(round(art_rect.height() * scale_dpr)))
        cache_key = (int(self._achievement_artwork.cacheKey()), target_w, target_h, scale_dpr)
        if (
            self._achievement_scaled_artwork_cache_key == cache_key
            and not self._achievement_scaled_artwork_cache.isNull()
        ):
            return self._achievement_scaled_artwork_cache

        scaled = self._achievement_artwork.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        crop_x = max(0, (scaled.width() - target_w) // 2)
        crop_y = max(0, (scaled.height() - target_h) // 2)
        cropped = scaled.copy(crop_x, crop_y, target_w, target_h)
        cropped.setDevicePixelRatio(scale_dpr)
        self._achievement_scaled_artwork_cache = cropped
        self._achievement_scaled_artwork_cache_key = cache_key
        return cropped

    def _start_widget_fade_in(self, duration_ms: int | None = None) -> None:
        """Start the same painter-owned overlay fade profile used by other cards."""

        resolved_duration_ms = ShadowFadeProfile.default_duration_ms() if duration_ms is None else max(0, int(duration_ms))
        if resolved_duration_ms <= 0:
            self.show()
            self.raise_()
            self._has_faded_in = True
            self.on_fade_complete()
            return
        self.show()
        self.raise_()
        ShadowFadeProfile.start_fade_in(
            self,
            self._shadow_config,
            duration_ms=resolved_duration_ms,
            has_background_frame=bool(self._show_background),
            on_finished=self._handle_fade_complete,
        )

    @staticmethod
    def connect_required_model(widget_id: str) -> SteamCardViewModel:
        """Factory helper for enabled runtime cards without OAuth/cache data."""

        return build_steam_connect_required_view_model(widget_id)

    def _paint_before_native_text(self) -> None:
        painter = None
        try:
            from PySide6.QtGui import QPainter

            painter = QPainter(self)
            shrink_r, shrink_b = self.painted_frame_shadow_card_shrink()
            target = QRectF(
                0.0,
                0.0,
                max(1.0, float(self.width() - shrink_r)),
                max(1.0, float(self.height() - shrink_b)),
            )
            dpr = max(1.0, float(self.devicePixelRatioF()))
            preview_layout = layout_steam_card(
                self._view_model,
                target,
                dpr=dpr,
                show_artwork=self._achievement_show_artwork,
                artwork_shape=self._achievement_artwork_shape,
            )
            artwork = (
                self._scaled_achievement_artwork(preview_layout.art_rect, dpr)
                if self._achievement_show_artwork
                else QImage()
            )
            self._last_layout = render_steam_card(
                painter,
                self._view_model,
                target,
                font_family=self.get_font_family(),
                font_size=self.get_font_size(),
                text_color=self.get_text_color(),
                dpr=dpr,
                logo_pixmap=self._steam_logo,
                artwork_image=artwork,
                show_artwork=self._achievement_show_artwork,
                artwork_shape=self._achievement_artwork_shape,
            )
        finally:
            if painter is not None:
                painter.end()
