"""
Base class for overlay widgets.

Provides common functionality for all screensaver overlay widgets including:
- Font/color/background styling
- Position management with margin support
- Shadow configuration
- Background frame with border
- Thread manager integration
- Pixel shift support
- Size calculation for stacking/collision detection
"""
from __future__ import annotations

from abc import abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from PySide6.QtCore import QPoint, QRect, QSize, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QLabel, QWidget

from core.logging.logger import get_logger
from widgets.shadow_utils import apply_widget_shadow, configure_overlay_widget_attributes

if TYPE_CHECKING:
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)


class OverlayPosition(Enum):
    """Standard overlay widget positions."""
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"
    
    @classmethod
    def from_string(cls, value: str) -> "OverlayPosition":
        """Convert string to OverlayPosition, with fallback."""
        try:
            return cls(value.lower().replace(" ", "_"))
        except ValueError:
            return cls.TOP_RIGHT


class BaseOverlayWidget(QLabel):
    """
    Base class for all overlay widgets.
    
    Provides common functionality:
    - Font family/size management
    - Text color management
    - Background frame with opacity and border
    - Position calculation with margins
    - Shadow configuration
    - Thread manager integration
    - Widget size calculation for stacking
    
    Subclasses should:
    - Call super().__init__() with parent and position
    - Override _update_content() for content updates
    - Override _calculate_content_size() for size hints
    - Call _apply_base_styling() in their _setup_ui()
    """
    
    # Signals
    visibility_changed = Signal(bool)
    position_changed = Signal(str)
    
    # Default styling
    DEFAULT_FONT_FAMILY = "Segoe UI"
    DEFAULT_FONT_SIZE = 18
    DEFAULT_MARGIN = 20
    DEFAULT_BG_OPACITY = 0.9
    DEFAULT_BG_COLOR = QColor(64, 64, 64, 230)
    DEFAULT_BORDER_WIDTH = 2
    DEFAULT_BORDER_COLOR = QColor(128, 128, 128, 200)
    DEFAULT_TEXT_COLOR = QColor(255, 255, 255, 230)
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position: OverlayPosition = OverlayPosition.TOP_RIGHT,
        overlay_name: str = "overlay"
    ):
        super().__init__(parent)
        
        # Position and layout
        self._position = position
        self._margin = self.DEFAULT_MARGIN
        self._overlay_name = overlay_name
        
        # Font styling
        self._font_family = self.DEFAULT_FONT_FAMILY
        self._font_size = self.DEFAULT_FONT_SIZE
        self._text_color = QColor(self.DEFAULT_TEXT_COLOR)
        
        # Background frame
        self._show_background = False
        self._bg_opacity = self.DEFAULT_BG_OPACITY
        self._bg_color = QColor(self.DEFAULT_BG_COLOR)
        self._bg_border_width = self.DEFAULT_BORDER_WIDTH
        self._bg_border_color = QColor(self.DEFAULT_BORDER_COLOR)
        self._bg_corner_radius = 8
        
        # Shadow
        self._shadow_config: Optional[Dict[str, Any]] = None
        self._has_faded_in = False
        
        # Thread manager
        self._thread_manager: Optional["ThreadManager"] = None
        self._inherit_thread_manager_from_parent(parent)
        
        # State
        self._enabled = False
        self._pixel_shift_offset = QPoint(0, 0)
        
        # Stack offset for widget stacking
        self._stack_offset = QPoint(0, 0)
        
    def _apply_base_styling(self) -> None:
        """Apply base widget attributes and styling. Call in subclass _setup_ui()."""
        configure_overlay_widget_attributes(self)
        self._update_font()
        self._update_stylesheet()
        self.hide()
    
    # -------------------------------------------------------------------------
    # Font Management
    # -------------------------------------------------------------------------
    
    def set_font_family(self, family: str) -> None:
        """Set the font family."""
        self._font_family = family or self.DEFAULT_FONT_FAMILY
        self._update_font()
    
    def set_font_size(self, size: int) -> None:
        """Set the font size in points."""
        self._font_size = max(8, int(size))
        self._update_font()
    
    def _update_font(self) -> None:
        """Update the widget font. Override for custom font handling."""
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
    
    def get_font_family(self) -> str:
        """Get current font family."""
        return self._font_family
    
    def get_font_size(self) -> int:
        """Get current font size."""
        return self._font_size
    
    # -------------------------------------------------------------------------
    # Color Management
    # -------------------------------------------------------------------------
    
    def set_text_color(self, color: QColor) -> None:
        """Set the text color."""
        if isinstance(color, QColor):
            self._text_color = color
            self._update_stylesheet()
    
    def get_text_color(self) -> QColor:
        """Get current text color."""
        return QColor(self._text_color)
    
    # -------------------------------------------------------------------------
    # Background Frame Management
    # -------------------------------------------------------------------------
    
    def set_show_background(self, show: bool) -> None:
        """Enable or disable background frame."""
        self._show_background = bool(show)
        self._update_stylesheet()
        self.update()
    
    def set_background_color(self, color: QColor) -> None:
        """Set background color."""
        if isinstance(color, QColor):
            self._bg_color = color
            self._update_stylesheet()
    
    def set_background_opacity(self, opacity: float) -> None:
        """Set background opacity (0.0 - 1.0)."""
        self._bg_opacity = max(0.0, min(1.0, float(opacity)))
        # Update bg_color alpha
        self._bg_color.setAlpha(int(255 * self._bg_opacity))
        self._update_stylesheet()
    
    def set_background_border(self, width: int, color: QColor) -> None:
        """Set background border width and color."""
        self._bg_border_width = max(0, int(width))
        if isinstance(color, QColor):
            self._bg_border_color = color
        self._update_stylesheet()
    
    def set_background_corner_radius(self, radius: int) -> None:
        """Set background corner radius."""
        self._bg_corner_radius = max(0, int(radius))
        self._update_stylesheet()
    
    def _update_stylesheet(self) -> None:
        """Update widget stylesheet. Override for custom styling."""
        if self._show_background:
            bg = self._bg_color
            border = self._bg_border_color
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()});
                    border: {self._bg_border_width}px solid rgba({border.red()}, {border.green()}, {border.blue()}, {border.alpha()});
                    border-radius: {self._bg_corner_radius}px;
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, {self._text_color.blue()}, {self._text_color.alpha()});
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: transparent;
                    border: none;
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, {self._text_color.blue()}, {self._text_color.alpha()});
                }}
            """)
    
    # -------------------------------------------------------------------------
    # Position Management
    # -------------------------------------------------------------------------
    
    def set_position(self, position: OverlayPosition) -> None:
        """Set widget position."""
        if isinstance(position, str):
            position = OverlayPosition.from_string(position)
        self._position = position
        self._update_position()
        self.position_changed.emit(position.value)
    
    def get_position(self) -> OverlayPosition:
        """Get current position."""
        return self._position
    
    def set_margin(self, margin: int) -> None:
        """Set margin from screen edge."""
        self._margin = max(0, int(margin))
        self._update_position()
    
    def get_margin(self) -> int:
        """Get current margin."""
        return self._margin
    
    def set_stack_offset(self, offset: QPoint) -> None:
        """Set stacking offset for widget collision avoidance."""
        self._stack_offset = offset
        self._update_position()
    
    def _update_position(self) -> None:
        """Update widget position based on current settings."""
        parent = self.parentWidget()
        if not parent:
            return

        try:
            old_geo = self.geometry()
        except Exception:
            old_geo = QRect()
        
        parent_size = parent.size()
        widget_size = self.sizeHint()
        
        # Ensure we have valid sizes
        if widget_size.width() <= 0 or widget_size.height() <= 0:
            widget_size = self.size()
        if widget_size.width() <= 0:
            widget_size = QSize(100, 50)
        
        margin = self._margin
        x, y = 0, 0
        
        # Calculate base position
        if self._position in (OverlayPosition.TOP_LEFT, OverlayPosition.BOTTOM_LEFT):
            x = margin
        elif self._position in (OverlayPosition.TOP_RIGHT, OverlayPosition.BOTTOM_RIGHT):
            x = parent_size.width() - widget_size.width() - margin
        elif self._position in (OverlayPosition.TOP_CENTER, OverlayPosition.BOTTOM_CENTER, OverlayPosition.CENTER):
            x = (parent_size.width() - widget_size.width()) // 2
        
        if self._position in (OverlayPosition.TOP_LEFT, OverlayPosition.TOP_RIGHT, OverlayPosition.TOP_CENTER):
            y = margin
        elif self._position in (OverlayPosition.BOTTOM_LEFT, OverlayPosition.BOTTOM_RIGHT, OverlayPosition.BOTTOM_CENTER):
            y = parent_size.height() - widget_size.height() - margin
        elif self._position == OverlayPosition.CENTER:
            y = (parent_size.height() - widget_size.height()) // 2
        
        # Apply pixel shift and stack offset
        x += self._pixel_shift_offset.x() + self._stack_offset.x()
        y += self._pixel_shift_offset.y() + self._stack_offset.y()
        
        self.move(x, y)

        try:
            new_geo = self.geometry()
        except Exception:
            new_geo = QRect()

        try:
            parent.update(old_geo.united(new_geo))
        except Exception:
            pass
    
    # -------------------------------------------------------------------------
    # Shadow Management
    # -------------------------------------------------------------------------
    
    def set_shadow_config(self, config: Optional[Dict[str, Any]]) -> None:
        """Set shadow configuration."""
        self._shadow_config = config
        if config and self._has_faded_in:
            apply_widget_shadow(self, config, has_background_frame=self._show_background)
    
    def get_shadow_config(self) -> Optional[Dict[str, Any]]:
        """Get current shadow configuration."""
        return self._shadow_config
    
    def on_fade_complete(self) -> None:
        """Called when fade-in animation completes. Apply shadow."""
        self._has_faded_in = True
        if self._shadow_config:
            apply_widget_shadow(self, self._shadow_config, has_background_frame=self._show_background)
    
    # -------------------------------------------------------------------------
    # Thread Manager Integration
    # -------------------------------------------------------------------------
    
    def set_thread_manager(self, manager: "ThreadManager") -> None:
        """Set thread manager for background operations."""
        self._thread_manager = manager
    
    def _ensure_thread_manager(self, context: str) -> bool:
        """Verify a ThreadManager is present, logging if missing."""
        if self._thread_manager is not None:
            return True
        self._inherit_thread_manager_from_parent(self.parent())
        if self._thread_manager is not None:
            return True
        overlay_name = getattr(self, "_overlay_name", self.objectName() or self.__class__.__name__)
        logger.error(
            "[THREAD_MANAGER] Missing ThreadManager for %s during %s; timer-driven features disabled.",
            overlay_name,
            context,
        )
        return False

    def _inherit_thread_manager_from_parent(self, parent: Optional[QWidget]) -> None:
        """Best-effort inheritance of ThreadManager from the parent widget."""
        if self._thread_manager is not None or parent is None:
            return
        try:
            inherited = getattr(parent, "_thread_manager", None)
        except Exception:
            inherited = None
        if inherited is not None:
            self._thread_manager = inherited
    
    def get_thread_manager(self) -> Optional["ThreadManager"]:
        """Get thread manager."""
        return self._thread_manager
    
    # -------------------------------------------------------------------------
    # Pixel Shift Support
    # -------------------------------------------------------------------------
    
    def apply_pixel_shift(self, offset: QPoint) -> None:
        """Apply pixel shift offset to prevent burn-in."""
        self._pixel_shift_offset = offset
        self._update_position()
    
    def get_pixel_shift_offset(self) -> QPoint:
        """Get current pixel shift offset."""
        return QPoint(self._pixel_shift_offset)
    
    # -------------------------------------------------------------------------
    # Size Calculation for Stacking
    # -------------------------------------------------------------------------
    
    def get_bounding_size(self) -> QSize:
        """Get widget bounding size including shadow/effects.
        
        Used for collision detection and stacking calculations.
        """
        base_size = self.sizeHint()
        if base_size.width() <= 0 or base_size.height() <= 0:
            base_size = self.size()
        
        # Add shadow padding if shadow is configured
        shadow_padding = 0
        if self._shadow_config:
            blur = self._shadow_config.get("blur_radius", 15)
            shadow_padding = int(blur * 1.5)
        
        return QSize(
            base_size.width() + shadow_padding * 2,
            base_size.height() + shadow_padding * 2
        )
    
    def get_screen_rect(self) -> Tuple[int, int, int, int]:
        """Get widget rect in screen coordinates (x, y, width, height).
        
        Accounts for pixel shift and stack offset.
        """
        pos = self.pos()
        size = self.get_bounding_size()
        return (pos.x(), pos.y(), size.width(), size.height())
    
    # -------------------------------------------------------------------------
    # Enable/Disable
    # -------------------------------------------------------------------------
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the widget."""
        self._enabled = bool(enabled)
        if enabled:
            self.show()
            self._update_position()
        else:
            self.hide()
        self.visibility_changed.emit(enabled)
    
    def is_enabled(self) -> bool:
        """Check if widget is enabled."""
        return self._enabled
    
    # -------------------------------------------------------------------------
    # Overlay Name
    # -------------------------------------------------------------------------
    
    def get_overlay_name(self) -> str:
        """Get overlay name for identification."""
        return self._overlay_name
    
    def set_overlay_name(self, name: str) -> None:
        """Set overlay name."""
        self._overlay_name = name
    
    # -------------------------------------------------------------------------
    # Abstract Methods
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def _update_content(self) -> None:
        """Update widget content. Must be implemented by subclasses."""
        pass
    
    def _calculate_content_size(self) -> QSize:
        """Calculate content size hint. Override for custom sizing."""
        return self.sizeHint()


