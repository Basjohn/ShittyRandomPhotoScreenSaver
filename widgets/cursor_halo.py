"""
Cursor halo widget for Ctrl-click interaction mode.

Provides a visual indicator (ring + dot) that follows the cursor when
Ctrl is held, allowing users to interact with widgets without triggering
the screensaver exit.

The halo is implemented as a top-level frameless window (not a child widget)
so it floats above all other widgets including QOpenGLWidget-based overlays
like the Spotify visualizer and volume slider. This avoids Z-order fighting
with GL widgets that have their own native window handles.

Mouse events are forwarded to the parent widget so context menus and clicks
still work. The mouse cursor is hidden when the halo is visible.
"""
import math
import os
import time
from typing import Optional

from PySide6.QtCore import Qt, QPointF, QRectF, QElapsedTimer
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPen,
    QRadialGradient,
    QWheelEvent,
)
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import Shiboken

from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve
from core.logging.logger import get_logger, is_perf_metrics_enabled
from rendering.multi_monitor_coordinator import get_coordinator

logger = get_logger(__name__)
PERF_METRICS_ENABLED = is_perf_metrics_enabled()


HALO_BASE_DIAMETER = 48
HALO_SCALE = 0.8
HALO_DIAMETER = int(round(HALO_BASE_DIAMETER * HALO_SCALE))

PRIMARY_COLOR = QColor(246, 248, 255, 235)
ACCENT_COLOR = QColor(130, 205, 255, 200)
SHADOW_COLOR = QColor(12, 14, 28, 160)
INNER_DOT_COLOR = QColor(255, 255, 255, 240)
OUTER_COLOR = QColor(246, 248, 255, 235)
OUTLINE_COLOR = QColor(255, 255, 255, 255)
OUTLINE_WIDTH = 3.5

_perf_env = os.getenv("SRPSS_HALO_PERF_MIN_MS")
try:
    HALO_PERF_LOG_MIN_MS = max(0.01, float(_perf_env)) if _perf_env else 0.25
except (TypeError, ValueError):
    HALO_PERF_LOG_MIN_MS = 0.25


def _scaled_shadow_color(scale: float = 1.0) -> QColor:
    color = QColor(SHADOW_COLOR)
    try:
        color.setAlpha(min(255, int(round(color.alpha() * max(0.1, scale)))))
    except Exception:
        pass
    return color


