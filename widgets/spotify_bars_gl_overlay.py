from __future__ import annotations

from typing import List, Sequence

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import get_logger
from rendering.gl_format import apply_widget_surface_format
from OpenGL import GL as gl


logger = get_logger(__name__)


class SpotifyBarsGLOverlay(QOpenGLWidget):
    """Small GL surface that renders the Spotify bar field.

    This overlay is parented to ``DisplayWidget`` and positioned so that it
    exactly covers the Spotify visualiser card. The card itself (background,
    border, fade, shadow) continues to be drawn by ``SpotifyVisualizerWidget``;
    this class is responsible only for the bar geometry.
    """

    def __init__(self, parent=None) -> None:  # type: ignore[override]
        super().__init__(parent)

        apply_widget_surface_format(self, reason="spotify_bars_overlay")

        try:
            self.setAutoFillBackground(False)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        except Exception:
            pass
        try:
            self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        except Exception:
            pass

        self._enabled: bool = False
        self._bars: List[float] = []
        self._bar_count: int = 0
        self._segments: int = 0
        self._fill_color: QColor = QColor(200, 200, 200, 230)
        self._border_color: QColor = QColor(255, 255, 255, 255)
        self._fade: float = 0.0
        self._playing: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_state(
        self,
        rect: QRect,
        bars: Sequence[float],
        bar_count: int,
        segments: int,
        fill_color: QColor,
        border_color: QColor,
        fade: float,
        playing: bool,
        visible: bool,
    ) -> None:
        """Update overlay bar state and geometry.

        ``rect`` is specified in the parent ``DisplayWidget`` coordinate space
        and should usually be the geometry of the associated
        ``SpotifyVisualizerWidget``.
        """

        if not visible:
            self._enabled = False
            try:
                self.hide()
            except Exception:
                pass
            return

        try:
            count = int(bar_count)
        except Exception:
            count = 0
        try:
            segs = int(segments)
        except Exception:
            segs = 0

        if count <= 0 or segs <= 0:
            self._enabled = False
            try:
                self.hide()
            except Exception:
                pass
            return

        try:
            bars_seq = list(bars)
        except Exception:
            self._enabled = False
            try:
                self.hide()
            except Exception:
                pass
            return

        if not bars_seq:
            self._enabled = False
            try:
                self.hide()
            except Exception:
                pass
            return

        if len(bars_seq) > count:
            bars_seq = bars_seq[:count]
        elif len(bars_seq) < count:
            bars_seq = bars_seq + [0.0] * (count - len(bars_seq))

        clamped: List[float] = []
        for v in bars_seq:
            try:
                f = float(v)
            except Exception:
                f = 0.0
            if f < 0.0:
                f = 0.0
            if f > 1.0:
                f = 1.0
            clamped.append(f)

        if not clamped:
            self._enabled = False
            try:
                self.hide()
            except Exception:
                pass
            return

        self._enabled = True
        self._bars = clamped
        self._bar_count = len(clamped)
        self._segments = max(1, segs)
        self._fill_color = QColor(fill_color)
        self._border_color = QColor(border_color)
        try:
            self._fade = max(0.0, min(1.0, float(fade)))
        except Exception:
            self._fade = 1.0
        self._playing = bool(playing)

        try:
            self.setGeometry(rect)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set overlay geometry", exc_info=True)

        try:
            if self._enabled:
                self.show()
                self.raise_()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to show/raise overlay", exc_info=True)

        self.update()

    # ------------------------------------------------------------------
    # QOpenGLWidget hooks
    # ------------------------------------------------------------------

    def paintGL(self) -> None:  # type: ignore[override]
        if not self._enabled:
            return

        try:
            fade = float(self._fade)
        except Exception:
            fade = 0.0
        if fade <= 0.0:
            return

        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Start from a clean transparent buffer each frame so that decaying
        # bars do not leave ghost outlines or coloured speckles behind.
        try:
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        except Exception:
            pass

        count = self._bar_count
        segments = self._segments
        if count <= 0 or segments <= 0:
            return

        margin_x = 8
        margin_y = 6
        inner = rect.adjusted(margin_x, margin_y, -margin_x, -margin_y)
        if inner.width() <= 0 or inner.height() <= 0:
            return

        gap = 2
        total_gap = gap * (count - 1) if count > 1 else 0
        bar_width = int((inner.width() - total_gap) / max(1, count))
        if bar_width <= 0:
            return

        # Match the QWidget visualiser: small rightward offset so bars visually
        # line up with the card frame.
        x0 = inner.left() + 5
        bar_x = [x0 + i * (bar_width + gap) for i in range(count)]

        seg_gap = 1
        total_seg_gap = seg_gap * max(0, segments - 1)
        seg_height = int((inner.height() - total_seg_gap) / max(1, segments))
        if seg_height <= 0:
            return
        base_bottom = inner.bottom()
        seg_y = [base_bottom - s * (seg_height + seg_gap) - seg_height + 1 for s in range(segments)]

        fill = QColor(self._fill_color)
        border = QColor(self._border_color)

        try:
            fade_clamped = max(0.0, min(1.0, fade))
            fill.setAlpha(int(fill.alpha() * fade_clamped))
            border.setAlpha(int(border.alpha() * fade_clamped))
        except Exception:
            pass

        painter = QPainter(self)
        try:
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            except Exception:
                pass

            painter.setBrush(fill)
            painter.setPen(border)

            max_segments = min(segments, len(seg_y))
            draw_count = min(count, len(bar_x), len(self._bars))

            for i in range(draw_count):
                x = bar_x[i]
                try:
                    value = float(self._bars[i])
                except Exception:
                    value = 0.0
                if value <= 0.0:
                    continue
                if value > 1.0:
                    value = 1.0
                active = int(round(value * segments))
                if active <= 0:
                    if self._playing and value > 0.0:
                        active = 1
                    else:
                        continue
                if active > max_segments:
                    active = max_segments
                for s in range(active):
                    y = seg_y[s]
                    painter.drawRect(QRect(x, y, bar_width, seg_height))
        finally:
            painter.end()
