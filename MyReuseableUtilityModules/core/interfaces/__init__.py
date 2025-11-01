"""
Core interfaces for the framework.

This module defines the abstract interfaces that core modules implement.
"""

from typing import Any, Callable, Optional, Union
from abc import ABC, abstractmethod


class IEventSystem(ABC):
    """Interface for event system implementations."""
    
    @abstractmethod
    def subscribe(
        self, 
        event_type: Union[str, Any],
        callback: Callable,
        priority: int = 0,
        filter_fn: Optional[Callable] = None
    ) -> str:
        """Subscribe to events of a specific type."""
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events."""
        pass
    
    @abstractmethod
    def publish(
        self, 
        event_type: Union[str, Any], 
        data: Any = None, 
        source: Any = None
    ) -> Any:
        """Publish an event."""
        pass


class ISettingsManager(ABC):
    """Interface for settings management."""
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        pass
    
    @abstractmethod
    def save(self) -> None:
        """Save settings to disk."""
        pass


__all__ = ['IEventSystem', 'ISettingsManager']
