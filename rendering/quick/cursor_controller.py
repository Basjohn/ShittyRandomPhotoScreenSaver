"""Native cursor owner for the Qt Quick runtime.

Cursor motion must never be represented by a moving retained QML item.  This
owner renders the configured Halo shape into a native ``QCursor`` once, then
lets Qt/the window system move it independently of the composited wallpaper
scene.  The only per-motion Python work is a monotonic timestamp used by the
existing two-second inactivity contract; the timer is *not* restarted at mouse
polling rate.
"""

from __future__ import annotations

import math
import time
from typing import Final

from PySide6.QtCore import QObject, QPointF, QTimer, Qt
from PySide6.QtGui import (
    QColor,
    QCursor,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtQuick import QQuickWindow

from .auxiliary import QuickAuxiliaryState


_CURSOR_SIZE: Final[int] = 38
_CURSOR_INACTIVITY_MS: Final[int] = 2000
_CURSOR_FADE_MS: Final[int] = 1200
_CURSOR_FADE_STEPS: Final[int] = 6
_CURSOR_FADE_STEP_MS: Final[int] = max(1, _CURSOR_FADE_MS // _CURSOR_FADE_STEPS)
_POINTER_REFERENCE_WIDTH: Final[float] = 106.3
_POINTER_REFERENCE_HEIGHT: Final[float] = 141.62
_POINTER_TIP_X: Final[float] = 5.0
_POINTER_TIP_Y: Final[float] = 3.42


class QuickCursorController(QObject):
    """Generation-scoped native cursor presentation for one Quick window."""

    def __init__(
        self,
        *,
        window: QQuickWindow,
        screen_index: int,
        runtime_generation: int | None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent if parent is not None else window)
        self._window = window
        self._screen_index = int(screen_index)
        self._runtime_generation = (
            None if runtime_generation is None else int(runtime_generation)
        )
        self._admission_open = True
        self._halo_enabled = False
        self._native_cursor_visible = False
        self._halo_shape = "cursor_light"
        self._motion_visible = False
        self._last_motion_ns = 0
        self._fade_step = 0
        self._last_cursor_signature: tuple[object, ...] | None = None
        self._cursor_cache: dict[tuple[str, float, int], QCursor] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timer)
        self._apply_cursor(force=True)

    @property
    def tracks_pointer_motion(self) -> bool:
        """Whether movement can affect the native Halo inactivity state."""

        return bool(self._admission_open and self._halo_enabled)

    def apply_auxiliary_state(self, state: QuickAuxiliaryState) -> bool:
        """Apply matching low-rate semantic cursor facts from auxiliary state."""

        if not isinstance(state, QuickAuxiliaryState):
            raise TypeError("Quick cursor auxiliary state requires QuickAuxiliaryState")
        if (
            state.screen_index != self._screen_index
            or state.runtime_generation != self._runtime_generation
        ):
            return False

        previous = (
            self._admission_open,
            self._halo_enabled,
            self._native_cursor_visible,
            self._halo_shape,
        )
        self._admission_open = bool(state.admission_open)
        self._halo_enabled = bool(state.halo_enabled and state.admission_open)
        self._native_cursor_visible = bool(
            state.native_cursor_visible and state.admission_open
        )
        self._halo_shape = str(state.halo_shape or "cursor_light").strip().lower()

        current = (
            self._admission_open,
            self._halo_enabled,
            self._native_cursor_visible,
            self._halo_shape,
        )
        if current == previous:
            return False

        if not self._halo_enabled:
            self._motion_visible = False
            self._last_motion_ns = 0
            self._fade_step = 0
            self._timer.stop()
        elif not previous[1]:
            # Event-driven admission may occur while the pointer is already
            # stationary over this display. Preserve the historical immediate
            # Halo appearance with one native position query at admission; this
            # is not a recurring poll and never touches the Quick scene.
            self._motion_visible = self._pointer_is_inside_window()
            self._last_motion_ns = time.monotonic_ns() if self._motion_visible else 0
            self._fade_step = 0
            self._timer.stop()
            if self._motion_visible:
                self._timer.start(_CURSOR_INACTIVITY_MS)

        self._apply_cursor(force=True)
        return True

    def note_pointer_motion(self, now_ns: int | None = None) -> bool:
        """Record Halo activity without restarting a timer at mouse poll rate."""

        if not self.tracks_pointer_motion:
            return False
        now = int(time.monotonic_ns() if now_ns is None else now_ns)
        self._last_motion_ns = now

        changed = False
        if not self._motion_visible or self._fade_step:
            self._motion_visible = True
            self._fade_step = 0
            self._apply_cursor(force=True)
            changed = True

        # One deadline timer is enough.  Continuous motion only updates the
        # timestamp; when the existing timer fires it computes the remaining
        # quiet time and re-arms once if needed.
        if not self._timer.isActive():
            self._timer.start(_CURSOR_INACTIVITY_MS)
        return changed

    def refresh_display_metrics(self) -> None:
        """Rebuild the native pixmap if display DPR changed."""

        self._last_cursor_signature = None
        self._apply_cursor(force=True)

    def close(self) -> bool:
        if not self._admission_open:
            return False
        self._admission_open = False
        self._halo_enabled = False
        self._native_cursor_visible = False
        self._motion_visible = False
        self._last_motion_ns = 0
        self._fade_step = 0
        self._timer.stop()
        self._cursor_cache.clear()
        self._apply_cursor(force=True)
        return True

    def describe(self) -> dict[str, object]:
        return {
            "screen_index": self._screen_index,
            "runtime_generation": self._runtime_generation,
            "admission_open": self._admission_open,
            "halo_enabled": self._halo_enabled,
            "native_cursor_visible": self._native_cursor_visible,
            "halo_shape": self._halo_shape,
            "motion_visible": self._motion_visible,
            "fade_step": self._fade_step,
            "inactivity_timer_active": self._timer.isActive(),
            "pointer_owner": "native_qcursor",
            "scene_position_binding": False,
        }

    def _on_timer(self) -> None:
        if not self.tracks_pointer_motion or not self._motion_visible:
            return

        now_ns = time.monotonic_ns()
        elapsed_ms = (
            float(now_ns - self._last_motion_ns) / 1_000_000.0
            if self._last_motion_ns > 0
            else float(_CURSOR_INACTIVITY_MS)
        )
        if elapsed_ms < _CURSOR_INACTIVITY_MS:
            remaining = max(1, int(math.ceil(_CURSOR_INACTIVITY_MS - elapsed_ms)))
            self._timer.start(remaining)
            return

        if self._fade_step < _CURSOR_FADE_STEPS:
            self._fade_step += 1
            self._apply_cursor(force=True)
            if self._fade_step < _CURSOR_FADE_STEPS:
                self._timer.start(_CURSOR_FADE_STEP_MS)
                return

        self._motion_visible = False
        self._fade_step = 0
        self._apply_cursor(force=True)

    def _apply_cursor(self, *, force: bool = False) -> None:
        if self._halo_enabled and self._motion_visible:
            alpha_step = min(_CURSOR_FADE_STEPS, max(0, self._fade_step))
            signature: tuple[object, ...] = (
                "halo",
                self._halo_shape,
                self._device_pixel_ratio(),
                alpha_step,
            )
            cursor = self._halo_cursor(self._halo_shape, alpha_step)
        elif self._native_cursor_visible:
            signature = ("arrow",)
            cursor = QCursor(Qt.CursorShape.ArrowCursor)
        else:
            signature = ("blank",)
            cursor = QCursor(Qt.CursorShape.BlankCursor)

        if not force and signature == self._last_cursor_signature:
            return
        self._last_cursor_signature = signature
        self._window.setCursor(cursor)

    def _halo_cursor(self, shape: str, fade_step: int) -> QCursor:
        dpr = self._device_pixel_ratio()
        key = (shape, dpr, int(fade_step))
        cached = self._cursor_cache.get(key)
        if cached is not None:
            return cached

        opacity = 1.0 - (float(fade_step) / float(_CURSOR_FADE_STEPS))
        opacity = max(0.0, min(1.0, opacity))
        pixmap, hotspot_x, hotspot_y = self._render_halo_pixmap(
            shape=shape,
            dpr=dpr,
            opacity=opacity,
        )
        cursor = QCursor(pixmap, hotspot_x, hotspot_y)
        self._cursor_cache[key] = cursor
        return cursor

    def _render_halo_pixmap(
        self,
        *,
        shape: str,
        dpr: float,
        opacity: float,
    ) -> tuple[QPixmap, int, int]:
        physical_size = max(1, int(round(_CURSOR_SIZE * dpr)))
        pixmap = QPixmap(physical_size, physical_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        pixmap.setDevicePixelRatio(dpr)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(opacity)
        try:
            hotspot = self._paint_shape(painter, shape)
        finally:
            painter.end()
        return pixmap, hotspot[0], hotspot[1]

    @staticmethod
    def _paint_shape(painter: QPainter, shape: str) -> tuple[int, int]:
        size = float(_CURSOR_SIZE)
        center = size / 2.0
        diameter = size - 8.0
        radius = diameter / 2.0
        normalized = str(shape or "cursor_light").strip().lower()

        if normalized in {"cursor_light", "cursor_dark"}:
            scale = min(
                diameter / _POINTER_REFERENCE_WIDTH,
                diameter / _POINTER_REFERENCE_HEIGHT,
            )
            pointer_width = _POINTER_REFERENCE_WIDTH * scale
            pointer_height = _POINTER_REFERENCE_HEIGHT * scale
            left = center - pointer_width / 2.0
            top = center - pointer_height / 2.0

            def project(points: tuple[tuple[float, float], ...]) -> QPolygonF:
                return QPolygonF(
                    [
                        QPointF(
                            left + (x / _POINTER_REFERENCE_WIDTH) * pointer_width,
                            top + (y / _POINTER_REFERENCE_HEIGHT) * pointer_height,
                        )
                        for x, y in points
                    ]
                )

            shadow = (
                (17.13, 8.38),
                (14.07, 137.38),
                (13.84, 141.59),
                (57.0, 94.22),
                (106.3, 93.0),
            )
            main = (
                (5.0, 3.42),
                (2.0, 132.45),
                (1.77, 136.66),
                (44.91, 89.26),
                (94.22, 88.08),
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 153))
            painter.drawPolygon(project(shadow))

            dark = normalized == "cursor_dark"
            outline = QColor("#fcfcfc") if dark else QColor("#000000")
            fill = QColor("#000000") if dark else QColor("#fcfcfc")
            pen = QPen(outline)
            pen.setWidthF(max(1.0, scale * 3.0))
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            painter.setPen(pen)
            painter.setBrush(fill)
            painter.drawPolygon(project(main))

            hotspot_x = int(
                round(left + (_POINTER_TIP_X / _POINTER_REFERENCE_WIDTH) * pointer_width)
            )
            hotspot_y = int(
                round(top + (_POINTER_TIP_Y / _POINTER_REFERENCE_HEIGHT) * pointer_height)
            )
            return hotspot_x, hotspot_y

        if normalized == "crosshair":
            gap = max(3.0, diameter / 8.0)
            half = diameter / 2.0
            segments = (
                (center - half, center, center - gap, center),
                (center + gap, center, center + half, center),
                (center, center - half, center, center - gap),
                (center, center + gap, center, center + half),
            )
            for offset, color in (
                (2.0, QColor(12, 14, 28, 161)),
                (0.0, QColor(246, 248, 255, 235)),
            ):
                pen = QPen(color)
                pen.setWidthF(3.0)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for x1, y1, x2, y2 in segments:
                    painter.drawLine(
                        QPointF(x1 + offset, y1 + offset),
                        QPointF(x2 + offset, y2 + offset),
                    )
            return int(round(center)), int(round(center))

        if normalized == "diamond":
            diamond = QPolygonF(
                [
                    QPointF(center, center - radius),
                    QPointF(center + radius, center),
                    QPointF(center, center + radius),
                    QPointF(center - radius, center),
                ]
            )
            shadow = QPolygonF(
                [QPointF(point.x() + 2.0, point.y() + 2.0) for point in diamond]
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            shadow_pen = QPen(QColor(12, 14, 28, 161))
            shadow_pen.setWidthF(3.0)
            painter.setPen(shadow_pen)
            painter.drawPolygon(shadow)
            main_pen = QPen(QColor(246, 248, 255, 235))
            main_pen.setWidthF(3.0)
            painter.setPen(main_pen)
            painter.drawPolygon(diamond)
            QuickCursorController._paint_center_dot(painter, center, center, 2.0)
            return int(round(center)), int(round(center))

        if normalized == "dot":
            QuickCursorController._paint_center_dot(
                painter,
                center,
                center,
                max(4.0, diameter / 6.0),
            )
            return int(round(center)), int(round(center))

        # circle / ring (and defensive unknown fallback) preserve the existing
        # luminous retained-Halo visual, now rendered once into a cursor pixmap.
        shadow_gradient = QRadialGradient(
            QPointF(center + 2.0, center + 2.0), radius
        )
        shadow_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        shadow_gradient.setColorAt(1.0, QColor(12, 14, 28, 161))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_gradient)
        painter.drawEllipse(QPointF(center, center), radius, radius)

        outer_pen = QPen(QColor(246, 248, 255, 235))
        outer_pen.setWidthF(3.0 if normalized == "ring" else 5.0)
        painter.setPen(outer_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(center, center), radius, radius)

        inner_pen = QPen(QColor("#ffffff"))
        inner_pen.setWidthF(3.5)
        painter.setPen(inner_pen)
        painter.drawEllipse(QPointF(center, center), radius, radius)
        if normalized != "ring":
            QuickCursorController._paint_center_dot(
                painter,
                center,
                center,
                max(2.0, diameter / 12.0),
            )
        return int(round(center)), int(round(center))

    @staticmethod
    def _paint_center_dot(
        painter: QPainter,
        center_x: float,
        center_y: float,
        dot_radius: float,
    ) -> None:
        gradient = QRadialGradient(QPointF(center_x, center_y), dot_radius)
        gradient.setColorAt(0.0, QColor(255, 255, 255, 240))
        gradient.setColorAt(1.0, QColor(130, 205, 255, 199))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(
            QPointF(center_x, center_y),
            dot_radius,
            dot_radius,
        )

    def _pointer_is_inside_window(self) -> bool:
        try:
            return bool(self._window.geometry().contains(QCursor.pos()))
        except (AttributeError, RuntimeError, TypeError):
            return False

    def _device_pixel_ratio(self) -> float:
        try:
            dpr = float(self._window.devicePixelRatio())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            dpr = 1.0
        if not math.isfinite(dpr) or dpr <= 0.0:
            dpr = 1.0
        # Cache key stability without materially changing the actual display DPR.
        return round(max(1.0, min(4.0, dpr)), 3)


__all__ = ["QuickCursorController"]
