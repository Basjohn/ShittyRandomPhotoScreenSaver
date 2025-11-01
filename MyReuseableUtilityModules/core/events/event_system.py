"""
Implementation of the event system.

This module contains the EventSystem class which implements the IEventSystem
interface for managing events and callbacks in the application.
"""

from typing import Any, Callable, Dict, List, Optional, Union, Type, TypeVar
import time
from collections import defaultdict
from core.logging import get_logger
from core.interfaces import IEventSystem
from core.events.event_types import Event, EventType, Subscription
from core.threading import ThreadManager

# Type variable for generic event types
T = TypeVar('T', bound=Event)
try:
    from core.settings.settings_manager import SettingsManager  # optional
except Exception:  # pragma: no cover - settings not critical for tracing
    SettingsManager = None  # type: ignore


class EventSystem(IEventSystem):
    """
    Centralized event system for the application.
    
    This class implements a publish-subscribe pattern for inter-module communication.
    It allows components to subscribe to specific event types and be notified when
    those events occur.
    """
    
    def __init__(self):
        """Initialize the event system with empty subscriptions."""
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._subscription_map: Dict[str, Subscription] = {}
        # Lock-free: All mutations dispatched to UI thread via ThreadManager
        self._logger = get_logger('EventSystem')
        self._event_history: List[Event] = []
        self._max_history = 1000  # Maximum number of events to keep in history
        # Tracing: lightweight, settings-gated dispatch tracing for diagnostics
        self._trace_enabled: bool = False
        try:
            if SettingsManager is not None:
                sm = SettingsManager()
                self._trace_enabled = bool(sm.get("debug.events_trace", False))
        except Exception:
            # Non-fatal; default remains False
            pass
        
        # Register with ResourceManager for deterministic cleanup
        try:
            from core.resources import ResourceManager, ResourceType
            
            # Get singleton instance
            if not hasattr(ResourceManager, '_instance'):
                ResourceManager._instance = ResourceManager()
            self._resource_manager = ResourceManager._instance
            
            self._resource_id = self._resource_manager.register(
                self,
                ResourceType.CUSTOM,
                "EventSystem singleton",
                cleanup_handler=lambda obj: obj._cleanup()
            )
            self._logger.debug("Registered EventSystem with ResourceManager")
        except Exception as e:
            self._logger.warning(f"Failed to register with ResourceManager: {e}")
            self._resource_manager = None
            self._resource_id = None
    
    def subscribe(
        self, 
        event_type: Union[str, EventType],
        callback: Callable[[Event], None],
        priority: int = 0,
        filter_fn: Optional[Callable[[Event], bool]] = None,
        dispatch_on_ui: bool = False,
    ) -> str:
        """Subscribe to events of a specific type.
        
        Args:
            event_type: Type of event to subscribe to (supports wildcards like 'window.*')
            callback: Function to call when the event is emitted
            priority: Priority of the subscription (higher = called earlier)
            filter_fn: Optional function to filter events before calling the callback
            
        Returns:
            str: Subscription ID that can be used to unsubscribe
            
        Raises:
            ValueError: If the callback is not callable
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        # Convert EventType enum to string if needed
        if isinstance(event_type, EventType):
            event_type = event_type.value
        
        # Validate event_type
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        
        # Optionally wrap callback to dispatch on UI thread
        if dispatch_on_ui:
            orig_cb = callback

            def _ui_dispatch(evt: Event) -> None:
                try:
                    ThreadManager.run_on_ui_thread(orig_cb, evt)
                except Exception:
                    # Fall back to direct call but still surface error via logger in publish
                    orig_cb(evt)

            effective_cb = _ui_dispatch
        else:
            effective_cb = callback

        # Create the subscription
        subscription = Subscription(effective_cb, event_type, priority, filter_fn)
        
        # Lock-free: UI thread only access
        # Store the subscription
        self._subscriptions[event_type].append(subscription)
        self._subscription_map[subscription.id] = subscription
        
        # Sort using Subscription.__lt__ to ensure single source of truth for ordering
        self._subscriptions[event_type].sort()
        
        self._logger.debug(
            "New subscription: id=%s, event_type=%s, priority=%d, callback=%s",
            subscription.id, 
            event_type, 
            priority,
            self._format_callback(callback)
        )
        
        return subscription.id
    
    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events.
        
        Args:
            subscription_id: ID of the subscription to remove
        """
        # Lock-free: UI thread only access
        subscription = self._subscription_map.pop(subscription_id, None)
        if subscription is None:
            self._logger.warning("Unsubscribe called with unknown id: %s", subscription_id)
            return
        
        # Mark as inactive
        subscription.active = False
        
        # Remove from the subscriptions list
        event_type = subscription.event_type
        if event_type in self._subscriptions:
            self._subscriptions[event_type] = [
                s for s in self._subscriptions[event_type] 
                if s.id != subscription_id
            ]
            
            # Remove the event type if there are no more subscriptions
            if not self._subscriptions[event_type]:
                self._subscriptions.pop(event_type, None)
        
        self._logger.debug(
            "Unsubscribed: id=%s, event_type=%s, callback=%s",
            subscription_id,
            event_type,
            self._format_callback(subscription.callback)
        )
    
    def publish(
        self, 
        event_type: Union[str, EventType], 
        data: Any = None, 
        source: Any = None,
        event_class: Type[T] = Event
    ) -> Event:
        """Publish an event.
        
        Args:
            event_type: Type of event being published
            data: Optional data to pass to subscribers
            source: Optional source of the event
            event_class: Optional custom event class to use
            
        Returns:
            Event: The published event object
        """
        # Convert EventType enum to string if needed
        if isinstance(event_type, EventType):
            event_type = event_type.value
        
        # Validate event_type
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        
        # Create the event
        event = event_class(event_type, data, source)
        
        # Get all matching subscriptions
        matching_subs = self._get_matching_subscriptions(event_type)
        
        if not matching_subs:
            # Even with no subscribers, record the event so waiters can see it
            self._add_to_history(event)
            self._logger.debug("No subscribers for event: %s", event_type)
            return event
        
        # Debug: log ordered subscription priorities
        try:
            ordered = [(s.priority, s.id, self._format_callback(s.callback)) for s in matching_subs]
        except Exception:
            ordered = []
        self._logger.debug(
            "Publishing event: type=%s, source=%s, subscribers=%d, order=%s",
            event_type,
            source,
            len(matching_subs),
            ordered
        )
        
        # Call all matching subscribers
        for subscription in matching_subs:
            if event.is_handled:
                break
            
            # Optional per-handler tracing
            start_ts = time.perf_counter() if self._trace_enabled else 0.0
            try:
                if self._trace_enabled:
                    try:
                        self._logger.debug(
                            "dispatch.begin id=%s type=%s sub=%s prio=%d",
                            event.id,
                            event_type,
                            self._format_callback(subscription.callback),
                            getattr(subscription, 'priority', 0),
                        )
                    except Exception:
                        pass
                subscription(event)
            except Exception as e:
                self._logger.error(
                    "Error in event handler for %s: %s",
                    event_type,
                    str(e),
                    exc_info=True
                )
            finally:
                if self._trace_enabled:
                    try:
                        dur_ms = (time.perf_counter() - start_ts) * 1000.0 if start_ts else 0.0
                        self._logger.debug(
                            "dispatch.end id=%s type=%s sub=%s prio=%d dur_ms=%.3f handled=%s",
                            event.id,
                            event_type,
                            self._format_callback(subscription.callback),
                            getattr(subscription, 'priority', 0),
                            dur_ms,
                            event.is_handled,
                        )
                    except Exception:
                        pass
        
        # Add to history
        self._add_to_history(event)
        
        return event
    
    def wait_for(
        self, 
        event_type: Union[str, EventType], 
        timeout: Optional[float] = None,
        condition: Optional[Callable[[Event], bool]] = None
    ) -> Optional[Event]:
        """Wait for an event of the specified type.
        
        Args:
            event_type: Type of event to wait for
            timeout: Maximum time to wait in seconds (None = wait forever)
            condition: Optional condition function that must return True for the event to be returned
            
        Returns:
            Optional[Event]: The matching event, or None if timeout occurred
        """
        # Normalize event type to string for comparisons
        if isinstance(event_type, EventType):
            event_type = event_type.value

        # Lock-free: Use callback-based pattern instead of blocking wait
        result = []

        # Fast-path: check recent event history for a matching event to avoid race
        # Lock-free: UI thread only access
        for evt in reversed(self._event_history):
            if evt.type == event_type and (condition is None or condition(evt)):
                self._logger.debug("wait_for satisfied from history: type=%s", event_type)
                return evt
        
        def handler(evt: Event) -> None:
            if condition is None or condition(evt):
                result.append(evt)
        
        # Subscribe to the event
        sub_id = self.subscribe(event_type, handler)
        
        # Lock-free: Use ThreadManager timer instead of blocking wait
        start_time = time.time()
        while not result and (timeout is None or (time.time() - start_time) < timeout):
            ThreadManager.process_events(10)  # Process events for 10ms
        
        # Always clean up the subscription
        self.unsubscribe(sub_id)
        return result[0] if result else None
    
    def get_subscription_count(self, event_type: Optional[Union[str, EventType]] = None) -> int:
        """Get the number of active subscriptions.
        
        Args:
            event_type: Optional event type to filter by
            
        Returns:
            int: Number of active subscriptions
        """
        if event_type is not None and isinstance(event_type, EventType):
            event_type = event_type.value
        
        # Lock-free: UI thread only access
        if event_type is None:
            return len(self._subscription_map)
        return len(self._subscriptions.get(event_type, []))
    
    def clear_all_subscriptions(self) -> None:
        """Remove all subscriptions."""
        # Lock-free: UI thread only access
        self._subscriptions.clear()
        self._subscription_map.clear()
    
    def _get_matching_subscriptions(self, event_type: str) -> List[Subscription]:
        """Get all subscriptions that match the given event type.
        
        Args:
            event_type: Event type to match
            
        Returns:
            List of matching subscriptions, sorted by priority
        """
        # Lock-free: UI thread only access
        # Get direct matches and wildcard matches
        subscriptions: List[Subscription] = []
        
        # Check for direct matches first
        if event_type in self._subscriptions:
            subscriptions.extend(self._subscriptions[event_type])
        
        # Check for wildcard matches
        for pattern, subs in self._subscriptions.items():
            if pattern == event_type:
                continue  # Already handled above
            
            # Check if this is a wildcard pattern that matches the event type
            if '*' in pattern:
                if self._pattern_matches(pattern, event_type):
                    subscriptions.extend(subs)
        
        # Sort using Subscription.__lt__ (higher numeric runs earlier; zero last)
        subscriptions.sort()
        return subscriptions
    
    def _pattern_matches(self, pattern: str, event_type: str) -> bool:
        """Check if an event type matches a wildcard pattern."""
        import re
        # Convert wildcard pattern to regex safely (e.g., 'window.*' -> '^window\..*$')
        # Use re.escape to avoid invalid escape sequences and ensure literals are escaped.
        regex = '^' + re.escape(pattern).replace(r'\*', '.*') + '$'
        return bool(re.match(regex, event_type))
    
    def _add_to_history(self, event: Event) -> None:
        """Add an event to the history, maintaining the maximum size."""
        # Lock-free: UI thread only access
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
    
    def _cleanup(self):
        """Cleanup handler for ResourceManager."""
        try:
            # Clear all subscriptions
            self._subscriptions.clear()
            self._subscription_map.clear()
            # Clear event history
            self._event_history.clear()
            self._logger.debug("EventSystem cleanup completed")
        except Exception as e:
            self._logger.error(f"Error during EventSystem cleanup: {e}")
    
    def shutdown(self):
        """Explicit shutdown method."""
        if hasattr(self, '_resource_id') and self._resource_id and hasattr(self, '_resource_manager') and self._resource_manager:
            try:
                self._resource_manager.unregister(self._resource_id)
                self._resource_id = None
            except Exception as e:
                self._logger.warning(f"Failed to unregister from ResourceManager: {e}")
        self._cleanup()
        self._logger.info(f"Event system shutdown complete. Processed {len(self._event_history)} events total.")
    
    @staticmethod
    def _format_callback(callback: Callable) -> str:
        """Format a callback function for logging."""
        if hasattr(callback, '__qualname__'):
            return callback.__qualname__
        if hasattr(callback, '__name__'):
            return callback.__name__
        return str(callback)