def calculate_widget_collision(
    widget1_rect: Tuple[int, int, int, int],
    widget2_rect: Tuple[int, int, int, int]
) -> bool:
    """Check if two widget rects overlap.
    
    Args:
        widget1_rect: (x, y, width, height) of first widget
        widget2_rect: (x, y, width, height) of second widget
        
    Returns:
        True if widgets overlap
    """
    x1, y1, w1, h1 = widget1_rect
    x2, y2, w2, h2 = widget2_rect
    
    return not (
        x1 + w1 <= x2 or  # widget1 is left of widget2
        x2 + w2 <= x1 or  # widget2 is left of widget1
        y1 + h1 <= y2 or  # widget1 is above widget2
        y2 + h2 <= y1     # widget2 is above widget1
    )


def calculate_stack_offset(
    existing_widgets: list,
    new_widget_size: QSize,
    position: OverlayPosition,
    parent_size: QSize,
    margin: int
) -> Tuple[QPoint, bool]:
    """Calculate stack offset for a new widget to avoid collision.
    
    Args:
        existing_widgets: List of BaseOverlayWidget instances at same position
        new_widget_size: Size of new widget
        position: Target position
        parent_size: Parent widget size
        margin: Margin from edge
        
    Returns:
        Tuple of (offset QPoint, success bool)
        If success is False, widgets cannot be stacked without clipping
    """
    if not existing_widgets:
        return QPoint(0, 0), True
    
    # Calculate total height needed
    total_height = sum(w.get_bounding_size().height() for w in existing_widgets)
    total_height += new_widget_size.height()
    spacing = 10  # Gap between stacked widgets
    total_height += spacing * len(existing_widgets)
    
    # Check if there's enough vertical space
    available_height = parent_size.height() - margin * 2
    if total_height > available_height:
        return QPoint(0, 0), False
    
    # Calculate offset based on position
    if position in (OverlayPosition.TOP_LEFT, OverlayPosition.TOP_RIGHT, OverlayPosition.TOP_CENTER):
        # Stack downward
        offset_y = sum(w.get_bounding_size().height() + spacing for w in existing_widgets)
        return QPoint(0, offset_y), True
    else:
        # Stack upward
        offset_y = -sum(w.get_bounding_size().height() + spacing for w in existing_widgets)
        return QPoint(0, offset_y), True
