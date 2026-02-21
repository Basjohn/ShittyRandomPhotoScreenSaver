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
- **Lifecycle management** with states (CREATED, INITIALIZED, ACTIVE, HIDDEN, DESTROYED)
- **ResourceManager integration** for proper cleanup
"""
from __future__ import annotations

import threading
from abc import abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QRect, QSize, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QLabel, QWidget
try:
    from shiboken6 import Shiboken  # type: ignore
except ImportError:  # pragma: no cover - optional dependency for validity checks
    Shiboken = None  # type: ignore

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.resources.manager import ResourceManager
from core.resources.types import ResourceType
from widgets.shadow_utils import apply_widget_shadow, configure_overlay_widget_attributes

if TYPE_CHECKING:
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)


class WidgetLifecycleState(Enum):
    """Standard widget lifecycle states.
    
    State transitions:
        CREATED → INITIALIZED → ACTIVE ⇄ HIDDEN → DESTROYED
    
    Valid transitions:
        - CREATED → INITIALIZED (via initialize())
        - INITIALIZED → ACTIVE (via activate())
        - ACTIVE → HIDDEN (via deactivate())
        - HIDDEN → ACTIVE (via activate())
        - ACTIVE → DESTROYED (via cleanup())
        - HIDDEN → DESTROYED (via cleanup())
        - INITIALIZED → DESTROYED (via cleanup())
    
    Invalid transitions:
        - DESTROYED → any state (terminal)
        - CREATED → ACTIVE (must initialize first)
        - CREATED → HIDDEN (must initialize first)
    """
    CREATED = auto()       # Widget instantiated but not initialized
    INITIALIZED = auto()   # Resources allocated, ready to activate
    ACTIVE = auto()        # Visible and updating
    HIDDEN = auto()        # Not visible but alive, can reactivate
    DESTROYED = auto()     # Cleaned up, terminal state


# Valid state transitions map
_VALID_TRANSITIONS: Dict[WidgetLifecycleState, set] = {
    WidgetLifecycleState.CREATED: {
        WidgetLifecycleState.INITIALIZED,
        WidgetLifecycleState.DESTROYED,  # Allow direct cleanup from CREATED
    },
    WidgetLifecycleState.INITIALIZED: {
        WidgetLifecycleState.ACTIVE,
        WidgetLifecycleState.DESTROYED,
    },
    WidgetLifecycleState.ACTIVE: {
        WidgetLifecycleState.HIDDEN,
        WidgetLifecycleState.DESTROYED,
    },
    WidgetLifecycleState.HIDDEN: {
        WidgetLifecycleState.ACTIVE,
        WidgetLifecycleState.DESTROYED,
    },
    WidgetLifecycleState.DESTROYED: set(),  # Terminal state
}


def is_valid_lifecycle_transition(old_state: WidgetLifecycleState, new_state: WidgetLifecycleState) -> bool:
    """Check if a lifecycle state transition is valid."""
    return new_state in _VALID_TRANSITIONS.get(old_state, set())


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
    Base class for all overlay widgets with lifecycle management.
    
    Provides common functionality:
    - **Lifecycle management** with states (CREATED, INITIALIZED, ACTIVE, HIDDEN, DESTROYED)
    - **ResourceManager integration** for proper cleanup
    - Font family/size management
    - Text color management
    - Background frame with opacity and border
    - Position calculation with margins
    - Shadow configuration
    - Thread manager integration
    - Widget size calculation for stacking
    
    Lifecycle Methods:
    - initialize() - Allocate resources, transition to INITIALIZED
    - activate() - Show widget and start updates, transition to ACTIVE
    - deactivate() - Hide widget and stop updates, transition to HIDDEN
    - cleanup() - Clean up all resources, transition to DESTROYED (terminal)
    
    Subclasses should:
    - Call super().__init__() with parent and position
    - Override _initialize_impl() for resource allocation
    - Override _activate_impl() for activation logic (start timers, etc.)
    - Override _deactivate_impl() for deactivation logic (stop timers, etc.)
    - Override _cleanup_impl() for cleanup logic
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
    DEFAULT_MARGIN = 30
    DEFAULT_BG_OPACITY = 0.9
    DEFAULT_BG_COLOR = QColor(64, 64, 64, 230)
    DEFAULT_BORDER_WIDTH = 3
    DEFAULT_BORDER_COLOR = QColor(128, 128, 128, 200)
    DEFAULT_TEXT_COLOR = QColor(255, 255, 255, 230)
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position: OverlayPosition = OverlayPosition.TOP_RIGHT,
        overlay_name: str = "overlay"
    ):
        super().__init__(parent)
        
        # =====================================================================
        # LIFECYCLE MANAGEMENT
        # =====================================================================
        self._lifecycle_state = WidgetLifecycleState.CREATED
        self._lifecycle_lock = threading.Lock()
        self._resource_manager: Optional[ResourceManager] = None
        self._registered_resource_ids: List[str] = []
        
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
        self._intense_shadow = False  # Intensified shadow styling
        
        # Thread manager
        self._thread_manager: Optional["ThreadManager"] = None
        self._inherit_thread_manager_from_parent(parent)
        
        # State (legacy - use lifecycle state instead)
        self._enabled = False
        self._pixel_shift_offset = QPoint(0, 0)
        
        # Fade sync: if True, set_enabled won't auto-show; visibility is deferred to fade sync
        self._defer_visibility_for_fade_sync = False
        
        # Stack offset for widget stacking
        self._stack_offset = QPoint(0, 0)
        
        # Visual padding - accounts for widget chrome vs visible content
        # Used to align the visible card edge (not QLabel frame) to margins
        self._visual_padding_top = 0
        self._visual_padding_right = 0
        self._visual_padding_bottom = 0
        self._visual_padding_left = 0
        
    def _apply_base_styling(self) -> None:
        """Apply base widget attributes and styling. Call in subclass _setup_ui()."""
        configure_overlay_widget_attributes(self)
        self._update_font()
        self._update_stylesheet()
        self.hide()

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
    
    def set_visual_padding(
        self,
        top: int = 0,
        right: int = 0,
        bottom: int = 0,
        left: int = 0
    ) -> None:
        """Set visual padding to align visible content edge to margins.
        
        Visual padding accounts for the difference between the QLabel frame
        and the actual visible content (e.g., card background with padding).
        When positioning, the visible content edge will align to margins,
        not the QLabel frame edge.
        
        Args:
            top: Padding from QLabel top to visible content top
            right: Padding from QLabel right to visible content right
            bottom: Padding from QLabel bottom to visible content bottom
            left: Padding from QLabel left to visible content left
        """
        self._visual_padding_top = max(0, int(top))
        self._visual_padding_right = max(0, int(right))
        self._visual_padding_bottom = max(0, int(bottom))
        self._visual_padding_left = max(0, int(left))
        self._update_position()
    
    def get_visual_padding(self) -> Tuple[int, int, int, int]:
        """Get visual padding (top, right, bottom, left)."""
        return (
            self._visual_padding_top,
            self._visual_padding_right,
            self._visual_padding_bottom,
            self._visual_padding_left,
        )
    
    def _compute_visual_offset(self) -> QPoint:
        """Compute position offset to align visible content to margins."""
        if self._show_background:
            return QPoint(0, 0)
        
        dx, dy = 0, 0
        
        if self._position in (OverlayPosition.TOP_LEFT, OverlayPosition.MIDDLE_LEFT, OverlayPosition.BOTTOM_LEFT):
            dx = -self._visual_padding_left
        elif self._position in (OverlayPosition.TOP_RIGHT, OverlayPosition.MIDDLE_RIGHT, OverlayPosition.BOTTOM_RIGHT):
            dx = self._visual_padding_right
        
        if self._position in (OverlayPosition.TOP_LEFT, OverlayPosition.TOP_CENTER, OverlayPosition.TOP_RIGHT):
            dy = -self._visual_padding_top
        elif self._position in (OverlayPosition.BOTTOM_LEFT, OverlayPosition.BOTTOM_CENTER, OverlayPosition.BOTTOM_RIGHT):
            dy = self._visual_padding_bottom
        
        return QPoint(dx, dy)
    
    def _update_position(self) -> None:
        """Update widget position based on current settings."""
        parent = self.parentWidget()
        if not parent:
            return

        try:
            old_geo = self.geometry()
        except Exception as e:
            logger.debug("[OVERLAY] Exception suppressed: %s", e)
            old_geo = QRect()
        
        parent_size = parent.size()
        widget_size = self.size()
        if widget_size.width() <= 0 or widget_size.height() <= 0:
            widget_size = self.sizeHint()
        if widget_size.width() <= 0:
            widget_size = QSize(100, 50)
        
        margin = self._margin
        x, y = 0, 0
        
        if self._position in (OverlayPosition.TOP_LEFT, OverlayPosition.MIDDLE_LEFT, OverlayPosition.BOTTOM_LEFT):
            x = margin
        elif self._position in (OverlayPosition.TOP_RIGHT, OverlayPosition.MIDDLE_RIGHT, OverlayPosition.BOTTOM_RIGHT):
            x = parent_size.width() - widget_size.width() - margin
        elif self._position in (OverlayPosition.TOP_CENTER, OverlayPosition.CENTER, OverlayPosition.BOTTOM_CENTER):
            x = (parent_size.width() - widget_size.width()) // 2
        
        if self._position in (OverlayPosition.TOP_LEFT, OverlayPosition.TOP_CENTER, OverlayPosition.TOP_RIGHT):
            y = margin
        elif self._position in (OverlayPosition.MIDDLE_LEFT, OverlayPosition.CENTER, OverlayPosition.MIDDLE_RIGHT):
            y = (parent_size.height() - widget_size.height()) // 2
        elif self._position in (OverlayPosition.BOTTOM_LEFT, OverlayPosition.BOTTOM_CENTER, OverlayPosition.BOTTOM_RIGHT):
            y = parent_size.height() - widget_size.height() - margin
        
        visual_offset = self._compute_visual_offset()
        x += visual_offset.x()
        y += visual_offset.y()
        
        x += self._pixel_shift_offset.x() + self._stack_offset.x()
        y += self._pixel_shift_offset.y() + self._stack_offset.y()
        
        min_visible = 10
        max_x = parent_size.width() - min_visible
        max_y = parent_size.height() - min_visible
        min_x = min_visible - widget_size.width()
        min_y = min_visible - widget_size.height()
        
        x = max(min_x, min(x, max_x))
        y = max(min_y, min(y, max_y))
        
        self.move(x, y)

        try:
            new_geo = self.geometry()
        except Exception as e:
            logger.debug("[OVERLAY] Exception suppressed: %s", e)
            new_geo = QRect()

        try:
            parent.update(old_geo.united(new_geo))
        except Exception as e:
            logger.debug("[OVERLAY] Exception suppressed: %s", e)
    
    # -------------------------------------------------------------------------
    # Shadow Management
    # -------------------------------------------------------------------------
    
    def set_shadow_config(self, config: Optional[Dict[str, Any]]) -> None:
        """Set shadow configuration."""
        self._shadow_config = config
        if is_perf_metrics_enabled():
            overlay = getattr(self, "_overlay_name", self.__class__.__name__)
            logger.info(
                "[PERF][OVERLAY] set_shadow_config overlay=%s has_config=%s has_faded_in=%s",
                overlay,
                "yes" if config else "no",
                self._has_faded_in,
            )
        if config and self._has_faded_in:
            apply_widget_shadow(self, config, has_background_frame=self._show_background, intense=self._intense_shadow)
    
    def get_shadow_config(self) -> Optional[Dict[str, Any]]:
        """Get current shadow configuration."""
        return self._shadow_config
    
    def set_intense_shadow(self, intense: bool) -> None:
        """Enable or disable intensified shadow styling.
        
        When enabled, shadows have doubled blur radius, increased opacity,
        and larger offset for dramatic visual effect on large displays.
        
        Args:
            intense: True to enable intense shadows
        """
        self._intense_shadow = bool(intense)
        if self._shadow_config and self._has_faded_in:
            apply_widget_shadow(self, self._shadow_config, has_background_frame=self._show_background, intense=self._intense_shadow)
    
    def get_intense_shadow(self) -> bool:
        """Get whether intense shadow styling is enabled."""
        return self._intense_shadow
    
    def on_fade_complete(self) -> None:
        """Called when fade-in animation completes. Apply shadow."""
        self._has_faded_in = True
        if self._shadow_config:
            apply_widget_shadow(self, self._shadow_config, has_background_frame=self._show_background, intense=self._intense_shadow)
    
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

        if Shiboken is not None:
            try:
                if not Shiboken.isValid(self):
                    logger.warning(
                        "[THREAD_MANAGER] %s skipped (%s) because widget was already destroyed",
                        getattr(self, "_overlay_name", self.__class__.__name__),
                        context,
                    )
                    return False
            except Exception:
                pass

        parent = None
        try:
            parent = self.parent()
            if Shiboken is not None and parent is not None and not Shiboken.isValid(parent):
                parent = None
        except Exception as exc:
            logger.debug("[THREAD_MANAGER] Failed to access parent during %s: %s", context, exc)
            parent = None

        self._inherit_thread_manager_from_parent(parent)
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
        if Shiboken is not None:
            try:
                if not Shiboken.isValid(parent):
                    return
            except Exception:
                return
        try:
            inherited = getattr(parent, "_thread_manager", None)
        except Exception as e:
            logger.debug("[OVERLAY] Exception suppressed: %s", e)
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
        """Enable or disable the widget.
        
        If _defer_visibility_for_fade_sync is True, the widget won't be shown
        immediately - visibility will be handled by the fade sync mechanism.
        """
        self._enabled = bool(enabled)
        if enabled:
            # Only show if not deferring visibility for fade sync
            if not self._defer_visibility_for_fade_sync:
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
    # LIFECYCLE MANAGEMENT
    # -------------------------------------------------------------------------
    
    def get_lifecycle_state(self) -> WidgetLifecycleState:
        """Get current lifecycle state (thread-safe)."""
        with self._lifecycle_lock:
            return self._lifecycle_state
    
    def is_lifecycle_initialized(self) -> bool:
        """Check if widget has been initialized."""
        with self._lifecycle_lock:
            return self._lifecycle_state in (
                WidgetLifecycleState.INITIALIZED,
                WidgetLifecycleState.ACTIVE,
                WidgetLifecycleState.HIDDEN,
            )
    
    def is_lifecycle_active(self) -> bool:
        """Check if widget is in ACTIVE state."""
        with self._lifecycle_lock:
            return self._lifecycle_state == WidgetLifecycleState.ACTIVE
    
    def is_lifecycle_destroyed(self) -> bool:
        """Check if widget has been destroyed."""
        with self._lifecycle_lock:
            return self._lifecycle_state == WidgetLifecycleState.DESTROYED
    
    def _transition_lifecycle_state(self, new_state: WidgetLifecycleState) -> bool:
        """
        Attempt to transition to a new lifecycle state.
        
        Args:
            new_state: Target state
            
        Returns:
            True if transition was valid and completed, False otherwise
        """
        with self._lifecycle_lock:
            old_state = self._lifecycle_state
            if not is_valid_lifecycle_transition(old_state, new_state):
                logger.warning(
                    f"[LIFECYCLE] Invalid transition for {self._overlay_name}: "
                    f"{old_state.name} → {new_state.name}"
                )
                return False
            
            self._lifecycle_state = new_state
            logger.debug(
                f"[LIFECYCLE] {self._overlay_name}: {old_state.name} → {new_state.name}"
            )
            return True
    
    def set_resource_manager(self, manager: ResourceManager) -> None:
        """Set the ResourceManager for this widget."""
        self._resource_manager = manager
    
    def get_resource_manager(self) -> Optional[ResourceManager]:
        """Get the ResourceManager for this widget."""
        return self._resource_manager
    
    def _register_resource(self, resource: Any, description: str) -> Optional[str]:
        """
        Register a resource with the ResourceManager.
        
        Args:
            resource: Resource to register
            description: Human-readable description
            
        Returns:
            Resource ID if registered, None if no ResourceManager
        """
        if self._resource_manager is None:
            return None
        try:
            resource_id = self._resource_manager.register(
                resource,
                ResourceType.GUI_COMPONENT,
                description=f"{self._overlay_name}: {description}",
            )
            self._registered_resource_ids.append(resource_id)
            return resource_id
        except Exception as e:
            logger.warning(f"[LIFECYCLE] Failed to register resource: {e}")
            return None
    
    def initialize(self) -> bool:
        """
        Initialize widget resources. Call once after construction.
        
        Transitions: CREATED → INITIALIZED
        
        Returns:
            True if initialization succeeded, False otherwise
        """
        with self._lifecycle_lock:
            if self._lifecycle_state != WidgetLifecycleState.CREATED:
                logger.warning(
                    f"[LIFECYCLE] Cannot initialize {self._overlay_name} from state "
                    f"{self._lifecycle_state.name}"
                )
                return False
        
        try:
            # Call subclass initialization
            self._initialize_impl()
            
            # Transition state
            if not self._transition_lifecycle_state(WidgetLifecycleState.INITIALIZED):
                return False
            
            logger.info(f"[LIFECYCLE] {self._overlay_name} initialized")
            return True
        except Exception as e:
            logger.error(
                f"[LIFECYCLE] Initialization failed for {self._overlay_name}: {e}",
                exc_info=True
            )
            return False
    
    def activate(self) -> bool:
        """
        Activate widget (show and start updates).
        
        Transitions: INITIALIZED → ACTIVE, HIDDEN → ACTIVE
        
        Returns:
            True if activation succeeded, False otherwise
        """
        with self._lifecycle_lock:
            if self._lifecycle_state not in (
                WidgetLifecycleState.INITIALIZED,
                WidgetLifecycleState.HIDDEN,
            ):
                logger.warning(
                    f"[LIFECYCLE] Cannot activate {self._overlay_name} from state "
                    f"{self._lifecycle_state.name}"
                )
                return False
        
        try:
            # Call subclass activation
            self._activate_impl()
            
            # Transition state
            if not self._transition_lifecycle_state(WidgetLifecycleState.ACTIVE):
                return False
            
            # Update legacy state
            self._enabled = True
            
            logger.info(f"[LIFECYCLE] {self._overlay_name} activated")
            return True
        except Exception as e:
            logger.error(
                f"[LIFECYCLE] Activation failed for {self._overlay_name}: {e}",
                exc_info=True
            )
            return False
    
    def deactivate(self) -> bool:
        """
        Deactivate widget (hide and stop updates).
        
        Transitions: ACTIVE → HIDDEN
        
        Returns:
            True if deactivation succeeded, False otherwise
        """
        with self._lifecycle_lock:
            if self._lifecycle_state != WidgetLifecycleState.ACTIVE:
                logger.warning(
                    f"[LIFECYCLE] Cannot deactivate {self._overlay_name} from state "
                    f"{self._lifecycle_state.name}"
                )
                return False
        
        try:
            # Call subclass deactivation
            self._deactivate_impl()
            
            # Transition state
            if not self._transition_lifecycle_state(WidgetLifecycleState.HIDDEN):
                return False
            
            # Update legacy state
            self._enabled = False
            
            # Hide widget
            self.hide()
            
            logger.info(f"[LIFECYCLE] {self._overlay_name} deactivated")
            return True
        except Exception as e:
            logger.error(
                f"[LIFECYCLE] Deactivation failed for {self._overlay_name}: {e}",
                exc_info=True
            )
            return False
    
    def cleanup(self) -> None:
        """
        Clean up all resources. Widget is unusable after this.
        
        Transitions: any → DESTROYED (terminal)
        
        This method is idempotent - calling it multiple times is safe.
        """
        with self._lifecycle_lock:
            if self._lifecycle_state == WidgetLifecycleState.DESTROYED:
                logger.debug(f"[LIFECYCLE] {self._overlay_name} already destroyed")
                return
            
            current_state = self._lifecycle_state
        
        try:
            # Deactivate if active
            if current_state == WidgetLifecycleState.ACTIVE:
                try:
                    self._deactivate_impl()
                except Exception as e:
                    logger.warning(f"[LIFECYCLE] Deactivation during cleanup failed: {e}")
            
            # Call subclass cleanup
            try:
                self._cleanup_impl()
            except Exception as e:
                logger.warning(f"[LIFECYCLE] Cleanup impl failed: {e}")
            
            # Clean up registered resources
            if self._resource_manager is not None:
                for resource_id in self._registered_resource_ids:
                    try:
                        self._resource_manager.unregister(resource_id, force=True)
                    except Exception as e:
                        logger.debug(f"[LIFECYCLE] Resource unregister failed: {e}")
                self._registered_resource_ids.clear()
            
            # Transition to destroyed
            with self._lifecycle_lock:
                self._lifecycle_state = WidgetLifecycleState.DESTROYED
            
            # Update legacy state
            self._enabled = False
            
            logger.info(f"[LIFECYCLE] {self._overlay_name} destroyed")
            
            # Schedule Qt deletion
            try:
                self.deleteLater()
            except Exception as e:
                logger.debug("[OVERLAY] Exception suppressed: %s", e)
                
        except Exception as e:
            logger.error(
                f"[LIFECYCLE] Cleanup failed for {self._overlay_name}: {e}",
                exc_info=True
            )
            # Force state to destroyed even on error
            with self._lifecycle_lock:
                self._lifecycle_state = WidgetLifecycleState.DESTROYED
    
    # -------------------------------------------------------------------------
    # Lifecycle Implementation Hooks (Override in Subclasses)
    # -------------------------------------------------------------------------
    
    def _initialize_impl(self) -> None:
        """
        Subclass initialization logic. Override to allocate resources.
        
        Called by initialize() after state validation.
        Raise an exception to indicate initialization failure.
        """
        pass
    
    def _activate_impl(self) -> None:
        """
        Subclass activation logic. Override to start timers, show widget, etc.
        
        Called by activate() after state validation.
        Raise an exception to indicate activation failure.
        """
        pass
    
    def _deactivate_impl(self) -> None:
        """
        Subclass deactivation logic. Override to stop timers, hide widget, etc.
        
        Called by deactivate() after state validation.
        Raise an exception to indicate deactivation failure.
        """
        pass
    
    def _cleanup_impl(self) -> None:
        """
        Subclass cleanup logic. Override to release resources.
        
        Called by cleanup() before ResourceManager cleanup.
        Should be idempotent - may be called multiple times.
        """
        pass
    
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
