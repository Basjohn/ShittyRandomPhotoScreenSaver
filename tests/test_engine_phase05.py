"""
Tests for Phase 0.5: Engine/Rendering Foundations.

Tests subscription ID tracking, signal disconnection, and cleanup behavior.
"""
from unittest.mock import patch


def test_engine_has_subscription_ids_list():
    """ScreensaverEngine should have _subscription_ids attribute."""
    from engine.screensaver_engine import ScreensaverEngine
    
    engine = ScreensaverEngine()
    assert hasattr(engine, '_subscription_ids')
    assert isinstance(engine._subscription_ids, list)
    assert len(engine._subscription_ids) == 0


def test_engine_unsubscribe_all_events_method_exists():
    """ScreensaverEngine should have _unsubscribe_all_events method."""
    from engine.screensaver_engine import ScreensaverEngine
    
    engine = ScreensaverEngine()
    assert hasattr(engine, '_unsubscribe_all_events')
    assert callable(engine._unsubscribe_all_events)


def test_display_manager_disconnect_monitor_signals_method_exists():
    """DisplayManager should have _disconnect_monitor_signals method."""
    from engine.display_manager import DisplayManager
    
    # Mock settings_manager to avoid Qt initialization
    with patch('engine.display_manager.QGuiApplication') as mock_app:
        mock_app.instance.return_value = None
        dm = DisplayManager()
        
    assert hasattr(dm, '_disconnect_monitor_signals')
    assert callable(dm._disconnect_monitor_signals)


def test_engine_subscription_ids_populated_on_subscribe():
    """_subscribe_to_events should populate _subscription_ids."""
    from engine.screensaver_engine import ScreensaverEngine
    from core.events import EventSystem
    
    engine = ScreensaverEngine()
    engine.event_system = EventSystem()
    
    # Call subscribe method
    engine._subscribe_to_events()
    
    # Should have at least one subscription ID
    assert len(engine._subscription_ids) >= 1


def test_engine_unsubscribe_clears_subscription_ids():
    """_unsubscribe_all_events should clear _subscription_ids."""
    from engine.screensaver_engine import ScreensaverEngine
    from core.events import EventSystem
    
    engine = ScreensaverEngine()
    engine.event_system = EventSystem()
    
    # Subscribe first
    engine._subscribe_to_events()
    assert len(engine._subscription_ids) >= 1
    
    # Unsubscribe
    engine._unsubscribe_all_events()
    assert len(engine._subscription_ids) == 0


def test_engine_unsubscribe_actually_removes_from_event_system():
    """_unsubscribe_all_events should remove subscriptions from EventSystem."""
    from engine.screensaver_engine import ScreensaverEngine
    from core.events import EventSystem
    
    engine = ScreensaverEngine()
    engine.event_system = EventSystem()
    
    # Get initial count
    initial_count = engine.event_system.get_subscription_count()
    
    # Subscribe
    engine._subscribe_to_events()
    after_subscribe = engine.event_system.get_subscription_count()
    assert after_subscribe > initial_count
    
    # Unsubscribe
    engine._unsubscribe_all_events()
    after_unsubscribe = engine.event_system.get_subscription_count()
    assert after_unsubscribe == initial_count
