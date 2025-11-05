"""
Base transition class for screensaver transitions.

Defines the abstract interface that all transitions must implement.
"""
from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Optional
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger

logger = get_logger(__name__)


class TransitionState(Enum):
    """State of a transition."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


# Combine QObject and ABC metaclasses
class QABCMeta(type(QObject), ABCMeta):
    """Metaclass combining QObject and ABC."""
    pass


class BaseTransition(QObject, metaclass=QABCMeta):
    """
    Abstract base class for image transitions.
    
    All transitions must inherit from this class and implement:
    - start() - Begin the transition
    - stop() - Stop the transition
    - cleanup() - Clean up resources
    
    Transitions should emit:
    - started - When transition begins
    - finished - When transition completes
    - progress(float) - Progress updates (0.0 to 1.0)
    - error(str) - If an error occurs
    
    Signals:
    - started: Transition started
    - finished: Transition completed
    - progress: Progress update (0.0 to 1.0)
    - error: Error occurred (message)
    """
    
    started = Signal()
    finished = Signal()
    progress = Signal(float)  # 0.0 to 1.0
    error = Signal(str)
    
    def __init__(self, duration_ms: int = 1000):
        """
        Initialize base transition.
        
        Args:
            duration_ms: Transition duration in milliseconds
        """
        super().__init__()
        
        self.duration_ms = duration_ms
        self._state = TransitionState.IDLE
        
        logger.debug(f"{self.__class__.__name__} created with duration {duration_ms}ms")
    
    @abstractmethod
    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, 
              widget: QWidget) -> bool:
        """
        Start the transition.
        
        Args:
            old_pixmap: Previous image (None if first image)
            new_pixmap: New image to transition to
            widget: Widget to perform transition on
        
        Returns:
            True if started successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the transition immediately."""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up transition resources."""
        pass
    
    def get_state(self) -> TransitionState:
        """
        Get current transition state.
        
        Returns:
            Current state
        """
        return self._state
    
    def is_running(self) -> bool:
        """
        Check if transition is currently running.
        
        Returns:
            True if running, False otherwise
        """
        return self._state == TransitionState.RUNNING
    
    def set_duration(self, duration_ms: int) -> None:
        """
        Set transition duration.
        
        Args:
            duration_ms: New duration in milliseconds
        """
        if duration_ms <= 0:
            logger.warning(f"[FALLBACK] Invalid duration {duration_ms}ms, using 1000ms")
            duration_ms = 1000
        
        self.duration_ms = duration_ms
        logger.debug(f"Transition duration set to {duration_ms}ms")
    
    def get_duration(self) -> int:
        """
        Get transition duration.
        
        Returns:
            Duration in milliseconds
        """
        return self.duration_ms
    
    def _set_state(self, state: TransitionState) -> None:
        """
        Set transition state.
        
        Args:
            state: New state
        """
        old_state = self._state
        self._state = state
        logger.debug(f"Transition state: {old_state.value} -> {state.value}")
    
    def _emit_progress(self, progress: float) -> None:
        """
        Emit progress signal with validation.
        
        Args:
            progress: Progress value (0.0 to 1.0)
        """
        # Clamp to valid range
        progress = max(0.0, min(1.0, progress))
        self.progress.emit(progress)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(duration={self.duration_ms}ms, state={self._state.value})"
