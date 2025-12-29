"""
Tests for GL State Manager.

Tests the GLStateManager state machine including:
- State transitions
- Invalid transition rejection
- Thread safety
- Callbacks
- Error handling
- Statistics and debugging
"""
import threading
from unittest.mock import MagicMock

import pytest

from rendering.gl_state_manager import (
    GLContextState,
    GLStateManager,
    GLStateGuard,
    is_valid_gl_transition,
    create_gl_state_manager,
)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state_manager():
    """Create a fresh GLStateManager for testing."""
    return GLStateManager("test_context")


# ---------------------------------------------------------------------------
# State Transition Validation Tests
# ---------------------------------------------------------------------------

class TestGLStateTransitions:
    """Test GL state transition validation."""
    
    def test_valid_transitions_from_uninitialized(self):
        """Test valid transitions from UNINITIALIZED state."""
        assert is_valid_gl_transition(
            GLContextState.UNINITIALIZED, 
            GLContextState.INITIALIZING
        )
        assert is_valid_gl_transition(
            GLContextState.UNINITIALIZED, 
            GLContextState.ERROR
        )
        assert is_valid_gl_transition(
            GLContextState.UNINITIALIZED, 
            GLContextState.DESTROYED
        )
    
    def test_invalid_transitions_from_uninitialized(self):
        """Test invalid transitions from UNINITIALIZED state."""
        assert not is_valid_gl_transition(
            GLContextState.UNINITIALIZED, 
            GLContextState.READY
        )
        assert not is_valid_gl_transition(
            GLContextState.UNINITIALIZED, 
            GLContextState.CONTEXT_LOST
        )
    
    def test_valid_transitions_from_initializing(self):
        """Test valid transitions from INITIALIZING state."""
        assert is_valid_gl_transition(
            GLContextState.INITIALIZING, 
            GLContextState.READY
        )
        assert is_valid_gl_transition(
            GLContextState.INITIALIZING, 
            GLContextState.ERROR
        )
        assert is_valid_gl_transition(
            GLContextState.INITIALIZING, 
            GLContextState.DESTROYED
        )
    
    def test_valid_transitions_from_ready(self):
        """Test valid transitions from READY state."""
        assert is_valid_gl_transition(
            GLContextState.READY, 
            GLContextState.CONTEXT_LOST
        )
        assert is_valid_gl_transition(
            GLContextState.READY, 
            GLContextState.DESTROYING
        )
        assert is_valid_gl_transition(
            GLContextState.READY, 
            GLContextState.ERROR
        )
    
    def test_invalid_transitions_from_ready(self):
        """Test invalid transitions from READY state."""
        assert not is_valid_gl_transition(
            GLContextState.READY, 
            GLContextState.UNINITIALIZED
        )
        assert not is_valid_gl_transition(
            GLContextState.READY, 
            GLContextState.INITIALIZING
        )
    
    def test_recovery_transitions(self):
        """Test recovery transitions from error states."""
        # Can retry from ERROR
        assert is_valid_gl_transition(
            GLContextState.ERROR, 
            GLContextState.INITIALIZING
        )
        # Can retry from CONTEXT_LOST
        assert is_valid_gl_transition(
            GLContextState.CONTEXT_LOST, 
            GLContextState.INITIALIZING
        )
    
    def test_destroyed_is_terminal(self):
        """Test that DESTROYED is a terminal state."""
        for state in GLContextState:
            assert not is_valid_gl_transition(
                GLContextState.DESTROYED, 
                state
            )


# ---------------------------------------------------------------------------
# GLStateManager Tests
# ---------------------------------------------------------------------------

