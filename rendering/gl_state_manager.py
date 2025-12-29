"""
GL Context State Manager.

Provides centralized, thread-safe state management for OpenGL contexts
with validated state transitions, error recovery, and debugging support.

State Machine:
    UNINITIALIZED → INITIALIZING → READY
    UNINITIALIZED → ERROR
    INITIALIZING → ERROR
    READY → CONTEXT_LOST
    READY → DESTROYING
    CONTEXT_LOST → DESTROYING
    ERROR → DESTROYING
    DESTROYING → DESTROYED

Usage:
    state_manager = GLStateManager("compositor")
    
    # Initialize
    if state_manager.transition(GLContextState.INITIALIZING):
        try:
            # Create GL context
            state_manager.transition(GLContextState.READY)
        except Exception as e:
            state_manager.transition(GLContextState.ERROR, str(e))
    
    # Check before rendering
    if state_manager.is_ready():
        # Safe to make GL calls
        pass
    
    # Cleanup
    state_manager.transition(GLContextState.DESTROYING)
    state_manager.transition(GLContextState.DESTROYED)
"""
from __future__ import annotations

import threading
import time
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Set, Tuple

from core.logging.logger import get_logger

logger = get_logger(__name__)


class GLContextState(Enum):
    """GL context lifecycle states.
    
    State descriptions:
        UNINITIALIZED: Context not created yet
        INITIALIZING: Context creation in progress
        READY: Context valid and usable for rendering
        ERROR: Context creation or operation failed
        CONTEXT_LOST: Context was lost (driver reset, etc.)
        DESTROYING: Cleanup in progress
        DESTROYED: Fully cleaned up (terminal state)
    """
    UNINITIALIZED = auto()
    INITIALIZING = auto()
    READY = auto()
    ERROR = auto()
    CONTEXT_LOST = auto()
    DESTROYING = auto()
    DESTROYED = auto()


# Valid state transitions map
_VALID_GL_TRANSITIONS: Dict[GLContextState, Set[GLContextState]] = {
    GLContextState.UNINITIALIZED: {
        GLContextState.INITIALIZING,
        GLContextState.ERROR,
        GLContextState.DESTROYED,  # Allow direct cleanup
    },
    GLContextState.INITIALIZING: {
        GLContextState.READY,
        GLContextState.ERROR,
        GLContextState.DESTROYED,  # Allow cleanup during init
    },
    GLContextState.READY: {
        GLContextState.CONTEXT_LOST,
        GLContextState.DESTROYING,
        GLContextState.ERROR,  # Runtime error
    },
    GLContextState.CONTEXT_LOST: {
        GLContextState.DESTROYING,
        GLContextState.INITIALIZING,  # Allow recovery attempt
    },
    GLContextState.ERROR: {
        GLContextState.DESTROYING,
        GLContextState.INITIALIZING,  # Allow retry
    },
    GLContextState.DESTROYING: {
        GLContextState.DESTROYED,
    },
    GLContextState.DESTROYED: set(),  # Terminal state
}


def is_valid_gl_transition(old_state: GLContextState, new_state: GLContextState) -> bool:
    """Check if a GL state transition is valid."""
    return new_state in _VALID_GL_TRANSITIONS.get(old_state, set())


