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

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.resources.manager import ResourceManager
from transitions.base_transition import BaseTransition, TransitionState

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget
    from rendering.widget_manager import WidgetManager

logger = get_logger(__name__)

# Default watchdog timeout for transitions
# Must be longer than the longest transition duration (15s max)
# Plus buffer for initialization and cleanup
TRANSITION_WATCHDOG_DEFAULT_SEC = 18.0


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
        self._generation: int = 0
        self._active_generation: int = 0
        self._admission_open: bool = True
        self._stopping: bool = False
        self._terminal_phase: str = "idle"
        self._finish_handler: Optional[Callable[[], None]] = None
        
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
    
    def get_active_transition_name(self) -> Optional[str]:
        """Return the active transition's class name, if any."""
        transition = self._current_transition
        if transition is None:
            return None
        try:
            return transition.__class__.__name__
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
            return None
    
    def get_active_transition_elapsed_s(self) -> Optional[float]:
        """Return seconds since the current transition started, if running."""
        transition = self._current_transition
        if transition is None or self._transition_started_at <= 0.0:
            return None
        try:
            return max(0.0, time.monotonic() - self._transition_started_at)
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
            return None

    def describe_state(self) -> dict:
        """Return a snapshot of the current transition state."""
        transition = self._current_transition
        try:
            name = transition.__class__.__name__ if transition else None
        except Exception:
            name = None
        return {
            "running": self.is_running,
            "transition": name,
            "overlay_key": self._current_overlay_key,
            "elapsed_s": self.get_active_transition_elapsed_s(),
            "skip_count": self._skip_count,
            "generation": self._active_generation,
            "admission_open": self._admission_open,
            "terminal_phase": self._terminal_phase,
        }
    
    @property
    def is_running(self) -> bool:
        """Check if a transition is currently running."""
        ct = self._current_transition
        try:
            return bool(ct and ct.is_running())
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
            return False
    
    @property
    def skip_count(self) -> int:
        """Get the number of skipped transition requests."""
        return self._skip_count
    
    @property
    def overlay_key(self) -> Optional[str]:
        """Get the current overlay key for GL transitions."""
        return self._current_overlay_key

    @property
    def active_generation(self) -> int:
        """Return the generation of the currently owned transition."""
        return int(self._active_generation)

    @property
    def admission_open(self) -> bool:
        """Return whether this display may accept new transition work."""
        return bool(self._admission_open)
    
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
        if not self._admission_open:
            logger.warning(
                "[TRANSITION][BLOCKED] Admission closed screen=%s transition=%s",
                getattr(self._parent, "screen_index", "?"),
                transition.__class__.__name__,
            )
            return False

        # A controller-owned object remains busy through terminal cleanup,
        # even after its public RUNNING state has changed.
        if self._current_transition is not None:
            self._skip_count += 1
            logger.debug(
                "Transition in progress - skipping request (skip_count=%d)",
                self._skip_count,
            )
            return False
        
        # Set up the new transition
        self._generation += 1
        generation = self._generation
        self._active_generation = generation
        self._current_transition = transition
        self._current_overlay_key = overlay_key
        self._terminal_phase = "running"
        deferred_start = False
        try:
            deferred_start = bool(transition.uses_deferred_start_telemetry())
        except Exception:
            deferred_start = False
        self._transition_started_at = 0.0 if deferred_start else time.monotonic()
        
        if overlay_key:
            self._overlay_timeouts[overlay_key] = self._transition_started_at
        
        def _finished() -> None:
            self._finish_transition(
                transition,
                generation=generation,
                on_finished=on_finished,
            )

        self._finish_handler = _finished
        transition.finished.connect(_finished)
        
        # Start the transition
        try:
            success = transition.start(old_pixmap, new_pixmap, self._parent)
            if success:
                # Immediate-completion transitions can emit synchronously from
                # start(). Do not arm a watchdog after that generation is idle.
                if self._current_transition is transition:
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
    
    def stop_current(self, snap_to_new: bool = True, reason: str = "unspecified") -> None:
        """Stop the current transition if running.
        
        Args:
            snap_to_new: If True, signal compositor to snap to new image
                         to avoid visual pops when interrupted.
            reason: Reason for stopping (used for instrumentation)
        """
        if self._current_transition is None:
            self._active_generation = 0
            self._terminal_phase = "idle"
            return
        
        transition = self._current_transition
        transition_name = None
        try:
            transition_name = transition.__class__.__name__
        except Exception:
            pass
        
        # Instrumentation: log stop reason with perf metrics
        if is_perf_metrics_enabled():
            anim_info = None
            try:
                compositor = getattr(self._parent, "_gl_compositor", None)
                if compositor is not None and hasattr(compositor, "get_current_animation_info"):
                    anim_info = compositor.get_current_animation_info()
            except Exception as exc:
                logger.debug("[TRANSITION] Failed to get animation info: %s", exc)
            logger.info(
                "[PERF][TRANSITION] stop_current reason=%s transition=%s anim_info=%s",
                reason, transition_name, anim_info
            )
        
        self._stopping = True
        self._terminal_phase = "cancelling"
        self._disconnect_finish_handler(transition)
        overlay_key = self._current_overlay_key
        self._current_transition = None
        self._current_overlay_key = None
        self._transition_started_at = 0.0
        self._active_generation = 0

        # Cancel the compositor exactly once. Detaching it first prevents each
        # transition class's stop()/cleanup() pair from re-entering GL state.
        compositor = getattr(transition, "_compositor", None)
        if compositor is None:
            compositor = getattr(self._parent, "_gl_compositor", None)
        try:
            setattr(transition, "_compositor", None)
        except Exception:
            pass
        try:
            if compositor is not None and hasattr(compositor, "cancel_current_transition"):
                compositor.cancel_current_transition(snap_to_new=bool(snap_to_new))
        except Exception:
            logger.error(
                "[TRANSITION] Compositor cancellation failed reason=%s",
                reason,
                exc_info=True,
            )

        try:
            transition.stop()
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
        
        try:
            transition.cleanup()
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
        
        self._cancel_watchdog()
        if overlay_key:
            self._overlay_timeouts.pop(overlay_key, None)
        self._clear_overlay_timeout()
        self._pending_finish_args = None
        self._terminal_phase = "idle"
        self._stopping = False
        self.transition_cancelled.emit(reason)

    def abort_current_preserving_old(self, reason: str) -> None:
        """Abort failed work without committing the uncompleted destination."""

        self.stop_current(snap_to_new=False, reason=reason)

    def begin_quiesce(self, *, reason: str, snap_to_new: bool = True) -> None:
        """Close admission and synchronously reconcile controller-owned work."""

        self._admission_open = False
        self.stop_current(snap_to_new=snap_to_new, reason=reason)

    def resume_after_quiesce(self) -> None:
        """Open a fresh admission generation after a non-destructive pause."""

        if self._current_transition is not None or self._terminal_phase != "idle":
            raise RuntimeError("Cannot resume transition admission while work is active")
        self._generation += 1
        self._active_generation = 0
        self._pending_finish_args = None
        self._stopping = False
        self._admission_open = True

    def _finish_transition(
        self,
        transition: BaseTransition,
        *,
        generation: int,
        on_finished: Optional[Callable],
    ) -> None:
        """Apply one natural completion after controller state is made idle."""

        if (
            self._stopping
            or transition is not self._current_transition
            or generation != self._active_generation
        ):
            return

        self._terminal_phase = "completion_applying"
        self._disconnect_finish_handler(transition)
        overlay_key = self._current_overlay_key
        if overlay_key:
            self._overlay_timeouts.pop(overlay_key, None)
        self._current_transition = None
        self._current_overlay_key = None
        self._transition_started_at = 0.0
        self._active_generation = 0
        self._cancel_watchdog()

        # The compositor has already committed its resident destination. Keep
        # mode-specific CPU cleanup, but prevent cleanup from cancelling GL a
        # second time inside the terminal callback.
        try:
            if transition.get_state() == TransitionState.FINISHED:
                setattr(transition, "_compositor", None)
                setattr(transition, "_animation_id", None)
        except Exception:
            logger.debug("[TRANSITION] Failed to detach completed compositor", exc_info=True)
        try:
            transition.cleanup()
        except Exception:
            logger.debug("[TRANSITION] Completed transition cleanup failed", exc_info=True)

        self._terminal_phase = "completion_applied"
        try:
            self.transition_finished.emit()
            if on_finished is not None:
                on_finished()
        finally:
            # Observers are outside authoritative ownership. A failing signal
            # must not strand the display after the compositor has committed.
            self._terminal_phase = "idle"

    def _disconnect_finish_handler(self, transition: BaseTransition) -> None:
        handler = self._finish_handler
        self._finish_handler = None
        if handler is None:
            return
        try:
            transition.finished.disconnect(handler)
        except Exception:
            pass
    
    def _cleanup_transition(self, transition: BaseTransition) -> None:
        """Clean up a failed or cancelled transition."""
        self._disconnect_finish_handler(transition)
        self._current_transition = None
        self._current_overlay_key = None
        self._transition_started_at = 0.0
        self._active_generation = 0
        self._terminal_phase = "idle"
        self._pending_finish_args = None
        self._cancel_watchdog()
        
        try:
            transition.cleanup()
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
    
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
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
        
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
                except Exception as e:
                    logger.debug("[TRANSITION] Exception suppressed: %s", e)
            
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
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)
        
        if self._watchdog_resource_id and self._resource_manager:
            try:
                self._resource_manager.unregister(self._watchdog_resource_id)
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)
        
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
        
        self._cancel_watchdog()
        callback = getattr(self._parent, "_on_deferred_transition_start_failed", None)
        if callable(callback):
            callback(transition_name, "watchdog_timeout")
            return
        self.abort_current_preserving_old("watchdog_timeout")
    
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
        self.begin_quiesce(reason="controller_cleanup")
        self._cancel_watchdog()
        self._overlay_timeouts.clear()
        self._pending_finish_args = None
        logger.debug("[TRANSITION_CONTROLLER] Cleanup complete")