class TestGLStateManager:
    """Test GLStateManager functionality."""
    
    def test_initial_state(self, state_manager):
        """Test initial state is UNINITIALIZED."""
        assert state_manager.get_state() == GLContextState.UNINITIALIZED
        assert state_manager.is_uninitialized()
        assert not state_manager.is_ready()
        assert not state_manager.is_error()
        assert not state_manager.is_destroyed()
    
    def test_transition_to_initializing(self, state_manager):
        """Test transition to INITIALIZING."""
        result = state_manager.transition(GLContextState.INITIALIZING)
        
        assert result is True
        assert state_manager.get_state() == GLContextState.INITIALIZING
        assert state_manager.is_initializing()
    
    def test_transition_to_ready(self, state_manager):
        """Test transition to READY."""
        state_manager.transition(GLContextState.INITIALIZING)
        result = state_manager.transition(GLContextState.READY)
        
        assert result is True
        assert state_manager.get_state() == GLContextState.READY
        assert state_manager.is_ready()
        assert state_manager.is_usable()
        assert state_manager.can_render()
    
    def test_transition_to_error(self, state_manager):
        """Test transition to ERROR with message."""
        state_manager.transition(GLContextState.INITIALIZING)
        result = state_manager.transition(
            GLContextState.ERROR, 
            "Shader compilation failed",
            "Fragment shader error at line 42"
        )
        
        assert result is True
        assert state_manager.get_state() == GLContextState.ERROR
        assert state_manager.is_error()
        assert state_manager.get_error_message() == "Shader compilation failed"
        assert state_manager.get_error_details() == "Fragment shader error at line 42"
    
    def test_transition_to_context_lost(self, state_manager):
        """Test transition to CONTEXT_LOST."""
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        result = state_manager.transition(
            GLContextState.CONTEXT_LOST, 
            "Driver reset"
        )
        
        assert result is True
        assert state_manager.get_state() == GLContextState.CONTEXT_LOST
        assert state_manager.is_error()
        assert state_manager.get_error_message() == "Driver reset"
    
    def test_full_lifecycle(self, state_manager):
        """Test complete lifecycle from creation to destruction."""
        # UNINITIALIZED → INITIALIZING
        assert state_manager.transition(GLContextState.INITIALIZING)
        
        # INITIALIZING → READY
        assert state_manager.transition(GLContextState.READY)
        
        # READY → DESTROYING
        assert state_manager.transition(GLContextState.DESTROYING)
        
        # DESTROYING → DESTROYED
        assert state_manager.transition(GLContextState.DESTROYED)
        
        assert state_manager.is_destroyed()
    
    def test_invalid_transition_rejected(self, state_manager):
        """Test invalid transitions are rejected."""
        # Can't go directly to READY from UNINITIALIZED
        result = state_manager.transition(GLContextState.READY)
        
        assert result is False
        assert state_manager.get_state() == GLContextState.UNINITIALIZED
    
    def test_recovery_from_error(self, state_manager):
        """Test recovery from ERROR state."""
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.ERROR, "Test error")
        
        # Can retry initialization
        assert state_manager.transition(GLContextState.INITIALIZING)
        assert state_manager.transition(GLContextState.READY)
        
        # Error should be cleared
        assert state_manager.get_error_message() is None
    
    def test_force_state(self, state_manager):
        """Test force_state bypasses validation."""
        state_manager.force_state(GLContextState.READY, "Testing")
        
        assert state_manager.get_state() == GLContextState.READY
    
    def test_clear_error(self, state_manager):
        """Test clear_error clears error info."""
        state_manager.transition(GLContextState.ERROR, "Test error")
        state_manager.clear_error()
        
        assert state_manager.get_error_message() is None
        assert state_manager.get_error_details() is None


# ---------------------------------------------------------------------------
# Callback Tests
# ---------------------------------------------------------------------------

class TestGLStateCallbacks:
    """Test GLStateManager callbacks."""
    
    def test_state_callback_invoked(self, state_manager):
        """Test callback is invoked on state change."""
        callback = MagicMock()
        state_manager.register_callback(GLContextState.READY, callback)
        
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == GLContextState.INITIALIZING  # old state
        assert args[1] == GLContextState.READY  # new state
    
    def test_any_state_callback(self, state_manager):
        """Test callback for any state change."""
        callback = MagicMock()
        state_manager.register_callback(None, callback)
        
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        
        assert callback.call_count == 2
    
    def test_unregister_callback(self, state_manager):
        """Test callback unregistration."""
        callback = MagicMock()
        state_manager.register_callback(GLContextState.READY, callback)
        state_manager.unregister_callback(GLContextState.READY, callback)
        
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        
        callback.assert_not_called()
    
    def test_callback_error_handled(self, state_manager):
        """Test callback errors don't break state transitions."""
        def bad_callback(old, new):
            raise RuntimeError("Callback error")
        
        state_manager.register_callback(GLContextState.READY, bad_callback)
        
        state_manager.transition(GLContextState.INITIALIZING)
        # Should not raise
        state_manager.transition(GLContextState.READY)
        
        assert state_manager.is_ready()


# ---------------------------------------------------------------------------
# Statistics and Debugging Tests
# ---------------------------------------------------------------------------

