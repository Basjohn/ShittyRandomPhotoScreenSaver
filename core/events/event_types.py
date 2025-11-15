"""
Event type definitions for screensaver application.
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Event:
    """Base event class."""
    event_type: str
    data: Any = None
    source: Any = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    is_handled: bool = False
    
    def mark_handled(self):
        """Mark this event as handled."""
        self.is_handled = True


@dataclass
class Subscription:
    """Subscription to an event type."""
    callback: Callable[[Event], None]
    event_type: str
    priority: int = 0
    filter_fn: Optional[Callable[[Event], bool]] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    active: bool = True
    
    def __call__(self, event: Event) -> None:
        """Call the subscription callback if filter passes."""
        if self.filter_fn is None or self.filter_fn(event):
            self.callback(event)
    
    def __lt__(self, other: 'Subscription') -> bool:
        """Sort by priority (higher first)."""
        return self.priority > other.priority


# Event type constants for the screensaver
class EventType:
    """Event type constants."""
    # Image events
    IMAGE_LOADED = "image.loaded"
    IMAGE_READY = "image.ready"
    IMAGE_FAILED = "image.failed"
    IMAGE_QUEUE_EMPTY = "image.queue.empty"
    
    # Display events
    DISPLAY_READY = "display.ready"
    TRANSITION_STARTED = "transition.started"
    TRANSITION_COMPLETE = "transition.complete"
    
    # Monitor events
    MONITOR_CONNECTED = "monitor.connected"
    MONITOR_DISCONNECTED = "monitor.disconnected"
    
    # User events
    USER_INPUT = "user.input"
    EXIT_REQUEST = "exit.request"
    
    # Source events
    RSS_UPDATED = "rss.updated"
    RSS_FAILED = "rss.failed"
    WEATHER_UPDATED = "weather.updated"
    WEATHER_FAILED = "weather.failed"
    
    # Settings events
    SETTINGS_CHANGED = "settings.changed"

    # Backend events
    RENDER_BACKEND_FAILED = "render.backend.failed"
    RENDER_BACKEND_FALLBACK = "render.backend.fallback"
    RENDER_BACKEND_SELECTED = "render.backend.selected"
