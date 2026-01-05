"""
Wipe transition effect.

Reveals new image progressively using a widget mask on the new image label.
No per-frame pixmap compositing to avoid DPR/size mismatches.
"""
from typing import Optional
from enum import Enum
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QRegion
from transitions.base_transition import BaseTransition, TransitionState
from core.animation.types import EasingCurve
from core.logging.logger import get_logger

logger = get_logger(__name__)


class WipeDirection(Enum):
    """Wipe direction options."""
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    TOP_TO_BOTTOM = "top_to_bottom"
    BOTTOM_TO_TOP = "bottom_to_top"
    DIAG_TL_BR = "diag_tl_br"  # Top-left to bottom-right
    DIAG_TR_BL = "diag_tr_bl"  # Top-right to bottom-left


def _compute_wipe_region(direction: WipeDirection, w: int, h: int, progress: float) -> QRegion:
    """Compute the QRegion used for wipe reveal based on direction and progress.

    This helper is shared between the CPU WipeTransition and the GL compositor
    wipe path to keep visual behaviour identical.
    """

    from PySide6.QtGui import QPolygon
    from PySide6.QtCore import QPoint

    p = max(0.0, min(1.0, float(progress)))

    if direction == WipeDirection.LEFT_TO_RIGHT:
        rw = int(w * p)
        return QRegion(0, 0, rw, h)
    if direction == WipeDirection.RIGHT_TO_LEFT:
        x = int(w * (1.0 - p))
        return QRegion(x, 0, w - x, h)
    if direction == WipeDirection.TOP_TO_BOTTOM:
        rh = int(h * p)
        return QRegion(0, 0, w, rh)
    if direction == WipeDirection.BOTTOM_TO_TOP:
        y = int(h * (1.0 - p))
        return QRegion(0, y, w, h - y)

    if direction == WipeDirection.DIAG_TL_BR:
        # Top-left to bottom-right diagonal
        diag = int((w + h) * p)
        if diag <= 0:
            return QRegion()
        if diag >= w + h:
            # Complete
            return QRegion(0, 0, w, h)
        if diag > max(w, h):
            # Both edges reached - pentagon shape
            points = [
                QPoint(0, 0),
                QPoint(w, 0),
                QPoint(w, diag - w),
                QPoint(diag - h, h),
                QPoint(0, h),
            ]
            return QRegion(QPolygon(points))
        if diag > min(w, h):
            # One edge reached - quadrilateral
            if w < h:
                # Right edge reached first
                points = [QPoint(0, 0), QPoint(w, 0), QPoint(w, diag - w), QPoint(0, diag)]
            else:
                # Bottom edge reached first
                points = [QPoint(0, 0), QPoint(diag, 0), QPoint(diag - h, h), QPoint(0, h)]
            return QRegion(QPolygon(points))
        # Initial triangle from corner
        points = [QPoint(0, 0), QPoint(diag, 0), QPoint(0, diag)]
        return QRegion(QPolygon(points))

    if direction == WipeDirection.DIAG_TR_BL:
        # Top-right to bottom-left diagonal
        diag = int((w + h) * p)
        if diag <= 0:
            return QRegion()
        if diag >= w + h:
            # Complete
            return QRegion(0, 0, w, h)
        if diag > max(w, h):
            # Both edges reached - pentagon shape
            points = [
                QPoint(w, 0),
                QPoint(0, 0),
                QPoint(0, diag - w),
                QPoint(w - (diag - h), h),
                QPoint(w, h),
            ]
            return QRegion(QPolygon(points))
        if diag > min(w, h):
            # One edge reached - quadrilateral
            if w < h:
                # Left edge reached first
                points = [QPoint(w, 0), QPoint(0, 0), QPoint(0, diag - w), QPoint(w, diag)]
            else:
                # Bottom edge reached first
                points = [QPoint(w, 0), QPoint(w - diag, 0), QPoint(w - (diag - h), h), QPoint(w, h)]
            return QRegion(QPolygon(points))
        # Initial triangle from corner
        points = [QPoint(w, 0), QPoint(w - diag, 0), QPoint(w, diag)]
        return QRegion(QPolygon(points))

    # Fallback
    rw = int(w * p)
    return QRegion(0, 0, rw, h)


