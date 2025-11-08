"""
GL Wipe transition - OpenGL-backed reveal of the new image.

Uses a QOpenGLWidget overlay that draws the old pixmap fully and the new
pixmap clipped by a moving rectangle according to the wipe direction.
Animation timing is driven by the centralized AnimationManager.
"""
from __future__ import annotations

import threading
from typing import Optional
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QWidget
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from transitions.base_transition import BaseTransition, TransitionState
from transitions.wipe_transition import WipeDirection
from core.animation.types import EasingCurve
from core.logging.logger import get_logger

logger = get_logger(__name__)


class _GLWipeWidget(QOpenGLWidget):
    def __init__(self, parent: QWidget, old_pixmap: QPixmap, new_pixmap: QPixmap, direction: WipeDirection) -> None:
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
        self._direction = direction
        self._progress: float = 0.0
        
        # Atomic state flags with lock protection
        self._state_lock = threading.Lock()
        self._gl_initialized: bool = False
        self._first_frame_drawn: bool = False
        self._has_drawn: bool = False

    def set_images(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> None:
        self._old = old_pixmap
        self._new = new_pixmap
        with self._state_lock:
            self._first_frame_drawn = False
            self._has_drawn = False
        self.update()
    
    def set_direction(self, direction: WipeDirection) -> None:
        """Update wipe direction (needed when reusing pre-warmed overlay)."""
        self._direction = direction
        self.update()

    def set_progress(self, p: float) -> None:
        self._progress = max(0.0, min(1.0, p))
        self.update()

    def has_drawn(self) -> bool:
        return self._has_drawn
    
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
            # Draw old fully
            if self._old and not self._old.isNull():
                p.setOpacity(1.0)
                p.drawPixmap(target, self._old)
            # Clip and draw new based on direction and progress
            if self._new and not self._new.isNull():
                w = target.width()
                h = target.height()
                if self._direction == WipeDirection.LEFT_TO_RIGHT:
                    rw = int(w * self._progress)
                    clip = target.adjusted(0, 0, -(w - rw), 0)
                elif self._direction == WipeDirection.RIGHT_TO_LEFT:
                    x = int(w * (1.0 - self._progress))
                    clip = target.adjusted(x, 0, 0, 0)
                elif self._direction == WipeDirection.TOP_TO_BOTTOM:
                    rh = int(h * self._progress)
                    clip = target.adjusted(0, 0, 0, -(h - rh))
                else:  # BOTTOM_TO_TOP
                    y = int(h * (1.0 - self._progress))
                    clip = target.adjusted(0, y, 0, 0)
                p.save()
                p.setClipRect(clip)
                p.setOpacity(1.0)
                p.drawPixmap(target, self._new)
                p.restore()
        finally:
            p.end()
        
        # Mark as drawn atomically
        with self._state_lock:
            if not self._first_frame_drawn:
                self._first_frame_drawn = True
                logger.debug("[GL WIPE] First frame drawn, overlay ready")
            self._has_drawn = True


class GLWipeTransition(BaseTransition):
    """OpenGL-backed Wipe transition that mirrors the CPU variant behavior."""

    def __init__(self, duration_ms: int = 1000, direction: WipeDirection = WipeDirection.LEFT_TO_RIGHT, easing: str = 'Auto'):
        super().__init__(duration_ms)
        self._widget: Optional[QWidget] = None
        self._gl: Optional[_GLWipeWidget] = None
        self._animation_id: Optional[str] = None
        self._direction = direction
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
            logger.error("Invalid pixmap for GL Wipe transition")
            self.error.emit("Invalid image")
            return False
        try:
            self._widget = widget
            if not old_pixmap or old_pixmap.isNull():
                logger.debug("No old image, showing new image immediately (GL Wipe)")
                self._show_image_immediately()
                return True

            w, h = widget.width(), widget.height()
            overlay = getattr(widget, "_srpss_gl_wipe_overlay", None)
            if overlay is None or not isinstance(overlay, _GLWipeWidget):
                logger.debug("[GL WIPE] Creating persistent GL overlay")
                overlay = _GLWipeWidget(widget, old_pixmap, new_pixmap, self._direction)
                overlay.setGeometry(0, 0, w, h)
                setattr(widget, "_srpss_gl_wipe_overlay", overlay)
                if getattr(self, "_resources", None):
                    try:
                        self._resources.register_qt(overlay, description="GL Wipe persistent overlay")
                    except Exception:
                        pass
            else:
                logger.debug("[GL WIPE] Reusing persistent GL overlay")
                overlay.set_direction(self._direction)
                overlay.set_images(old_pixmap, new_pixmap)
                overlay.set_progress(0.0)

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
            
            # Process events to ensure GL context is initialized before prepainting
            try:
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents()
            except Exception:
                pass
            
            # Prepaint initial frame to avoid black flicker
            try:
                self._gl.makeCurrent()
                self._gl.set_progress(0.0)
                _fb = self._gl.grabFramebuffer()  # forces a paintGL pass
                _ = _fb
                logger.debug("[GL WIPE] Prepainted initial frame (progress=0.0)")
            except Exception as e:
                logger.warning(f"[GL WIPE] Prepaint failed: {e}")
            try:
                self._gl.repaint()
            except Exception:
                pass

            am = self._get_animation_manager(widget)
            duration_sec = max(0.001, self.duration_ms / 1000.0)
            self._animation_id = am.animate_custom(
                duration=duration_sec,
                easing=self._resolve_easing(),
                update_callback=lambda p: self._on_anim_update(p),
                on_complete=lambda: self._on_anim_complete(),
            )

            self._set_state(TransitionState.RUNNING)
            self.started.emit()
            logger.info(f"GLWipe transition started ({self.duration_ms}ms, dir={self._direction.value})")
            return True
        except Exception as e:
            logger.exception(f"Failed to start GL Wipe: {e}")
            self.error.emit(f"Transition failed: {e}")
            self.cleanup()
            return False

    def stop(self) -> None:
        if self._state != TransitionState.RUNNING:
            return
        logger.debug("Stopping GL Wipe")
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
        logger.debug("Cleaning up GL Wipe")
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
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)

    # Internals
    def _on_anim_update(self, progress: float) -> None:
        if self._gl is None:
            return
        progress = max(0.0, min(1.0, progress))
        try:
            self._gl.set_progress(progress)
            self._gl.repaint()
        except Exception:
            pass
        self._emit_progress(progress)

    def _on_anim_complete(self) -> None:
        if self._state != TransitionState.RUNNING:
            return
        if self._gl:
            try:
                self._gl.set_progress(1.0)
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
