"""
Widget Pixel Shift Manager for burn-in prevention.

Provides subtle periodic movement of overlay widgets to prevent static elements
from causing burn-in on older LCD displays. The shift is designed to be
imperceptible while still providing protection.

Features:
- Coordinated shifting of all overlay widgets
- Maximum drift of 4px in any direction
- Automatic drift-back when hitting boundaries
- Configurable shift rate (1-5 shifts per minute)
- Deferred execution to avoid interfering with transitions/fades
"""
from typing import Optional, List, Callable
import random

from PySide6.QtCore import QTimer, QPoint
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from core.threading.manager import ThreadManager

logger = get_logger(__name__)


class PixelShiftManager:
    """Manages periodic pixel shifting of overlay widgets for burn-in prevention.
    
    The manager maintains a global offset that is applied to all registered
    widgets. The offset drifts randomly by 1px at a time, up to a maximum
    of 4px in any direction, then drifts back toward center.
    """
    
    # Maximum drift in any direction (pixels)
    MAX_DRIFT = 4
    
    def __init__(
        self,
        resource_manager: Optional[ResourceManager] = None,
        thread_manager: Optional[ThreadManager] = None,
    ) -> None:
        """
        Initialize the pixel shift manager.
        
        Args:
            resource_manager: Optional ResourceManager for timer lifecycle
        """
        self._resource_manager = resource_manager
        self._thread_manager = thread_manager
        self._enabled = False
        self._shifts_per_minute = 1
        self._timer: Optional[QTimer] = None
        self._timer_resource_id: Optional[str] = None
        
        # Current drift offset from original positions
        self._offset_x = 0
        self._offset_y = 0
        
        # Original widget positions (widget -> QPoint)
        self._original_positions: dict[int, QPoint] = {}
        
        # Registered widgets (weak references would be better, but we'll
        # clean up on stop)
        self._widgets: List[QWidget] = []
        
        # Callback to check if we should defer shifting (e.g., during transitions)
        self._defer_check: Optional[Callable[[], bool]] = None
        
        logger.debug("PixelShiftManager created")
    
    def set_thread_manager(self, thread_manager: ThreadManager) -> None:
        """Inject the shared ThreadManager for timer scheduling."""
        self._thread_manager = thread_manager

    def _require_thread_manager(self) -> ThreadManager:
        """Ensure we have a ThreadManager before scheduling timers."""
        if self._thread_manager is None:
            raise RuntimeError("PixelShiftManager requires a ThreadManager before enabling shifts.")
        return self._thread_manager

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable pixel shifting."""
        if enabled == self._enabled:
            return
        
        self._enabled = enabled
        if enabled:
            self._start_timer()
            logger.debug("PixelShiftManager enabled (rate=%d/min)", self._shifts_per_minute)
        else:
            self._stop_timer()
            self._reset_positions()
            logger.debug("PixelShiftManager disabled")
    
    def is_enabled(self) -> bool:
        """Check if pixel shifting is enabled."""
        return self._enabled
    
    def set_shifts_per_minute(self, rate: int) -> None:
        """Set the shift rate (1-5 shifts per minute)."""
        rate = max(1, min(5, rate))
        if rate != self._shifts_per_minute:
            self._shifts_per_minute = rate
            if self._enabled:
                # Restart timer with new interval
                self._stop_timer()
                self._start_timer()
            logger.debug("PixelShiftManager rate set to %d/min", rate)
    
    def get_shifts_per_minute(self) -> int:
        """Get the current shift rate."""
        return self._shifts_per_minute
    
    def set_defer_check(self, check: Optional[Callable[[], bool]]) -> None:
        """Set a callback to check if shifting should be deferred.
        
        The callback should return True if shifting should be deferred
        (e.g., during a transition).
        """
        self._defer_check = check
    
    def register_widget(self, widget: QWidget) -> None:
        """Register a widget for pixel shifting.
        
        The widget's current position is stored as its original position.
        Note: Registration does NOT move the widget - only _apply_offset does,
        and that only runs when enabled and the timer fires.
        """
        if widget is None:
            return
        
        widget_id = id(widget)
        if widget_id in self._original_positions:
            # Already registered
            return
        
        try:
            pos = widget.pos()
            self._original_positions[widget_id] = QPoint(pos.x(), pos.y())
            if widget not in self._widgets:
                self._widgets.append(widget)
            logger.debug("Registered widget for pixel shift: %s at (%d, %d) [enabled=%s]",
                        widget.__class__.__name__, pos.x(), pos.y(), self._enabled)
        except Exception:
            pass
    
    def unregister_widget(self, widget: QWidget) -> None:
        """Unregister a widget from pixel shifting."""
        if widget is None:
            return
        
        widget_id = id(widget)
        if widget_id in self._original_positions:
            try:
                orig = self._original_positions[widget_id]
                widget.move(orig)
            except Exception:
                pass
            del self._original_positions[widget_id]
        
        if widget in self._widgets:
            self._widgets.remove(widget)
    
    def _require_thread_manager(self) -> ThreadManager:
        if self._thread_manager is None:
            raise RuntimeError("PixelShiftManager requires a ThreadManager before enabling shifts.")
        return self._thread_manager
    
    def update_original_position(self, widget: QWidget) -> None:
        """Update the stored original position for a widget.
        
        Call this after a widget has been repositioned (e.g., after resize).
        The new position should be the widget's current position minus the
        current offset.
        """
        if widget is None:
            return
        
        widget_id = id(widget)
        try:
            pos = widget.pos()
            # Subtract current offset to get the "original" position
            orig_x = pos.x() - self._offset_x
            orig_y = pos.y() - self._offset_y
            self._original_positions[widget_id] = QPoint(orig_x, orig_y)
        except Exception:
            pass
    
    def get_current_offset(self) -> tuple[int, int]:
        """Get the current drift offset (x, y)."""
        return (self._offset_x, self._offset_y)
    
    def cleanup(self) -> None:
        """Clean up resources and reset all widgets to original positions."""
        self._stop_timer()
        self._reset_positions()
        self._widgets.clear()
        self._original_positions.clear()
        logger.debug("PixelShiftManager cleaned up")
    
    def _start_timer(self) -> None:
        """Start the shift timer."""
        if self._timer is not None:
            return
        
        # Calculate interval: shifts_per_minute -> milliseconds between shifts
        interval_ms = int(60000 / self._shifts_per_minute)
        
        tm = self._require_thread_manager()
        self._timer = tm.schedule_recurring(interval_ms, self._on_shift_tick)
        
        if self._resource_manager is not None:
            try:
                self._timer_resource_id = self._resource_manager.register_qt(
                    self._timer,
                    description="PixelShiftManager timer",
                )
            except Exception:
                pass
        
        logger.debug("PixelShiftManager timer started (interval=%dms)", interval_ms)
    
    def _stop_timer(self) -> None:
        """Stop the shift timer."""
        if self._timer is None:
            return
        
        try:
            self._timer.stop()
        except Exception:
            pass
        
        if self._timer_resource_id and self._resource_manager:
            try:
                self._resource_manager.unregister(self._timer_resource_id, force=True)
            except Exception:
                pass
            self._timer_resource_id = None
        
        try:
            self._timer.deleteLater()
        except Exception:
            pass
        self._timer = None
        
        logger.debug("PixelShiftManager timer stopped")
    
    def _on_shift_tick(self) -> None:
        """Handle a shift tick - move all widgets by 1px."""
        if not self._enabled:
            return
        
        # Check if we should defer (e.g., during transitions)
        if self._defer_check is not None:
            try:
                if self._defer_check():
                    logger.debug("PixelShiftManager: shift deferred")
                    return
            except Exception:
                pass
        
        # Calculate new offset
        new_x, new_y = self._calculate_next_offset()
        
        if new_x == self._offset_x and new_y == self._offset_y:
            # No change needed
            return
        
        self._offset_x = new_x
        self._offset_y = new_y
        
        # Apply offset to all registered widgets
        self._apply_offset()
        
        logger.debug("PixelShiftManager: shifted to offset (%d, %d)", new_x, new_y)
    
    def _calculate_next_offset(self) -> tuple[int, int]:
        """Calculate the next drift offset.
        
        The algorithm:
        1. If at or near max drift, bias toward drifting back
        2. Otherwise, bias toward continuing outward (away from center)
        3. Move 1px in that direction
        
        This prevents immediate shift-back by biasing toward outward movement
        until we hit the max drift boundary.
        """
        # Possible directions: up, down, left, right, and diagonals
        directions = [
            (0, -1),   # up
            (0, 1),    # down
            (-1, 0),   # left
            (1, 0),    # right
            (-1, -1),  # up-left
            (1, -1),   # up-right
            (-1, 1),   # down-left
            (1, 1),    # down-right
        ]
        
        # Calculate distance from center
        dist_x = abs(self._offset_x)
        dist_y = abs(self._offset_y)
        total_dist = dist_x + dist_y
        
        # If we're at max drift in any direction, we must drift back
        if dist_x >= self.MAX_DRIFT or dist_y >= self.MAX_DRIFT:
            # Filter directions to only those that move us back toward center
            valid_dirs = []
            for dx, dy in directions:
                new_x = self._offset_x + dx
                new_y = self._offset_y + dy
                new_dist_x = abs(new_x)
                new_dist_y = abs(new_y)
                # Only allow if it reduces distance or stays within bounds
                if new_dist_x <= self.MAX_DRIFT and new_dist_y <= self.MAX_DRIFT:
                    # Prefer directions that move toward center
                    if new_dist_x <= dist_x and new_dist_y <= dist_y:
                        valid_dirs.append((dx, dy))
            
            if not valid_dirs:
                # Fallback: just move toward center
                dx = -1 if self._offset_x > 0 else (1 if self._offset_x < 0 else 0)
                dy = -1 if self._offset_y > 0 else (1 if self._offset_y < 0 else 0)
                return (self._offset_x + dx, self._offset_y + dy)
            
            dx, dy = random.choice(valid_dirs)
            return (self._offset_x + dx, self._offset_y + dy)
        
        # Not at max drift - bias toward continuing outward (away from center)
        # This prevents immediate shift-back behavior
        outward_dirs = []
        neutral_dirs = []
        inward_dirs = []
        
        for dx, dy in directions:
            new_x = self._offset_x + dx
            new_y = self._offset_y + dy
            if abs(new_x) > self.MAX_DRIFT or abs(new_y) > self.MAX_DRIFT:
                continue  # Would exceed max drift
            
            new_dist = abs(new_x) + abs(new_y)
            if new_dist > total_dist:
                outward_dirs.append((dx, dy))
            elif new_dist == total_dist:
                neutral_dirs.append((dx, dy))
            else:
                inward_dirs.append((dx, dy))
        
        # Strongly prefer outward movement, then neutral, then inward
        # This creates a natural drift pattern that doesn't immediately reverse
        if outward_dirs:
            # 80% chance to continue outward
            if random.random() < 0.8:
                return (self._offset_x + random.choice(outward_dirs)[0],
                        self._offset_y + random.choice(outward_dirs)[1])
        
        if neutral_dirs:
            # 15% chance for neutral (perpendicular) movement
            if random.random() < 0.75:
                dx, dy = random.choice(neutral_dirs)
                return (self._offset_x + dx, self._offset_y + dy)
        
        # Only 5% chance to move inward when not at max drift
        if inward_dirs:
            dx, dy = random.choice(inward_dirs)
            return (self._offset_x + dx, self._offset_y + dy)
        
        # Fallback: stay in place
        return (self._offset_x, self._offset_y)
    
    def _apply_offset(self) -> None:
        """Apply the current offset to all registered widgets.
        
        For widgets that support apply_pixel_shift() (BaseOverlayWidget subclasses),
        we use that method so the offset is integrated into their position calculation.
        For other widgets, we move them directly.
        """
        from shiboken6 import Shiboken
        from PySide6.QtCore import QPoint
        
        # Clean up destroyed widgets - use in-place filtering to avoid list recreation
        valid_widgets = []
        for w in self._widgets:
            if w is not None:
                try:
                    if Shiboken.isValid(w):
                        valid_widgets.append(w)
                except Exception:
                    pass
        self._widgets = valid_widgets
        
        offset_point = QPoint(self._offset_x, self._offset_y)
        
        for widget in self._widgets:
            widget_id = id(widget)
            
            try:
                # Prefer apply_pixel_shift() for BaseOverlayWidget subclasses
                # This integrates the offset into their position calculation
                if hasattr(widget, 'apply_pixel_shift'):
                    widget.apply_pixel_shift(offset_point)
                elif widget_id in self._original_positions:
                    # Fallback: direct move for non-overlay widgets
                    orig = self._original_positions[widget_id]
                    new_x = orig.x() + self._offset_x
                    new_y = orig.y() + self._offset_y
                    
                    # Block signals during move to prevent flicker from layout updates
                    was_blocked = widget.signalsBlocked()
                    widget.blockSignals(True)
                    try:
                        widget.move(new_x, new_y)
                    finally:
                        widget.blockSignals(was_blocked)
            except Exception:
                # Widget may have been destroyed
                pass
    
    def _reset_positions(self) -> None:
        """Reset all widgets to their original positions."""
        from PySide6.QtCore import QPoint
        
        self._offset_x = 0
        self._offset_y = 0
        
        zero_offset = QPoint(0, 0)
        
        for widget in self._widgets:
            if widget is None:
                continue
            
            widget_id = id(widget)
            
            try:
                # Prefer apply_pixel_shift() for BaseOverlayWidget subclasses
                if hasattr(widget, 'apply_pixel_shift'):
                    widget.apply_pixel_shift(zero_offset)
                elif widget_id in self._original_positions:
                    # Fallback: direct move for non-overlay widgets
                    orig = self._original_positions[widget_id]
                    widget.move(orig)
            except Exception:
                pass
