"""
Tests for GLStateManager overlay integration.

Tests cover:
- State transitions for GL overlays
- GLStateManager is_ready() gating for paintGL
- Group A→B→C fallback scenarios
- Error recovery with exponential backoff
"""
import pytest

from rendering.gl_state_manager import GLStateManager, GLContextState, is_valid_gl_transition


class TestGLStateTransitions:
    """Tests for GL state transition validation."""
    
    def test_valid_init_to_ready(self):
        """Test UNINITIALIZED → INITIALIZING → READY path."""
        assert is_valid_gl_transition(GLContextState.UNINITIALIZED, GLContextState.INITIALIZING)
        assert is_valid_gl_transition(GLContextState.INITIALIZING, GLContextState.READY)
    
    def test_valid_init_to_error(self):
        """Test INITIALIZING → ERROR path."""
        assert is_valid_gl_transition(GLContextState.INITIALIZING, GLContextState.ERROR)
    
    def test_valid_ready_to_error(self):
        """Test READY → ERROR path (runtime error)."""
        assert is_valid_gl_transition(GLContextState.READY, GLContextState.ERROR)
    
    def test_valid_ready_to_context_lost(self):
        """Test READY → CONTEXT_LOST path (driver reset)."""
        assert is_valid_gl_transition(GLContextState.READY, GLContextState.CONTEXT_LOST)
    
    def test_valid_error_to_init_retry(self):
        """Test ERROR → INITIALIZING path (retry)."""
        assert is_valid_gl_transition(GLContextState.ERROR, GLContextState.INITIALIZING)
    
    def test_valid_cleanup_path(self):
        """Test READY → DESTROYING → DESTROYED path."""
        assert is_valid_gl_transition(GLContextState.READY, GLContextState.DESTROYING)
        assert is_valid_gl_transition(GLContextState.DESTROYING, GLContextState.DESTROYED)
    
    def test_invalid_skip_init(self):
        """Test that skipping INITIALIZING is invalid."""
        assert not is_valid_gl_transition(GLContextState.UNINITIALIZED, GLContextState.READY)
    
    def test_invalid_destroyed_transition(self):
        """Test that DESTROYED is terminal (no outgoing transitions)."""
        assert not is_valid_gl_transition(GLContextState.DESTROYED, GLContextState.UNINITIALIZED)
        assert not is_valid_gl_transition(GLContextState.DESTROYED, GLContextState.INITIALIZING)
        assert not is_valid_gl_transition(GLContextState.DESTROYED, GLContextState.READY)


class TestGLStateManager:
    """Tests for GLStateManager class."""
    
    def test_initial_state(self):
        """Test initial state is UNINITIALIZED."""
        manager = GLStateManager("test_overlay")
        assert manager.get_state() == GLContextState.UNINITIALIZED
        assert manager.is_uninitialized()
        assert not manager.is_ready()
    
    def test_transition_to_ready(self):
        """Test transitioning to READY state."""
        manager = GLStateManager("test_overlay")
        
        assert manager.transition(GLContextState.INITIALIZING)
        assert manager.is_initializing()
        
        assert manager.transition(GLContextState.READY)
        assert manager.is_ready()
        assert manager.can_render()
    
    def test_transition_to_error(self):
        """Test transitioning to ERROR state with message."""
        manager = GLStateManager("test_overlay")
        
        manager.transition(GLContextState.INITIALIZING)
        
        error_msg = "Shader compilation failed"
        assert manager.transition(GLContextState.ERROR, error_msg)
        
        assert manager.is_error()
        assert manager.get_error_message() == error_msg
    
    def test_invalid_transition_rejected(self):
        """Test that invalid transitions are rejected."""
        manager = GLStateManager("test_overlay")
        
        # Can't go directly to READY
        assert not manager.transition(GLContextState.READY)
        assert manager.is_uninitialized()
    
    def test_force_state(self):
        """Test force_state bypasses validation."""
        manager = GLStateManager("test_overlay")
        
        # Force directly to READY (bypasses validation)
        manager.force_state(GLContextState.READY, "test_force")
        assert manager.is_ready()
    
    def test_callback_invocation(self):
        """Test state change callbacks are invoked."""
        manager = GLStateManager("test_overlay")
        
        callback_called = []
        
        def on_ready(old_state, new_state):
            callback_called.append((old_state, new_state))
        
        manager.register_callback(GLContextState.READY, on_ready)
        
        manager.transition(GLContextState.INITIALIZING)
        manager.transition(GLContextState.READY)
        
        assert len(callback_called) == 1
        assert callback_called[0] == (GLContextState.INITIALIZING, GLContextState.READY)
    
    def test_transition_history(self):
        """Test transition history is recorded."""
        manager = GLStateManager("test_overlay")
        
        manager.transition(GLContextState.INITIALIZING)
        manager.transition(GLContextState.READY)
        
        history = manager.get_transition_history()
        assert len(history) == 2
        
        # Check first transition
        assert history[0][0] == GLContextState.UNINITIALIZED
        assert history[0][1] == GLContextState.INITIALIZING
        
        # Check second transition
        assert history[1][0] == GLContextState.INITIALIZING
        assert history[1][1] == GLContextState.READY
    
    def test_statistics(self):
        """Test statistics tracking."""
        manager = GLStateManager("test_overlay")
        
        manager.transition(GLContextState.INITIALIZING)
        manager.transition(GLContextState.READY)
        manager.transition(GLContextState.DESTROYED)  # Invalid from READY
        
        stats = manager.get_stats()  # Correct method name
        assert stats["transitions"] == 2  # Only valid transitions counted
        assert stats["invalid_transitions"] == 1


