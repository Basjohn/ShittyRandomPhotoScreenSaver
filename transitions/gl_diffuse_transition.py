"""
GL Diffuse transition - OpenGL-backed block-wise reveal.

Reveals the new image by progressively revealing grid cells in randomized
order, approximating the CPU Diffuse effect. Uses a persistent QOpenGLWidget
overlay and centralized AnimationManager timing.
"""
from __future__ import annotations

import random
import threading
from typing import Optional, List
from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap, QPainter, QRegion
from PySide6.QtWidgets import QWidget
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from transitions.base_transition import BaseTransition, TransitionState
from core.animation.types import EasingCurve
from core.logging.logger import get_logger

logger = get_logger(__name__)


class _Cell:
    def __init__(self, rect: QRect):
        self.rect = rect
        self.revealed = False
        self.threshold = random.random()


class _GLDiffuseWidget(QOpenGLWidget):
    def __init__(self, parent: QWidget, old_pixmap: QPixmap, new_pixmap: QPixmap, cells: List[_Cell], shape: str = 'Rectangle'):
        super().__init__(parent)
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
        self._cells: List[_Cell] = cells
        self._region = QRegion()
        self._shape = shape or 'Rectangle'
        
        # Atomic state flags with lock protection
        self._state_lock = threading.Lock()
        self._gl_initialized: bool = False
        self._first_frame_drawn: bool = False
        self._has_drawn: bool = False

    def set_images(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> None:
        self._old = old_pixmap
        self._new = new_pixmap
        self._region = QRegion()
        self.update()
    
    def set_shape(self, shape: str) -> None:
        self._shape = shape or 'Rectangle'
        self.update()

    def set_region(self, region: QRegion) -> None:
        self._region = region
        self.update()

    def has_drawn(self) -> bool:
        return getattr(self, "_has_drawn", False)
    
    def is_ready_for_display(self) -> bool:
        """Thread-safe check if overlay is ready to display."""
        try:
            with self._state_lock:
                return self._gl_initialized and self._first_frame_drawn
        except Exception:
            return False
    
    def initializeGL(self) -> None:  # type: ignore[override]
        """Called once when GL context is created."""
        try:
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
            if self._new and not self._new.isNull() and not self._region.isEmpty():
                p.save()
                p.setClipRegion(self._region)
                p.setOpacity(1.0)
                p.drawPixmap(target, self._new)
                p.restore()
        finally:
            p.end()
        
        # Mark as drawn atomically
        with self._state_lock:
            if not self._first_frame_drawn:
                self._first_frame_drawn = True
                logger.debug("[GL DIFFUSE] First frame drawn, overlay ready")
            self._has_drawn = True


class GLDiffuseTransition(BaseTransition):
    """OpenGL-backed Diffuse transition (rectangular cells)."""

    def __init__(self, duration_ms: int = 1000, block_size: int = 50, shape: str = 'Rectangle', easing: str = 'Auto'):
        super().__init__(duration_ms)
        self._block_size = max(1, int(block_size))
        self._shape = shape or 'Rectangle'
        self._widget: Optional[QWidget] = None
        self._old_pixmap: Optional[QPixmap] = None
        self._new_pixmap: Optional[QPixmap] = None
        self._cells: List[_Cell] = []
        self._order: List[int] = []
        self._animation_id: Optional[str] = None
        self._gl: Optional[_GLDiffuseWidget] = None
        self._easing_str = easing
        try:
            from core.resources.manager import ResourceManager
            self._resources = ResourceManager()
        except Exception:
            self._resources = None

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL Diffuse transition")
            self.error.emit("Invalid image")
            return False
        try:
            self._widget = widget
            self._new_pixmap = new_pixmap
            self._old_pixmap = old_pixmap
            if not old_pixmap or old_pixmap.isNull():
                logger.debug("No old image, showing new image immediately (GL Diffuse)")
                self._show_image_immediately()
                return True

            w, h = widget.width(), widget.height()
            self._build_cells(w, h)
            total = len(self._cells)
            self._order = list(range(total))
            random.shuffle(self._order)

            overlay = getattr(widget, "_srpss_gl_diffuse_overlay", None)
            if overlay is None or not isinstance(overlay, _GLDiffuseWidget):
                logger.debug("[GL DIFFUSE] Creating persistent GL overlay")
                overlay = _GLDiffuseWidget(widget, old_pixmap, new_pixmap, self._cells, self._shape)
                overlay.setGeometry(0, 0, w, h)
                setattr(widget, "_srpss_gl_diffuse_overlay", overlay)
                if getattr(self, "_resources", None):
                    try:
                        self._resources.register_qt(overlay, description="GL Diffuse persistent overlay")
                    except Exception:
                        pass
            else:
                logger.debug("[GL DIFFUSE] Reusing persistent GL overlay")
                overlay.set_images(old_pixmap, new_pixmap)
                overlay.set_shape(self._shape)
                overlay.set_region(QRegion())

            self._gl = overlay
            self._gl.setVisible(True)
            self._gl.setGeometry(0, 0, w, h)
            try:
                self._gl.raise_()
            except Exception:
                pass
            # Keep clock above overlay
            try:
                if hasattr(widget, "clock_widget") and getattr(widget, "clock_widget"):
                    widget.clock_widget.raise_()
            except Exception:
                pass
            
            # Prepaint initial frame to avoid black flicker (same pattern as GLCrossfade)
            try:
                self._gl.makeCurrent()
            except Exception:
                pass
            try:
                self._gl.set_region(QRegion())  # Start with empty region
                _fb = self._gl.grabFramebuffer()  # forces a paintGL pass
                _ = _fb
                logger.debug("[GL DIFFUSE] Prepainted initial frame (empty region)")
            except Exception:
                pass
            try:
                self._gl.repaint()
            except Exception:
                pass

            am = self._get_animation_manager(widget)
            duration_sec = max(0.001, self.duration_ms / 1000.0)
            self._animation_id = am.animate_custom(
                duration=duration_sec,
                easing=self._resolve_easing(),
                update_callback=lambda p, total=total: self._on_anim_update(p, total),
                on_complete=lambda: self._on_anim_complete(),
            )

            self._set_state(TransitionState.RUNNING)
            self.started.emit()
            logger.info(f"GL Diffuse transition started ({self.duration_ms}ms, block={self._block_size}px)")
            return True
        except Exception as e:
            logger.exception(f"Failed to start GL Diffuse: {e}")
            self.error.emit(f"Transition failed: {e}")
            self.cleanup()
            return False

    def stop(self) -> None:
        if self._state != TransitionState.RUNNING:
            return
        logger.debug("Stopping GL Diffuse")
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
        logger.debug("Cleaning up GL Diffuse")
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception:
                pass
            self._animation_id = None
        if self._gl:
            try:
                self._gl.hide()
            except Exception:
                pass
            self._gl = None
        self._widget = None
        self._cells = []
        self._order = []
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)

    # Internals
    def _build_cells(self, width: int, height: int) -> None:
        self._cells = []
        cols = max(1, (width + self._block_size - 1) // self._block_size)
        rows = max(1, (height + self._block_size - 1) // self._block_size)
        for r in range(rows):
            for c in range(cols):
                x = c * self._block_size
                y = r * self._block_size
                w = self._block_size if c < cols - 1 else (width - x)
                h = self._block_size if r < rows - 1 else (height - y)
                self._cells.append(_Cell(QRect(x, y, w, h)))

    def _on_anim_update(self, progress: float, total: int) -> None:
        if self._state != TransitionState.RUNNING or self._gl is None:
            return
        progress = max(0.0, min(1.0, progress))
        # Reveal cells whose thresholds are below progress
        region = QRegion()
        revealed = 0
        for cell in self._cells:
            if not cell.revealed and progress >= cell.threshold:
                cell.revealed = True
            if cell.revealed:
                revealed += 1
                # Build region based on shape
                if self._shape == 'Circle':
                    from PySide6.QtGui import QPainterPath
                    from PySide6.QtCore import QRectF
                    path = QPainterPath()
                    path.addEllipse(QRectF(cell.rect))
                    region = region.united(QRegion(path.toFillPolygon().toPolygon()))
                elif self._shape == 'Triangle':
                    from PySide6.QtGui import QPolygon
                    from PySide6.QtCore import QPoint
                    r = cell.rect
                    top = QPoint(r.x() + r.width() // 2, r.y())
                    bottom_left = QPoint(r.x(), r.y() + r.height())
                    bottom_right = QPoint(r.x() + r.width(), r.y() + r.height())
                    region = region.united(QRegion(QPolygon([top, bottom_left, bottom_right])))
                else:  # Rectangle
                    region = region.united(QRegion(cell.rect))
        try:
            self._gl.set_region(region)
            self._gl.repaint()
        except Exception:
            pass
        if total > 0:
            self._emit_progress(revealed / total)

    def _on_anim_complete(self) -> None:
        if self._state != TransitionState.RUNNING:
            return
        if self._gl:
            try:
                self._gl.set_region(QRegion(self._gl.rect()))
                self._gl.repaint()
            except Exception:
                pass
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()

    def _resolve_easing(self) -> EasingCurve:
        name = (self._easing_str or 'Auto').strip()
        if name == 'Auto':
            return EasingCurve.QUAD_IN_OUT
        mapping = {
            'Linear': EasingCurve.LINEAR,
            'InQuad': EasingCurve.QUAD_IN,
            'OutQuad': EasingCurve.QUAD_OUT,
            'InOutQuad': EasingCurve.QUAD_IN_OUT,
            'InCubic': EasingCurve.CUBIC_IN,
            'OutCubic': EasingCurve.CUBIC_OUT,
            'InOutCubic': EasingCurve.CUBIC_IN_OUT,
        }
        return mapping.get(name, EasingCurve.QUAD_IN_OUT)