class CursorHaloWidget(QWidget):
    """
    Visual cursor indicator for Ctrl-held interaction mode.
    
    Displays a semi-transparent ring with a center dot that follows
    the cursor position. Supports fade-in/fade-out animations.
    
    Implemented as a top-level frameless window to guarantee it stays
    above QOpenGLWidget-based overlays (Spotify visualizer, volume slider).
    Mouse events are forwarded to the parent widget for context menu support.
    """
    
    def __init__(self, parent: QWidget) -> None:
        # Create as top-level frameless window, not a child widget
        # This ensures it floats above all sibling widgets including GL overlays
        super().__init__(
            None,  # No parent - top-level window
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |  # Exclude from taskbar/alt-tab
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self._parent_widget = parent  # Keep reference for coordinate mapping and event forwarding
        
        # Don't use WA_TransparentForMouseEvents - we need to receive and forward events
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAutoFillBackground(False)
        # Hide mouse cursor over halo - the halo IS the cursor
        self.setCursor(Qt.CursorShape.BlankCursor)
        # Match the 2.6 reference footprint (48px * 0.8 scale).
        self.resize(HALO_DIAMETER, HALO_DIAMETER)
        self._opacity = 1.0
        self._shape: str = "circle"  # circle, ring, crosshair, diamond, dot
        self._animation_id: Optional[str] = None
        self._animation_manager = AnimationManager()
        self._is_fading_out = False  # Track fade state to prevent interference
        self._last_perf_log_ts: float = 0.0
        self._perf_log_threshold_ms: float = HALO_PERF_LOG_MIN_MS

    def set_parent_widget(self, parent: QWidget) -> None:
        """Refresh the parent widget reference after display rebuilds."""
        if parent is not None and Shiboken.isValid(parent):
            self._parent_widget = parent

    def setOpacity(self, value: float) -> None:
        """Set the halo opacity (0.0 to 1.0)."""
        try:
            self._opacity = max(0.0, min(1.0, float(value)))
            self.setWindowOpacity(self._opacity)
        except Exception as e:
            logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            self._opacity = 1.0
        self.update()

    def opacity(self) -> float:
        """Get the current opacity."""
        return float(self._opacity)

    def set_shape(self, shape: str) -> None:
        """Set the halo shape. Valid: circle, ring, crosshair, diamond, dot, cursor_triangle."""
        valid = {"circle", "ring", "crosshair", "diamond", "dot", "cursor_triangle"}
        normalized = shape if shape in valid else "circle"
        if normalized == self._shape:
            return
        self._shape = normalized
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        """Paint the halo in the configured shape with drop shadow."""
        perf_timer: Optional[QElapsedTimer] = None
        if PERF_METRICS_ENABLED:
            perf_timer = QElapsedTimer()
            perf_timer.start()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        r = min(self.width(), self.height()) - 8
        cx = self.width() // 2
        cy = self.height() // 2
        inner_radius = max(2, r // 6)
        shape = self._shape

        if shape == "ring":
            self._paint_ring(painter, cx, cy, r)
        elif shape == "crosshair":
            self._paint_crosshair(painter, cx, cy, r)
        elif shape == "diamond":
            self._paint_diamond(painter, cx, cy, r)
        elif shape == "dot":
            self._paint_dot(painter, cx, cy, inner_radius * 2)
        elif shape == "cursor_triangle":
            self._paint_cursor_triangle(painter, cx, cy, r)
        else:
            self._paint_circle(painter, cx, cy, r, inner_radius)
        painter.end()

        if perf_timer is not None and perf_timer.isValid():
            elapsed_ms = perf_timer.nsecsElapsed() / 1_000_000.0
            now = time.monotonic()
            threshold = max(0.01, getattr(self, "_perf_log_threshold_ms", HALO_PERF_LOG_MIN_MS))
            if elapsed_ms >= threshold and (now - self._last_perf_log_ts) >= 1.0:
                self._last_perf_log_ts = now
                logger.info(
                    "[CURSOR_HALO][PERF] paint shape=%s %.3fms size=%dx%d",
                    self._shape,
                    elapsed_ms,
                    self.width(),
                    self.height(),
                )

    def _paint_circle(self, painter: QPainter, cx: int, cy: int, r: int, inner_r: int) -> None:
        """Default circle: ring + center dot."""
        self._paint_shadow_ring(painter, cx, cy, r)
        pen = painter.pen()
        pen.setWidth(5)
        pen.setColor(PRIMARY_COLOR)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(4, 4, r, r)

        highlight = QRadialGradient(QPointF(cx, cy), float(inner_r) * 1.6)
        highlight.setColorAt(0.0, INNER_DOT_COLOR)
        highlight.setColorAt(1.0, ACCENT_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(highlight)
        painter.drawEllipse(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)
        self._paint_outer_outline(painter)

    def _paint_ring(self, painter: QPainter, cx: int, cy: int, r: int) -> None:
        self._paint_shadow_ring(painter, cx, cy, r)
        pen = painter.pen()
        pen.setColor(PRIMARY_COLOR)
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(4, 4, r, r)
        self._paint_outer_outline(painter)

    def _paint_crosshair(self, painter: QPainter, cx: int, cy: int, r: int) -> None:
        from PySide6.QtCore import QLineF

        half = r // 2
        gap = max(3, r // 8)
        pen = painter.pen()
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for color in (SHADOW_COLOR, PRIMARY_COLOR):
            pen.setColor(color)
            painter.setPen(pen)
            offset = 2 if color == SHADOW_COLOR else 0
            painter.drawLine(QLineF(cx - half + offset, cy + offset, cx - gap + offset, cy + offset))
            painter.drawLine(QLineF(cx + gap + offset, cy + offset, cx + half + offset, cy + offset))
            painter.drawLine(QLineF(cx + offset, cy - half + offset, cx + offset, cy - gap + offset))
            painter.drawLine(QLineF(cx + offset, cy + gap + offset, cx + offset, cy + half + offset))

    def _paint_diamond(self, painter: QPainter, cx: int, cy: int, r: int) -> None:
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF as QPF

        half = r // 2
        points = [QPF(cx, cy - half), QPF(cx + half, cy), QPF(cx, cy + half), QPF(cx - half, cy)]
        pen = painter.pen()
        pen.setWidthF(max(1.0, pen.widthF()) + 1.5)
        for color in (SHADOW_COLOR, PRIMARY_COLOR):
            offset = 2 if color == SHADOW_COLOR else 0
            shifted = QPolygonF([QPF(pt.x() + offset, pt.y() + offset) for pt in points])
            pen.setColor(QColor(color))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(shifted)

        self._paint_center_indicator(painter, cx, cy)

    def _paint_dot(self, painter: QPainter, cx: int, cy: int, diameter: int) -> None:
        radius = max(4, int(round(diameter * 1.2)))
        shadow_radius = float(radius) * 1.35
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        shadow = QRadialGradient(QPointF(cx + 2, cy + 2), shadow_radius)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 0))
        shadow.setColorAt(1.0, _scaled_shadow_color(1.8))
        painter.setBrush(shadow)
        painter.drawEllipse(
            cx - int(shadow_radius // 2) + 1,
            cy - int(shadow_radius // 2) + 1,
            int(shadow_radius),
            int(shadow_radius),
        )

        gradient = QRadialGradient(QPointF(cx, cy), float(radius))
        gradient.setColorAt(0.0, PRIMARY_COLOR)
        gradient.setColorAt(1.0, ACCENT_COLOR)
        painter.setBrush(gradient)
        painter.drawEllipse(cx - radius // 2, cy - radius // 2, radius, radius)
        painter.restore()

    def _paint_cursor_triangle(self, painter: QPainter, cx: int, cy: int, r: int) -> None:
        """Three elongated arrow-tip triangles merged at center, slightly left-slanted.

        Each triangle has a sharp outer tip and a wide inner base meeting at the
        centre, creating a 3-pointed star.  The whole shape is rotated ~15 degrees
        counter-clockwise so it reads as a left-leaning cursor.
        """
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF as QPF

        half = r / 2.0
        tip_r = half * 0.95
        base_r = half * 0.38
        base_hw = half * 0.28

        def rot(angle_deg: float) -> tuple[float, float]:
            angle = math.radians(angle_deg)
            return math.cos(angle), math.sin(angle)

        arm_angles = [135.0, 255.0, 15.0]
        points: list[QPF] = []
        for angle in arm_angles:
            tx, ty = rot(angle)
            tip = QPF(cx + tx * tip_r, cy - ty * tip_r)

            perp_l = angle + 90.0
            perp_r = angle - 90.0
            lx, ly = rot(perp_l)
            rx, ry = rot(perp_r)
            back_x, back_y = rot(angle + 180.0)
            base_cx = cx + back_x * base_r
            base_cy = cy - back_y * base_r
            base_left = QPF(base_cx + lx * base_hw, base_cy - ly * base_hw)
            base_right = QPF(base_cx + rx * base_hw, base_cy - ry * base_hw)

            points += [tip, base_left, base_right]

        outline = [
            points[0],
            points[2],
            points[4],
            points[3],
            points[5],
            points[7],
            points[6],
            points[8],
            points[1],
        ]

        pen = painter.pen()
        pen.setWidth(2)
        for color in (SHADOW_COLOR, PRIMARY_COLOR):
            offset = 2 if color == SHADOW_COLOR else 0
            shifted = QPolygonF([QPF(pt.x() + offset, pt.y() + offset) for pt in outline])
            pen.setColor(color)
            painter.setPen(pen)
            painter.setBrush(color)
            painter.drawPolygon(shifted)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Forward mouse press to parent widget."""
        self._forward_mouse_event(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Forward mouse release to parent widget."""
        self._forward_mouse_event(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Forward mouse move to parent widget."""
        self._forward_mouse_event(event)
    
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Forward double click to parent widget."""
        self._forward_mouse_event(event)
    
    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        """Forward wheel events to the parent widget."""
        self._forward_wheel_event(event)
    
    def _resolve_target_widget(self) -> Optional[QWidget]:
        """Return a valid DisplayWidget target, refreshing stale references."""
        parent = self._parent_widget
        if parent is not None and Shiboken.isValid(parent):
            return parent

        target = None
        coordinator = None
        try:
            coordinator = get_coordinator()
        except Exception as e:
            logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            coordinator = None

        if coordinator is not None:
            target = coordinator.halo_owner or coordinator.focus_owner

        if target is None and coordinator is not None:
            try:
                instances = coordinator.get_all_instances()
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
                instances = []
            for inst in instances:
                if inst is not None and Shiboken.isValid(inst):
                    target = inst
                    break

        if target is not None and Shiboken.isValid(target):
            self._parent_widget = target
            return target
        return None

    def _forward_mouse_event(self, event: QMouseEvent) -> None:
        """Forward a mouse event to the parent widget at the correct position."""
        parent = self._resolve_target_widget()
        if parent is None:
            return
        try:
            # Map halo-local position to global, then to parent-local
            global_pos = self.mapToGlobal(event.pos())
            local_pos = parent.mapFromGlobal(global_pos)
            
            # Create a new event with the mapped position
            new_event = QMouseEvent(
                event.type(),
                local_pos,
                global_pos,
                event.button(),
                event.buttons(),
                event.modifiers()
            )
            
            # Set guard so DisplayWidget skips halo repositioning for this event
            # (prevents feedback loop: halo forward → reposition halo → jitter)
            parent._halo_forwarding = True
            try:
                QApplication.sendEvent(parent, new_event)
            finally:
                parent._halo_forwarding = False
        except Exception:
            logger.debug("Failed to forward mouse event to parent", exc_info=True)
    
    def _forward_wheel_event(self, event: QWheelEvent) -> None:
        """Forward a wheel event to the parent widget."""
        parent = self._resolve_target_widget()
        if parent is None:
            return
        try:
            global_pos = event.globalPosition()
            local_point = parent.mapFromGlobal(global_pos.toPoint())
            local_pos = QPointF(local_point)
            logger.debug(
                "[HALO] Forwarding wheel event to parent: local=%s global=(%.1f, %.1f) delta=%s",
                local_pos,
                global_pos.x(),
                global_pos.y(),
                event.angleDelta(),
            )
            new_event = QWheelEvent(
                local_pos,
                global_pos,
                event.pixelDelta(),
                event.angleDelta(),
                event.buttons(),
                event.modifiers(),
                event.phase(),
                event.inverted(),
                event.source(),
            )
            # DEBUG_WHEEL_TRACE: parent metadata for easy removal once routing fixed.
            logger.debug(
                "[HALO] Wheel target parent id=%s screen=%s object=%s",
                hex(id(parent)),
                getattr(parent, "screen_index", None),
                getattr(parent, "objectName", None) or parent.__class__.__name__,
            )
            handled_direct = False
            if hasattr(parent, "handle_forwarded_halo_wheel"):
                try:
                    handled_direct = bool(
                        parent.handle_forwarded_halo_wheel(local_pos, global_pos, event.angleDelta())
                    )
                except Exception:
                    logger.debug("[HALO] Direct halo routing failed", exc_info=True)
            if not handled_direct:
                # DEBUG_WHEEL_TRACE: use postEvent so the app-wide filters observe it.
                QApplication.sendEvent(parent, new_event)
            event.accept()
            logger.debug("[HALO] Wheel event forwarded to parent (direct=%s)", handled_direct)
        except Exception:
            logger.debug("Failed to forward wheel event to parent", exc_info=True)
    
    def cancel_animation(self) -> None:
        """Cancel any running fade animation."""
        if self._animation_id is not None:
            try:
                self._animation_manager.cancel_animation(self._animation_id)
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            self._animation_id = None
        self._is_fading_out = False
    
    def fade_in(self, on_finished: Optional[callable] = None) -> None:
        """Fade in the halo over 600ms."""
        self._start_fade(fade_in=True, on_finished=on_finished)
    
    def fade_out(self, on_finished: Optional[callable] = None) -> None:
        """Fade out the halo over 1200ms."""
        self._start_fade(fade_in=False, on_finished=on_finished)
    
    def _start_fade(self, fade_in: bool, on_finished: Optional[callable] = None) -> None:
        """Start a fade animation."""
        self.cancel_animation()
        
        try:
            if fade_in:
                self._is_fading_out = False
                # CRITICAL: Show widget BEFORE setting opacity to 0.0
                # Otherwise the widget stays hidden even after animation
                if not self.isVisible():
                    self.show()
                    # Force immediate visibility update
                    self.raise_()
                self.setWindowOpacity(0.0)
                self._opacity = 0.0
            else:
                self._is_fading_out = True
                self.setWindowOpacity(1.0)
                self._opacity = 1.0
        except Exception as e:
            logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)

        duration_ms = 600 if fade_in else 1200
        start_val = 0.0 if fade_in else 1.0
        end_val = 1.0 if fade_in else 0.0
        
        def _on_tick(progress: float) -> None:
            try:
                value = start_val + (end_val - start_val) * progress
                self.setWindowOpacity(float(value))
                self._opacity = float(value)
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)

        def _on_anim_finished() -> None:
            if not fade_in:
                self._is_fading_out = False
                try:
                    self.hide()
                except Exception as e:
                    logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            else:
                # Ensure full opacity after fade in completes
                try:
                    self.setWindowOpacity(1.0)
                    self._opacity = 1.0
                except Exception as e:
                    logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            self._animation_id = None
            if on_finished:
                try:
                    on_finished()
                except Exception as e:
                    logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)

        try:
            # AnimationManager uses seconds, not milliseconds
            duration_sec = duration_ms / 1000.0
            self._animation_id = self._animation_manager.animate_custom(
                duration=duration_sec,
                update_callback=_on_tick,
                on_complete=_on_anim_finished,
                easing=EasingCurve.QUAD_OUT,
            )
        except Exception:
            logger.debug("Failed to start halo animation via AnimationManager", exc_info=True)
    
    def show_at(self, x: int, y: int) -> None:
        """Show the halo centered at the given local position.
        
        Args:
            x, y: Position in parent widget coordinates (will be mapped to global)
        """
        # Don't show if settings dialog is active
        try:
            from rendering.multi_monitor_coordinator import get_coordinator
            if get_coordinator().settings_dialog_active:
                return
        except Exception as e:
            logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
        
        self._move_internal(x, y)
        self.show()
    
    def move_to(self, x: int, y: int) -> None:
        """Move the halo to be centered at the given local position.
        
        Args:
            x, y: Position in parent widget coordinates (will be mapped to global)
        """
        self._move_internal(x, y)

    # --- Helpers ---------------------------------------------------------

    def _shape_anchor_offset(self) -> QPointF:
        width = max(1, self.width())
        height = max(1, self.height())
        if self._shape != "cursor_triangle":
            return QPointF(0.0, 0.0)

        r = min(width, height) - 8
        half = r / 2.0
        tip_r = half * 0.95
        tx = math.cos(math.radians(135.0)) * tip_r
        ty = -math.sin(math.radians(135.0)) * tip_r
        return QPointF(tx, ty)

    def _move_internal(self, x: int, y: int) -> None:
        size = self.size()
        anchor = self._shape_anchor_offset()
        anchor_x = int(round(anchor.x()))
        anchor_y = int(round(anchor.y()))

        if self._parent_widget is not None:
            try:
                global_origin = self._parent_widget.mapToGlobal(self._parent_widget.rect().topLeft())
                global_x = global_origin.x() + x - size.width() // 2 - anchor_x
                global_y = global_origin.y() + y - size.height() // 2 - anchor_y
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
                global_x = x - size.width() // 2 - anchor_x
                global_y = y - size.height() // 2 - anchor_y
        else:
            global_x = x - size.width() // 2 - anchor_x
            global_y = y - size.height() // 2 - anchor_y

        self.move(global_x, global_y)

    def _paint_shadow_ring(self, painter: QPainter, cx: int, cy: int, r: int) -> None:
        gradient = QRadialGradient(QPointF(cx + 2, cy + 2), float(r))
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(1.0, SHADOW_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(4, 4, r, r)

    def _paint_outer_outline(self, painter: QPainter) -> None:
        diameter = max(0.0, min(self.width(), self.height()) - 2.0)
        if diameter <= 0.0:
            return
        offset_x = (self.width() - diameter) / 2.0
        offset_y = (self.height() - diameter) / 2.0
        painter.save()
        pen = QPen(OUTLINE_COLOR)
        pen.setWidthF(OUTLINE_WIDTH)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(offset_x, offset_y, diameter, diameter))
        painter.restore()

    def _paint_center_indicator(self, painter: QPainter, cx: int, cy: int) -> None:
        size = max(4, self.width() // 12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(INNER_DOT_COLOR)
        painter.drawEllipse(cx - size // 2, cy - size // 2, size, size)
    
    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Ensure halo fades out when destroyed."""
        try:
            # Cancel any running animation
            self.cancel_animation()
            # Fade out before closing
            if self.isVisible():
                self.fade_out(on_finished=lambda: event.accept())
            else:
                event.accept()
        except Exception as e:
            logger.debug("[CURSOR_HALO] Exception suppressed during close: %s", e)
            event.accept()
