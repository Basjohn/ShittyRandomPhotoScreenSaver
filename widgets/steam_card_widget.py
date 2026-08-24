"""Steam card overlays with cache-first Achievement Pulse support.

Constructors and paint stay provider-inert. The unfinished card prototypes remain
dev-gated while Achievement Pulse resolves data through its bounded cache bridge.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from shiboken6 import Shiboken
from widgets.shadow_utils import ShadowFadeProfile

from core.logging.logger import get_logger
from core.steam.achievement_pulse import AchievementPulseSelection
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.steam_card_models import (
    SteamCardViewModel,
    build_mock_steam_view_model,
    build_steam_connect_required_view_model,
)
from widgets.steam_components import (
    ACHIEVEMENT_CAPSULE_BORDER_RGBA,
    ACHIEVEMENT_CAPSULE_FILL_RGBA,
    ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT,
    ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT,
    STEAM_CARD_AUTHORED_SIZE,
    SteamCardLayout,
    achievement_capsule_geometry,
    achievement_field_rail_count,
    achievement_pulse_authored_size,
    layout_steam_card,
    normalize_achievement_artwork_shape,
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
        subtitle="Cache-first library rediscovery card",
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
        achievement_artwork_shape: str = "portrait",
        achievement_square_artwork_size: int = ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT,
        achievement_double_capsules: bool = True,
        achievement_capsule_font_size: int = ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT,
        achievement_capsule_fill_color: QColor | None = None,
        achievement_capsule_border_color: QColor | None = None,
        refresh_minutes: int = 10,
        achievement_show_connection_info_icon: bool = True,
        build_default_runtime: bool = True,
    ) -> None:
        super().__init__(parent=parent, position=position, overlay_name=definition.widget_id)
        self._achievement_runtime_service: Optional[Any] = None
        self._owns_achievement_runtime_service = False
        self.definition = definition
        self._achievement_selection = achievement_selection
        self._achievement_field_visibility = dict(achievement_field_visibility or {})
        self._achievement_latest_unlock_count = max(1, min(5, int(achievement_latest_unlock_count)))
        self._achievement_show_latest_artwork = bool(achievement_show_latest_artwork)
        self._achievement_show_artwork = bool(achievement_show_artwork)
        self._achievement_artwork_shape = normalize_achievement_artwork_shape(
            achievement_artwork_shape
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
        self._achievement_show_connection_info_icon = bool(
            achievement_show_connection_info_icon
        )
        self._achievement_artwork = QImage()
        self._achievement_scaled_artwork_cache = QImage()
        self._achievement_scaled_artwork_cache_key: tuple[int, int, int, float, str] | None = None
        self._achievement_latest_artwork = QImage()
        self._achievement_scaled_latest_artwork_cache = QImage()
        self._achievement_scaled_latest_artwork_cache_key: tuple[int, int, int, float] | None = None
        self._achievement_artwork_identity = ""
        self._achievement_latest_artwork_identity = ""
        self._pending_achievement_manual_refresh = False
        self._deferred_achievement_presentation = None
        self._content_opacity = 1.0
        self._content_transition_key: object | None = None
        self._content_transition_animation_id: str | None = None
        self._content_transition_generation = 0
        self._pending_content_transition: tuple[object, Callable[[], None]] | None = None
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
        if definition.widget_id == "achievement_pulse" and build_default_runtime:
            from widgets.steam_achievement_runtime import (
                AchievementPulseRuntimeService,
            )

            self.set_achievement_runtime_service(
                AchievementPulseRuntimeService(
                    runtime_generation=getattr(self, "_runtime_generation", None)
                ),
                owns_service=True,
            )

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
            artwork_size=self._achievement_square_artwork_size,
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

    def content_opacity(self) -> float:
        """Return painter-owned payload opacity for card-specific renderers."""

        return max(0.0, min(1.0, float(self._content_opacity)))

    def apply_content_transition(
        self,
        transition_key: object,
        commit: Callable[[], None],
        *,
        animate: bool = True,
    ) -> None:
        """Fade changing card payloads out, commit once hidden, then fade in."""

        if not callable(commit):
            raise TypeError("Steam content transition commit must be callable")
        if transition_key == self._content_transition_key:
            commit()
            self.update()
            return
        should_animate = bool(
            animate
            and getattr(self, "_has_displayed_valid_data", False)
            and getattr(self, "_has_faded_in", False)
            and self.isVisible()
        )
        if not should_animate:
            self._cancel_content_transition()
            commit()
            self._content_transition_key = transition_key
            self._content_opacity = 1.0
            self.update()
            return

        self._pending_content_transition = (transition_key, commit)
        if self._content_transition_animation_id is None:
            self._start_content_fade_out()

    def _start_content_fade_out(self) -> None:
        from core.animation.animator import AnimationManager
        from core.animation.types import EasingCurve

        self._content_transition_generation += 1
        generation = self._content_transition_generation
        start_opacity = self.content_opacity()

        def _on_tick(progress: float) -> None:
            if generation != self._content_transition_generation:
                return
            quantized = round(max(0.0, min(1.0, float(progress))) * 7.0) / 7.0
            next_opacity = start_opacity * (1.0 - quantized)
            if abs(next_opacity - self._content_opacity) < 0.001:
                return
            self._content_opacity = next_opacity
            self.update()

        def _on_complete() -> None:
            if generation != self._content_transition_generation:
                return
            self._content_transition_animation_id = None
            pending = self._pending_content_transition
            self._pending_content_transition = None
            if pending is None:
                self._content_opacity = 1.0
                self.update()
                return
            transition_key, commit = pending
            try:
                commit()
                self._content_transition_key = transition_key
            except Exception:
                logger.warning("[STEAM] Content transition commit failed", exc_info=True)
                self._content_opacity = 1.0
                self.update()
                return
            self._content_opacity = 0.0
            self._start_content_fade_in()

        try:
            manager = AnimationManager.get_or_create_app_shared()
            self._content_transition_animation_id = manager.animate_custom(
                duration=0.28,
                update_callback=_on_tick,
                on_complete=_on_complete,
                easing=EasingCurve.CUBIC_IN_OUT,
            )
        except Exception:
            logger.debug("[STEAM] Content fade-out unavailable; committing immediately", exc_info=True)
            self._content_transition_animation_id = None
            pending = self._pending_content_transition
            self._pending_content_transition = None
            if pending is not None:
                transition_key, commit = pending
                commit()
                self._content_transition_key = transition_key
            self._content_opacity = 1.0
            self.update()

    def _start_content_fade_in(self) -> None:
        from core.animation.animator import AnimationManager
        from core.animation.types import EasingCurve

        generation = self._content_transition_generation

        def _on_tick(progress: float) -> None:
            if generation != self._content_transition_generation:
                return
            next_opacity = round(max(0.0, min(1.0, float(progress))) * 10.0) / 10.0
            if abs(next_opacity - self._content_opacity) < 0.001:
                return
            self._content_opacity = next_opacity
            self.update()

        def _on_complete() -> None:
            if generation != self._content_transition_generation:
                return
            self._content_transition_animation_id = None
            self._content_opacity = 1.0
            self.update()
            if self._pending_content_transition is not None:
                self._start_content_fade_out()

        try:
            manager = AnimationManager.get_or_create_app_shared()
            self._content_transition_animation_id = manager.animate_custom(
                duration=0.42,
                update_callback=_on_tick,
                on_complete=_on_complete,
                easing=EasingCurve.CUBIC_IN_OUT,
            )
        except Exception:
            logger.debug("[STEAM] Content fade-in unavailable; revealing immediately", exc_info=True)
            self._content_transition_animation_id = None
            self._content_opacity = 1.0
            self.update()

    def _cancel_content_transition(self) -> None:
        animation_id = self._content_transition_animation_id
        self._content_transition_generation += 1
        self._content_transition_animation_id = None
        self._pending_content_transition = None
        self._content_opacity = 1.0
        if not animation_id:
            return
        try:
            from core.animation.animator import AnimationManager

            manager = AnimationManager.get_app_shared()
            if manager is not None:
                manager.cancel_animation(animation_id)
        except Exception:
            logger.debug("[STEAM] Could not cancel content transition", exc_info=True)

    def _deactivate_impl(self) -> None:
        self._reset_deferred_achievement_state()
        service = self._achievement_runtime_service
        if service is not None and service.is_running():
            service.stop()
        self._cancel_content_transition()

    def _cleanup_impl(self) -> None:
        self._reset_deferred_achievement_state()
        service = self._achievement_runtime_service
        if service is not None and service.is_running():
            service.stop()
        self._release_achievement_runtime_service()
        self._cancel_content_transition()

    def set_achievement_selection(self, selection: AchievementPulseSelection) -> None:
        """Set persisted non-secret app selection before an activation refresh."""
        self._achievement_selection = selection
        self._sync_achievement_runtime_config()

    def set_achievement_field_visibility(self, visibility: Mapping[str, bool]) -> None:
        """Apply persisted field preferences to later cache-derived card models."""
        self._achievement_field_visibility = {str(key): bool(value) for key, value in visibility.items()}
        self._sync_achievement_runtime_config()

    # ------------------------------------------------------------------
    # Achievement runtime/model owner bridge
    # ------------------------------------------------------------------
    def _build_achievement_runtime_config(self):
        from widgets.steam_achievement_preparation import (
            AchievementPulseRuntimeConfig,
        )

        return AchievementPulseRuntimeConfig(
            selection=self._achievement_selection,
            field_visibility=dict(self._achievement_field_visibility),
            latest_unlock_count=self._achievement_latest_unlock_count,
            show_latest_artwork=self._achievement_show_latest_artwork,
            show_artwork=self._achievement_show_artwork,
            artwork_shape=self._achievement_artwork_shape,
            refresh_minutes=self._refresh_minutes,
            show_connection_info_icon=self._achievement_show_connection_info_icon,
        )

    def _sync_achievement_runtime_config(self) -> None:
        service = self._achievement_runtime_service
        if service is not None:
            service.configure(self._build_achievement_runtime_config())

    def set_achievement_runtime_service(
        self,
        service: Optional[Any],
        *,
        owns_service: bool = False,
    ) -> None:
        """Attach the presentation-neutral Achievement Pulse runtime owner."""

        previous = self._achievement_runtime_service
        previous_owned = self._owns_achievement_runtime_service
        if previous is service:
            owns_service = previous_owned or owns_service
        if previous is not None and previous is not service:
            if previous_owned:
                previous.retire()
            else:
                previous.detach_consumer(self)

        self._achievement_runtime_service = service
        self._owns_achievement_runtime_service = bool(
            service is not None and owns_service
        )
        if service is None:
            return
        try:
            service.configure(self._build_achievement_runtime_config())
            thread_manager = getattr(self, "_thread_manager", None)
            if thread_manager is not None:
                service.set_thread_manager(thread_manager)
            service.attach_consumer(self)
        except Exception:
            self._achievement_runtime_service = None
            self._owns_achievement_runtime_service = False
            try:
                service.detach_consumer(self)
            except Exception:
                pass
            if owns_service:
                service.retire()
            raise

    def _release_achievement_runtime_service(self) -> None:
        service = self._achievement_runtime_service
        owns_service = self._owns_achievement_runtime_service
        self._achievement_runtime_service = None
        self._owns_achievement_runtime_service = False
        if service is None:
            return
        if owns_service:
            service.retire()
        else:
            service.detach_consumer(self)

    def set_thread_manager(self, manager) -> None:
        super().set_thread_manager(manager)
        service = self._achievement_runtime_service
        if service is not None:
            service.set_thread_manager(manager)

    def is_achievement_consumer_alive(self) -> bool:
        return bool(Shiboken.isValid(self))

    def on_achievement_presentation(
        self,
        presentation: Any,
        *,
        animate: bool,
    ) -> None:
        self._apply_achievement_presentation(presentation, animate=animate)

    def request_achievement_fade(self) -> None:
        self._request_coordinated_fade()

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
            service = self._achievement_runtime_service
            if service is None:
                raise RuntimeError("Achievement Pulse runtime service is not attached")
            if not self._ensure_thread_manager("Achievement Pulse activation"):
                raise RuntimeError("ThreadManager is not configured")
            if not service.start(start_fade_after_load=True):
                raise RuntimeError("Achievement Pulse runtime service failed to start")
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
        service = self._achievement_runtime_service
        if service is not None:
            service.on_presentation_fade_complete()

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
        service = self._achievement_runtime_service
        return bool(service is not None and service.request_manual_refresh())

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
        service = self._achievement_runtime_service
        if service is not None:
            service.request_manual_refresh()

    def _reset_deferred_achievement_state(self) -> None:
        self._pending_achievement_manual_refresh = False
        self._deferred_achievement_presentation = None

    def _apply_achievement_presentation(
        self,
        presentation: Any,
        *,
        animate: bool,
    ) -> None:
        from widgets.service_widget_runtime import defer_value_if_transition

        if defer_value_if_transition(
            self,
            attr_name="_deferred_achievement_presentation",
            value=(presentation, animate),
            clear_attrs=(),
            schedule_callback=self._schedule_deferred_achievement_apply,
            logger=logger,
            log_message="[STEAM] Deferred Achievement Pulse presentation during parent transition",
        ):
            return
        self._commit_achievement_presentation(presentation, animate=animate)

    def _schedule_deferred_achievement_apply(self) -> None:
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(250, self._apply_deferred_achievement_presentation)

    def _apply_deferred_achievement_presentation(self) -> None:
        from widgets.service_widget_runtime import parent_transition_running

        deferred = self._deferred_achievement_presentation
        if deferred is None:
            return
        if parent_transition_running(self):
            self._schedule_deferred_achievement_apply()
            return
        self._deferred_achievement_presentation = None
        presentation, animate = deferred
        self._commit_achievement_presentation(
            presentation,
            animate=bool(animate),
        )

    def _commit_achievement_presentation(
        self,
        presentation: Any,
        *,
        animate: bool,
    ) -> None:
        # Achievement historically swaps accepted model/artwork without its own
        # content fade. Parent-transition deferral above preserves that behavior;
        # ``animate`` is retained for the future presenter contract.
        _ = animate
        changed = False
        model = presentation.model
        if model.content_fingerprint() != self._view_model.content_fingerprint():
            self.set_view_model(model)
            changed = True

        artwork_identity = str(presentation.artwork_identity or "")
        if artwork_identity != self._achievement_artwork_identity:
            self._achievement_artwork_identity = artwork_identity
            self._achievement_artwork = QImage(presentation.artwork)
            self._achievement_scaled_artwork_cache = QImage()
            self._achievement_scaled_artwork_cache_key = None
            changed = True

        latest_identity = str(presentation.latest_artwork_identity or "")
        if latest_identity != self._achievement_latest_artwork_identity:
            self._achievement_latest_artwork_identity = latest_identity
            self._achievement_latest_artwork = QImage(presentation.latest_artwork)
            self._achievement_scaled_latest_artwork_cache = QImage()
            self._achievement_scaled_latest_artwork_cache_key = None
            changed = True

        self._has_displayed_valid_data = True
        if changed:
            self.update()

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