class TestGLStateDebugging:
    """Test GLStateManager debugging features."""
    
    def test_transition_history(self, state_manager):
        """Test transition history tracking."""
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        
        history = state_manager.get_transition_history()
        
        assert len(history) == 2
        assert history[0][0] == GLContextState.UNINITIALIZED
        assert history[0][1] == GLContextState.INITIALIZING
        assert history[1][0] == GLContextState.INITIALIZING
        assert history[1][1] == GLContextState.READY
    
    def test_stats_tracking(self, state_manager):
        """Test statistics tracking."""
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.ERROR, "Test")
        state_manager.transition(GLContextState.INITIALIZING)  # Recovery
        state_manager.transition(GLContextState.READY)
        
        # Try invalid transition
        state_manager.transition(GLContextState.UNINITIALIZED)
        
        stats = state_manager.get_stats()
        
        assert stats["transitions"] == 4
        assert stats["invalid_transitions"] == 1
        assert stats["errors"] == 1
        assert stats["recoveries"] == 1
    
    def test_dump_state(self, state_manager):
        """Test state dump for debugging."""
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        
        dump = state_manager.dump_state()
        
        assert "test_context" in dump
        assert "READY" in dump
        assert "Recent Transitions" in dump
    
    def test_get_name(self, state_manager):
        """Test get_name returns correct name."""
        assert state_manager.get_name() == "test_context"
    
    def test_reset(self, state_manager):
        """Test reset returns to initial state."""
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        
        state_manager.reset()
        
        assert state_manager.get_state() == GLContextState.UNINITIALIZED
        assert len(state_manager.get_transition_history()) == 0
        assert state_manager.get_stats()["transitions"] == 0


# ---------------------------------------------------------------------------
# Thread Safety Tests
# ---------------------------------------------------------------------------

class TestGLStateThreadSafety:
    """Test thread safety of GLStateManager."""
    
    def test_concurrent_state_reads(self, state_manager):
        """Test concurrent state reads are safe."""
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        errors = []
        
        def reader():
            try:
                for _ in range(100):
                    state = state_manager.get_state()
                    assert state in GLContextState
                    state_manager.is_ready()
                    state_manager.is_error()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
    
    def test_concurrent_transitions(self, state_manager):
        """Test concurrent transitions don't corrupt state."""
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        errors = []
        
        def transitioner():
            try:
                for _ in range(50):
                    # Try various transitions (some will fail, that's OK)
                    state_manager.transition(GLContextState.CONTEXT_LOST)
                    state_manager.transition(GLContextState.INITIALIZING)
                    state_manager.transition(GLContextState.READY)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=transitioner) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        # State should be valid
        assert state_manager.get_state() in GLContextState


# ---------------------------------------------------------------------------
# GLStateGuard Tests
# ---------------------------------------------------------------------------

class TestGLStateGuard:
    """Test GLStateGuard context manager."""
    
    def test_guard_valid_when_ready(self, state_manager):
        """Test guard is valid when context is ready."""
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        
        with GLStateGuard(state_manager, "test op") as guard:
            assert guard.is_valid
    
    def test_guard_invalid_when_not_ready(self, state_manager):
        """Test guard is invalid when context not ready."""
        with GLStateGuard(state_manager, "test op") as guard:
            assert not guard.is_valid
    
    def test_guard_handles_exception(self, state_manager):
        """Test guard transitions to ERROR on exception."""
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        
        with pytest.raises(RuntimeError):
            with GLStateGuard(state_manager, "test op"):
                raise RuntimeError("GL error")
        
        assert state_manager.is_error()
        assert "test op failed" in state_manager.get_error_message()


# ---------------------------------------------------------------------------
# Context Manager Tests
# ---------------------------------------------------------------------------

class TestGLStateContextManager:
    """Test GLStateManager as context manager."""
    
    def test_context_manager_normal_flow(self):
        """Test context manager with normal flow."""
        sm = GLStateManager("ctx_test")
        
        with sm:
            sm.transition(GLContextState.READY)
            assert sm.is_ready()
        
        assert sm.is_destroyed()
    
    def test_context_manager_with_exception(self):
        """Test context manager handles exceptions."""
        sm = GLStateManager("ctx_test")
        
        with pytest.raises(RuntimeError):
            with sm:
                raise RuntimeError("Test error")
        
        assert sm.is_destroyed()


# ---------------------------------------------------------------------------
# Factory Function Tests
# ---------------------------------------------------------------------------

class TestGLStateFactory:
    """Test factory functions."""
    
    def test_create_gl_state_manager(self):
        """Test create_gl_state_manager factory."""
        sm = create_gl_state_manager("factory_test")
        
        assert isinstance(sm, GLStateManager)
        assert sm.get_name() == "factory_test"
        assert sm.is_uninitialized()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
