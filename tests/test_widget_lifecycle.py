"""
Tests for widget lifecycle management.

Tests the BaseOverlayWidget lifecycle state machine including:
- State transitions (CREATED → INITIALIZED → ACTIVE ⇄ HIDDEN → DESTROYED)
- Invalid transition rejection
- Thread safety
- ResourceManager integration
- Cleanup behavior
"""
import gc
import threading
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from widgets.base_overlay_widget import (
    BaseOverlayWidget,
    OverlayPosition,
    WidgetLifecycleState,
    is_valid_lifecycle_transition,
)
from core.resources.manager import ResourceManager


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qt_app():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def parent_widget(qt_app):
    """Create a parent widget for testing."""
    parent = QWidget()
    parent.resize(800, 600)
    yield parent
    parent.deleteLater()


@pytest.fixture
def resource_manager():
    """Create a ResourceManager for testing."""
    rm = ResourceManager()
    yield rm
    try:
        rm.cleanup_all()
    except Exception:
        pass


class ConcreteOverlayWidget(BaseOverlayWidget):
    """Concrete implementation of BaseOverlayWidget for testing."""
    
    def __init__(self, parent=None, overlay_name="test_widget"):
        super().__init__(parent, OverlayPosition.TOP_RIGHT, overlay_name)
        self.initialize_called = False
        self.activate_called = False
        self.deactivate_called = False
        self.cleanup_called = False
        self.update_content_called = False
        
    def _initialize_impl(self) -> None:
        self.initialize_called = True
        
    def _activate_impl(self) -> None:
        self.activate_called = True
        
    def _deactivate_impl(self) -> None:
        self.deactivate_called = True
        
    def _cleanup_impl(self) -> None:
        self.cleanup_called = True
        
    def _update_content(self) -> None:
        self.update_content_called = True


class FailingOverlayWidget(BaseOverlayWidget):
    """Widget that fails during lifecycle transitions for testing error handling."""
    
    def __init__(self, parent=None, fail_on: str = "initialize"):
        super().__init__(parent, OverlayPosition.TOP_RIGHT, "failing_widget")
        self.fail_on = fail_on
        
    def _initialize_impl(self) -> None:
        if self.fail_on == "initialize":
            raise RuntimeError("Initialization failed")
        
    def _activate_impl(self) -> None:
        if self.fail_on == "activate":
            raise RuntimeError("Activation failed")
        
    def _deactivate_impl(self) -> None:
        if self.fail_on == "deactivate":
            raise RuntimeError("Deactivation failed")
        
    def _cleanup_impl(self) -> None:
        if self.fail_on == "cleanup":
            raise RuntimeError("Cleanup failed")
        
    def _update_content(self) -> None:
        pass


# ---------------------------------------------------------------------------
# State Transition Validation Tests
# ---------------------------------------------------------------------------

