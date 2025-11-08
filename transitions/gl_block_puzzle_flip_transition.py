"""
GL Block Puzzle Flip transition - OpenGL-backed block reveal.

Approximates the CPU Block Puzzle Flip by revealing per-block rectangles
horizontally from center (flip simulation) using a persistent QOpenGLWidget
overlay. Animation timing is driven by the centralized AnimationManager.
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


class _GLFlipBlock:
    def __init__(self, rect: QRect):
        self.rect = rect
        self.flip_progress = 0.0
        self.started = False
        self.is_complete = False
        self.start_threshold = random.random()


class _GLBlockFlipWidget(QOpenGLWidget):
    def __init__(self, parent: QWidget, old_pixmap: QPixmap, new_pixmap: QPixmap, blocks: List[_GLFlipBlock]):
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
        self._blocks: List[_GLFlipBlock] = blocks
        self._region: QRegion = QRegion()
        
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
            # Draw old fully
            if self._old and not self._old.isNull():
                p.setOpacity(1.0)
                p.drawPixmap(target, self._old)
            # Clip and draw new according to region
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
                logger.debug("[GL BLOCK] First frame drawn, overlay ready")
            self._has_drawn = True


class GLBlockPuzzleFlipTransition(BaseTransition):
    """OpenGL-backed Block Puzzle Flip transition (approximation)."""

    def __init__(self, duration_ms: int = 3000, grid_rows: int = 4, grid_cols: int = 6, flip_duration_ms: int = 500):
        super().__init__(duration_ms)
        self._grid_rows = grid_rows
        self._grid_cols = grid_cols
        self._flip_duration_ms = flip_duration_ms
        self._widget: Optional[QWidget] = None
        self._old_pixmap: Optional[QPixmap] = None
        self._new_pixmap: Optional[QPixmap] = None
        self._blocks: List[_GLFlipBlock] = []
        self._flip_order: List[int] = []
        self._animation_id: Optional[str] = None
        self._gl: Optional[_GLBlockFlipWidget] = None
        self._total_duration_ms: int = duration_ms
        self._total_dur_sec: float = max(0.001, duration_ms / 1000.0)
        self._last_progress: float = 0.0
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
            logger.error("Invalid pixmap for GL Block Puzzle Flip")
            self.error.emit("Invalid image")
            return False
        try:
            self._widget = widget
            self._new_pixmap = new_pixmap
            self._old_pixmap = old_pixmap
            if not old_pixmap or old_pixmap.isNull():
                logger.debug("No old image, showing new image immediately (GL BlockFlip)")
                self._show_image_immediately()
                return True

            w, h = widget.width(), widget.height()
            self._create_block_grid(w, h)
            total_blocks = len(self._blocks)
            self._flip_order = list(range(total_blocks))
            random.shuffle(self._flip_order)

            overlay = getattr(widget, "_srpss_gl_blockflip_overlay", None)
            if overlay is None or not isinstance(overlay, _GLBlockFlipWidget):
                logger.debug("[GL BLOCK] Creating persistent GL overlay")
                overlay = _GLBlockFlipWidget(widget, old_pixmap, new_pixmap, self._blocks)
                overlay.setGeometry(0, 0, w, h)
                setattr(widget, "_srpss_gl_blockflip_overlay", overlay)
                if getattr(self, "_resources", None):
                    try:
                        self._resources.register_qt(overlay, description="GL BlockFlip persistent overlay")
                    except Exception:
                        pass
            else:
                logger.debug("[GL BLOCK] Reusing persistent GL overlay")
                overlay.set_images(old_pixmap, new_pixmap)
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
                logger.debug("[GL BLOCK] Prepainted initial frame (empty region)")
            except Exception:
                pass
            try:
                self._gl.repaint()
            except Exception:
                pass

            # Two-phase timeline similar to CPU: total duration includes drain
            self._total_duration_ms = max(1, int(self.duration_ms + self._flip_duration_ms))
            self._total_dur_sec = max(0.001, self._total_duration_ms / 1000.0)
            self._last_progress = 0.0

            am = self._get_animation_manager(widget)
            self._animation_id = am.animate_custom(
                duration=self._total_dur_sec,
                easing=EasingCurve.LINEAR,
                update_callback=lambda p, total=total_blocks: self._on_anim_update(p, total),
                on_complete=lambda: self._on_anim_complete(),
            )

            self._set_state(TransitionState.RUNNING)
            self.started.emit()
            logger.info(f"GL Block puzzle flip started ({self.duration_ms}ms, {total_blocks} blocks)")
            return True
        except Exception as e:
            logger.exception(f"Failed to start GL BlockFlip: {e}")
            self.error.emit(f"Transition failed: {e}")
            self.cleanup()
            return False

    def stop(self) -> None:
        if self._state != TransitionState.RUNNING:
            return
        logger.debug("Stopping GL BlockFlip")
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
        logger.debug("Cleaning up GL BlockFlip")
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
        self._blocks = []
        self._flip_order = []
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)

    # Internals
    def _create_block_grid(self, width: int, height: int) -> None:
        self._blocks = []
        
        # Calculate square blocks based on aspect ratio
        # Use cols as base (doubled for more blocks), calculate rows to maintain square aspect
        base_cols = self._grid_cols * 2  # Double the blocks
        aspect_ratio = height / max(1, width)
        calculated_rows = max(2, int(round(base_cols * aspect_ratio)))
        
        # Use calculated rows for square blocks
        effective_rows = calculated_rows
        effective_cols = base_cols
        
        logger.debug(f"[GL BLOCK] Grid: {effective_cols}x{effective_rows} (aspect={aspect_ratio:.2f}, square blocks)")
        
        block_width = max(1, width // effective_cols)
        block_height = max(1, height // effective_rows)
        
        for row in range(effective_rows):
            for col in range(effective_cols):
                x = col * block_width
                y = row * block_height
                w = block_width if col < effective_cols - 1 else (width - x)
                h = block_height if row < effective_rows - 1 else (height - y)
                self._blocks.append(_GLFlipBlock(QRect(x, y, w, h)))

    def _on_anim_update(self, progress: float, total_blocks: int) -> None:
        if self._state != TransitionState.RUNNING or self._gl is None:
            return
        progress = max(0.0, min(1.0, progress))
        total_ms = max(1, getattr(self, "_total_duration_ms", self.duration_ms))
        t_ms = progress * total_ms
        start_phase_progress = min(1.0, t_ms / max(1, self.duration_ms))
        # Start new flips based on randomized threshold
        for block in self._blocks:
            if not block.started and start_phase_progress >= block.start_threshold:
                block.started = True
        # Advance flip progress
        delta = progress - getattr(self, "_last_progress", 0.0)
        self._last_progress = progress
        if delta < 0:
            delta = 0
        delta_sec = delta * max(0.001, getattr(self, "_total_dur_sec", self.duration_ms / 1000.0))
        flip_dur_sec = max(0.001, self._flip_duration_ms / 1000.0)
        inc = delta_sec / flip_dur_sec
        all_complete = True
        completed_count = 0
        for block in self._blocks:
            if block.started and not block.is_complete:
                block.flip_progress += inc
                if block.flip_progress >= 1.0:
                    block.flip_progress = 1.0
                    block.is_complete = True
            if not block.is_complete:
                all_complete = False
            else:
                completed_count += 1
        # Build union region for revealed areas
        region = QRegion()
        for block in self._blocks:
            p = max(0.0, min(1.0, block.flip_progress))
            if p <= 0.0:
                continue
            r = block.rect
            reveal_w = max(1, int(r.width() * p))
            dx = r.x() + (r.width() - reveal_w) // 2
            reveal_rect = QRect(dx, r.y(), reveal_w, r.height())
            region = region.united(QRegion(reveal_rect))
        try:
            self._gl.set_region(region)
            self._gl.repaint()
        except Exception:
            pass
        if total_blocks > 0:
            self._emit_progress(0.5 + (completed_count / total_blocks) * 0.5)
        if progress >= 1.0 or all_complete:
            self._on_anim_complete()

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
