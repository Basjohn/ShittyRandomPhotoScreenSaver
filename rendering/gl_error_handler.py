"""GLErrorHandler - Centralized GL error handling and session-level fallback policy.

This module implements the session-level fallback policy for GL transitions:
- Group A: shader-backed GLSL transitions
- Group B: QPainter-based compositor transitions  
- Group C: pure software transitions (no compositor)

On any shader initialization/runtime failure, the handler disables shader usage
for the rest of the session and demotes future Group A requests to Group B.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Set, TYPE_CHECKING

from core.logging.logger import get_logger

if TYPE_CHECKING:
    from rendering.gl_state_manager import GLStateManager, GLContextState

logger = get_logger(__name__)


class GLCapabilityLevel(Enum):
    """GL capability levels for session-level fallback."""
    FULL_SHADERS = auto()      # Group A: Full GLSL shader support
    COMPOSITOR_ONLY = auto()   # Group B: QPainter on GL surface only
    SOFTWARE_ONLY = auto()     # Group C: No GL, pure software


@dataclass
class GLErrorState:
    """Tracks GL error state for session-level fallback decisions."""
    
    capability_level: GLCapabilityLevel = GLCapabilityLevel.FULL_SHADERS
    shader_disabled_reason: Optional[str] = None
    failed_programs: Set[str] = field(default_factory=set)
    failed_operations: int = 0
    
    # Software GL detection
    is_software_gl: bool = False
    gl_vendor: Optional[str] = None
    gl_renderer: Optional[str] = None
    gl_version: Optional[str] = None


class GLErrorHandler:
    """Centralized GL error handling with session-level fallback policy.
    
    Thread-safe singleton that tracks GL errors and manages capability demotion.
    All GL components should check capabilities through this handler before
    attempting shader operations.
    
    Phase 5 Integration:
        GLStateManager instances can subscribe to this handler via
        `subscribe_state_manager()`. When any subscribed GLStateManager
        transitions to ERROR or CONTEXT_LOST, this handler triggers
        session-wide demotion (Group A→B→C).
    """
    
    _instance: Optional["GLErrorHandler"] = None
    _lock = threading.Lock()
    
    # Known software GL implementations that should skip shaders
    SOFTWARE_GL_PATTERNS = frozenset({
        "gdi generic",
        "microsoft basic render driver", 
        "llvmpipe",
        "softpipe",
        "swrast",
        "mesa software",
    })
    
    def __new__(cls) -> "GLErrorHandler":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        self._state = GLErrorState()
        self._state_lock = threading.Lock()
        self._on_capability_change: Optional[Callable[[GLCapabilityLevel], None]] = None
        self._subscribed_managers: Set[str] = set()  # Track subscribed GLStateManager names
        self._initialized = True
    
    @property
    def capability_level(self) -> GLCapabilityLevel:
        """Current GL capability level."""
        with self._state_lock:
            return self._state.capability_level
    
    @property
    def can_use_shaders(self) -> bool:
        """Whether shader-backed transitions (Group A) are available."""
        with self._state_lock:
            return self._state.capability_level == GLCapabilityLevel.FULL_SHADERS
    
    @property
    def can_use_compositor(self) -> bool:
        """Whether compositor transitions (Group A or B) are available."""
        with self._state_lock:
            return self._state.capability_level in (
                GLCapabilityLevel.FULL_SHADERS,
                GLCapabilityLevel.COMPOSITOR_ONLY
            )
    
    @property
    def is_software_gl(self) -> bool:
        """Whether running on software GL implementation."""
        with self._state_lock:
            return self._state.is_software_gl
    
    def set_capability_change_callback(
        self, callback: Optional[Callable[[GLCapabilityLevel], None]]
    ) -> None:
        """Set callback for capability level changes."""
        self._on_capability_change = callback
    
    def record_gl_info(self, vendor: str, renderer: str, version: str) -> None:
        """Record GL adapter info and detect software implementations.
        
        Should be called from initializeGL after context is valid.
        """
        with self._state_lock:
            self._state.gl_vendor = vendor
            self._state.gl_renderer = renderer
            self._state.gl_version = version
            
            # Check for software GL
            renderer_lower = renderer.lower() if renderer else ""
            vendor_lower = vendor.lower() if vendor else ""
            
            for pattern in self.SOFTWARE_GL_PATTERNS:
                if pattern in renderer_lower or pattern in vendor_lower:
                    self._state.is_software_gl = True
                    self._demote_to_level(
                        GLCapabilityLevel.COMPOSITOR_ONLY,
                        f"Software GL detected: {renderer}"
                    )
                    break
    
    def record_shader_failure(self, program_name: str, error: Optional[str] = None) -> None:
        """Record a shader compilation or runtime failure.
        
        This triggers session-level demotion from Group A to Group B.
        """
        with self._state_lock:
            self._state.failed_programs.add(program_name)
            self._state.failed_operations += 1
            
            reason = f"Shader '{program_name}' failed"
            if error:
                reason += f": {error}"
            
            self._demote_to_level(GLCapabilityLevel.COMPOSITOR_ONLY, reason)
    
    def record_compositor_failure(self, error: Optional[str] = None) -> None:
        """Record a compositor/GL backend failure.
        
        This triggers session-level demotion from Group B to Group C.
        """
        with self._state_lock:
            self._state.failed_operations += 1
            
            reason = "Compositor failure"
            if error:
                reason += f": {error}"
            
            self._demote_to_level(GLCapabilityLevel.SOFTWARE_ONLY, reason)
    
    def record_texture_failure(self, error: Optional[str] = None) -> None:
        """Record a texture upload failure.
        
        Texture failures demote to compositor-only (Group B).
        """
        with self._state_lock:
            self._state.failed_operations += 1
            
            reason = "Texture upload failed"
            if error:
                reason += f": {error}"
            
            self._demote_to_level(GLCapabilityLevel.COMPOSITOR_ONLY, reason)
    
    def _demote_to_level(self, level: GLCapabilityLevel, reason: str) -> None:
        """Demote capability level (internal, must hold lock).
        
        Capability levels: FULL_SHADERS(1) > COMPOSITOR_ONLY(2) > SOFTWARE_ONLY(3)
        Higher enum value = lower capability. We demote when target level value is higher.
        """
        if self._state.capability_level.value >= level.value:
            return  # Already at or below this capability level
        
        old_level = self._state.capability_level
        self._state.capability_level = level
        self._state.shader_disabled_reason = reason
        
        # Log the demotion
        level_names = {
            GLCapabilityLevel.FULL_SHADERS: "Group A (shaders)",
            GLCapabilityLevel.COMPOSITOR_ONLY: "Group B (compositor)",
            GLCapabilityLevel.SOFTWARE_ONLY: "Group C (software)",
        }
        logger.warning(
            "[GL ERROR] Session demoted from %s to %s: %s",
            level_names.get(old_level, str(old_level)),
            level_names.get(level, str(level)),
            reason
        )
        
        # Notify callback outside lock
        callback = self._on_capability_change
        if callback:
            try:
                # Release lock before callback to avoid deadlock
                self._state_lock.release()
                try:
                    callback(level)
                finally:
                    self._state_lock.acquire()
            except Exception as e:
                logger.debug("[GL ERROR] Capability change callback failed", exc_info=True)
    
    def get_status(self) -> dict:
        """Get current error handler status for diagnostics."""
        with self._state_lock:
            return {
                "capability_level": self._state.capability_level.name,
                "can_use_shaders": self._state.capability_level == GLCapabilityLevel.FULL_SHADERS,
                "can_use_compositor": self._state.capability_level != GLCapabilityLevel.SOFTWARE_ONLY,
                "is_software_gl": self._state.is_software_gl,
                "shader_disabled_reason": self._state.shader_disabled_reason,
                "failed_programs": list(self._state.failed_programs),
                "failed_operations": self._state.failed_operations,
                "gl_vendor": self._state.gl_vendor,
                "gl_renderer": self._state.gl_renderer,
                "gl_version": self._state.gl_version,
            }
    
    def reset(self) -> None:
        """Reset error state (for testing only)."""
        with self._state_lock:
            self._state = GLErrorState()
            self._subscribed_managers = set()
            self._on_capability_change = None
    
    def subscribe_state_manager(self, manager_name: str, state_manager: "GLStateManager") -> None:
        """Subscribe a GLStateManager to receive error state callbacks.
        
        When the subscribed GLStateManager transitions to ERROR or CONTEXT_LOST,
        this handler will trigger session-wide capability demotion.
        
        Args:
            manager_name: Unique name for the state manager (e.g., "compositor", "visualizer")
            state_manager: The GLStateManager instance to subscribe
        """
        from rendering.gl_state_manager import GLContextState
        
        with self._state_lock:
            if manager_name in self._subscribed_managers:
                return  # Already subscribed
            self._subscribed_managers.add(manager_name)
        
        # Register callback for state changes
        def on_state_change(old_state: "GLContextState", new_state: "GLContextState") -> None:
            if new_state == GLContextState.ERROR:
                self.record_gl_state_error(manager_name, "GLStateManager entered ERROR state")
            elif new_state == GLContextState.CONTEXT_LOST:
                self.record_gl_state_error(manager_name, "GLStateManager context lost")
        
        state_manager.add_callback(on_state_change)
        logger.debug(f"[GL ERROR] Subscribed GLStateManager '{manager_name}' for error callbacks")
    
    def record_gl_state_error(self, manager_name: str, error: str) -> None:
        """Record an error from a subscribed GLStateManager.
        
        This triggers session-wide demotion based on the error type.
        Visualizer errors demote to COMPOSITOR_ONLY (Group B).
        Compositor errors demote to SOFTWARE_ONLY (Group C).
        """
        with self._state_lock:
            self._state.failed_operations += 1
            
            # Determine demotion level based on which component failed
            if "compositor" in manager_name.lower():
                # Compositor failure = demote to software
                self._demote_to_level(
                    GLCapabilityLevel.SOFTWARE_ONLY,
                    f"Compositor '{manager_name}' error: {error}"
                )
            else:
                # Other GL component failure = demote to compositor only
                self._demote_to_level(
                    GLCapabilityLevel.COMPOSITOR_ONLY,
                    f"GL component '{manager_name}' error: {error}"
                )


def get_gl_error_handler() -> GLErrorHandler:
    """Get the singleton GLErrorHandler instance."""
    return GLErrorHandler()
