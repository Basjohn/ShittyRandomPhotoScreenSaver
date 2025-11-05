"""
Event system implementation for screensaver.

Simplified version adapted from SPQDocker reusable modules.
Provides publish-subscribe pattern for inter-module communication.
"""
from typing import Any, Callable, Dict, List, Optional
import threading
from collections import defaultdict
from core.logging.logger import get_logger
from core.events.event_types import Event, Subscription

logger = get_logger('EventSystem')


class EventSystem:
    """
    Centralized event system for the screensaver.
    
    Implements publish-subscribe pattern for loose coupling between components.
    Thread-safe with priority-based subscription ordering.
    """
    
    def __init__(self):
        """Initialize the event system."""
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._subscription_map: Dict[str, Subscription] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._lock = threading.RLock()
        
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
        
        Args:
            event_type: Type of event
            data: Optional event data
            source: Optional event source
        
        Returns:
            Event: The published event object
        """
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        
        event = Event(event_type, data, source)
        
        with self._lock:
            # Get matching subscriptions
            matching_subs = self._subscriptions.get(event_type, [])
            
            if not matching_subs:
                self._add_to_history(event)
                logger.debug(f"No subscribers for event: {event_type}")
                return event
            
            logger.debug(f"Publishing event: {event_type}, subscribers={len(matching_subs)}")
            
            # Call all matching subscribers in priority order
            for subscription in matching_subs:
                if event.is_handled:
                    break
                
                try:
                    subscription(event)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)
        
        self._add_to_history(event)
        return event
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to history."""
        with self._lock:
            self._event_history.append(event)
            
            # Keep history size limited
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]
    
    def get_event_history(self, limit: int = 100) -> List[Event]:
        """
        Get recent event history.
        
        Args:
            limit: Maximum number of events to return
        
        Returns:
            List of recent events
        """
        with self._lock:
            return self._event_history[-limit:]
    
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
