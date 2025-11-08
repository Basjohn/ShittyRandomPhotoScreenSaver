"""
Base transition class for screensaver transitions.

Defines the abstract interface that all transitions must implement.
"""
from abc import ABCMeta, abstractmethod
from enum import Enum
import time
from typing import Optional
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QPixmap, QPainter
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
        
        # Telemetry tracking
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        
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
    
    # --- Telemetry helpers (Phase 2.2) ---------------------------------------
    def _mark_start(self) -> None:
        """Mark transition start time for telemetry."""
        self._start_time = time.time()
        logger.debug(f"[PERF] {self.__class__.__name__} started")
    
    def _mark_end(self) -> None:
        """Mark transition end time and log performance metrics."""
        if self._start_time is not None:
            self._end_time = time.time()
            elapsed_ms = (self._end_time - self._start_time) * 1000
            expected_ms = self.duration_ms
            delta_ms = elapsed_ms - expected_ms
            
            # Log performance with delta from expected
            if abs(delta_ms) < 50:  # Within 50ms tolerance
                logger.info(f"[PERF] {self.__class__.__name__} completed in {elapsed_ms:.1f}ms "
                          f"(expected {expected_ms}ms, Δ{delta_ms:+.1f}ms)")
            else:
                logger.warning(f"[PERF] {self.__class__.__name__} completed in {elapsed_ms:.1f}ms "
                             f"(expected {expected_ms}ms, Δ{delta_ms:+.1f}ms) - TIMING DRIFT")
        else:
            logger.warning(f"[PERF] {self.__class__.__name__} completed without start time")
    
    def get_elapsed_ms(self) -> Optional[float]:
        """Get elapsed time since transition start in milliseconds."""
        if self._start_time is None:
            return None
        return (time.time() - self._start_time) * 1000

    # --- Centralized helpers for transitions ---------------------------------
    def _fit_pixmap_to_widget(self, pixmap: QPixmap, widget: QWidget) -> QPixmap:
        """
        Create a widget-sized pixmap by scaling/cropping the source while
        preserving aspect ratio (equivalent to DisplayMode.FILL).
        The result is ARGB32 with transparent background.
        """
        w, h = widget.width(), widget.height()
        if not pixmap or pixmap.isNull() or w <= 0 or h <= 0:
            return QPixmap()
        # Use device pixels for backing store then set DPR so logical size is w x h
        try:
            dpr = getattr(widget, "_device_pixel_ratio", widget.devicePixelRatioF())
        except Exception:
            dpr = 1.0
        tw = max(1, int(round(w * dpr)))
        th = max(1, int(round(h * dpr)))
        # Scale to cover in device pixels, then center-crop
        fitted = pixmap.scaled(
            tw, th,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        cx = max(0, (fitted.width() - tw) // 2)
        cy = max(0, (fitted.height() - th) // 2)
        # Compose onto transparent canvas (device pixels) and assign DPR
        canvas = QPixmap(tw, th)
        canvas.fill(Qt.GlobalColor.transparent)
        canvas.setDevicePixelRatio(dpr)
        p = QPainter(canvas)
        try:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            p.drawPixmap(-cx, -cy, fitted)
        finally:
            p.end()
        return canvas

    def _create_transparent_canvas(self, widget: QWidget) -> QPixmap:
        """Create an ARGB32 transparent canvas exactly widget-sized."""
        w, h = widget.width(), widget.height()
        try:
            dpr = getattr(widget, "_device_pixel_ratio", widget.devicePixelRatioF())
        except Exception:
            dpr = 1.0
        tw = max(1, int(round(w * dpr)))
        th = max(1, int(round(h * dpr)))
        canvas = QPixmap(tw, th)
        canvas.fill(Qt.GlobalColor.transparent)
        canvas.setDevicePixelRatio(dpr)
        return canvas

    def _get_animation_manager(self, widget: QWidget):
        """
        Retrieve or attach a per-widget AnimationManager instance.
        Avoids raw QTimer usage inside transitions.
        """
        am = getattr(widget, "_animation_manager", None)
        if am is None:
            from core.animation.animator import AnimationManager
            am = AnimationManager()
            setattr(widget, "_animation_manager", am)
        return am
    
    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(duration={self.duration_ms}ms, state={self._state.value})"
