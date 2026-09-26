"""Settings action buttons whose rounded border is painted as one continuous path.

Qt style sheets draw a rounded border as separate edge and corner segments.
With a translucent border colour (most Settings themes) the overlaps are
composited twice, leaving bright or dark seams where the straight edges meet
the corners. This button keeps the stylesheet for its surface, text, padding and
metrics, makes the stylesheet border transparent, and strokes the border itself
with one antialiased ``QPainterPath``. That is seam-free at any opacity or width.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton

from ui.settings_theme_runtime import get_active_settings_theme
from ui.tabs import shared_styles

# role -> (shared style, radius, border tokens: normal, hover, pressed, disabled)
_ROLES = {
    # 15 px, not the style's 16: a stylesheet radius above half the height (30 px
    # buttons) renders its own corner artefacts.
    "primary": ("GHOST_ACTION_BUTTON_STYLE", 15.0, (
        "control.ghost_action.border", "control.ghost_action.hover_border",
        "control.ghost_action.hover_border", "control.ghost_action.disabled_border")),
    "secondary": ("COMPACT_ACTION_BUTTON_STYLE", 7.0, (
        "control.button.border", "control.button.border",
        "control.button.pressed_border", "control.ghost_action.disabled_border")),
}

BORDER_WIDTH = 2.0


class OutlinedButton(QPushButton):
    """A shared-style Settings button with a seam-free painted border."""

    def __init__(self, text: str = "", parent=None, *, role: str = "primary") -> None:
        super().__init__(text, parent)
        if role not in _ROLES:
            raise ValueError(f"unknown OutlinedButton role: {role!r}")
        self._role = role
        style, _radius, _tokens = _ROLES[role]
        # The stylesheet keeps an equally wide *transparent* border so padding,
        # size hints and the surface fill are unchanged; paintEvent strokes it.
        shared_styles.bind_shared_styles(
            self, style,
            trailing_style=(
                f"QPushButton {{ border: {BORDER_WIDTH}px solid transparent;"
                f" border-radius: {_ROLES[role][1]}px; }}"
                f" QPushButton:hover {{ border-color: transparent; }}"
                f" QPushButton:pressed {{ border-color: transparent; }}"
                f" QPushButton:disabled {{ border-color: transparent; }}"
            ),
        )
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def _border_color(self) -> QColor:
        normal, hover, pressed, disabled = _ROLES[self._role][2]
        if not self.isEnabled():
            token = disabled
        elif self.isDown():
            token = pressed
        elif self.underMouse():
            token = hover
        else:
            token = normal
        return QColor(*get_active_settings_theme().color(token).as_tuple())

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        radius = _ROLES[self._role][1]
        inset = BORDER_WIDTH / 2.0
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        radius = max(0.0, min(radius - inset, rect.height() / 2.0, rect.width() / 2.0))
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._border_color(), BORDER_WIDTH))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
