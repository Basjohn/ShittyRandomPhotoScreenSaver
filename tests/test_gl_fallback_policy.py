"""
Tests for session-scoped GL fallback policy (Group A→B→C).

Verifies that shader failures trigger session-wide demotion:
- Group A (FULL_SHADERS): shader-backed GLSL transitions
- Group B (COMPOSITOR_ONLY): QPainter-based compositor transitions
- Group C (SOFTWARE_ONLY): pure software transitions (no compositor)

On shader init/runtime failure, Group A→B demotion occurs for the session.
Only when GL backend is unavailable should Group B→C demotion occur.
"""
import pytest
from rendering.gl_error_handler import GLErrorHandler, GLCapabilityLevel


@pytest.fixture
def error_handler():
    """Get fresh GLErrorHandler instance for each test."""
    handler = GLErrorHandler()
    # Reset to default state
    handler.reset()
    yield handler
    # Clean up after test
    handler.reset()


def test_gl_error_handler_singleton():
    """Test GLErrorHandler is a singleton."""
    handler1 = GLErrorHandler()
    handler2 = GLErrorHandler()
    assert handler1 is handler2, "GLErrorHandler should be a singleton"


def test_initial_capability_level(error_handler):
    """Test initial capability level is FULL_SHADERS."""
    assert error_handler.capability_level == GLCapabilityLevel.FULL_SHADERS
    assert error_handler.shaders_enabled is True


def test_software_gl_detection_demotes_to_compositor(error_handler):
    """Test software GL detection demotes to COMPOSITOR_ONLY."""
    # Simulate software GL detection
    error_handler.report_gl_info(
        vendor="Microsoft Corporation",
        renderer="GDI Generic",
        version="1.1.0"
    )
    
    # Should demote to COMPOSITOR_ONLY (Group B)
    assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    assert error_handler.shaders_enabled is False
    assert error_handler.is_software_gl is True


def test_shader_compile_failure_demotes_to_compositor(error_handler):
    """Test shader compile failure demotes to COMPOSITOR_ONLY for session."""
    # Report shader compile failure
    error_handler.report_shader_failure(
        program_name="crossfade",
        error_message="Failed to compile vertex shader"
    )
    
    # Should demote to COMPOSITOR_ONLY (Group B)
    assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    assert error_handler.shaders_enabled is False
    assert "crossfade" in error_handler.failed_programs


def test_shader_link_failure_demotes_to_compositor(error_handler):
    """Test shader link failure demotes to COMPOSITOR_ONLY for session."""
    error_handler.report_shader_failure(
        program_name="slide",
        error_message="Failed to link shader program"
    )
    
    assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    assert error_handler.shaders_enabled is False


def test_shader_runtime_failure_demotes_to_compositor(error_handler):
    """Test shader runtime failure demotes to COMPOSITOR_ONLY for session."""
    error_handler.report_shader_failure(
        program_name="wipe",
        error_message="GL_INVALID_OPERATION during draw call"
    )
    
    assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    assert error_handler.shaders_enabled is False


def test_demotion_is_session_scoped(error_handler):
    """Test that demotion persists for the session (no per-call fallbacks)."""
    # Initial state: FULL_SHADERS
    assert error_handler.capability_level == GLCapabilityLevel.FULL_SHADERS
    
    # Report first shader failure
    error_handler.report_shader_failure("crossfade", "compile error")
    assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    
    # Subsequent checks should still be COMPOSITOR_ONLY (no reset)
    assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    assert error_handler.shaders_enabled is False
    
    # Even checking multiple times doesn't reset
    for _ in range(5):
        assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY


def test_multiple_shader_failures_accumulate(error_handler):
    """Test multiple shader failures are tracked."""
    error_handler.report_shader_failure("crossfade", "error 1")
    error_handler.report_shader_failure("slide", "error 2")
    error_handler.report_shader_failure("wipe", "error 3")
    
    assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    assert len(error_handler.failed_programs) == 3
    assert "crossfade" in error_handler.failed_programs
    assert "slide" in error_handler.failed_programs
    assert "wipe" in error_handler.failed_programs


def test_compositor_unavailable_demotes_to_software(error_handler):
    """Test compositor unavailable demotes to SOFTWARE_ONLY (Group C)."""
    # Report compositor unavailable
    error_handler.report_compositor_unavailable(
        reason="Failed to create GL context"
    )
    
    # Should demote to SOFTWARE_ONLY (Group C)
    assert error_handler.capability_level == GLCapabilityLevel.SOFTWARE_ONLY
    assert error_handler.shaders_enabled is False
    assert error_handler.compositor_available is False


