"""
Core event system for the application.

This module provides a publish-subscribe messaging system for inter-module communication.
Components can subscribe to specific event types and be notified when those events occur.
"""

from .event_system import EventSystem
from .event_types import Event, Subscription, EventType

# Public API
__all__ = ['EventSystem', 'Event', 'Subscription', 'EventType']
