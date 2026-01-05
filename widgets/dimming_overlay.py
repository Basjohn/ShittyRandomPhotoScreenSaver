"""
Background dimming overlay widget.

Provides a semi-transparent black overlay that sits above the wallpaper/transitions
but below all other overlay widgets. Used to reduce overall screen brightness and
improve widget readability on bright images.
"""
from typing import Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor

from core.logging.logger import get_logger
from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve

logger = get_logger(__name__)


class DimmingOverlay(QWidget):
    """Semi-transparent black overlay for background dimming.
    
    This widget renders a simple black rectangle with configurable opacity.
    It should be positioned to cover the entire display and raised above
    the compositor/transitions but below all other overlay widgets.
    """
    
    def __init__(self, parent: Optional[QWidget] = None, opacity: int = 30) -> None:
        """
        Initialize the dimming overlay.
        
        Args:
            parent: Parent widget (typically DisplayWidget)
            opacity: Opacity percentage (0-100), default 30%
        """
        super().__init__(parent)
        
        self._target_opacity = max(0, min(100, opacity))
        self._opacity = 0  # Start at 0 for fade-in
        self._enabled = False
        self._fade_animation_id: Optional[str] = None
        self._animation_manager: Optional[AnimationManager] = None
        
        # Make the widget transparent to mouse events so clicks pass through
        # to the parent DisplayWidget for proper handling
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        # For the dimming overlay, we need WA_TranslucentBackground so our
        # QPainter fillRect with alpha actually composites correctly over the
        # GL compositor. WA_StyledBackground would conflict with this.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        
        # Start hidden
        self.hide()
        
        logger.debug("DimmingOverlay created with target_opacity=%d%%", self._target_opacity)
    
    def set_opacity(self, opacity: int, animate: bool = False) -> None:
        """Set the dimming opacity percentage.
        
        Args:
            opacity: Opacity percentage (0-100)
            animate: If True, animate to the new opacity
        """
        new_opacity = max(0, min(100, opacity))
        self._target_opacity = new_opacity
        if animate and self._enabled and self.isVisible():
            self._start_fade_animation(new_opacity)
        elif new_opacity != self._opacity:
            self._opacity = new_opacity
            if self._enabled and self.isVisible():
                self.update()
            logger.debug("DimmingOverlay opacity set to %d%%", self._opacity)
    
    def get_opacity(self) -> int:
        """Get the current dimming opacity percentage."""
        return self._opacity
    
    def set_enabled(self, enabled: bool, fade_in: bool = False) -> None:
        """Enable or disable the dimming overlay.
        
        Args:
            enabled: True to show the overlay, False to hide it
            fade_in: If True and enabling, fade in gently instead of instant show
        
        NOTE: This widget-based dimming overlay is DEPRECATED. The GL compositor
        now handles dimming directly in the shader pipeline for proper compositing.
        This widget remains for fallback/compatibility but should not be used
        when the GL compositor is active.
        """
        # Guard against redundant enable calls
        if enabled and self._enabled and self.isVisible():
            logger.debug("DimmingOverlay already enabled and visible, skipping")
            return
            
        self._enabled = enabled
        if enabled:
            self._opacity = self._target_opacity
            self.show()
            self.update()
        else:
            self._stop_fade_animation()
            self.hide()
        logger.debug("DimmingOverlay enabled=%s, opacity=%d%%", enabled, self._opacity)
    
    def is_enabled(self) -> bool:
        """Check if the dimming overlay is enabled."""
        return self._enabled
    
    def update_geometry(self) -> None:
        """Update the overlay geometry to match the parent widget EXACTLY."""
        parent = self.parent()
        if parent is not None:
            try:
                # Cover the entire parent - NO pixel reduction!
                # The old -1px workaround caused visible gaps at screen bottom.
                w = parent.width()
                h = parent.height()
                self.setGeometry(0, 0, w, h)
            except Exception as e:
                logger.debug("[DIMMING] Exception suppressed: %s", e)
    
    def _get_animation_manager(self) -> Optional[AnimationManager]:
        """Get or create AnimationManager instance."""
        if self._animation_manager is None:
            try:
                self._animation_manager = AnimationManager()
            except Exception as e:
                logger.debug("[DIMMING] Exception suppressed: %s", e)
        return self._animation_manager

    def _start_fade_animation(self, target_opacity: int) -> None:
        """Start a fade animation to the target opacity using AnimationManager."""
        self._stop_fade_animation()
        
        manager = self._get_animation_manager()
        if manager is None:
            # Fallback: set opacity directly if AnimationManager unavailable
            self._opacity = target_opacity
            self.update()
            return
        
        start_opacity = self._opacity
        duration_sec = 0.8  # 800ms fade - gentle and coordinated with widget fades
        
        def on_update(progress: float) -> None:
            try:
                # Interpolate opacity based on progress
                self._opacity = int(start_opacity + (target_opacity - start_opacity) * progress)
                self.update()
            except Exception as e:
                logger.debug("[DIMMING] Exception suppressed: %s", e)
        
        def on_complete() -> None:
            self._opacity = target_opacity
            self._fade_animation_id = None
            self.update()
            logger.debug("DimmingOverlay fade complete, opacity=%d%%", self._opacity)
        
        try:
            self._fade_animation_id = manager.animate_custom(
                duration=duration_sec,
                update_callback=on_update,
                easing=EasingCurve.OUT_QUAD,
                on_complete=on_complete
            )
            logger.debug("DimmingOverlay starting fade: %d%% → %d%%", start_opacity, target_opacity)
        except Exception as e:
            logger.warning("Failed to start fade animation: %s", e)
            # Fallback: set opacity directly
            self._opacity = target_opacity
            self.update()
    
    def _stop_fade_animation(self) -> None:
        """Stop any running fade animation."""
        if self._fade_animation_id is not None:
            manager = self._get_animation_manager()
            if manager is not None:
                try:
                    manager.cancel_animation(self._fade_animation_id)
                except Exception as e:
                    logger.debug("[DIMMING] Exception suppressed: %s", e)
            self._fade_animation_id = None
    
    def paintEvent(self, event) -> None:  # type: ignore[override]
        """Paint the dimming overlay.
        
        NOTE: This widget-based overlay is DEPRECATED. The GL compositor now
        handles dimming directly in the shader pipeline for proper compositing.
        """
        if not self._enabled:
            return
        
        painter = QPainter(self)
        try:
            alpha = int((self._opacity / 100.0) * 255)
            color = QColor(0, 0, 0, alpha)
            painter.fillRect(self.rect(), color)
        finally:
            painter.end()
    
    def showEvent(self, event) -> None:  # type: ignore[override]
        """Handle show event - update geometry."""
        super().showEvent(event)
        self.update_geometry()
    
    def resizeEvent(self, event) -> None:  # type: ignore[override]
        """Handle resize event - update geometry."""
        super().resizeEvent(event)
        # Geometry is managed by parent, but ensure we fill it
        self.update_geometry()
