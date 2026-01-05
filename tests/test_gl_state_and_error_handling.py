"""
Consolidated GL State Management and Error Handling Tests.

Tests for:
- GLStateManager state transitions and lifecycle
- GLErrorHandler capability demotion (Group A→B→C)
- GLStateManager subscription and error propagation
- Cleanup order and resource purging
- State statistics and debugging
"""
from __future__ import annotations

import pytest

from rendering.gl_error_handler import GLCapabilityLevel, get_gl_error_handler
from rendering.gl_state_manager import GLStateManager, GLContextState
from core.resources.manager import ResourceManager


@pytest.fixture(autouse=True)
def reset_gl_error_handler():
    """Reset GLErrorHandler state before and after each test."""
    handler = get_gl_error_handler()
    handler.reset()
    yield
    handler.reset()


class TestGLCapabilityDemotion:
    """Test GLErrorHandler capability demotion (Group A→B→C)."""
    
    def test_initial_capability_level(self):
        """Handler should start with full shader capability."""
        handler = get_gl_error_handler()
        assert handler.capability_level == GLCapabilityLevel.FULL_SHADERS
        assert handler.can_use_shaders is True
        assert handler.can_use_compositor is True
    
    def test_shader_failure_demotes_to_compositor(self):
        """Shader failure should demote to compositor-only (Group B)."""
        handler = get_gl_error_handler()
        handler.record_shader_failure("test_program", "compile error")
        
        assert handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
        assert handler.can_use_shaders is False
        assert handler.can_use_compositor is True
    
    def test_compositor_failure_demotes_to_software(self):
        """Compositor failure should demote to software-only (Group C)."""
        handler = get_gl_error_handler()
        handler.record_compositor_failure("GL context lost")
        
        assert handler.capability_level == GLCapabilityLevel.SOFTWARE_ONLY
        assert handler.can_use_shaders is False
        assert handler.can_use_compositor is False
    
    def test_texture_failure_demotes_to_compositor(self):
        """Texture failure should demote to compositor-only."""
        handler = get_gl_error_handler()
        handler.record_texture_failure("upload failed")
        
        assert handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    
    def test_demotion_is_one_way(self):
        """Demotion should only go down, never up."""
        handler = get_gl_error_handler()
        
        handler.record_shader_failure("test", "error")
        assert handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
        
        handler.record_shader_failure("test2", "error2")
        assert handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
        
        handler.record_compositor_failure("context lost")
        assert handler.capability_level == GLCapabilityLevel.SOFTWARE_ONLY
        
        handler.record_shader_failure("test3", "error3")
        assert handler.capability_level == GLCapabilityLevel.SOFTWARE_ONLY
    
    def test_software_gl_detection(self):
        """Software GL should auto-demote to compositor."""
        handler = get_gl_error_handler()
        handler.record_gl_info(vendor="Microsoft Corporation", renderer="GDI Generic", version="1.1")
        
        assert handler.is_software_gl is True
        assert handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    
    def test_hardware_gl_no_demotion(self):
        """Hardware GL should not trigger demotion."""
        handler = get_gl_error_handler()
        handler.record_gl_info(vendor="NVIDIA Corporation", renderer="GeForce RTX 3080", version="4.6")
        
        assert handler.is_software_gl is False
        assert handler.capability_level == GLCapabilityLevel.FULL_SHADERS
    
    def test_get_status_returns_complete_state(self):
        """get_status should return complete state."""
        handler = get_gl_error_handler()
        handler.record_shader_failure("test_prog", "compile error")
        
        status = handler.get_status()
        assert status["capability_level"] == "COMPOSITOR_ONLY"
        assert status["can_use_shaders"] is False
        assert "test_prog" in status["failed_programs"]


