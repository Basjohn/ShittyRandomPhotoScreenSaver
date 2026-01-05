"""
Event system implementation for screensaver.

Simplified version adapted from SPQDocker reusable modules.
Provides publish-subscribe pattern for inter-module communication.
"""
from typing import Any, Callable, Dict, List, Optional
import threading
from collections import defaultdict, deque
from core.logging.logger import get_logger
from core.events.event_types import Event, Subscription

logger = get_logger('EventSystem')


class EventSystem:
    """
    Centralized event system for the screensaver.
    
    Implements publish-subscribe pattern for loose coupling between components.
    Thread-safe with priority-based subscription ordering.
    
    PERF: Lock is released before calling subscribers to avoid blocking other
    threads during potentially slow callback execution.
    """
    
    # Maximum recursion depth for publish() to prevent infinite loops
    MAX_PUBLISH_DEPTH = 10
    
    def __init__(self):
        """Initialize the event system."""
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._subscription_map: Dict[str, Subscription] = {}
        # Use deque with maxlen for automatic size limiting (no manual trimming needed)
        self._event_history: deque[Event] = deque(maxlen=1000)
        self._max_history = 1000
        self._lock = threading.RLock()
        # Track publish recursion depth per thread to prevent infinite loops
        self._publish_depth: Dict[int, int] = {}
        
        logger.info("EventSystem initialized")
    
    def subscribe(
        self, 
        event_type: str,
        callback: Callable[[Event], None],
        priority: int = 50,
        filter_fn: Optional[Callable[[Event], bool]] = None,
    ) -> str:
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event is published
            priority: Priority (higher = called earlier), default 50
            filter_fn: Optional filter function
        
        Returns:
            str: Subscription ID for unsubscribing
        
        Raises:
            ValueError: If callback is not callable
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        
        subscription = Subscription(callback, event_type, priority, filter_fn)
        
        with self._lock:
            self._subscriptions[event_type].append(subscription)
            self._subscription_map[subscription.id] = subscription
            
            # Sort by priority (higher first)
            self._subscriptions[event_type].sort()
        
        logger.debug(f"New subscription: {subscription.id} for {event_type} (priority={priority})")
        return subscription.id
    
    def unsubscribe(self, subscription_id: str) -> None:
        """
        Unsubscribe from events.
        
        Args:
            subscription_id: ID returned from subscribe()
        """
        with self._lock:
            subscription = self._subscription_map.pop(subscription_id, None)
            if subscription is None:
                logger.warning(f"Unsubscribe called with unknown id: {subscription_id}")
                return
            
            subscription.active = False
            
            event_type = subscription.event_type
            if event_type in self._subscriptions:
                self._subscriptions[event_type] = [
                    s for s in self._subscriptions[event_type] 
                    if s.id != subscription_id
                ]
                
                if not self._subscriptions[event_type]:
                    self._subscriptions.pop(event_type, None)
        
        logger.debug(f"Unsubscribed: {subscription_id}")
    
    def publish(
        self, 
        event_type: str, 
        data: Any = None, 
        source: Any = None
    ) -> Event:
        """
        Publish an event to all subscribers.
        
        PERF: Copies subscriber list under lock, then releases lock before
        calling callbacks. This prevents slow callbacks from blocking other
        threads that need to subscribe/unsubscribe.
        
        SAFETY: Tracks recursion depth per thread to prevent infinite loops
        when a subscriber publishes another event.
        
        Args:
            event_type: Type of event
            data: Optional event data
            source: Optional event source
        
        Returns:
            Event: The published event object
        """
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        
        # Check recursion depth to prevent infinite loops
        thread_id = threading.get_ident()
        current_depth = self._publish_depth.get(thread_id, 0)
        if current_depth >= self.MAX_PUBLISH_DEPTH:
            logger.warning(
                f"Event publish recursion limit ({self.MAX_PUBLISH_DEPTH}) reached for {event_type}, "
                "dropping event to prevent infinite loop"
            )
            return Event(event_type, data, source)
        
        self._publish_depth[thread_id] = current_depth + 1
        
        try:
            event = Event(event_type, data, source)
            
            # Copy subscriber list under lock, then release before calling
            with self._lock:
                matching_subs = list(self._subscriptions.get(event_type, []))
            
            if not matching_subs:
                self._add_to_history(event)
                logger.debug(f"No subscribers for event: {event_type}")
                return event
            
            logger.debug(f"Publishing event: {event_type}, subscribers={len(matching_subs)}")
            
            # Call subscribers WITHOUT holding the lock
            for subscription in matching_subs:
                if event.is_handled:
                    break
                
                # Skip if subscription was deactivated while we were iterating
                if not subscription.active:
                    continue
                
                try:
                    subscription(event)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)
            
            self._add_to_history(event)
            return event
        finally:
            # Decrement depth, clean up if back to zero
            self._publish_depth[thread_id] = current_depth
            if current_depth == 0:
                self._publish_depth.pop(thread_id, None)
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to history. Deque maxlen handles size limiting automatically."""
        with self._lock:
            self._event_history.append(event)
    
    def get_event_history(self, limit: int = 100) -> List[Event]:
        """
        Get recent event history.
        
        Args:
            limit: Maximum number of events to return
        
        Returns:
            List of recent events
        """
        with self._lock:
            try:
                limit_int = int(limit)
            except Exception as e:
                logger.debug("[MISC] Exception suppressed: %s", e)
                limit_int = 100

            if limit_int <= 0:
                return []

            history = list(self._event_history)
            return history[-limit_int:]
    
    def clear(self) -> None:
        """Clear all subscriptions and history."""
        with self._lock:
            self._subscriptions.clear()
            self._subscription_map.clear()
            self._event_history.clear()
        
        logger.info("EventSystem cleared")
    
    def get_subscription_count(self) -> int:
        """Get total number of active subscriptions."""
        with self._lock:
            return len(self._subscription_map)
    
    def get_subscriptions_for_type(self, event_type: str) -> int:
        """Get number of subscriptions for a specific event type."""
        with self._lock:
            return len(self._subscriptions.get(event_type, []))