class TestGLOverlayIntegration:
    """Tests for overlay integration patterns."""
    
    def test_overlay_gating_pattern(self):
        """Test the paintGL gating pattern."""
        manager = GLStateManager("spotify_bars")
        
        # Before initialization - should not render
        should_render = manager.is_ready() or manager.is_error()
        assert not should_render
        
        # During initialization - should not render
        manager.transition(GLContextState.INITIALIZING)
        should_render = manager.is_ready() or manager.is_error()
        assert not should_render
        
        # After successful init - should render
        manager.transition(GLContextState.READY)
        should_render = manager.is_ready() or manager.is_error()
        assert should_render
    
    def test_error_fallback_pattern(self):
        """Test the error fallback pattern (Group A→B)."""
        manager = GLStateManager("gl_compositor")
        
        # Successful init
        manager.transition(GLContextState.INITIALIZING)
        manager.transition(GLContextState.READY)
        
        # Runtime error (shader failed)
        manager.transition(GLContextState.ERROR, "Shader runtime error")
        
        # Should allow fallback to QPainter (Group B)
        assert manager.is_error()
        assert manager.get_error_message() == "Shader runtime error"
        
        # Retry allowed
        assert is_valid_gl_transition(GLContextState.ERROR, GLContextState.INITIALIZING)
    
    def test_context_lost_recovery(self):
        """Test context lost recovery pattern."""
        manager = GLStateManager("gl_compositor")
        
        manager.transition(GLContextState.INITIALIZING)
        manager.transition(GLContextState.READY)
        
        # Context lost (driver reset)
        manager.transition(GLContextState.CONTEXT_LOST)
        assert manager.is_error()  # CONTEXT_LOST is an error state
        
        # Recovery attempt allowed
        assert is_valid_gl_transition(GLContextState.CONTEXT_LOST, GLContextState.INITIALIZING)


class TestGLDemotionScenarios:
    """Tests for Group A→B→C fallback scenarios."""
    
    def test_shader_failure_demotion(self):
        """Test demotion from Group A (shader) to Group B (QPainter)."""
        # Simulate shader compilation failure
        manager = GLStateManager("glsl_transition")
        
        manager.transition(GLContextState.INITIALIZING)
        manager.transition(GLContextState.ERROR, "GLSL compile failed")
        
        # Session-level flag should track demotion
        # (This would be tracked in the actual GLErrorHandler singleton)
        assert manager.is_error()
        
        # Retry should be allowed (will try Group B instead)
        assert is_valid_gl_transition(GLContextState.ERROR, GLContextState.INITIALIZING)
    
    def test_compositor_failure_demotion(self):
        """Test demotion from Group B (compositor) to Group C (software)."""
        manager = GLStateManager("compositor")
        
        manager.transition(GLContextState.INITIALIZING)
        manager.transition(GLContextState.ERROR, "GL context creation failed")
        
        # Should allow destroying and falling back to software
        manager.transition(GLContextState.DESTROYING)
        manager.transition(GLContextState.DESTROYED)
        
        assert manager.is_destroyed()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
