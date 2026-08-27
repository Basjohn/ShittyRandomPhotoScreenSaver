"""Shared QWidget shell for Abandonment Issues and dev-gated Steam scaffolds."""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from widgets.shadow_utils import ShadowFadeProfile

from core.logging.logger import get_logger
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.steam_card_models import (
    SteamCardViewModel,
    build_mock_steam_view_model,
    build_steam_connect_required_view_model,
)
from widgets.steam_components import (
    STEAM_CARD_AUTHORED_SIZE,
    SteamCardLayout,
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
    """Temporary QWidget shell retained only for F8 and dev scaffolds."""

    settings_requested = Signal(str)

    def __init__(
        self,
        parent=None,
        *,
        definition: SteamCardDefinition,
        position: OverlayPosition = OverlayPosition.TOP_RIGHT,
        initial_view_model: SteamCardViewModel | None = None,
        refresh_minutes: int = 10,
    ) -> None:
        super().__init__(parent=parent, position=position, overlay_name=definition.widget_id)
        self.definition = definition
        self._refresh_minutes = max(5, int(refresh_minutes))
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

    def _authored_content_size(self):
        return STEAM_CARD_AUTHORED_SIZE

    def set_text_color(self, color: QColor) -> None:
        super().set_text_color(color)
        self.update()

    def set_view_model(self, view_model: SteamCardViewModel) -> None:
        """Apply an already-resolved view model without provider/cache work."""

        self._view_model = view_model
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
        self._cancel_content_transition()

    def _cleanup_impl(self) -> None:
        self._cancel_content_transition()

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
        """Dev scaffolds have no semantic double-click action."""

        return False

    def _activate_impl(self) -> None:
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
        super().on_fade_complete()

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
            target = QRectF(
                0.0,
                0.0,
                max(1.0, float(self.width())),
                max(1.0, float(self.height())),
            )
            self._last_layout = render_steam_card(
                painter,
                self._view_model,
                target,
                font_family=self.get_font_family(),
                font_size=self.get_font_size(),
                text_color=self.get_text_color(),
                dpr=max(1.0, float(self.devicePixelRatioF())),
                logo_pixmap=self._steam_logo,
            )
        finally:
            if painter is not None:
                painter.end()
