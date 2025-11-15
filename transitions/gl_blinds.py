"""
GL Blinds Transition.

Simulates a window-blinds reveal using a persistent QOpenGLWidget overlay.
We progressively reveal bands across the frame while leveraging the centralized
AnimationManager and ResourceManager. This is GL-only and should only be
selectable when hardware acceleration is enabled.
"""
from __future__ import annotations

import threading
from typing import Optional, List

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QImage, QPainterPath, QRegion
from PySide6.QtWidgets import QWidget
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from transitions.base_transition import BaseTransition, TransitionState
from transitions.overlay_manager import (
    get_or_create_overlay,
    notify_overlay_stage,
    prepare_gl_overlay,
)
from core.animation.types import EasingCurve
from core.logging.logger import get_logger
from rendering.gl_format import apply_widget_surface_format

logger = get_logger(__name__)


def _make_puzzle_mask(w: int, h: int) -> QImage:
    """Create a simple puzzle-like alpha mask. Placeholder silhouette with rounded rect."""
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        margin = max(2, int(min(w, h) * 0.12))
        path.addRoundedRect(0, 0, w, h, margin, margin)
        p.fillPath(path, QColor(255, 255, 255, 255))
    finally:
        p.end()
    return img


class _GLBlindSlat:
    def __init__(self, rect: QRect) -> None:
        self.rect = rect
        self.progress = 0.0