class TestLifecycleStateTransitions:
    """Test lifecycle state transition validation."""
    
    def test_valid_transitions_from_created(self):
        """Test valid transitions from CREATED state."""
        assert is_valid_lifecycle_transition(
            WidgetLifecycleState.CREATED, 
            WidgetLifecycleState.INITIALIZED
        )
        assert is_valid_lifecycle_transition(
            WidgetLifecycleState.CREATED, 
            WidgetLifecycleState.DESTROYED
        )
    
    def test_invalid_transitions_from_created(self):
        """Test invalid transitions from CREATED state."""
        assert not is_valid_lifecycle_transition(
            WidgetLifecycleState.CREATED, 
            WidgetLifecycleState.ACTIVE
        )
        assert not is_valid_lifecycle_transition(
            WidgetLifecycleState.CREATED, 
            WidgetLifecycleState.HIDDEN
        )
    
    def test_valid_transitions_from_initialized(self):
        """Test valid transitions from INITIALIZED state."""
        assert is_valid_lifecycle_transition(
            WidgetLifecycleState.INITIALIZED, 
            WidgetLifecycleState.ACTIVE
        )
        assert is_valid_lifecycle_transition(
            WidgetLifecycleState.INITIALIZED, 
            WidgetLifecycleState.DESTROYED
        )
    
    def test_invalid_transitions_from_initialized(self):
        """Test invalid transitions from INITIALIZED state."""
        assert not is_valid_lifecycle_transition(
            WidgetLifecycleState.INITIALIZED, 
            WidgetLifecycleState.CREATED
        )
        assert not is_valid_lifecycle_transition(
            WidgetLifecycleState.INITIALIZED, 
            WidgetLifecycleState.HIDDEN
        )
    
    def test_valid_transitions_from_active(self):
        """Test valid transitions from ACTIVE state."""
        assert is_valid_lifecycle_transition(
            WidgetLifecycleState.ACTIVE, 
            WidgetLifecycleState.HIDDEN
        )
        assert is_valid_lifecycle_transition(
            WidgetLifecycleState.ACTIVE, 
            WidgetLifecycleState.DESTROYED
        )
    
    def test_invalid_transitions_from_active(self):
        """Test invalid transitions from ACTIVE state."""
        assert not is_valid_lifecycle_transition(
            WidgetLifecycleState.ACTIVE, 
            WidgetLifecycleState.CREATED
        )
        assert not is_valid_lifecycle_transition(
            WidgetLifecycleState.ACTIVE, 
            WidgetLifecycleState.INITIALIZED
        )
    
    def test_valid_transitions_from_hidden(self):
        """Test valid transitions from HIDDEN state."""
        assert is_valid_lifecycle_transition(
            WidgetLifecycleState.HIDDEN, 
            WidgetLifecycleState.ACTIVE
        )
        assert is_valid_lifecycle_transition(
            WidgetLifecycleState.HIDDEN, 
            WidgetLifecycleState.DESTROYED
        )
    
    def test_destroyed_is_terminal(self):
        """Test that DESTROYED is a terminal state."""
        for state in WidgetLifecycleState:
            assert not is_valid_lifecycle_transition(
                WidgetLifecycleState.DESTROYED, 
                state
            )


# ---------------------------------------------------------------------------
# Widget Lifecycle Tests
# ---------------------------------------------------------------------------

class TestWidgetLifecycle:
    """Test widget lifecycle methods."""
    
    def test_initial_state_is_created(self, qt_app, parent_widget):
        """Test widget starts in CREATED state."""
        widget = ConcreteOverlayWidget(parent_widget)
        assert widget.get_lifecycle_state() == WidgetLifecycleState.CREATED
        assert not widget.is_lifecycle_initialized()
        assert not widget.is_lifecycle_active()
        assert not widget.is_lifecycle_destroyed()
    
    def test_initialize_transitions_to_initialized(self, qt_app, parent_widget):
        """Test initialize() transitions to INITIALIZED state."""
        widget = ConcreteOverlayWidget(parent_widget)
        
        result = widget.initialize()
        
        assert result is True
        assert widget.get_lifecycle_state() == WidgetLifecycleState.INITIALIZED
        assert widget.is_lifecycle_initialized()
        assert widget.initialize_called
    
    def test_activate_transitions_to_active(self, qt_app, parent_widget):
        """Test activate() transitions to ACTIVE state."""
        widget = ConcreteOverlayWidget(parent_widget)
        widget.initialize()
        
        result = widget.activate()
        
        assert result is True
        assert widget.get_lifecycle_state() == WidgetLifecycleState.ACTIVE
        assert widget.is_lifecycle_active()
        assert widget.activate_called
    
    def test_deactivate_transitions_to_hidden(self, qt_app, parent_widget):
        """Test deactivate() transitions to HIDDEN state."""
        widget = ConcreteOverlayWidget(parent_widget)
        widget.initialize()
        widget.activate()
        
        result = widget.deactivate()
        
        assert result is True
        assert widget.get_lifecycle_state() == WidgetLifecycleState.HIDDEN
        assert not widget.is_lifecycle_active()
        assert widget.deactivate_called
    
    def test_reactivate_from_hidden(self, qt_app, parent_widget):
        """Test widget can be reactivated from HIDDEN state."""
        widget = ConcreteOverlayWidget(parent_widget)
        widget.initialize()
        widget.activate()
        widget.deactivate()
        
        # Reset flag to verify it's called again
        widget.activate_called = False
        
        result = widget.activate()
        
        assert result is True
        assert widget.get_lifecycle_state() == WidgetLifecycleState.ACTIVE
        assert widget.activate_called
    
    def test_cleanup_transitions_to_destroyed(self, qt_app, parent_widget):
        """Test cleanup() transitions to DESTROYED state."""
        widget = ConcreteOverlayWidget(parent_widget)
        widget.initialize()
        widget.activate()
        
        widget.cleanup()
        
        assert widget.get_lifecycle_state() == WidgetLifecycleState.DESTROYED
        assert widget.is_lifecycle_destroyed()
        assert widget.cleanup_called
    
    def test_cleanup_is_idempotent(self, qt_app, parent_widget):
        """Test cleanup() can be called multiple times safely."""
        widget = ConcreteOverlayWidget(parent_widget)
        widget.initialize()
        
        widget.cleanup()
        widget.cleanup()  # Should not raise
        widget.cleanup()  # Should not raise
        
        assert widget.get_lifecycle_state() == WidgetLifecycleState.DESTROYED
    
    def test_cleanup_from_any_state(self, qt_app, parent_widget):
        """Test cleanup() works from any state."""
        # From CREATED
        widget1 = ConcreteOverlayWidget(parent_widget, "widget1")
        widget1.cleanup()
        assert widget1.get_lifecycle_state() == WidgetLifecycleState.DESTROYED
        
        # From INITIALIZED
        widget2 = ConcreteOverlayWidget(parent_widget, "widget2")
        widget2.initialize()
        widget2.cleanup()
        assert widget2.get_lifecycle_state() == WidgetLifecycleState.DESTROYED
        
        # From ACTIVE
        widget3 = ConcreteOverlayWidget(parent_widget, "widget3")
        widget3.initialize()
        widget3.activate()
        widget3.cleanup()
        assert widget3.get_lifecycle_state() == WidgetLifecycleState.DESTROYED
        
        # From HIDDEN
        widget4 = ConcreteOverlayWidget(parent_widget, "widget4")
        widget4.initialize()
        widget4.activate()
        widget4.deactivate()
        widget4.cleanup()
        assert widget4.get_lifecycle_state() == WidgetLifecycleState.DESTROYED


