"""Dev-gated mock Steam card overlays.

These cards intentionally avoid provider, cache, credential, and timer work so
the Steam family can prove descriptor, factory, settings, Custom-layout, and
shared visual contracts before production data is wired.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor

from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.steam_components import (
    STEAM_CARD_AUTHORED_SIZE,
    SteamCardLayout,
    SteamCardViewModel,
    build_mock_steam_view_model,
    render_steam_card,
)


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

    def __init__(
        self,
        parent=None,
        *,
        definition: SteamCardDefinition,
        position: OverlayPosition = OverlayPosition.TOP_RIGHT,
    ) -> None:
        super().__init__(parent=parent, position=position, overlay_name=definition.widget_id)
        self.definition = definition
        self._view_model: SteamCardViewModel = build_mock_steam_view_model(definition.widget_id)
        self._last_layout: SteamCardLayout | None = None
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText("")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setWordWrap(False)
        self.setMinimumSize(QSize(int(STEAM_CARD_AUTHORED_SIZE.width()), int(STEAM_CARD_AUTHORED_SIZE.height())))
        self._apply_base_styling()
        self._update_content()

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
            )
        finally:
            if painter is not None:
                painter.end()
