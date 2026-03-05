"""Self-contained overlay that paints the StyledComboBox knob crisply at runtime."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from PySide6.QtCore import QObject, QEvent, QRect, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger

KnobState = Literal["normal", "hover", "pressed", "disabled"]

_logger = get_logger(__name__)


class ComboKnobOverlay(QWidget):
    """Renders the reference knob by cropping the original SVG."""

    _DESIGN_SIZE = QSizeF(355.43, 71.02)
    _KNOB_SLICE = QRectF(312.0, 14.0, 30.0, 38.0)
    _SVG_DIR = Path(__file__).resolve().parents[2] / "images" / "svg"
    _SVG_FILES = {
        "normal": "ComboboxNOHover.svg",
        "hover": "ComboboxHOVER.svg",
    }
    _renderers: dict[str, QSvgRenderer | None] = {}

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._state: KnobState = "normal"
        self._paint_rect = QRectF()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._ensure_renderers()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_state(self, state: KnobState) -> None:
        if state == self._state:
            return
        self._state = state
        self.update()

    def set_paint_rect(self, rect: QRectF) -> None:
        if rect == self._paint_rect:
            return
        self._paint_rect = rect
        self.update()

    # ------------------------------------------------------------------
    # QWidget overrides
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        if self._paint_rect.isEmpty():
            return

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform,
            True,
        )

        renderer_key = "hover" if self._state in {"hover", "pressed"} else "normal"
        renderer = self._renderers.get(renderer_key)

        if renderer is None:
            self._paint_fallback(painter)
            return

        if self._state == "disabled":
            painter.setOpacity(0.45)
        renderer.render(painter, self._paint_rect)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @classmethod
    def _ensure_renderers(cls) -> None:
        if cls._renderers:
            return
        for state, filename in cls._SVG_FILES.items():
            path = cls._SVG_DIR / filename
            if not path.exists():
                _logger.error("Knob SVG missing: %s", path)
                cls._renderers[state] = None
                continue
            renderer = QSvgRenderer(str(path))
            renderer.setViewBox(cls._KNOB_SLICE)
            cls._renderers[state] = renderer

    def _paint_fallback(self, painter: QPainter) -> None:
        rect = self._paint_rect
        if rect.isEmpty():
            return
        radius = rect.height() * 0.5
        shadow_rect = rect.translated(rect.width() * 0.05, rect.height() * 0.08)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 210))
        painter.drawRoundedRect(shadow_rect, radius, radius)
        painter.setBrush(QColor("#7c7c7c"))
        painter.drawRoundedRect(rect, radius, radius)
        highlight = rect.adjusted(1.0, 1.0, -1.0, -2.0)
        gradient = QLinearGradient(highlight.topLeft(), highlight.bottomLeft())
        gradient.setColorAt(0.0, QColor(255, 255, 255, 50))
        gradient.setColorAt(0.6, QColor(120, 120, 120, 60))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 110))
        painter.setBrush(gradient)
        painter.drawRoundedRect(highlight, radius * 0.85, radius * 0.85)


class ComboKnobController(QObject):
    """Attaches the overlay to any combobox-like widget and keeps it in sync."""

    def __init__(self, host: QWidget) -> None:
        super().__init__(host)
        self._host = host
        self._overlay = ComboKnobOverlay(host)
        self._overlay.show()
        self._hovered = False
        self._pressed = False
        host.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        host.installEventFilter(self)
        self._position_overlay()
        self._update_state()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def eventFilter(self, watched, event):  # type: ignore[override]
        if watched is not self._host:
            return super().eventFilter(watched, event)

        etype = event.type()
        if etype == QEvent.Type.Resize:
            self._position_overlay()
        elif etype == QEvent.Type.HoverEnter:
            self._hovered = True
            self._update_state()
        elif etype == QEvent.Type.HoverLeave:
            self._hovered = False
            self._update_state()
        elif etype == QEvent.Type.FocusIn:
            self._hovered = True
            self._update_state()
        elif etype == QEvent.Type.FocusOut:
            self._hovered = False
            self._pressed = False
            self._update_state()
        elif etype == QEvent.Type.EnabledChange:
            self._pressed = False
            self._update_state()
        elif etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._update_state()
        elif etype == QEvent.Type.MouseButtonRelease:
            self._pressed = False
            self._update_state()
        elif etype == QEvent.Type.Hide:
            self._overlay.hide()
        elif etype == QEvent.Type.Show:
            self._overlay.show()
            self._position_overlay()
            self._update_state()

        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _position_overlay(self) -> None:
        if not self._host.isVisible():
            return

        host_rect: QRect = self._host.rect()
        if host_rect.height() <= 0:
            return

        design = ComboKnobOverlay._DESIGN_SIZE
        slice_rect = ComboKnobOverlay._KNOB_SLICE
        scale = host_rect.height() / design.height()

        knob_width = slice_rect.width() * scale
        knob_height = slice_rect.height() * scale
        right_margin = (design.width() - (slice_rect.left() + slice_rect.width())) * scale
        top_margin = slice_rect.top() * scale

        x = host_rect.width() - knob_width - right_margin
        y = top_margin

        if host_rect.width() <= knob_width:
            x = host_rect.width() - knob_width
        x = max(0.0, x)
        y = max(0.0, min(y, host_rect.height() - knob_height))

        geom = QRectF(x, y, knob_width, knob_height)
        self._overlay.setGeometry(
            int(round(geom.x())),
            int(round(geom.y())),
            max(1, int(round(geom.width()))),
            max(1, int(round(geom.height()))),
        )
        self._overlay.set_paint_rect(QRectF(0.0, 0.0, geom.width(), geom.height()))
        self._overlay.raise_()

    def _update_state(self) -> None:
        if not self._host.isEnabled():
            state: KnobState = "disabled"
        elif self._pressed:
            state = "pressed"
        elif self._hovered:
            state = "hover"
        else:
            state = "normal"
        self._overlay.set_state(state)


__all__ = ["ComboKnobController"]