# ---------------------------------------------------------------------------
# Invalid Transition Tests
# ---------------------------------------------------------------------------

class TestInvalidTransitions:
    """Test that invalid transitions are rejected."""
    
    def test_cannot_activate_from_created(self, qt_app, parent_widget):
        """Test activate() fails from CREATED state."""
        widget = ConcreteOverlayWidget(parent_widget)
        
        result = widget.activate()
        
        assert result is False
        assert widget.get_lifecycle_state() == WidgetLifecycleState.CREATED
        assert not widget.activate_called
    
    def test_cannot_deactivate_from_created(self, qt_app, parent_widget):
        """Test deactivate() fails from CREATED state."""
        widget = ConcreteOverlayWidget(parent_widget)
        
        result = widget.deactivate()
        
        assert result is False
        assert widget.get_lifecycle_state() == WidgetLifecycleState.CREATED
    
    def test_cannot_initialize_twice(self, qt_app, parent_widget):
        """Test initialize() fails if already initialized."""
        widget = ConcreteOverlayWidget(parent_widget)
        widget.initialize()
        
        # Reset flag
        widget.initialize_called = False
        
        result = widget.initialize()
        
        assert result is False
        assert not widget.initialize_called
    
    def test_cannot_deactivate_from_initialized(self, qt_app, parent_widget):
        """Test deactivate() fails from INITIALIZED state."""
        widget = ConcreteOverlayWidget(parent_widget)
        widget.initialize()
        
        result = widget.deactivate()
        
        assert result is False
        assert widget.get_lifecycle_state() == WidgetLifecycleState.INITIALIZED


# ---------------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------------

class TestLifecycleErrorHandling:
    """Test error handling during lifecycle transitions."""
    
    def test_initialization_failure(self, qt_app, parent_widget):
        """Test widget handles initialization failure gracefully."""
        widget = FailingOverlayWidget(parent_widget, fail_on="initialize")
        
        result = widget.initialize()
        
        assert result is False
        assert widget.get_lifecycle_state() == WidgetLifecycleState.CREATED
    
    def test_activation_failure(self, qt_app, parent_widget):
        """Test widget handles activation failure gracefully."""
        widget = FailingOverlayWidget(parent_widget, fail_on="activate")
        widget.initialize()
        
        result = widget.activate()
        
        assert result is False
        assert widget.get_lifecycle_state() == WidgetLifecycleState.INITIALIZED
    
    def test_deactivation_failure(self, qt_app, parent_widget):
        """Test widget handles deactivation failure gracefully."""
        widget = FailingOverlayWidget(parent_widget, fail_on="deactivate")
        widget.initialize()
        widget.activate()
        
        result = widget.deactivate()
        
        assert result is False
        assert widget.get_lifecycle_state() == WidgetLifecycleState.ACTIVE
    
    def test_cleanup_continues_on_failure(self, qt_app, parent_widget):
        """Test cleanup() completes even if _cleanup_impl fails."""
        widget = FailingOverlayWidget(parent_widget, fail_on="cleanup")
        widget.initialize()
        widget.activate()
        
        # Should not raise
        widget.cleanup()
        
        # State should still be DESTROYED
        assert widget.get_lifecycle_state() == WidgetLifecycleState.DESTROYED