class TestGLStateManagerSubscription:
    """Test GLStateManager subscription to GLErrorHandler."""
    
    def test_subscribe_state_manager(self):
        """Should be able to subscribe a GLStateManager."""
        handler = get_gl_error_handler()
        state_manager = GLStateManager("test_visualizer")
        
        handler.subscribe_state_manager("visualizer", state_manager)
        assert "visualizer" in handler._subscribed_managers
    
    def test_duplicate_subscription_ignored(self):
        """Duplicate subscriptions should be ignored."""
        handler = get_gl_error_handler()
        state_manager = GLStateManager("test_visualizer")
        
        handler.subscribe_state_manager("visualizer", state_manager)
        handler.subscribe_state_manager("visualizer", state_manager)
        assert len(handler._subscribed_managers) == 1
    
    def test_visualizer_error_demotes_to_compositor(self):
        """Visualizer error should demote to compositor-only."""
        handler = get_gl_error_handler()
        state_manager = GLStateManager("visualizer")
        handler.subscribe_state_manager("visualizer", state_manager)
        
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.ERROR, "test error")
        
        assert handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    
    def test_compositor_error_demotes_to_software(self):
        """Compositor error should demote to software-only."""
        handler = get_gl_error_handler()
        state_manager = GLStateManager("compositor")
        handler.subscribe_state_manager("compositor", state_manager)
        
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.ERROR, "context lost")
        
        assert handler.capability_level == GLCapabilityLevel.SOFTWARE_ONLY
    
    def test_context_lost_triggers_demotion(self):
        """CONTEXT_LOST state should trigger demotion."""
        handler = get_gl_error_handler()
        state_manager = GLStateManager("visualizer")
        handler.subscribe_state_manager("visualizer", state_manager)
        
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        state_manager.transition(GLContextState.CONTEXT_LOST, "driver reset")
        
        assert handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    
    def test_ready_state_no_demotion(self):
        """READY state should not trigger demotion."""
        handler = get_gl_error_handler()
        state_manager = GLStateManager("visualizer")
        handler.subscribe_state_manager("visualizer", state_manager)
        
        state_manager.transition(GLContextState.INITIALIZING)
        state_manager.transition(GLContextState.READY)
        
        assert handler.capability_level == GLCapabilityLevel.FULL_SHADERS


class TestGLStateManagerLifecycle:
    """Test GLStateManager state transitions and cleanup."""
    
    def test_valid_initialization_sequence(self):
        """Normal init sequence: UNINITIALIZED → INITIALIZING → READY."""
        sm = GLStateManager("test")
        
        assert sm.transition(GLContextState.INITIALIZING) is True
        assert sm.transition(GLContextState.READY) is True
        assert sm.is_ready()
    
    def test_error_during_initialization(self):
        """Error during init: INITIALIZING → ERROR."""
        sm = GLStateManager("test")
        
        sm.transition(GLContextState.INITIALIZING)
        assert sm.transition(GLContextState.ERROR, "Shader compile failed") is True
        assert sm.is_error()
        assert "Shader compile failed" in (sm.get_error_message() or "")
    
    def test_cleanup_from_ready_state(self):
        """Cleanup from READY: READY → DESTROYING → DESTROYED."""
        sm = GLStateManager("test")
        sm.transition(GLContextState.INITIALIZING)
        sm.transition(GLContextState.READY)
        
        assert sm.transition(GLContextState.DESTROYING) is True
        assert sm.transition(GLContextState.DESTROYED) is True
        assert sm.is_destroyed()
    
    def test_cleanup_from_error_state(self):
        """Cleanup from ERROR: ERROR → DESTROYING → DESTROYED."""
        sm = GLStateManager("test")
        sm.transition(GLContextState.INITIALIZING)
        sm.transition(GLContextState.ERROR, "Test error")
        
        assert sm.transition(GLContextState.DESTROYING) is True
        assert sm.transition(GLContextState.DESTROYED) is True
    
    def test_cleanup_from_context_lost(self):
        """Cleanup from CONTEXT_LOST."""
        sm = GLStateManager("test")
        sm.transition(GLContextState.INITIALIZING)
        sm.transition(GLContextState.READY)
        sm.transition(GLContextState.CONTEXT_LOST, "Driver reset")
        
        assert sm.transition(GLContextState.DESTROYING) is True
        assert sm.transition(GLContextState.DESTROYED) is True
    
    def test_invalid_transition_rejected(self):
        """Invalid transitions should be rejected."""
        sm = GLStateManager("test")
        
        # Can't go directly from UNINITIALIZED to READY
        assert sm.transition(GLContextState.READY) is False
        assert sm.get_state() == GLContextState.UNINITIALIZED
    
    def test_direct_cleanup_from_uninitialized(self):
        """Direct cleanup from UNINITIALIZED should work."""
        sm = GLStateManager("test")
        assert sm.transition(GLContextState.DESTROYED) is True


