"""Dev-gated mock Steam card overlays.

These cards intentionally avoid provider, cache, credential, and timer work so
the Steam family can prove descriptor, factory, settings, Custom-layout, and
shared visual contracts before production data is wired.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from widgets.shadow_utils import ShadowFadeProfile

from core.logging.logger import get_logger
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.steam_components import (
    STEAM_CARD_AUTHORED_SIZE,
    SteamCardLayout,
    SteamCardViewModel,
    build_mock_steam_view_model,
    build_steam_connect_required_view_model,
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
    """Framed mock card used to validate Steam widget-family plumbing."""

    settings_requested = Signal(str)

    def __init__(
        self,
        parent=None,
        *,
        definition: SteamCardDefinition,
        position: OverlayPosition = OverlayPosition.TOP_RIGHT,
        initial_view_model: SteamCardViewModel | None = None,
    ) -> None:
        super().__init__(parent=parent, position=position, overlay_name=definition.widget_id)
        self.definition = definition
        self._defer_visibility_for_fade_sync = True
        self._view_model: SteamCardViewModel = initial_view_model or build_mock_steam_view_model(definition.widget_id)
        self._last_layout: SteamCardLayout | None = None
        self._steam_logo = self._load_steam_logo()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText("")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setWordWrap(False)
        self.setMinimumSize(QSize(int(STEAM_CARD_AUTHORED_SIZE.width()), int(STEAM_CARD_AUTHORED_SIZE.height())))
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
        self.setToolTip(f"Steam mock card: {self.definition.title}")

    def _calculate_content_size(self) -> QSize:
        return QSize(max(int(STEAM_CARD_AUTHORED_SIZE.width()), self.minimumWidth()), max(int(STEAM_CARD_AUTHORED_SIZE.height()), self.minimumHeight()))

    def set_text_color(self, color: QColor) -> None:
        super().set_text_color(color)
        self.update()

    def set_view_model(self, view_model: SteamCardViewModel) -> None:
        """Apply an already-resolved view model without provider/cache work."""

        self._view_model = view_model
        self.update()

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

    def _activate_impl(self) -> None:
        """Activate a provider-inert card through the normal coordinated fade path."""

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