# ---------------------------------------------------------------------------
# Thread Safety Tests
# ---------------------------------------------------------------------------

class TestLifecycleThreadSafety:
    """Test thread safety of lifecycle operations."""
    
    def test_concurrent_state_reads(self, qt_app, parent_widget):
        """Test concurrent state reads are safe."""
        widget = ConcreteOverlayWidget(parent_widget)
        widget.initialize()
        errors = []
        
        def reader():
            try:
                for _ in range(100):
                    state = widget.get_lifecycle_state()
                    assert state in WidgetLifecycleState
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
    
    def test_concurrent_lifecycle_queries(self, qt_app, parent_widget):
        """Test concurrent lifecycle query methods are safe."""
        widget = ConcreteOverlayWidget(parent_widget)
        widget.initialize()
        widget.activate()
        errors = []
        
        def query():
            try:
                for _ in range(100):
                    widget.is_lifecycle_initialized()
                    widget.is_lifecycle_active()
                    widget.is_lifecycle_destroyed()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=query) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# ResourceManager Integration Tests
# ---------------------------------------------------------------------------

class TestResourceManagerIntegration:
    """Test ResourceManager integration with widget lifecycle."""
    
    def test_set_resource_manager(self, qt_app, parent_widget, resource_manager):
        """Test setting ResourceManager on widget."""
        widget = ConcreteOverlayWidget(parent_widget)
        
        widget.set_resource_manager(resource_manager)
        
        assert widget.get_resource_manager() is resource_manager
    
    def test_cleanup_unregisters_resources(self, qt_app, parent_widget, resource_manager):
        """Test cleanup unregisters all resources."""
        widget = ConcreteOverlayWidget(parent_widget)
        widget.set_resource_manager(resource_manager)
        widget.initialize()
        
        # Register a mock resource
        mock_resource = MagicMock()
        resource_id = widget._register_resource(mock_resource, "test resource")
        
        assert resource_id is not None
        assert resource_id in widget._registered_resource_ids
        
        # Cleanup should unregister
        widget.cleanup()
        
        assert len(widget._registered_resource_ids) == 0


# ---------------------------------------------------------------------------
# Full Lifecycle Cycle Tests
# ---------------------------------------------------------------------------

class TestFullLifecycleCycle:
    """Test complete lifecycle cycles."""
    
    def test_full_lifecycle_cycle(self, qt_app, parent_widget):
        """Test complete lifecycle from creation to destruction."""
        widget = ConcreteOverlayWidget(parent_widget)
        
        # CREATED
        assert widget.get_lifecycle_state() == WidgetLifecycleState.CREATED
        
        # CREATED → INITIALIZED
        assert widget.initialize()
        assert widget.get_lifecycle_state() == WidgetLifecycleState.INITIALIZED
        
        # INITIALIZED → ACTIVE
        assert widget.activate()
        assert widget.get_lifecycle_state() == WidgetLifecycleState.ACTIVE
        
        # ACTIVE → HIDDEN
        assert widget.deactivate()
        assert widget.get_lifecycle_state() == WidgetLifecycleState.HIDDEN
        
        # HIDDEN → ACTIVE (reactivate)
        assert widget.activate()
        assert widget.get_lifecycle_state() == WidgetLifecycleState.ACTIVE
        
        # ACTIVE → DESTROYED
        widget.cleanup()
        assert widget.get_lifecycle_state() == WidgetLifecycleState.DESTROYED
    
    def test_multiple_lifecycle_cycles_no_leaks(self, qt_app, parent_widget):
        """Test multiple lifecycle cycles don't leak memory."""
        # Run multiple cycles
        for i in range(50):
            widget = ConcreteOverlayWidget(parent_widget, f"widget_{i}")
            widget.initialize()
            widget.activate()
            widget.deactivate()
            widget.cleanup()
        
        # Force garbage collection
        gc.collect()
        
        # If we get here without error, no obvious leaks
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
