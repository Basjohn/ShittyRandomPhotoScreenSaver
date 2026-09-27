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

_BUTTON_BORDERS = ("control.button.border", "control.button.border",
                   "control.button.pressed_border", "control.ghost_action.disabled_border")

# role -> (shared style, radius, stroke width, stylesheet border width, border tokens:
# normal, hover, pressed, disabled). Every role uses the ordinary Settings button
# semantics; no button is painted as a permanently filled emphasis pill (a stuck
# hover in themes that fill it). ``None`` keeps the Settings root ``QPushButton``
# rule for surface, text, font and padding. The stylesheet border (transparent)
# keeps each look's original width so its size hint is unchanged; the painted
# stroke may be a little wider.
_ROLES = {
    "secondary": ("COMPACT_ACTION_BUTTON_STYLE", 7.0, 2.0, 2.0, _BUTTON_BORDERS),  # dense rows
    "standard": (None, 8.0, 1.5, 1.25, _BUTTON_BORDERS),  # the root Settings button
    "source": ("SOURCE_ACTION_BUTTON_STYLE", 8.0, 1.5, 1.0, _BUTTON_BORDERS),  # Sources actions
}

BORDER_WIDTH = 2.0  # the compact role's stroke


class OutlinedButton(QPushButton):
    """A shared-style Settings button with a seam-free painted border."""

    def __init__(self, text: str = "", parent=None, *, role: str = "secondary") -> None:
        super().__init__(text, parent)
        if role not in _ROLES:
            raise ValueError(f"unknown OutlinedButton role: {role!r}")
        self._role = role
        style, radius, _stroke, width, _tokens = _ROLES[role]
        # The stylesheet keeps an equally wide *transparent* border in every state
        # so padding, size hints and the surface fill are unchanged; paintEvent
        # strokes it. A widget's own sheet outranks the root sheet's hover border.
        transparent = f"border: {width}px solid transparent;"
        trailing = (
            f"QPushButton {{ {transparent} border-radius: {radius}px; }}"
            f" QPushButton:hover {{ {transparent} }}"
            f" QPushButton:pressed {{ {transparent} }}"
            f" QPushButton:disabled {{ {transparent} }}"
        )
        if style is None:
            self.setStyleSheet(trailing)  # colours come from the live root sheet
        else:
            shared_styles.bind_shared_styles(self, style, trailing_style=trailing)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def _border_color(self) -> QColor:
        normal, hover, pressed, disabled = _ROLES[self._role][4]
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
        _style, radius, width, _css_width, _tokens = _ROLES[self._role]
        inset = width / 2.0
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        radius = max(0.0, min(radius - inset, rect.height() / 2.0, rect.width() / 2.0))
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._border_color(), width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
