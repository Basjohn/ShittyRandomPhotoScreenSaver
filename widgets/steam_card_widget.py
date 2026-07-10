"""Steam card overlays with cache-first Achievement Pulse support.

Constructors and paint stay provider-inert. The unfinished card prototypes remain
dev-gated while Achievement Pulse resolves data through its bounded cache bridge.
"""
from __future__ import annotations

import hashlib
import math
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
    ACHIEVEMENT_CAPSULE_BORDER_RGBA,
    ACHIEVEMENT_CAPSULE_FILL_RGBA,
    ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT,
    ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT,
    STEAM_CARD_AUTHORED_SIZE,
    SteamCardLayout,
    SteamCardViewModel,
    achievement_capsule_geometry,
    achievement_field_rail_count,
    achievement_pulse_authored_size,
    build_mock_steam_view_model,
    build_steam_connect_required_view_model,
    layout_steam_card,
    normalize_achievement_capsule_font_size,
    normalize_achievement_square_artwork_size,
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
        title="Steam Journey",
        subtitle="Dev-gated update card scaffold",
    ),
    "achievement_pulse": SteamCardDefinition(
        widget_id="achievement_pulse",
        title="Achievement Pulse",
        subtitle="Cache-first achievement card",
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
    """Framed Steam card with cache-first Achievement Pulse support."""

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
        achievement_show_latest_artwork: bool = True,
        achievement_show_artwork: bool = True,
        achievement_artwork_shape: str = "wide",
        achievement_square_artwork_size: int = ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT,
        achievement_double_capsules: bool = True,
        achievement_capsule_font_size: int = ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT,
        achievement_capsule_fill_color: QColor | None = None,
        achievement_capsule_border_color: QColor | None = None,
        refresh_minutes: int = 10,
    ) -> None:
        super().__init__(parent=parent, position=position, overlay_name=definition.widget_id)
        self.definition = definition
        self._achievement_selection = achievement_selection
        self._achievement_field_visibility = dict(achievement_field_visibility or {})
        self._achievement_latest_unlock_count = max(1, min(5, int(achievement_latest_unlock_count)))
        self._achievement_show_latest_artwork = bool(achievement_show_latest_artwork)
        self._achievement_show_artwork = bool(achievement_show_artwork)
        self._achievement_artwork_shape = (
            "square" if str(achievement_artwork_shape).strip().lower() == "square" else "wide"
        )
        self._achievement_square_artwork_size = normalize_achievement_square_artwork_size(
            achievement_square_artwork_size
        )
        self._achievement_double_capsules = bool(achievement_double_capsules)
        self._achievement_capsule_font_size = normalize_achievement_capsule_font_size(
            achievement_capsule_font_size
        )
        self._achievement_capsule_fill_color = QColor(
            achievement_capsule_fill_color or QColor(*ACHIEVEMENT_CAPSULE_FILL_RGBA)
        )
        self._achievement_capsule_border_color = QColor(
            achievement_capsule_border_color or QColor(*ACHIEVEMENT_CAPSULE_BORDER_RGBA)
        )
        self._refresh_minutes = max(5, int(refresh_minutes))
        self._achievement_artwork = QImage()
        self._achievement_scaled_artwork_cache = QImage()
        self._achievement_scaled_artwork_cache_key: tuple[int, int, int, float, str] | None = None
        self._achievement_latest_artwork = QImage()
        self._achievement_scaled_latest_artwork_cache = QImage()
        self._achievement_scaled_latest_artwork_cache_key: tuple[int, int, int, float] | None = None
        self._defer_visibility_for_fade_sync = True
        self._view_model: SteamCardViewModel = initial_view_model or build_mock_steam_view_model(definition.widget_id)
        self._last_layout: SteamCardLayout | None = None
        self._steam_logo = self._load_steam_logo()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText("")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setWordWrap(False)
        authored_size = self._authored_content_size()
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
        authored_size = self._authored_content_size()
        return QSize(
            max(int(math.ceil(authored_size.width())), self.minimumWidth()),
            max(int(math.ceil(authored_size.height())), self.minimumHeight()),
        )

    def _achievement_capsule_field_count(self) -> int:
        if self._view_model.fields:
            return sum(1 for field in self._view_model.fields if field.enabled)
        defaults = {
            "total": True,
            "playtime": True,
            "previous": True,
            "source": False,
            "selected": False,
        }
        return sum(
            1
            for field_id, default in defaults.items()
            if bool(self._achievement_field_visibility.get(field_id, default))
        )

    def _authored_content_size(self):
        if self.definition.widget_id != "achievement_pulse":
            return STEAM_CARD_AUTHORED_SIZE
        field_count = self._achievement_capsule_field_count()
        field_rails = achievement_field_rail_count(
            field_count,
            double_capsules=self._achievement_double_capsules,
        )
        capsule_height, capsule_gap = achievement_capsule_geometry(
            font_family=self.get_font_family(),
            capsule_font_size=self._achievement_capsule_font_size,
        )
        return achievement_pulse_authored_size(
            show_artwork=self._achievement_show_artwork,
            artwork_shape=self._achievement_artwork_shape,
            field_rail_count=field_rails,
            capsule_height=capsule_height,
            capsule_gap=capsule_gap,
        )

    def _grow_to_authored_content_size(self) -> None:
        """Grow non-Custom cards when capsule typography needs more vertical room."""

        if self.definition.widget_id != "achievement_pulse":
            return
        authored = self._authored_content_size()
        width = int(math.ceil(authored.width()))
        height = int(math.ceil(authored.height()))
        self.setMinimumSize(
            max(self.minimumWidth(), width),
            max(self.minimumHeight(), height),
        )
        if self._active_custom_layout_rect() is None:
            self.resize(max(self.width(), width), max(self.height(), height))
            self.updateGeometry()

    def set_text_color(self, color: QColor) -> None:
        super().set_text_color(color)
        self.update()

    def set_view_model(self, view_model: SteamCardViewModel) -> None:
        """Apply an already-resolved view model without provider/cache work."""

        self._view_model = view_model
        self._grow_to_authored_content_size()
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
                # A fade-sync failure remains a lifecycle fallback even for a public card.
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
        if self._achievement_show_latest_artwork and model.latest_unlock_icon_url:
            self._load_latest_achievement_artwork(model.latest_unlock_icon_url)
        else:
            self._clear_latest_achievement_artwork()
        self._has_displayed_valid_data = True

    def _load_achievement_artwork(self, appid: int) -> None:
        """Load one cached public header or portrait capsule for the selected app."""
        artwork_identity = (appid, self._achievement_artwork_shape)
        if getattr(self, "_achievement_artwork_identity", None) == artwork_identity:
            return
        if not self._ensure_thread_manager("Achievement Pulse artwork"):
            return
        self._achievement_artwork_identity = artwork_identity
        generation = int(getattr(self, "_achievement_artwork_generation", 0)) + 1
        self._achievement_artwork_generation = generation

        def _load_artwork():
            from core.settings.storage_paths import get_steam_cache_dir
            from core.steam.assets import SteamAssetRecord, fetch_steam_app_artwork
            from core.steam.credentials import read_credential_metadata

            metadata = read_credential_metadata()
            if metadata is None:
                return None
            asset = fetch_steam_app_artwork(
                cache_dir=get_steam_cache_dir(profile_key=metadata.profile_cache_key) / "assets",
                appid=appid,
                artwork_shape=self._achievement_artwork_shape,
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
                task_id=f"steam_achievement_artwork_{self._achievement_artwork_shape}_{appid}_{generation}",
                callback=_finished,
            )
        except Exception:
            logger.warning("[STEAM] Could not submit Achievement Pulse artwork load", exc_info=True)

    def _clear_latest_achievement_artwork(self) -> None:
        if (
            not getattr(self, "_achievement_latest_artwork_identity", "")
            and self._achievement_latest_artwork.isNull()
        ):
            return
        self._achievement_latest_artwork_generation = int(
            getattr(self, "_achievement_latest_artwork_generation", 0)
        ) + 1
        self._achievement_latest_artwork_identity = ""
        self._achievement_latest_artwork = QImage()
        self._achievement_scaled_latest_artwork_cache = QImage()
        self._achievement_scaled_latest_artwork_cache_key = None
        self.update()

    def _load_latest_achievement_artwork(self, icon_url: str) -> None:
        """Load the schema-owned primary achievement icon through the asset cache."""
        safe_url = str(icon_url or "").strip()
        if not safe_url:
            self._clear_latest_achievement_artwork()
            return
        if getattr(self, "_achievement_latest_artwork_identity", "") == safe_url:
            return
        if not self._ensure_thread_manager("Achievement Pulse latest artwork"):
            return

        self._achievement_latest_artwork_identity = safe_url
        generation = int(getattr(self, "_achievement_latest_artwork_generation", 0)) + 1
        self._achievement_latest_artwork_generation = generation
        url_fingerprint = hashlib.sha256(safe_url.encode("utf-8")).hexdigest()[:12]

        def _load_artwork():
            from core.settings.storage_paths import get_steam_cache_dir
            from core.steam.assets import SteamAssetRecord, fetch_steam_achievement_icon
            from core.steam.credentials import read_credential_metadata

            metadata = read_credential_metadata()
            if metadata is None:
                return None
            asset = fetch_steam_achievement_icon(
                cache_dir=get_steam_cache_dir(profile_key=metadata.profile_cache_key) / "assets",
                url=safe_url,
            )
            return asset.path if isinstance(asset, SteamAssetRecord) else None

        def _finished(task_result) -> None:
            from core.threading.manager import ThreadManager

            def _apply_result() -> None:
                if getattr(self, "_achievement_latest_artwork_generation", None) != generation:
                    return
                asset_path = task_result.result if task_result.success else None
                image = QImage(str(asset_path)) if asset_path else QImage()
                self._achievement_latest_artwork = image
                self._achievement_scaled_latest_artwork_cache = QImage()
                self._achievement_scaled_latest_artwork_cache_key = None
                self.update()

            ThreadManager.run_on_ui_thread(_apply_result)

        try:
            self._thread_manager.submit_io_task(
                _load_artwork,
                task_id=f"steam_achievement_latest_artwork_{url_fingerprint}_{generation}",
                callback=_finished,
            )
        except Exception:
            logger.warning(
                "[STEAM] Could not submit latest achievement artwork load",
                exc_info=True,
            )

    def _scaled_achievement_artwork(self, art_rect: QRectF, dpr: float) -> QImage:
        """Return a cached DPR-aware cover crop using Media's quality policy."""

        if self._achievement_artwork.isNull() or art_rect.isNull():
            return QImage()
        scale_dpr = max(1.0, float(dpr))
        target_w = max(1, int(round(art_rect.width() * scale_dpr)))
        target_h = max(1, int(round(art_rect.height() * scale_dpr)))
        cache_key = (
            int(self._achievement_artwork.cacheKey()),
            target_w,
            target_h,
            scale_dpr,
            self._achievement_artwork_shape,
        )
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
        prepared = scaled.copy(crop_x, crop_y, target_w, target_h)
        prepared.setDevicePixelRatio(scale_dpr)
        self._achievement_scaled_artwork_cache = prepared
        self._achievement_scaled_artwork_cache_key = cache_key
        return prepared

    def _scaled_latest_achievement_artwork(self, art_rect: QRectF, dpr: float) -> QImage:
        """Return a cached DPR-aware cover crop for the 40px achievement flair."""
        if self._achievement_latest_artwork.isNull() or art_rect.isNull():
            return QImage()
        scale_dpr = max(1.0, float(dpr))
        target_w = max(1, int(round(art_rect.width() * scale_dpr)))
        target_h = max(1, int(round(art_rect.height() * scale_dpr)))
        cache_key = (
            int(self._achievement_latest_artwork.cacheKey()),
            target_w,
            target_h,
            scale_dpr,
        )
        if (
            self._achievement_scaled_latest_artwork_cache_key == cache_key
            and not self._achievement_scaled_latest_artwork_cache.isNull()
        ):
            return self._achievement_scaled_latest_artwork_cache

        scaled = self._achievement_latest_artwork.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        crop_x = max(0, (scaled.width() - target_w) // 2)
        crop_y = max(0, (scaled.height() - target_h) // 2)
        prepared = scaled.copy(crop_x, crop_y, target_w, target_h)
        prepared.setDevicePixelRatio(scale_dpr)
        self._achievement_scaled_latest_artwork_cache = prepared
        self._achievement_scaled_latest_artwork_cache_key = cache_key
        return prepared

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
            show_latest_artwork = bool(
                self._achievement_show_latest_artwork
                and not self._achievement_latest_artwork.isNull()
            )
            preview_layout = layout_steam_card(
                self._view_model,
                target,
                dpr=dpr,
                show_artwork=self._achievement_show_artwork,
                artwork_shape=self._achievement_artwork_shape,
                square_artwork_size=self._achievement_square_artwork_size,
                show_latest_artwork=show_latest_artwork,
                double_capsules=self._achievement_double_capsules,
                capsule_font_size=self._achievement_capsule_font_size,
                font_family=self.get_font_family(),
                font_size=self.get_font_size(),
            )
            artwork = (
                self._scaled_achievement_artwork(preview_layout.art_rect, dpr)
                if self._achievement_show_artwork
                else QImage()
            )
            latest_artwork = (
                self._scaled_latest_achievement_artwork(
                    preview_layout.latest_unlock_art_rect,
                    dpr,
                )
                if show_latest_artwork
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
                latest_artwork_image=latest_artwork,
                show_artwork=self._achievement_show_artwork,
                artwork_shape=self._achievement_artwork_shape,
                square_artwork_size=self._achievement_square_artwork_size,
                show_latest_artwork=show_latest_artwork,
                double_capsules=self._achievement_double_capsules,
                capsule_font_size=self._achievement_capsule_font_size,
                capsule_fill_color=self._achievement_capsule_fill_color,
                capsule_border_color=self._achievement_capsule_border_color,
            )
        finally:
            if painter is not None:
                painter.end()
