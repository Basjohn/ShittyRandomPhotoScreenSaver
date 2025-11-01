"""
Event-related types and base classes.

This module defines the core types used by the event system,
including the Event class, Subscription class, and common event types.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union

# Import Qt types for mouse events
try:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QWidget
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


class EventType(str, Enum):
    """Common event types used throughout the application."""
    # System events
    APP_STARTUP = "app.startup"
    APP_SHUTDOWN = "app.shutdown"
    
    # Test events (used by unit tests)
    TEST = "test.event"
    
    # Window management events
    WINDOW_CREATED = "window.created"
    WINDOW_CLOSED = "window.closed"
    WINDOW_SHOWN = "window.shown"
    WINDOW_HIDDEN = "window.hidden"
    WINDOW_FOCUS_CHANGED = "window.focus_changed"
    
    # Settings events
    SETTING_CHANGED = "setting.changed"
    SETTINGS_LOADED = "settings.loaded"
    SETTINGS_SAVED = "settings.saved"
    
    # Hotkey events
    HOTKEY_PRESSED = "hotkey.pressed"
    HOTKEY_REGISTERED = "hotkey.registered"
    HOTKEY_UNREGISTERED = "hotkey.unregistered"
    
    # Mouse events
    MOUSE_PRESS = "mouse.press"
    MOUSE_RELEASE = "mouse.release"
    MOUSE_MOVE = "mouse.move"
    MOUSE_CONTEXT_MENU = "mouse.context_menu"
    
    # Mouse capture coordination events
    MOUSE_CAPTURE_REQUEST = "mouse.capture.request"
    MOUSE_CAPTURE_GRANTED = "mouse.capture.granted"
    MOUSE_CAPTURE_DENIED = "mouse.capture.denied"
    MOUSE_CAPTURE_RELEASED = "mouse.capture.released"
    
    # Overlay mouse events
    OVERLAY_MOUSE_CAPTURE = "overlay.mouse.capture"
    OVERLAY_MOUSE_RELEASE = "overlay.mouse.release"
    OVERLAY_CONTEXT_MENU_SHOW = "overlay.context_menu.show"
    OVERLAY_CONTEXT_MENU_HIDE = "overlay.context_menu.hide"
    OVERLAY_BORDER_MOUSE_ENABLE = "overlay.border.mouse.enable"
    OVERLAY_BORDER_MOUSE_DISABLE = "overlay.border.mouse.disable"
    
    # Cursor management events
    CURSOR_SET = "cursor.set"
    CURSOR_UNSET = "cursor.unset"
    CURSOR_OVERRIDE = "cursor.override"
    
    # Media events
    MEDIA_VOLUME_CHANGED = "media.volume.changed"
    
    # Add more event types as needed


@dataclass
class Event:
    """Represents an event in the system."""
    
    # Core event properties
    type: Union[str, EventType]
    data: Any = None
    source: Any = None
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Initialize the event with a unique ID and set default values."""
        self.id = str(uuid.uuid4())
        self._handled = False
    
    def mark_handled(self) -> None:
        """Mark this event as handled to prevent further processing."""
        self._handled = True
    
    @property
    def is_handled(self) -> bool:
        """Check if this event has been marked as handled."""
        return self._handled


class Subscription:
    """Represents a subscription to an event type."""
    
    def __init__(
        self, 
        callback: Callable[[Event], None], 
        event_type: Union[str, EventType],
        priority: int = 0,
        filter_fn: Optional[Callable[[Event], bool]] = None
    ):
        """Initialize the subscription.
        
        Args:
            callback: Function to call when the event is emitted
            event_type: Type of event to subscribe to (supports wildcards)
            priority: Priority of the subscription (higher number = called earlier; 0 runs last)
            filter_fn: Optional function to filter events before calling the callback
        """
        self.id = str(uuid.uuid4())
        self.callback = callback
        self.event_type = event_type
        self.priority = priority
        self.filter_fn = filter_fn
        self.active = True
    
    def __call__(self, event: Event) -> None:
        """Call the callback if the subscription is active and the filter passes."""
        if self.active and (self.filter_fn is None or self.filter_fn(event)):
            self.callback(event)
    
    def __lt__(self, other: 'Subscription') -> bool:
        """Compare subscriptions by priority for sorting.
        
        Rules:
        - Higher numeric priority runs earlier.
        - Priority 0 is the lowest (runs last).
        """
        self_key = (self.priority == 0, -self.priority)
        other_key = (other.priority == 0, -other.priority)
        return self_key < other_key
    
    def matches(self, event_type: str) -> bool:
        """Check if this subscription matches the given event type.
        
        Supports wildcard matching (e.g., 'window.*' matches 'window.created').
        """
        if self.event_type == event_type:
            return True
        
        # Handle wildcard matching (e.g., 'window.*' matches 'window.created')
        if '*' in self.event_type:
            import re
            # Escape literals and convert '*' wildcards to '.*'
            pattern = re.escape(self.event_type).replace(r'\*', '.*')
            return bool(re.fullmatch(pattern, event_type))
        
        return False


# Specialized event classes for mouse coordination
if QT_AVAILABLE:
    @dataclass
    class MouseEvent(Event):
        """Mouse event with Qt-specific data."""
        button: Optional[Qt.MouseButton] = None
        position: Optional[QPoint] = None
        global_position: Optional[QPoint] = None
        modifiers: Optional[Qt.KeyboardModifiers] = None
        widget_id: Optional[str] = None
        widget: Optional[QWidget] = None
    
    @dataclass
    class MouseCaptureEvent(Event):
        """Mouse capture coordination event."""
        requester: str = ""
        widget_id: Optional[str] = None
        widget: Optional[QWidget] = None
        priority: int = 0
        reason: str = ""
        success: bool = False
    
    @dataclass
    class CursorEvent(Event):
        """Cursor management event."""
        requester: str = ""
        widget_id: Optional[str] = None
        widget: Optional[QWidget] = None
        cursor_shape: Optional[Qt.CursorShape] = None
        priority: int = 0
        reason: str = ""
        success: bool = False
    
    @dataclass
    class OverlayMouseEvent(Event):
        """Overlay-specific mouse event."""
        overlay_id: str = ""
        overlay_type: str = ""
        mouse_event: Optional[MouseEvent] = None
        border_overlay_affected: bool = False
