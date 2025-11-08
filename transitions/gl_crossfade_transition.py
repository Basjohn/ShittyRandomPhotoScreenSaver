"""
GPU-accelerated crossfade transition using QOpenGLWidget.

This transition mirrors CrossfadeTransition behavior but renders on an
OpenGL-backed surface. Animation timing is driven by the centralized
AnimationManager; no raw QPropertyAnimation is used.
"""
from __future__ import annotations

import threading
from typing import Optional
from PySide6.QtGui import QPixmap, QPainter, QSurfaceFormat
from PySide6.QtWidgets import QWidget
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from transitions.base_transition import BaseTransition, TransitionState
from core.animation.types import EasingCurve
from core.logging.logger import get_logger

logger = get_logger(__name__)


class _GLFadeWidget(QOpenGLWidget):
    """Internal GL widget that draws old and new pixmaps with opacity."""

    def __init__(self, parent: QWidget, old_pixmap: QPixmap, new_pixmap: QPixmap) -> None:
        # Configure surface format before context is created
        try:
            fmt = QSurfaceFormat()
            fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
            fmt.setSwapInterval(1)  # vsync
            self.setFormat(fmt)
        except Exception:
            pass
        super().__init__(parent)
        self.setAutoFillBackground(False)
        try:
            # Avoid system background clears and rely on our paint
            from PySide6.QtCore import Qt as _Qt
            self.setAttribute(_Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(_Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            # Allow normal stacking so clock can be raised above GL overlay
            self.setAttribute(_Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        try:
            self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        except Exception:
            pass
        self._alpha: float = 0.0  # 0..1
        self._old = old_pixmap
        self._new = new_pixmap
        
        # Atomic state flags with lock protection
        self._state_lock = threading.Lock()
        self._gl_initialized: bool = False
        self._first_frame_drawn: bool = False
        
        # Legacy compatibility
        self._initialized: bool = False
        self._has_drawn: bool = False

    def set_images(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> None:
        self._old = old_pixmap
        self._new = new_pixmap
        with self._state_lock:
            self._first_frame_drawn = False
            self._has_drawn = False
        self.update()

    def set_alpha(self, a: float) -> None:
        self._alpha = max(0.0, min(1.0, a))
        self.update()

    # QOpenGLWidget paint cycle
    def paintGL(self) -> None:  # type: ignore[override]
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            target = self.rect()
            if self._old and not self._old.isNull():
                painter.setOpacity(1.0)
                painter.drawPixmap(target, self._old)
            if self._new and not self._new.isNull():
                painter.setOpacity(self._alpha)
                painter.drawPixmap(target, self._new)
        finally:
            painter.end()
        
        # Mark as drawn atomically
        with self._state_lock:
            if not self._first_frame_drawn:
                self._first_frame_drawn = True
                logger.debug("[GL XFADE] First frame drawn, overlay ready")
            self._has_drawn = True

    def initializeGL(self) -> None:  # type: ignore[override]
        try:
            ctx = self.context()
            if ctx is not None:
                fmt = ctx.format()
                logger.debug(
                    f"[GL XFADE] Context initialized: version={fmt.majorVersion()}.{fmt.minorVersion()}, "
                    f"swap={fmt.swapBehavior()}, interval={fmt.swapInterval()}"
                )
            
            # Mark GL initialized atomically
            with self._state_lock:
                self._gl_initialized = True
                self._initialized = True  # Legacy
        except Exception:
            pass

    def has_drawn(self) -> bool:
        return getattr(self, "_has_drawn", False)
    
    def is_ready_for_display(self) -> bool:
        """Thread-safe check if overlay is ready to display (GL initialized and first frame drawn)."""
        try:
            with self._state_lock:
                return self._gl_initialized and self._first_frame_drawn
        except Exception:
            return False


class GLCrossfadeTransition(BaseTransition):
    """GPU-backed crossfade with identical sizing behavior to CPU variant."""

    def __init__(self, duration_ms: int = 1000, easing: str = 'Auto'):
        super().__init__(duration_ms)
        self._widget: Optional[QWidget] = None
        self._gl: Optional[_GLFadeWidget] = None
        self._animation_id: Optional[str] = None
        self._easing_str = easing
        # ResourceManager integration (best-effort)
        try:
            from core.resources.manager import ResourceManager
            self._resources = ResourceManager()
        except Exception:
            self._resources = None  # Fallback if manager unavailable during tests

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL transition")
            self.error.emit("Invalid image")
            return False
        
        # Start telemetry tracking
        self._mark_start()
        
        try:
            self._widget = widget
            w, h = widget.width(), widget.height()

            # If no old image, just show new one immediately
            if not old_pixmap or old_pixmap.isNull():
                logger.debug("No old image, showing new image immediately (GL)")
                self._show_image_immediately()
                return True

            # Reuse or create persistent overlay on the widget
            overlay = getattr(widget, "_srpss_gl_xfade_overlay", None)
            if overlay is None or not isinstance(overlay, _GLFadeWidget):
                logger.debug("[GL XFADE] Creating persistent GL overlay")
                overlay = _GLFadeWidget(widget, old_pixmap, new_pixmap)
                overlay.setGeometry(0, 0, w, h)
                setattr(widget, "_srpss_gl_xfade_overlay", overlay)
                if getattr(self, "_resources", None):
                    try:
                        self._resources.register_qt(overlay, description="GL Crossfade persistent overlay")
                    except Exception:
                        pass
            else:
                logger.debug("[GL XFADE] Reusing persistent GL overlay")
                overlay.set_images(old_pixmap, new_pixmap)
                overlay.set_alpha(0.0)

            self._gl = overlay
            # Show first so QOpenGLWidget creates context/FBO, then prepaint
            self._gl.setVisible(True)
            self._gl.setGeometry(0, 0, w, h)
            try:
                self._gl.raise_()
            except Exception:
                pass
            # Keep clock widget above GL overlay if present
            try:
                if hasattr(widget, "clock_widget") and getattr(widget, "clock_widget"):
                    widget.clock_widget.raise_()
            except Exception:
                pass
            try:
                self._gl.makeCurrent()
            except Exception:
                pass
            # Prepaint the initial frame offscreen to avoid one-frame black
            try:
                self._gl.set_alpha(0.0)
                _fb = self._gl.grabFramebuffer()  # forces a paintGL pass
                _ = _fb
                logger.debug("[GL XFADE] Prepainted initial frame (alpha=0.0)")
            except Exception:
                pass
            try:
                # Present first frame synchronously
                self._gl.repaint()
            except Exception:
                pass

            # Drive via AnimationManager
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
            logger.info(f"GLCrossfade transition started ({self.duration_ms}ms)")
            return True
        except Exception as e:
            logger.exception(f"Failed to start GLCrossfade: {e}")
            self.error.emit(f"Transition failed: {e}")
            self.cleanup()
            return False

    def stop(self) -> None:
        if self._state != TransitionState.RUNNING:
            return
        logger.debug("Stopping GLCrossfade")
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
        logger.debug("Cleaning up GLCrossfade")
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception:
                pass
            self._animation_id = None
        if self._gl:
            try:
                logger.debug("[GL XFADE] Hiding persistent GL overlay (no delete)")
                self._gl.hide()
            except Exception:
                pass
            self._gl = None
        self._widget = None
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)

    # --- internals ---
    def _on_anim_update(self, progress: float) -> None:
        if self._gl is None:
            return
        progress = max(0.0, min(1.0, progress))
        try:
            self._gl.set_alpha(progress)
            # Force immediate draw to avoid missed vsync paints causing black flashes
            self._gl.repaint()
        except Exception:
            pass
        self._emit_progress(progress)

    def _on_anim_complete(self) -> None:
        """Called when animation finishes."""
        try:
            if self._gl:
                self._gl.set_alpha(1.0)
                self._gl.update()
        except Exception:
            pass
        
        # End telemetry tracking
        self._mark_end()
        
        self._set_state(TransitionState.FINISHED)
        self.finished.emit()
        logger.debug("GLCrossfade transition finished")

    def _show_image_immediately(self) -> None:
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
            'InQuart': EasingCurve.QUART_IN,
            'OutQuart': EasingCurve.QUART_OUT,
            'InOutQuart': EasingCurve.QUART_IN_OUT,
            'InExpo': EasingCurve.EXPO_IN,
            'OutExpo': EasingCurve.EXPO_OUT,
            'InOutExpo': EasingCurve.EXPO_IN_OUT,
            'InSine': EasingCurve.SINE_IN,
            'OutSine': EasingCurve.SINE_OUT,
            'InOutSine': EasingCurve.SINE_IN_OUT,
            'InCirc': EasingCurve.CIRC_IN,
            'OutCirc': EasingCurve.CIRC_OUT,
            'InOutCirc': EasingCurve.CIRC_IN_OUT,
            'InBack': EasingCurve.BACK_IN,
            'OutBack': EasingCurve.BACK_OUT,
            'InOutBack': EasingCurve.BACK_IN_OUT,
        }
        return mapping.get(name, EasingCurve.QUAD_IN_OUT)
