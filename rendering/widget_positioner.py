"""
Widget Positioner - Centralized widget positioning logic.

Extracted from WidgetManager to provide:
- Standard position calculations for all overlay widgets
- Multi-monitor positioning support
- Collision detection and avoidance
- Stacking logic for widgets at the same position
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple, TYPE_CHECKING

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class PositionAnchor(Enum):
    """Anchor point for widget positioning."""
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


@dataclass
class PositionConfig:
    """Configuration for widget positioning."""
    anchor: PositionAnchor
    margin_x: int = 20
    margin_y: int = 20
    stack_offset: QPoint = None
    
    def __post_init__(self):
        if self.stack_offset is None:
            self.stack_offset = QPoint(0, 0)


@dataclass
class WidgetBounds:
    """Bounds information for a widget."""
    widget: QWidget
    name: str
    rect: QRect
    anchor: PositionAnchor
    
    @property
    def center(self) -> QPoint:
        return self.rect.center()
    
    @property
    def size(self) -> QSize:
        return self.rect.size()


class WidgetPositioner:
    """
    Centralized widget positioning logic.
    
    Responsibilities:
    - Calculate widget positions based on anchor and margins
    - Handle multi-monitor positioning
    - Detect and resolve widget collisions
    - Apply stacking offsets for widgets at the same position
    """
    
    # Default spacing between stacked widgets
    DEFAULT_STACK_SPACING = 10
    
    def __init__(self, container_size: QSize = None):
        """
        Initialize the WidgetPositioner.
        
        Args:
            container_size: Size of the container (screen/window)
        """
        self._container_size = container_size or QSize(1920, 1080)
        self._widget_bounds: Dict[str, WidgetBounds] = {}
    
    def set_container_size(self, size: QSize) -> None:
        """Set the container size for positioning calculations."""
        self._container_size = size
    
    def calculate_position(
        self,
        widget_size: QSize,
        anchor: PositionAnchor,
        margin_x: int = 20,
        margin_y: int = 20,
        stack_offset: QPoint = None,
    ) -> QPoint:
        """
        Calculate widget position based on anchor and margins.
        
        Args:
            widget_size: Size of the widget
            anchor: Position anchor (e.g., TOP_LEFT, BOTTOM_RIGHT)
            margin_x: Horizontal margin from screen edge
            margin_y: Vertical margin from screen edge
            stack_offset: Additional offset for stacking
            
        Returns:
            Calculated position as QPoint
        """
        if stack_offset is None:
            stack_offset = QPoint(0, 0)
        
        container_w = self._container_size.width()
        container_h = self._container_size.height()
        widget_w = widget_size.width()
        widget_h = widget_size.height()
        
        # Calculate base position based on anchor
        if anchor in (PositionAnchor.TOP_LEFT, PositionAnchor.MIDDLE_LEFT, PositionAnchor.BOTTOM_LEFT):
            x = margin_x
        elif anchor in (PositionAnchor.TOP_CENTER, PositionAnchor.CENTER, PositionAnchor.BOTTOM_CENTER):
            x = (container_w - widget_w) // 2
        else:  # RIGHT
            x = container_w - widget_w - margin_x
        
        if anchor in (PositionAnchor.TOP_LEFT, PositionAnchor.TOP_CENTER, PositionAnchor.TOP_RIGHT):
            y = margin_y
        elif anchor in (PositionAnchor.MIDDLE_LEFT, PositionAnchor.CENTER, PositionAnchor.MIDDLE_RIGHT):
            y = (container_h - widget_h) // 2
        else:  # BOTTOM
            y = container_h - widget_h - margin_y
        
        # Apply stack offset
        x += stack_offset.x()
        y += stack_offset.y()
        
        # Clamp to container bounds
        x = max(0, min(x, container_w - widget_w))
        y = max(0, min(y, container_h - widget_h))
        
        return QPoint(x, y)
    
    def position_widget(
        self,
        widget: QWidget,
        anchor: PositionAnchor,
        margin_x: int = 20,
        margin_y: int = 20,
        stack_offset: QPoint = None,
    ) -> QRect:
        """
        Position a widget based on anchor and margins.
        
        Args:
            widget: Widget to position
            anchor: Position anchor
            margin_x: Horizontal margin
            margin_y: Vertical margin
            stack_offset: Additional offset for stacking
            
        Returns:
            Final geometry as QRect
        """
        widget_size = widget.sizeHint()
        if not widget_size.isValid() or widget_size.width() <= 0:
            widget_size = widget.size()
        
        pos = self.calculate_position(widget_size, anchor, margin_x, margin_y, stack_offset)
        geometry = QRect(pos, widget_size)
        
        try:
            widget.setGeometry(geometry)
        except Exception:
            pass
        
        return geometry
    
    def register_widget_bounds(self, name: str, widget: QWidget, anchor: PositionAnchor) -> None:
        """
        Register a widget's bounds for collision detection.
        
        Args:
            name: Unique name for the widget
            widget: The widget
            anchor: Widget's position anchor
        """
        try:
            rect = widget.geometry()
            self._widget_bounds[name] = WidgetBounds(
                widget=widget,
                name=name,
                rect=rect,
                anchor=anchor,
            )
        except Exception:
            pass
    
    def unregister_widget_bounds(self, name: str) -> None:
        """Remove a widget from collision tracking."""
        self._widget_bounds.pop(name, None)
    
    def check_collision(self, rect1: QRect, rect2: QRect) -> bool:
        """
        Check if two rectangles overlap.
        
        Args:
            rect1: First rectangle
            rect2: Second rectangle
            
        Returns:
            True if rectangles overlap
        """
        return rect1.intersects(rect2)
    
    def find_collisions(self, name: str, rect: QRect) -> List[str]:
        """
        Find all widgets that collide with the given rectangle.
        
        Args:
            name: Name of the widget being checked (excluded from results)
            rect: Rectangle to check for collisions
            
        Returns:
            List of widget names that collide
        """
        collisions = []
        for other_name, bounds in self._widget_bounds.items():
            if other_name == name:
                continue
            if self.check_collision(rect, bounds.rect):
                collisions.append(other_name)
        return collisions
    
    def calculate_stack_offsets(
        self,
        widgets: List[Tuple[str, QWidget, PositionAnchor]],
        spacing: int = None,
    ) -> Dict[str, QPoint]:
        """
        Calculate stacking offsets for widgets at the same position.
        
        Args:
            widgets: List of (name, widget, anchor) tuples
            spacing: Spacing between stacked widgets
            
        Returns:
            Dict mapping widget name to stack offset
        """
        if spacing is None:
            spacing = self.DEFAULT_STACK_SPACING
        
        # Group widgets by anchor
        anchor_groups: Dict[PositionAnchor, List[Tuple[str, QWidget]]] = {}
        for name, widget, anchor in widgets:
            if anchor not in anchor_groups:
                anchor_groups[anchor] = []
            anchor_groups[anchor].append((name, widget))
        
        offsets: Dict[str, QPoint] = {}
        
        for anchor, group in anchor_groups.items():
            if len(group) <= 1:
                # No stacking needed
                for name, _ in group:
                    offsets[name] = QPoint(0, 0)
                continue
            
            # Determine stacking direction based on anchor
            stack_down = anchor in (
                PositionAnchor.TOP_LEFT,
                PositionAnchor.TOP_CENTER,
                PositionAnchor.TOP_RIGHT,
            )
            
            cumulative_offset = 0
            for i, (name, widget) in enumerate(group):
                if i == 0:
                    offsets[name] = QPoint(0, 0)
                    continue
                
                # Get previous widget height
                prev_widget = group[i - 1][1]
                try:
                    prev_height = prev_widget.sizeHint().height()
                    if prev_height <= 0:
                        prev_height = prev_widget.height()
                except Exception:
                    prev_height = 100
                
                cumulative_offset += prev_height + spacing
                offset_y = cumulative_offset if stack_down else -cumulative_offset
                offsets[name] = QPoint(0, offset_y)
        
        return offsets
    
    def position_relative_to(
        self,
        widget: QWidget,
        anchor_widget: QWidget,
        placement: str = "above",
        gap: int = 20,
    ) -> QRect:
        """
        Position a widget relative to another widget.
        
        Args:
            widget: Widget to position
            anchor_widget: Widget to position relative to
            placement: Where to place ("above", "below", "left", "right")
            gap: Gap between widgets
            
        Returns:
            Final geometry as QRect
        """
        try:
            anchor_geom = anchor_widget.geometry()
            widget_size = widget.sizeHint()
            if not widget_size.isValid() or widget_size.width() <= 0:
                widget_size = widget.size()
            
            if placement == "above":
                x = anchor_geom.left()
                y = anchor_geom.top() - gap - widget_size.height()
            elif placement == "below":
                x = anchor_geom.left()
                y = anchor_geom.bottom() + gap
            elif placement == "left":
                x = anchor_geom.left() - gap - widget_size.width()
                y = anchor_geom.top()
            elif placement == "right":
                x = anchor_geom.right() + gap
                y = anchor_geom.top()
            else:
                x = anchor_geom.left()
                y = anchor_geom.top()
            
            # Clamp to container bounds
            container_w = self._container_size.width()
            container_h = self._container_size.height()
            x = max(0, min(x, container_w - widget_size.width()))
            y = max(0, min(y, container_h - widget_size.height()))
            
            geometry = QRect(x, y, widget_size.width(), widget_size.height())
            widget.setGeometry(geometry)
            return geometry
        except Exception:
            return QRect()
    
    def clear(self) -> None:
        """Clear all registered widget bounds."""
        self._widget_bounds.clear()
