"""
Transition Controller - Extracted from DisplayWidget for better separation of concerns.

Manages transition lifecycle including start, progress, completion, cancellation,
and watchdog timeout handling.

Phase E Context: This module centralizes transition state management to provide
deterministic ordering of overlay visibility changes during transitions.
"""
from __future__ import annotations

import time
from typing import Callable, Optional, TYPE_CHECKING

from PySide6.QtCore import Signal, QObject, QTimer
from PySide6.QtGui import QPixmap

from core.logging.logger import get_logger, is_verbose_logging
from core.resources.manager import ResourceManager
from transitions.base_transition import BaseTransition

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget
    from rendering.widget_manager import WidgetManager

logger = get_logger(__name__)

# Default watchdog timeout for transitions
# Must be longer than the longest transition duration (currently 8.1s for Ripple/Raindrops)
# Plus buffer for initialization and cleanup
TRANSITION_WATCHDOG_DEFAULT_SEC = 12.0


class TransitionController(QObject):
    """
    Manages transition lifecycle for DisplayWidget.
    
    Responsibilities:
    - Transition start/stop/cleanup
    - Progress tracking
    - Watchdog timeout handling
    - Overlay key management for GL transitions
    
    Phase E Context:
        This class provides deterministic transition state management,
        ensuring overlay visibility changes happen in a consistent order
        during transition start/finish sequences.
    """
    
    # Signals
    transition_started = Signal(str)  # transition_name
    transition_finished = Signal()
    transition_cancelled = Signal(str)  # reason
    
    def __init__(
        self,
        parent: "DisplayWidget",
        resource_manager: Optional[ResourceManager] = None,
        widget_manager: Optional["WidgetManager"] = None,
    ):
        """
        Initialize the TransitionController.
        
        Args:
            parent: The DisplayWidget that owns this controller
            resource_manager: Optional ResourceManager for lifecycle tracking
            widget_manager: Optional WidgetManager for overlay coordination
        """
        super().__init__(parent)
        self._parent = parent
        self._resource_manager = resource_manager
        self._widget_manager = widget_manager
        
        # Current transition state
        self._current_transition: Optional[BaseTransition] = None
        self._current_overlay_key: Optional[str] = None
        self._transition_started_at: float = 0.0
        self._skip_count: int = 0
        
        # Watchdog timer
        self._watchdog_timer: Optional[QTimer] = None
        self._watchdog_resource_id: Optional[str] = None
        self._watchdog_overlay_key: Optional[str] = None
        self._watchdog_transition_name: Optional[str] = None
        self._watchdog_started_at: float = 0.0
        
        # Pending finish args for deferred completion
        self._pending_finish_args: Optional[tuple] = None
        
        # Overlay timeout tracking
        self._overlay_timeouts: dict[str, float] = {}
        
        logger.debug("[TRANSITION_CONTROLLER] Initialized")
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def current_transition(self) -> Optional[BaseTransition]:
        """Get the current running transition."""
        return self._current_transition
    
    @property
    def is_running(self) -> bool:
        """Check if a transition is currently running."""
        ct = self._current_transition
        try:
            return bool(ct and ct.is_running())
        except Exception:
            return False
    
    @property
    def skip_count(self) -> int:
        """Get the number of skipped transition requests."""
        return self._skip_count
    
    @property
    def overlay_key(self) -> Optional[str]:
        """Get the current overlay key for GL transitions."""
        return self._current_overlay_key
    
    # =========================================================================
    # Transition Lifecycle
    # =========================================================================
    
    def start_transition(
        self,
        transition: BaseTransition,
        old_pixmap: QPixmap,
        new_pixmap: QPixmap,
        overlay_key: Optional[str] = None,
        on_finished: Optional[Callable] = None,
    ) -> bool:
        """
        Start a new transition.
        
        Args:
            transition: The transition to start
            old_pixmap: The source pixmap
            new_pixmap: The destination pixmap
            overlay_key: Optional overlay key for GL transitions
            on_finished: Optional callback when transition finishes
            
        Returns:
            True if transition started successfully
        """
        # If a transition is already running, skip this request
        if self.is_running:
            self._skip_count += 1
            logger.debug(
                "Transition in progress - skipping request (skip_count=%d)",
                self._skip_count,
            )
            return False
        
        # Stop any existing transition
        self.stop_current()
        
        # Set up the new transition
        self._current_transition = transition
        self._current_overlay_key = overlay_key
        self._transition_started_at = time.monotonic()
        
        if overlay_key:
            self._overlay_timeouts[overlay_key] = self._transition_started_at
        
        # Connect finish handler
        if on_finished:
            transition.finished.connect(on_finished)
        
        # Start the transition
        try:
            success = transition.start(old_pixmap, new_pixmap, self._parent)
            if success:
                self._start_watchdog(overlay_key, transition)
                self.transition_started.emit(transition.__class__.__name__)
                return True
            else:
                logger.warning("Transition failed to start")
                self._cleanup_transition(transition)
                return False
        except Exception as e:
            logger.error("Exception starting transition: %s", e, exc_info=True)
            self._cleanup_transition(transition)
            return False
    
    def stop_current(self) -> None:
        """Stop the current transition if running."""
        if self._current_transition is None:
            return
        
        transition = self._current_transition
        self._current_transition = None
        
        try:
            transition.stop()
        except Exception:
            pass
        
        try:
            transition.cleanup()
        except Exception:
            pass
        
        self._cancel_watchdog()
        self._clear_overlay_timeout()
    
    def on_transition_finished(self) -> None:
        """Handle transition completion.
        
        Called by DisplayWidget when the transition's finished signal fires.
        """
        overlay_key = self._current_overlay_key
        if overlay_key:
            self._overlay_timeouts.pop(overlay_key, None)
        
        self._current_overlay_key = None
        self._transition_started_at = 0.0
        self._cancel_watchdog()
        
        transition = self._current_transition
        self._current_transition = None
        
        if transition:
            try:
                transition.cleanup()
            except Exception:
                pass
        
        self.transition_finished.emit()
    
    def _cleanup_transition(self, transition: BaseTransition) -> None:
        """Clean up a failed or cancelled transition."""
        self._current_transition = None
        self._current_overlay_key = None
        self._transition_started_at = 0.0
        self._pending_finish_args = None
        self._cancel_watchdog()
        
        try:
            transition.cleanup()
        except Exception:
            pass
    
    def _clear_overlay_timeout(self) -> None:
        """Clear the current overlay timeout."""
        if self._current_overlay_key:
            self._overlay_timeouts.pop(self._current_overlay_key, None)
        self._current_overlay_key = None
        self._transition_started_at = 0.0
    
    # =========================================================================
    # Watchdog Timer
    # =========================================================================
    
    def _start_watchdog(self, overlay_key: Optional[str], transition: BaseTransition) -> None:
        """Start the transition watchdog timer."""
        timeout_sec = TRANSITION_WATCHDOG_DEFAULT_SEC
        
        # Check for custom timeout in settings
        try:
            settings = getattr(self._parent, "settings_manager", None)
            if settings:
                custom = settings.get("transitions.watchdog_timeout_sec", None)
                if custom is not None:
                    timeout_sec = float(custom)
        except Exception:
            pass
        
        timeout_ms = int(timeout_sec * 1000)
        
        self._cancel_watchdog()
        
        self._watchdog_overlay_key = overlay_key
        self._watchdog_transition_name = transition.__class__.__name__
        self._watchdog_started_at = time.monotonic()
        
        try:
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(self._on_watchdog_timeout)
            timer.start(timeout_ms)
            self._watchdog_timer = timer
            
            if self._resource_manager:
                try:
                    rid = self._resource_manager.register_qt(
                        timer, description="TransitionWatchdog"
                    )
                    self._watchdog_resource_id = rid
                except Exception:
                    pass
            
            if is_verbose_logging():
                logger.debug(
                    "[WATCHDOG] Started: timeout=%.1fs overlay=%s transition=%s",
                    timeout_sec, overlay_key, self._watchdog_transition_name,
                )
        except Exception:
            logger.debug("[WATCHDOG] Failed to start watchdog timer", exc_info=True)
    
    def _cancel_watchdog(self) -> None:
        """Stop the watchdog timer."""
        if self._watchdog_timer and self._watchdog_timer.isActive():
            try:
                self._watchdog_timer.stop()
            except Exception:
                pass
        
        if self._watchdog_resource_id and self._resource_manager:
            try:
                self._resource_manager.unregister(self._watchdog_resource_id)
            except Exception:
                pass
        
        self._watchdog_timer = None
        self._watchdog_resource_id = None
        self._watchdog_overlay_key = None
        self._watchdog_transition_name = None
        self._watchdog_started_at = 0.0
    
    def _on_watchdog_timeout(self) -> None:
        """Handle watchdog timeout - transition took too long."""
        elapsed = 0.0
        if self._watchdog_started_at > 0:
            elapsed = max(0.0, time.monotonic() - self._watchdog_started_at)
        
        transition_name = self._watchdog_transition_name or (
            self._current_transition.__class__.__name__ if self._current_transition else "<unknown>"
        )
        
        logger.warning(
            "[WATCHDOG] Transition timeout: %s elapsed=%.2fs overlay=%s",
            transition_name, elapsed, self._watchdog_overlay_key,
        )
        
        transition = self._current_transition
        self._cancel_watchdog()
        
        # Force cleanup the stuck transition
        if transition:
            try:
                transition.stop()
            except Exception:
                pass
            try:
                transition.cleanup()
            except Exception:
                pass
            if self._current_transition is transition:
                self._current_transition = None
        
        self.transition_cancelled.emit("watchdog_timeout")
    
    # =========================================================================
    # Pending Finish Args
    # =========================================================================
    
    def set_pending_finish_args(self, args: tuple) -> None:
        """Store pending finish arguments for deferred completion."""
        self._pending_finish_args = args
    
    def get_pending_finish_args(self) -> Optional[tuple]:
        """Get and clear pending finish arguments."""
        args = self._pending_finish_args
        self._pending_finish_args = None
        return args
    
    def clear_pending_finish_args(self) -> None:
        """Clear pending finish arguments."""
        self._pending_finish_args = None
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def cleanup(self) -> None:
        """Clean up all transition state."""
        self.stop_current()
        self._cancel_watchdog()
        self._overlay_timeouts.clear()
        self._pending_finish_args = None
        logger.debug("[TRANSITION_CONTROLLER] Cleanup complete")
