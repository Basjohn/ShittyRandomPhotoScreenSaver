"""
Tests for WidgetManager lifecycle and coordination.

Tests cover:
- Widget registration and retrieval
- Lifecycle methods (initialize, activate, deactivate, cleanup)
- Fade coordination
- Raise operations with rate limiting
- Settings integration for live updates
- ResourceManager integration
"""
import pytest
from unittest.mock import MagicMock
from typing import Dict, Any


class MockWidget:
    """Mock widget for testing."""
    
    def __init__(self, name: str = "mock"):
        self._name = name
        self._visible = False
        self._geometry = (0, 0, 100, 100)
        self._lifecycle_state = "CREATED"
        self._raised = False
        self._widget_manager = None
        
    def show(self):
        self._visible = True
        
    def hide(self):
        self._visible = False
        
    def isVisible(self):
        return self._visible
        
    def raise_(self):
        self._raised = True
        
    def setGeometry(self, x, y, w, h):
        self._geometry = (x, y, w, h)
        
    def geometry(self):
        from PySide6.QtCore import QRect
        return QRect(*self._geometry)
        
    def set_widget_manager(self, manager):
        self._widget_manager = manager
        
    def initialize(self):
        self._lifecycle_state = "INITIALIZED"
        
    def activate(self):
        self._lifecycle_state = "ACTIVE"
        
    def deactivate(self):
        self._lifecycle_state = "INACTIVE"
        
    def cleanup(self):
        self._lifecycle_state = "CLEANED"


class MockResourceManager:
    """Mock ResourceManager for testing."""
    
    def __init__(self):
        self._registered = {}
        
    def register_qt(self, widget, description=""):
        self._registered[id(widget)] = description


class MockSettingsManager:
    """Mock SettingsManager for testing."""
    
    def __init__(self):
        self._settings: Dict[str, Any] = {}
        self._handlers = []
        
    def get(self, key, default=None):
        return self._settings.get(key, default)
        
    def set(self, key, value):
        self._settings[key] = value
        for handler in self._handlers:
            handler(key, value)
            
    class settings_changed:
        _handlers = []
        
        @classmethod
        def connect(cls, handler):
            cls._handlers.append(handler)
            
        @classmethod
        def disconnect(cls, handler):
            if handler in cls._handlers:
                cls._handlers.remove(handler)


class TestWidgetRegistration:
    """Tests for widget registration."""
    
    def test_register_widget(self):
        """Test registering a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        assert manager.get_widget("test") is widget
    
    def test_unregister_widget(self):
        """Test unregistering a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        removed = manager.unregister_widget("test")
        assert removed is widget
        assert manager.get_widget("test") is None
    
    def test_get_all_widgets(self):
        """Test getting all widgets."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        w1 = MockWidget("w1")
        w2 = MockWidget("w2")
        manager.register_widget("w1", w1)
        manager.register_widget("w2", w2)
        
        all_widgets = manager.get_all_widgets()
        assert len(all_widgets) == 2
        assert w1 in all_widgets
        assert w2 in all_widgets
    
    def test_widget_manager_set_on_register(self):
        """Test that widget manager is set on widget during registration."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        assert widget._widget_manager is manager


class TestWidgetLifecycle:
    """Tests for widget lifecycle methods."""
    
    def test_initialize_widget(self):
        """Test initializing a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.initialize_widget("test")
        assert result is True
        assert widget._lifecycle_state == "INITIALIZED"
    
    def test_activate_widget(self):
        """Test activating a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.activate_widget("test")
        assert result is True
        assert widget._lifecycle_state == "ACTIVE"
    
    def test_deactivate_widget(self):
        """Test deactivating a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.deactivate_widget("test")
        assert result is True
        assert widget._lifecycle_state == "INACTIVE"
    
    def test_cleanup_widget(self):
        """Test cleaning up a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.cleanup_widget("test")
        assert result is True
        assert widget._lifecycle_state == "CLEANED"
    
    def test_initialize_all_widgets(self):
        """Test initializing all widgets."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        w1 = MockWidget("w1")
        w2 = MockWidget("w2")
        manager.register_widget("w1", w1)
        manager.register_widget("w2", w2)
        
        count = manager.initialize_all_widgets()
        assert count == 2
        assert w1._lifecycle_state == "INITIALIZED"
        assert w2._lifecycle_state == "INITIALIZED"


class TestWidgetVisibility:
    """Tests for widget visibility operations."""
    
    def test_show_widget(self):
        """Test showing a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.show_widget("test")
        assert result is True
        assert widget._visible is True
    
    def test_hide_widget(self):
        """Test hiding a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        widget._visible = True
        manager.register_widget("test", widget)
        
        result = manager.hide_widget("test")
        assert result is True
        assert widget._visible is False
    
    def test_set_widget_geometry(self):
        """Test setting widget geometry."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.set_widget_geometry("test", 10, 20, 300, 200)
        assert result is True
        assert widget._geometry == (10, 20, 300, 200)


class TestRaiseOperations:
    """Tests for raise operations."""
    
    def test_raise_widget(self):
        """Test raising a specific widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.raise_widget("test")
        assert result is True
        assert widget._raised is True
    
    def test_raise_all_widgets(self):
        """Test raising all widgets."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        w1 = MockWidget("w1")
        w2 = MockWidget("w2")
        manager.register_widget("w1", w1)
        manager.register_widget("w2", w2)
        
        manager.raise_all_widgets()
        assert w1._raised is True
        assert w2._raised is True


class TestFadeCallbacks:
    """Tests for fade callback coordination."""
    
    def test_register_fade_callback(self):
        """Test registering a fade callback."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        callback = MagicMock()
        manager.register_fade_callback("test", callback)
        
        manager.invoke_fade_callbacks(0.5)
        callback.assert_called_once_with(0.5)
    
    def test_multiple_fade_callbacks(self):
        """Test invoking multiple fade callbacks."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        cb1 = MagicMock()
        cb2 = MagicMock()
        manager.register_fade_callback("cb1", cb1)
        manager.register_fade_callback("cb2", cb2)
        
        manager.invoke_fade_callbacks(0.75)
        cb1.assert_called_once_with(0.75)
        cb2.assert_called_once_with(0.75)


class TestCleanup:
    """Tests for cleanup operations."""
    
    def test_cleanup_clears_widgets(self):
        """Test that cleanup clears all widgets."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        w1 = MockWidget("w1")
        w2 = MockWidget("w2")
        manager.register_widget("w1", w1)
        manager.register_widget("w2", w2)
        
        manager.cleanup()
        
        assert len(manager.get_all_widgets()) == 0
    
    def test_cleanup_calls_widget_cleanup(self):
        """Test that cleanup calls cleanup on widgets."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        manager.cleanup()
        
        assert widget._lifecycle_state == "CLEANED"


class TestPositioning:
    """Tests for widget positioning."""
    
    def test_set_container_size(self):
        """Test setting container size."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        manager.set_container_size(1920, 1080)
        
        positioner = manager.get_positioner()
        assert positioner is not None


class TestResourceManagerIntegration:
    """Tests for ResourceManager integration."""
    
    def test_widget_registered_with_resource_manager(self):
        """Test that widgets are registered with ResourceManager."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        resource_manager = MockResourceManager()
        manager = WidgetManager(parent, resource_manager)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        assert id(widget) in resource_manager._registered


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
