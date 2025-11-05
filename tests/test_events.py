"""
Tests for EventSystem.
"""
import pytest
from core.events import EventSystem, Event


def test_event_system_initialization():
    """Test EventSystem initialization."""
    system = EventSystem()
    
    assert system is not None
    assert system.get_subscription_count() == 0


def test_subscribe_and_publish():
    """Test subscribing to and publishing events."""
    system = EventSystem()
    
    received_events = []
    
    def handler(event: Event):
        received_events.append(event)
    
    sub_id = system.subscribe("test.event", handler)
    
    assert sub_id is not None
    assert system.get_subscription_count() == 1
    
    # Publish event
    event = system.publish("test.event", data="test data")
    
    assert len(received_events) == 1
    assert received_events[0].event_type == "test.event"
    assert received_events[0].data == "test data"
    
    system.clear()


def test_unsubscribe():
    """Test unsubscribing from events."""
    system = EventSystem()
    
    received_events = []
    
    def handler(event: Event):
        received_events.append(event)
    
    sub_id = system.subscribe("test.event", handler)
    
    # Publish before unsubscribe
    system.publish("test.event", data="first")
    assert len(received_events) == 1
    
    # Unsubscribe
    system.unsubscribe(sub_id)
    assert system.get_subscription_count() == 0
    
    # Publish after unsubscribe
    system.publish("test.event", data="second")
    assert len(received_events) == 1  # Still 1, not 2
    
    system.clear()


def test_priority_ordering():
    """Test that higher priority handlers are called first."""
    system = EventSystem()
    
    call_order = []
    
    def handler_low(event):
        call_order.append("low")
    
    def handler_high(event):
        call_order.append("high")
    
    def handler_normal(event):
        call_order.append("normal")
    
    # Subscribe with different priorities
    system.subscribe("test.event", handler_low, priority=10)
    system.subscribe("test.event", handler_high, priority=90)
    system.subscribe("test.event", handler_normal, priority=50)
    
    # Publish
    system.publish("test.event")
    
    # Higher priority should be called first
    assert call_order == ["high", "normal", "low"]
    
    system.clear()


def test_event_filter():
    """Test event filtering."""
    system = EventSystem()
    
    received_events = []
    
    def handler(event: Event):
        received_events.append(event)
    
    def filter_fn(event: Event):
        # Only accept events with data == "accept"
        return event.data == "accept"
    
    system.subscribe("test.event", handler, filter_fn=filter_fn)
    
    # Publish with filter match
    system.publish("test.event", data="accept")
    assert len(received_events) == 1
    
    # Publish without filter match
    system.publish("test.event", data="reject")
    assert len(received_events) == 1  # Still 1
    
    system.clear()


def test_event_history():
    """Test event history tracking."""
    system = EventSystem()
    
    # Publish some events
    system.publish("event.1", data="first")
    system.publish("event.2", data="second")
    system.publish("event.3", data="third")
    
    history = system.get_event_history(limit=10)
    
    assert len(history) == 3
    assert history[0].event_type == "event.1"
    assert history[1].event_type == "event.2"
    assert history[2].event_type == "event.3"
    
    system.clear()