def test_group_a_to_b_to_c_cascade(error_handler):
    """Test cascading demotion: Group A→B→C."""
    # Start at Group A (FULL_SHADERS)
    assert error_handler.capability_level == GLCapabilityLevel.FULL_SHADERS
    
    # Shader failure: A→B
    error_handler.report_shader_failure("test", "shader error")
    assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    
    # Compositor failure: B→C
    error_handler.report_compositor_unavailable("GL context lost")
    assert error_handler.capability_level == GLCapabilityLevel.SOFTWARE_ONLY


def test_no_silent_per_call_fallbacks(error_handler):
    """Test that there are no silent per-call fallbacks after demotion."""
    # Demote to COMPOSITOR_ONLY
    error_handler.report_shader_failure("test", "error")
    assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    
    # Simulate checking capability before multiple transition requests
    capabilities = []
    for _ in range(10):
        capabilities.append(error_handler.capability_level)
    
    # All checks should return COMPOSITOR_ONLY (no per-call resets)
    assert all(cap == GLCapabilityLevel.COMPOSITOR_ONLY for cap in capabilities)


def test_capability_change_callback(error_handler):
    """Test capability change callback is invoked on demotion."""
    callback_invocations = []
    
    def on_change(new_level: GLCapabilityLevel):
        callback_invocations.append(new_level)
    
    error_handler.set_capability_change_callback(on_change)
    
    # Trigger demotion
    error_handler.report_shader_failure("test", "error")
    
    # Callback should have been invoked
    assert len(callback_invocations) == 1
    assert callback_invocations[0] == GLCapabilityLevel.COMPOSITOR_ONLY


def test_reset_clears_state(error_handler):
    """Test reset() clears error state and restores FULL_SHADERS."""
    # Demote to COMPOSITOR_ONLY
    error_handler.report_shader_failure("test", "error")
    assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    
    # Reset
    error_handler.reset()
    
    # Should be back to FULL_SHADERS
    assert error_handler.capability_level == GLCapabilityLevel.FULL_SHADERS
    assert error_handler.shaders_enabled is True
    assert len(error_handler.failed_programs) == 0


def test_known_software_gl_patterns(error_handler):
    """Test known software GL patterns are detected."""
    software_patterns = [
        ("Microsoft Corporation", "GDI Generic", "1.1.0"),
        ("Microsoft", "Microsoft Basic Render Driver", "1.0"),
        ("VMware", "llvmpipe", "3.0"),
        ("Mesa", "softpipe", "3.0"),
        ("Mesa", "swrast", "3.0"),
    ]
    
    for vendor, renderer, version in software_patterns:
        error_handler.reset()
        error_handler.report_gl_info(vendor, renderer, version)
        
        assert error_handler.is_software_gl is True, f"Failed to detect: {renderer}"
        assert error_handler.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY


def test_hardware_gl_not_demoted(error_handler):
    """Test hardware GL is not demoted on detection."""
    error_handler.report_gl_info(
        vendor="NVIDIA Corporation",
        renderer="NVIDIA GeForce RTX 3080",
        version="4.6.0"
    )
    
    # Should remain at FULL_SHADERS
    assert error_handler.capability_level == GLCapabilityLevel.FULL_SHADERS
    assert error_handler.is_software_gl is False
    assert error_handler.shaders_enabled is True


def test_thread_safety_of_demotion(error_handler):
    """Test thread-safe capability demotion."""
    import threading
    
    results = []
    
    def report_failure():
        error_handler.report_shader_failure("test", "error")
        results.append(error_handler.capability_level)
    
    # Trigger demotion from multiple threads
    threads = [threading.Thread(target=report_failure) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All threads should see COMPOSITOR_ONLY after demotion
    assert all(level == GLCapabilityLevel.COMPOSITOR_ONLY for level in results)


def test_error_state_tracking(error_handler):
    """Test GLErrorState tracks failures correctly."""
    error_handler.report_shader_failure("program1", "error1")
    error_handler.report_shader_failure("program2", "error2")
    
    state = error_handler.get_error_state()
    
    assert state.capability_level == GLCapabilityLevel.COMPOSITOR_ONLY
    assert state.shader_disabled_reason is not None
    assert len(state.failed_programs) == 2
    assert state.failed_operations >= 2


def test_no_demotion_without_errors(error_handler):
    """Test capability level stays at FULL_SHADERS without errors."""
    # Report successful GL info (hardware)
    error_handler.report_gl_info("NVIDIA", "GeForce", "4.6")
    
    # Check capability multiple times
    for _ in range(100):
        assert error_handler.capability_level == GLCapabilityLevel.FULL_SHADERS
        assert error_handler.shaders_enabled is True