class GLStateManager:
    """
    Centralized GL state management with thread safety.
    
    Features:
    - Thread-safe state access and transitions
    - State transition validation
    - State change callbacks
    - Transition history for debugging
    - Error message tracking
    
    Thread Safety:
    - All state access is protected by a lock
    - Callbacks are invoked outside the lock to prevent deadlocks
    """
    
    # Maximum transition history entries to keep
    MAX_HISTORY_SIZE = 100
    
    def __init__(self, name: str = "gl_context"):
        """
        Initialize the GL state manager.
        
        Args:
            name: Identifier for this GL context (for logging)
        """
        self._name = name
        self._state = GLContextState.UNINITIALIZED
        self._state_lock = threading.Lock()
        self._error_message: Optional[str] = None
        self._error_details: Optional[str] = None
        
        # Callbacks for state changes
        self._state_callbacks: Dict[GLContextState, List[Callable[[GLContextState, GLContextState], None]]] = {}
        self._any_state_callbacks: List[Callable[[GLContextState, GLContextState], None]] = []
        
        # Transition history for debugging
        self._transition_history: List[Tuple[GLContextState, GLContextState, float, Optional[str]]] = []
        
        # Statistics
        self._stats = {
            "transitions": 0,
            "invalid_transitions": 0,
            "errors": 0,
            "recoveries": 0,
        }
        
        logger.debug(f"[GL_STATE] {self._name}: State manager created")
    
    # -------------------------------------------------------------------------
    # State Queries (Thread-Safe)
    # -------------------------------------------------------------------------
    
    def get_state(self) -> GLContextState:
        """Get current state (thread-safe)."""
        with self._state_lock:
            return self._state
    
    def is_uninitialized(self) -> bool:
        """Check if in UNINITIALIZED state."""
        with self._state_lock:
            return self._state == GLContextState.UNINITIALIZED
    
    def is_initializing(self) -> bool:
        """Check if in INITIALIZING state."""
        with self._state_lock:
            return self._state == GLContextState.INITIALIZING
    
    def is_ready(self) -> bool:
        """Check if GL context is ready for use."""
        with self._state_lock:
            return self._state == GLContextState.READY
    
    def is_error(self) -> bool:
        """Check if in error state (ERROR or CONTEXT_LOST)."""
        with self._state_lock:
            return self._state in (GLContextState.ERROR, GLContextState.CONTEXT_LOST)
    
    def is_destroyed(self) -> bool:
        """Check if in DESTROYED state."""
        with self._state_lock:
            return self._state == GLContextState.DESTROYED
    
    def is_usable(self) -> bool:
        """Check if GL context can be used (READY state only)."""
        with self._state_lock:
            return self._state == GLContextState.READY
    
    def can_render(self) -> bool:
        """Alias for is_ready() - check if safe to make GL calls."""
        return self.is_ready()
    
    # -------------------------------------------------------------------------
    # State Transitions
    # -------------------------------------------------------------------------
    
    def transition(
        self, 
        new_state: GLContextState, 
        error_msg: Optional[str] = None,
        error_details: Optional[str] = None
    ) -> bool:
        """
        Attempt state transition with validation.
        
        Args:
            new_state: Target state
            error_msg: Error message (for ERROR/CONTEXT_LOST states)
            error_details: Additional error details
            
        Returns:
            True if transition was valid and completed, False otherwise
        """
        callbacks_to_invoke = []
        
        with self._state_lock:
            old_state = self._state
            
            # Validate transition
            if not is_valid_gl_transition(old_state, new_state):
                self._stats["invalid_transitions"] += 1
                logger.warning(
                    f"[GL_STATE] {self._name}: Invalid transition "
                    f"{old_state.name} → {new_state.name}"
                )
                return False
            
            # Update state
            self._state = new_state
            self._stats["transitions"] += 1
            
            # Track errors and recovery
            if new_state in (GLContextState.ERROR, GLContextState.CONTEXT_LOST):
                self._error_message = error_msg
                self._error_details = error_details
                self._stats["errors"] += 1
            elif new_state == GLContextState.INITIALIZING and old_state in (GLContextState.ERROR, GLContextState.CONTEXT_LOST):
                # Starting recovery attempt - clear error but don't count as recovered yet
                self._error_message = None
                self._error_details = None
            elif new_state == GLContextState.READY and old_state == GLContextState.INITIALIZING:
                # Check if we were recovering (error was cleared during INITIALIZING)
                # Count as recovery if we came from an error state path
                if self._error_message is None and len(self._transition_history) >= 1:
                    # Check if previous transition was from error state
                    for old_s, new_s, _, _ in reversed(self._transition_history[-5:]):
                        if new_s == GLContextState.INITIALIZING and old_s in (GLContextState.ERROR, GLContextState.CONTEXT_LOST):
                            self._stats["recoveries"] += 1
                            break
                        elif new_s == GLContextState.INITIALIZING:
                            break  # Normal init, not recovery
            
            # Record transition
            self._transition_history.append((old_state, new_state, time.time(), error_msg))
            if len(self._transition_history) > self.MAX_HISTORY_SIZE:
                self._transition_history = self._transition_history[-self.MAX_HISTORY_SIZE:]
            
            # Collect callbacks to invoke (outside lock)
            callbacks_to_invoke.extend(self._any_state_callbacks)
            if new_state in self._state_callbacks:
                callbacks_to_invoke.extend(self._state_callbacks[new_state])
        
        # Log transition
        if error_msg:
            logger.info(
                f"[GL_STATE] {self._name}: {old_state.name} → {new_state.name} "
                f"(error: {error_msg})"
            )
        else:
            logger.debug(f"[GL_STATE] {self._name}: {old_state.name} → {new_state.name}")
        
        # Invoke callbacks outside lock to prevent deadlocks
        for callback in callbacks_to_invoke:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error(f"[GL_STATE] {self._name}: Callback error: {e}", exc_info=True)
        
        return True
    
    def force_state(self, new_state: GLContextState, reason: str = "") -> None:
        """
        Force state change without validation (emergency use only).
        
        Use this only for error recovery when normal transitions fail.
        
        Args:
            new_state: Target state
            reason: Reason for forced transition
        """
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            self._transition_history.append((old_state, new_state, time.time(), f"FORCED: {reason}"))
        
        logger.warning(
            f"[GL_STATE] {self._name}: FORCED {old_state.name} → {new_state.name} "
            f"(reason: {reason})"
        )
    
    # -------------------------------------------------------------------------
    # Error Information
    # -------------------------------------------------------------------------
    
    def get_error_message(self) -> Optional[str]:
        """Get error message if in error state."""
        with self._state_lock:
            return self._error_message
    
    def get_error_details(self) -> Optional[str]:
        """Get detailed error information."""
        with self._state_lock:
            return self._error_details
    
    def get_error_info(self) -> Tuple[Optional[str], Optional[str]]:
        """Get both error message and details."""
        with self._state_lock:
            return self._error_message, self._error_details
    
    def clear_error(self) -> None:
        """Clear error state (call after handling error)."""
        with self._state_lock:
            self._error_message = None
            self._error_details = None
    
    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------
    
    def register_callback(
        self, 
        state: Optional[GLContextState], 
        callback: Callable[[GLContextState, GLContextState], None]
    ) -> None:
        """
        Register callback for state entry.
        
        Args:
            state: State to trigger on (None for any state change)
            callback: Function(old_state, new_state) to call
        """
        with self._state_lock:
            if state is None:
                self._any_state_callbacks.append(callback)
            else:
                if state not in self._state_callbacks:
                    self._state_callbacks[state] = []
                self._state_callbacks[state].append(callback)
    
    def unregister_callback(
        self, 
        state: Optional[GLContextState], 
        callback: Callable[[GLContextState, GLContextState], None]
    ) -> bool:
        """
        Unregister a callback.
        
        Args:
            state: State the callback was registered for (None for any)
            callback: The callback to remove
            
        Returns:
            True if callback was found and removed
        """
        with self._state_lock:
            if state is None:
                if callback in self._any_state_callbacks:
                    self._any_state_callbacks.remove(callback)
                    return True
            else:
                if state in self._state_callbacks and callback in self._state_callbacks[state]:
                    self._state_callbacks[state].remove(callback)
                    return True
            return False
    
    # -------------------------------------------------------------------------
    # Debugging
    # -------------------------------------------------------------------------
    
    def get_transition_history(
        self, 
        limit: int = 10
    ) -> List[Tuple[GLContextState, GLContextState, float, Optional[str]]]:
        """
        Get recent state transitions for debugging.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of (old_state, new_state, timestamp, error_msg) tuples
        """
        with self._state_lock:
            return self._transition_history[-limit:]
    
    def get_stats(self) -> Dict[str, int]:
        """Get state manager statistics."""
        with self._state_lock:
            return dict(self._stats)
    
    def get_name(self) -> str:
        """Get the name of this state manager."""
        return self._name
    
    def dump_state(self) -> str:
        """Get a debug dump of current state."""
        with self._state_lock:
            lines = [
                f"GLStateManager: {self._name}",
                f"  Current State: {self._state.name}",
                f"  Error Message: {self._error_message}",
                f"  Stats: {self._stats}",
                "  Recent Transitions:",
            ]
            for old, new, ts, err in self._transition_history[-5:]:
                t = time.strftime("%H:%M:%S", time.localtime(ts))
                err_str = f" ({err})" if err else ""
                lines.append(f"    {t}: {old.name} → {new.name}{err_str}")
            return "\n".join(lines)
    
    # -------------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------------
    
    def __enter__(self) -> "GLStateManager":
        """Enter context - transition to INITIALIZING."""
        self.transition(GLContextState.INITIALIZING)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context - transition to DESTROYED."""
        if exc_type is not None:
            self.transition(GLContextState.ERROR, str(exc_val))
        self.transition(GLContextState.DESTROYING)
        self.transition(GLContextState.DESTROYED)
        return False  # Don't suppress exceptions
    
    # -------------------------------------------------------------------------
    # Reset (for testing)
    # -------------------------------------------------------------------------
    
    def reset(self) -> None:
        """Reset to initial state (for testing only)."""
        with self._state_lock:
            self._state = GLContextState.UNINITIALIZED
            self._error_message = None
            self._error_details = None
            self._transition_history.clear()
            self._stats = {
                "transitions": 0,
                "invalid_transitions": 0,
                "errors": 0,
                "recoveries": 0,
            }
        logger.debug("[GL_STATE] %s: State manager reset", self._name)


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_gl_state_manager(name: str = "gl_context") -> GLStateManager:
    """Create a new GL state manager instance."""
    return GLStateManager(name)


# ---------------------------------------------------------------------------
# GL State Guard (Context Manager for Safe GL Operations)
# ---------------------------------------------------------------------------

class GLStateGuard:
    """
    Context manager for safe GL operations.
    
    Ensures GL context is ready before operations and handles errors.
    
    Usage:
        with GLStateGuard(state_manager) as guard:
            if guard.is_valid:
                # Safe to make GL calls
                pass
    """
    
    def __init__(self, state_manager: GLStateManager, operation: str = "GL operation"):
        self._state_manager = state_manager
        self._operation = operation
        self._is_valid = False
    
    def __enter__(self) -> "GLStateGuard":
        self._is_valid = self._state_manager.is_ready()
        if not self._is_valid:
            state = self._state_manager.get_state()
            logger.warning(
                f"[GL_STATE] {self._operation} skipped: context not ready "
                f"(state={state.name})"
            )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            # GL error occurred
            self._state_manager.transition(
                GLContextState.ERROR,
                f"{self._operation} failed: {exc_val}"
            )
        return False  # Don't suppress exceptions
    
    @property
    def is_valid(self) -> bool:
        """Check if GL operations are safe."""
        return self._is_valid