class _GLBlindsOverlay(QOpenGLWidget):
    def __init__(self, parent: QWidget, old_pixmap: QPixmap, new_pixmap: QPixmap, slats: List[_GLBlindSlat]):
        super().__init__(parent)
        apply_widget_surface_format(self, reason="gl_blinds_overlay")
        self.setAutoFillBackground(False)
        try:
            from PySide6.QtCore import Qt as _Qt
            self.setAttribute(_Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(_Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self.setAttribute(_Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        self._old = old_pixmap
        self._new = new_pixmap
        self._slats = slats
        self._reveal_region: QRegion = QRegion()
        self._state_lock = threading.Lock()
        self._gl_initialized = False
        self._first_frame_drawn = False
        self._has_drawn = False

    def set_images(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> None:
        self._old = old_pixmap
        self._new = new_pixmap
        with self._state_lock:
            self._first_frame_drawn = False
            self._has_drawn = False
        self.update()

    def set_region(self, region: QRegion) -> None:
        self._reveal_region = region
        self.update()

    def is_ready_for_display(self) -> bool:
        try:
            with self._state_lock:
                return self._gl_initialized and self._first_frame_drawn
        except Exception:
            return False

    def initializeGL(self) -> None:  # type: ignore[override]
        try:
            ctx = self.context()
            if ctx is not None:
                fmt = ctx.format()
                logger.debug(
                    f"[GL BLINDS] Context initialized: version={fmt.majorVersion()}.{fmt.minorVersion()}, "
                    f"swap={fmt.swapBehavior()}, interval={fmt.swapInterval()}"
                )
                notify_overlay_stage(self, "gl_initialized",
                                     version=f"{fmt.majorVersion()}.{fmt.minorVersion()}",
                                     swap=str(fmt.swapBehavior()),
                                     interval=fmt.swapInterval())
            with self._state_lock:
                self._gl_initialized = True
        except Exception:
            pass

    def paintGL(self) -> None:  # type: ignore[override]
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            target = self.rect()
            if self._old and not self._old.isNull():
                p.setOpacity(1.0)
                p.drawPixmap(target, self._old)
            if self._new and not self._new.isNull() and not self._reveal_region.isEmpty():
                p.save()
                p.setClipRegion(self._reveal_region)
                p.setOpacity(1.0)
                p.drawPixmap(target, self._new)
                p.restore()
        finally:
            p.end()
        with self._state_lock:
            if not self._first_frame_drawn:
                self._first_frame_drawn = True
                notify_overlay_stage(self, "first_frame_drawn")
            self._has_drawn = True


class GLBlindsTransition(BaseTransition):
    """OpenGL-backed Blinds transition."""

    def __init__(self, duration_ms: int = 1800, slat_rows: int = 5, slat_cols: int = 7):
        super().__init__(duration_ms)
        self._rows = slat_rows
        self._cols = slat_cols
        self._widget: Optional[QWidget] = None
        self._old_pixmap: Optional[QPixmap] = None
        self._new_pixmap: Optional[QPixmap] = None
        self._slats: List[_GLBlindSlat] = []
        self._overlay: Optional[_GLBlindsOverlay] = None
        self._animation_id: Optional[str] = None
        self._tail_repaint_sent: bool = False

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:
        if self._state == TransitionState.RUNNING:
            return False
        if not new_pixmap or new_pixmap.isNull():
            self.error.emit("Invalid image")
            return False
        try:
            self._widget = widget
            self._new_pixmap = new_pixmap
            self._old_pixmap = old_pixmap
            if not old_pixmap or old_pixmap.isNull():
                self._show_image_immediately()
                return True

            w, h = widget.width(), widget.height()
            self._create_slats(w, h)
            self._tail_repaint_sent = False

            overlay = get_or_create_overlay(
                widget,
                "_srpss_gl_blinds_overlay",
                _GLBlindsOverlay,
                lambda: _GLBlindsOverlay(widget, old_pixmap, new_pixmap, self._slats),
            )
            overlay._slats = self._slats  # keep reference current
            overlay.set_images(old_pixmap, new_pixmap)
            overlay.set_region(QRegion())

            self._overlay = overlay
            prepare_gl_overlay(
                widget,
                self._overlay,
                stage="initial_raise_blinds",
                prepaint_description="GL BLINDS",
            )

            am = self._get_animation_manager(widget)
            duration_sec = max(0.001, self.duration_ms / 1000.0)
            self._animation_id = am.animate_custom(
                duration=duration_sec,
                easing=EasingCurve.LINEAR,
                update_callback=lambda p: self._on_anim_update(p),
                on_complete=self._on_anim_complete,
            )

            self._set_state(TransitionState.RUNNING)
            self.started.emit()
            logger.info(f"GL Blinds started ({self.duration_ms}ms, grid={self._cols}x{self._rows})")
            return True
        except Exception as e:
            logger.exception(f"Failed to start GL Blinds: {e}")
            self.error.emit(f"Transition failed: {e}")
            self.cleanup()
            return False

    def stop(self) -> None:
        if self._state != TransitionState.RUNNING:
            return
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception:
                pass
        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception:
                pass
            self._animation_id = None
        if self._overlay:
            try:
                self._overlay.hide()
            except Exception:
                pass
            self._overlay = None
        self._widget = None
        self._slats = []
        self._tail_repaint_sent = False
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)

    # Internals
    def _create_slats(self, width: int, height: int) -> None:
        self._slats = []
        cols = max(2, int(self._cols) * 2)
        aspect = height / max(1, width)
        rows = max(2, int(round(cols * aspect)))
        bw = max(1, width // cols)
        bh = max(1, height // rows)
        for r in range(rows):
            for c in range(cols):
                x = c * bw
                y = r * bh
                w = bw if c < cols - 1 else (width - x)
                h = bh if r < rows - 1 else (height - y)
                self._slats.append(_GLBlindSlat(QRect(x, y, w, h)))

    def _on_anim_update(self, progress: float) -> None:
        if self._state != TransitionState.RUNNING or not self._overlay:
            return
        progress = max(0.0, min(1.0, progress))
        # Build union region of revealed masked rectangles proportionally
        region = QRegion()
        for slat in self._slats:
            r = slat.rect
            reveal_w = max(1, int(r.width() * progress))
            dx = r.x() + (r.width() - reveal_w) // 2
            reveal = QRect(dx, r.y(), reveal_w, r.height())
            region = region.united(QRegion(reveal))
        try:
            self._overlay.set_region(region)
            self._overlay.repaint()
        except Exception:
            pass
        if not self._tail_repaint_sent and progress >= 0.93:
            self._trigger_tail_repaint()
        self._emit_progress(progress)

    def _on_anim_complete(self) -> None:
        if self._state != TransitionState.RUNNING:
            return
        if self._overlay:
            try:
                self._overlay.set_region(QRegion(self._overlay.rect()))
                self._overlay.repaint()
            except Exception:
                pass
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()

    def _trigger_tail_repaint(self) -> None:
        if self._overlay is None:
            return
        self._tail_repaint_sent = True
        try:
            self._overlay.repaint()
        except Exception:
            pass

