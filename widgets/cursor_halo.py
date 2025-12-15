"""
Cursor halo widget for Ctrl-click interaction mode.

Provides a visual indicator (ring + dot) that follows the cursor when
Ctrl is held, allowing users to interact with widgets without triggering
the screensaver exit.
"""
from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPaintEvent

from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve
from core.logging.logger import get_logger

logger = get_logger(__name__)


class CursorHaloWidget(QWidget):
    """
    Visual cursor indicator for Ctrl-held interaction mode.
    
    Displays a semi-transparent ring with a center dot that follows
    the cursor position. Supports fade-in/fade-out animations.
    """
    
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # WA_TranslucentBackground is REQUIRED for true transparency.
        # The halo must be raised ABOVE the dimming overlay via Z-order,
        # not by using opaque widget attributes.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.resize(40, 40)
        self._opacity = 1.0
        self._animation_id: Optional[str] = None

    def setOpacity(self, value: float) -> None:
        """Set the halo opacity (0.0 to 1.0)."""
        try:
            self._opacity = max(0.0, min(1.0, float(value)))
        except Exception:
            self._opacity = 1.0
        self.update()

    def opacity(self) -> float:
        """Get the current opacity."""
        return float(self._opacity)

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        """Paint the halo ring and center dot."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        try:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        except Exception:
            pass

        base_alpha = 200
        alpha = int(max(0.0, min(1.0, self._opacity)) * base_alpha)
        color = QColor(255, 255, 255, alpha)

        # Thicker outer ring
        pen = painter.pen()
        pen.setColor(color)
        pen.setWidth(4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        r = min(self.width(), self.height()) - 8
        painter.drawEllipse(4, 4, r, r)

        # Inner solid dot to suggest the click position
        inner_radius = max(2, r // 6)
        cx = self.width() // 2
        cy = self.height() // 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(cx - inner_radius, cy - inner_radius, inner_radius * 2, inner_radius * 2)
        painter.end()
    
    def cancel_animation(self) -> None:
        """Cancel any running fade animation."""
        if self._animation_id is not None:
            try:
                manager = AnimationManager()
                manager.cancel_animation(self._animation_id)
            except Exception:
                pass
            self._animation_id = None
    
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
                self.setOpacity(0.0)
            else:
                self.setOpacity(1.0)
        except Exception:
            pass

        duration_ms = 600 if fade_in else 1200
        start_val = 0.0 if fade_in else 1.0
        end_val = 1.0 if fade_in else 0.0
        
        def _on_tick(progress: float) -> None:
            try:
                value = start_val + (end_val - start_val) * progress
                self.setOpacity(float(value))
            except Exception:
                pass

        def _on_anim_finished() -> None:
            if not fade_in:
                try:
                    self.hide()
                except Exception:
                    pass
            try:
                self.setWindowOpacity(1.0)
            except Exception:
                pass
            self._animation_id = None
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    pass

        try:
            manager = AnimationManager()
            # AnimationManager uses seconds, not milliseconds
            duration_sec = duration_ms / 1000.0
            self._animation_id = manager.animate_custom(
                duration=duration_sec,
                update_callback=_on_tick,
                on_complete=_on_anim_finished,
                easing=EasingCurve.QUAD_OUT,
            )
        except Exception:
            logger.debug("Failed to start halo animation via AnimationManager", exc_info=True)
    
    def show_at(self, x: int, y: int) -> None:
        """Show the halo centered at the given position."""
        size = self.size()
        self.move(x - size.width() // 2, y - size.height() // 2)
        self.show()
        self.raise_()