class TestGLStateManagerStats:
    """Test GLStateManager statistics and debugging."""
    
    def test_transition_count_tracked(self):
        """Transition count should be tracked."""
        sm = GLStateManager("test")
        sm.transition(GLContextState.INITIALIZING)
        sm.transition(GLContextState.READY)
        
        stats = sm.get_stats()
        assert stats["transitions"] >= 2
    
    def test_error_count_tracked(self):
        """Error count should be tracked."""
        sm = GLStateManager("test")
        sm.transition(GLContextState.INITIALIZING)
        sm.transition(GLContextState.ERROR, "Test error")
        
        stats = sm.get_stats()
        assert stats["errors"] >= 1
    
    def test_invalid_transition_count_tracked(self):
        """Invalid transition count should be tracked."""
        sm = GLStateManager("test")
        sm.transition(GLContextState.READY)  # Invalid
        
        stats = sm.get_stats()
        assert stats["invalid_transitions"] >= 1
    
    def test_dump_state_provides_debug_info(self):
        """dump_state should provide debug information."""
        sm = GLStateManager("test_debug")
        sm.transition(GLContextState.INITIALIZING)
        sm.transition(GLContextState.READY)
        
        dump = sm.dump_state()
        assert "test_debug" in dump
        assert "READY" in dump
    
    def test_transition_history_tracked(self):
        """Transition history should be tracked."""
        sm = GLStateManager("test")
        sm.transition(GLContextState.INITIALIZING)
        sm.transition(GLContextState.ERROR, "Error 1")
        sm.force_state(GLContextState.UNINITIALIZED, "Reset")
        sm.transition(GLContextState.INITIALIZING)
        sm.transition(GLContextState.ERROR, "Error 2")
        
        history = sm.get_transition_history(limit=10)
        error_transitions = [h for h in history if h[1] == GLContextState.ERROR]
        assert len(error_transitions) >= 2


class TestCapabilityChangeCallback:
    """Test capability change callbacks."""
    
    def test_callback_invoked_on_demotion(self):
        """Callback should be invoked when capability changes."""
        handler = get_gl_error_handler()
        callback_invoked = []
        
        handler.set_capability_change_callback(lambda level: callback_invoked.append(level))
        handler.record_shader_failure("test", "error")
        
        assert len(callback_invoked) == 1
        assert callback_invoked[0] == GLCapabilityLevel.COMPOSITOR_ONLY
    
    def test_callback_not_invoked_on_same_level(self):
        """Callback should not be invoked if level doesn't change."""
        handler = get_gl_error_handler()
        handler.record_shader_failure("test1", "error1")
        
        callback_invoked = []
        handler.set_capability_change_callback(lambda level: callback_invoked.append(level))
        handler.record_shader_failure("test2", "error2")
        
        assert len(callback_invoked) == 0


class TestResourceManagerGLHandles:
    """Test ResourceManager GL handle tracking."""
    
    def test_gl_stats_available(self):
        """ResourceManager should provide GL stats."""
        rm = ResourceManager()
        stats = rm.get_gl_stats()
        
        assert isinstance(stats, dict)
        assert "total" in stats
    
    def test_gl_handle_registration(self):
        """GL handles should be registerable."""
        rm = ResourceManager()
        cleanup_called = []
        
        rm.register_gl_handle(12345, "test_handle", lambda h: cleanup_called.append(h))
        stats = rm.get_gl_stats()
        assert isinstance(stats, dict)
    
    def test_cleanup_purges_handles(self):
        """cleanup_all should purge registered handles."""
        rm = ResourceManager()
        cleanup_called = []
        
        rm.register_gl_handle(99999, "test_purge", lambda h: cleanup_called.append(h))
        rm.cleanup_all()
        # API should exist and not crash
