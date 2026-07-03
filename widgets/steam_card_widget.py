"""Dev-gated mock Steam card overlays.

These cards are Phase 3 scaffolding only. They intentionally avoid provider,
cache, credential, and timer work so the Steam family can prove descriptor,
factory, settings, and Custom-layout plumbing before production data is wired.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor

from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition


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
    """Simple framed card used to validate Steam widget-family plumbing."""

    def __init__(
        self,
        parent=None,
        *,
        definition: SteamCardDefinition,
        position: OverlayPosition = OverlayPosition.TOP_RIGHT,
    ) -> None:
        super().__init__(parent=parent, position=position, overlay_name=definition.widget_id)
        self.definition = definition
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setWordWrap(True)
        self.setMinimumSize(QSize(360, 150))
        self._apply_base_styling()
        self._update_content()

    def _update_content(self) -> None:
        self.setText(
            f"STEAM | {self.definition.title}\n"
            f"{self.definition.subtitle}\n"
            "Waiting for production data wiring."
        )

    def _calculate_content_size(self) -> QSize:
        return QSize(max(360, self.minimumWidth()), max(150, self.minimumHeight()))

    def set_text_color(self, color: QColor) -> None:
        super().set_text_color(color)
        self.update()
