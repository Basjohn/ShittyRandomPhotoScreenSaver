"""GL State Tracker - Eliminates redundant GL state changes.

Tracks current GL state and skips redundant glUseProgram, glBindTexture, etc.
This reduces driver overhead by batching state changes.
"""

from __future__ import annotations
from typing import Optional

try:
    from OpenGL import GL as gl
except ImportError:
    gl = None


class GLStateTracker:
    """Tracks current GL state to avoid redundant calls.
    
    OPTIMIZATION: Each GL state change has driver overhead. By tracking
    current state, we can skip redundant calls and reduce overhead.
    
    Thread Safety: Must be called from UI thread only (Qt requirement).
    """
    
    def __init__(self):
        self._current_program: int = 0
        self._current_texture_2d: int = 0
        self._current_active_texture: int = gl.GL_TEXTURE0 if gl else 0
        self._depth_test_enabled: bool = True  # GL default
        
    def use_program(self, program: int) -> bool:
        """Bind shader program if not already bound.
        
        Returns True if state changed, False if already bound.
        """
        if self._current_program != program:
            if gl:
                gl.glUseProgram(program)
            self._current_program = program
            return True
        return False
    
    def bind_texture_2d(self, texture: int) -> bool:
        """Bind 2D texture if not already bound.
        
        Returns True if state changed, False if already bound.
        """
        if self._current_texture_2d != texture:
            if gl:
                gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            self._current_texture_2d = texture
            return True
        return False
    
    def active_texture(self, unit: int) -> bool:
        """Set active texture unit if not already active.
        
        Returns True if state changed, False if already active.
        """
        if self._current_active_texture != unit:
            if gl:
                gl.glActiveTexture(unit)
            self._current_active_texture = unit
            return True
        return False
    
    def set_depth_test(self, enabled: bool) -> bool:
        """Enable/disable depth test if not already in that state.
        
        Returns True if state changed, False if already in that state.
        """
        if self._depth_test_enabled != enabled:
            if gl:
                if enabled:
                    gl.glEnable(gl.GL_DEPTH_TEST)
                else:
                    gl.glDisable(gl.GL_DEPTH_TEST)
            self._depth_test_enabled = enabled
            return True
        return False
    
    def reset(self) -> None:
        """Reset state tracker (call after context loss or manual GL calls)."""
        self._current_program = 0
        self._current_texture_2d = 0
        self._current_active_texture = gl.GL_TEXTURE0 if gl else 0
        self._depth_test_enabled = True


# Module-level singleton
_state_tracker: Optional[GLStateTracker] = None


def get_gl_state_tracker() -> GLStateTracker:
    """Get the singleton GL state tracker."""
    global _state_tracker
    if _state_tracker is None:
        _state_tracker = GLStateTracker()
    return _state_tracker


def reset_gl_state_tracker() -> None:
    """Reset the singleton GL state tracker."""
    global _state_tracker
    if _state_tracker is not None:
        _state_tracker.reset()