class WipeTransition(BaseTransition):
    """
    Wipe/Reveal transition effect.
    
    Progressively reveals the new image as an invisible line
    moves across the screen. The reveal speed is determined by duration.
    """
    
    def __init__(self, duration_ms: int = 1000, direction: WipeDirection = WipeDirection.LEFT_TO_RIGHT, easing: str = 'Auto'):
        """
        Initialize wipe transition.
        
        Args:
            duration_ms: Duration in milliseconds
            direction: Wipe direction
        """
        super().__init__(duration_ms)
        
        self._duration_ms = duration_ms
        self._direction = direction
        self._easing_str = easing
        self._old_label: Optional[QLabel] = None
        self._new_label: Optional[QLabel] = None
        self._animation_id: Optional[str] = None
        self._widget: Optional[QWidget] = None
        self._old_pixmap: Optional[QPixmap] = None
        self._new_pixmap: Optional[QPixmap] = None
        self._elapsed_ms = 0
        self._fps = 60
        
        logger.debug(f"WipeTransition created (duration={duration_ms}ms, direction={direction.value})")
    
    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, 
              widget: QWidget) -> bool:
        """
        Start wipe transition.
        
        Args:
            old_pixmap: Previous image (can be None)
            new_pixmap: New image to display
            widget: Parent widget for display
        
        Returns:
            True if transition started successfully
        """
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid new pixmap")
            self.error.emit("Invalid image")
            return False
        
        # Pre-fit pixmaps to widget size (device pixels) for caching and fidelity.
        # Pan & Scan preview alignment has been removed; both old and new use
        # the standard fitted frames.
        fitted_old = self._fit_pixmap_to_widget(old_pixmap, widget) if old_pixmap and not old_pixmap.isNull() else None
        fitted_new = self._fit_pixmap_to_widget(new_pixmap, widget)
        self._old_pixmap = fitted_old if fitted_old is not None else old_pixmap
        self._new_pixmap = fitted_new
        self._elapsed_ms = 0
        self._widget = widget
        
        # If no old image, show immediately
        if not old_pixmap or old_pixmap.isNull():
            self._show_image_immediately(widget)
            return True
        
        # Begin telemetry tracking for animated wipe
        self._mark_start()

        # Two-label pattern (like Crossfade): old below, new above with mask
        self._old_label = QLabel(widget)
        self._old_label.setGeometry(0, 0, widget.width(), widget.height())
        self._old_label.setScaledContents(False)
        self._old_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._old_label.setStyleSheet("background: transparent;")
        self._old_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if self._old_pixmap:
            self._old_label.setPixmap(self._old_pixmap)
        self._old_label.show()
        if self._resource_manager:
            try:
                self._resource_manager.register_qt(self._old_label, description="WipeTransition old label")
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)

        self._new_label = QLabel(widget)
        self._new_label.setGeometry(0, 0, widget.width(), widget.height())
        self._new_label.setScaledContents(False)
        self._new_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._new_label.setStyleSheet("background: transparent;")
        self._new_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._new_label.setPixmap(self._new_pixmap)
        # Start fully hidden (no show yet); apply empty mask
        self._new_label.setMask(QRegion())
        try:
            self._new_label.raise_()
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
        if self._resource_manager:
            try:
                self._resource_manager.register_qt(self._new_label, description="WipeTransition new label")
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)
        
        # Drive animation via centralized AnimationManager
        am = self._get_animation_manager(widget)
        duration_sec = max(0.001, self._duration_ms / 1000.0)
        self._animation_id = am.animate_custom(
            duration=duration_sec,
            easing=self._resolve_easing(),
            update_callback=lambda p: self._on_anim_update(p),
            on_complete=lambda: self._finish_transition(),
        )
        
        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        
        logger.info(f"Wipe transition started (direction={self._direction.value})")
        return True
    
    def stop(self) -> None:
        """Stop the transition."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Stopping wipe transition")
        
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)
            self._animation_id = None
        
        self._set_state(TransitionState.CANCELLED)
    
    def cleanup(self) -> None:
        """Clean up transition resources."""
        logger.debug("Cleaning up wipe transition")
        
        self.stop()
        
        if self._new_label:
            try:
                self._new_label.deleteLater()
            except RuntimeError:
                pass
            self._new_label = None

        if self._old_label:
            try:
                self._old_label.deleteLater()
            except RuntimeError:
                pass
            self._old_label = None
        
        self._old_pixmap = None
        self._new_pixmap = None
    
    def _on_anim_update(self, progress: float) -> None:
        if not self._new_label or not self._widget:
            return
        w = self._widget.width()
        h = self._widget.height()
        region = _compute_wipe_region(self._direction, w, h, progress)

        try:
            # Show only when region is non-empty to avoid pre-mask flash
            if (not self._new_label.isVisible()) and (not region.isEmpty()):
                self._new_label.show()
            self._new_label.setMask(region)
        except RuntimeError:
            return
        self._emit_progress(progress)
    
    def _compose_wipe_frame(self, progress: float, fitted_old: QPixmap, fitted_new: QPixmap) -> QPixmap:
        # Deprecated path retained for compatibility; not used in new implementation
        return fitted_new
    
    def _finish_transition(self) -> None:
        """Finish the transition."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Wipe transition finished")
        
        # Cancel central animation if active
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)
            self._animation_id = None
        
        # Clear mask and ensure new label fully visible before finishing
        if self._new_label:
            try:
                self._new_label.clearMask()
            except RuntimeError:
                pass
        
        # End telemetry tracking for successful completion
        self._mark_end()
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
    
    def _show_image_immediately(self, widget: QWidget) -> None:
        """Show new image immediately without transition."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("Image shown immediately (no old image)")
    
    def set_direction(self, direction: WipeDirection) -> None:
        """
        Set wipe direction.
        
        Args:
            direction: Wipe direction
        """
        self._direction = direction
        logger.debug(f"Wipe direction set to {direction.value}")
    
    def _resolve_easing(self) -> EasingCurve:
        """Map UI easing string to core EasingCurve with 'Auto' default."""
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
    
    def set_duration(self, duration_ms: int) -> None:
        """
        Set transition duration.
        
        Args:
            duration_ms: Duration in milliseconds
        """
        if duration_ms <= 0:
            logger.warning(f"[FALLBACK] Invalid duration {duration_ms}ms, using 1000ms")
            duration_ms = 1000
        
        self._duration_ms = duration_ms
        logger.debug(f"Duration set to {duration_ms}ms")
