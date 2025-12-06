"""
Centralized animation framework.

Provides the AnimationManager for coordinating ALL animations in the application.
NO raw QPropertyAnimation or QTimer should be used outside this module.

FRAME PACING: Animations now support decoupled rendering via FrameState. When
a frame_state is attached, progress samples are pushed with timestamps, and
the render thread can interpolate to the actual render time for smooth motion
even when timer callbacks are delayed.
"""
import time
import uuid
from typing import Any, Dict, Optional, Callable, TYPE_CHECKING
from PySide6.QtCore import QObject, QTimer, Signal, Qt
from core.animation.types import (
    AnimationState, EasingCurve,
    PropertyAnimationConfig, CustomAnimationConfig, AnimationGroupConfig
)
from core.animation.easing import ease
from core.animation.frame_interpolator import FrameState
from core.logging.logger import get_logger, is_perf_metrics_enabled

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from core.resources.manager import ResourceManager

logger = get_logger(__name__)


class Animation(QObject):
    """
    Base animation class.
    
    Handles the timing and easing logic for a single animation.
    """
    
    # Signals
    started = Signal()
    progress_changed = Signal(float)  # 0.0 to 1.0
    completed = Signal()
    cancelled = Signal()
    
    def __init__(self, animation_id: str, duration: float, easing: EasingCurve, 
                 delay: float = 0.0, frame_state: Optional[FrameState] = None):
        """
        Initialize animation.
        
        Args:
            animation_id: Unique ID for this animation
            duration: Duration in seconds
            easing: Easing curve
            delay: Delay before starting (seconds)
            frame_state: Optional FrameState for decoupled rendering
        """
        super().__init__()
        
        self.animation_id = animation_id
        self.duration = duration
        self.easing = easing
        self.delay = delay
        self.frame_state = frame_state
        
        self.state = AnimationState.IDLE
        self.elapsed = 0.0
        self.delay_elapsed = 0.0
        self.start_time: Optional[float] = None
        self.last_update_time: Optional[float] = None
    
    def start(self) -> None:
        """Start the animation."""
        if self.state == AnimationState.RUNNING:
            logger.warning(f"Animation {self.animation_id} already running")
            return
        
        self.state = AnimationState.RUNNING
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.elapsed = 0.0
        self.delay_elapsed = 0.0
        
        self.started.emit()
        logger.debug(f"Animation started: {self.animation_id} (duration={self.duration}s)")
    
    def pause(self) -> None:
        """Pause the animation."""
        if self.state == AnimationState.RUNNING:
            self.state = AnimationState.PAUSED
            logger.debug(f"Animation paused: {self.animation_id}")
    
    def resume(self) -> None:
        """Resume the animation."""
        if self.state == AnimationState.PAUSED:
            self.state = AnimationState.RUNNING
            self.last_update_time = time.time()
            logger.debug(f"Animation resumed: {self.animation_id}")
    
    def cancel(self) -> None:
        """Cancel the animation."""
        if self.state in (AnimationState.RUNNING, AnimationState.PAUSED):
            self.state = AnimationState.CANCELLED
            self.cancelled.emit()
            logger.debug(f"Animation cancelled: {self.animation_id}")
    
    def update(self, delta_time: float) -> bool:
        """
        Update animation state.
        
        Args:
            delta_time: Time since last update in seconds
        
        Returns:
            True if animation is still running, False if complete/cancelled
        """
        if self.state != AnimationState.RUNNING:
            return False
        
        # Handle delay
        if self.delay_elapsed < self.delay:
            self.delay_elapsed += delta_time
            if self.delay_elapsed < self.delay:
                return True  # Still in delay period
            # Delay complete, continue to animation
            delta_time = self.delay_elapsed - self.delay
        
        # Update elapsed time with minimal clamping.
        # Only clamp extreme outliers (>500ms) to prevent teleporting on major
        # stalls, but otherwise let the animation progress naturally. The old
        # aggressive clamping (25% of duration) caused visible stuttering.
        if delta_time > 0.5:
            delta_time = 0.5
        self.elapsed += delta_time

        # Calculate progress (0.0 to 1.0)
        if self.duration <= 0:
            progress = 1.0
        else:
            progress = min(1.0, self.elapsed / self.duration)
        
        # Apply easing
        eased_progress = ease(progress, self.easing)
        
        # Push to frame state for decoupled rendering (if attached)
        if self.frame_state is not None:
            self.frame_state.push(eased_progress)
        
        # Emit progress - PERF: measure signal emission time
        _emit_start = time.time()
        self.progress_changed.emit(eased_progress)
        _emit_elapsed = (time.time() - _emit_start) * 1000.0
        if _emit_elapsed > 30.0 and is_perf_metrics_enabled():
            logger.warning("[PERF] [ANIM] Slow progress_changed.emit: %.2fms (anim=%s)", 
                          _emit_elapsed, self.animation_id[:8])
        
        # Check if complete
        if progress >= 1.0:
            self.state = AnimationState.COMPLETE
            if self.frame_state is not None:
                self.frame_state.mark_complete()
            _complete_start = time.time()
            self.completed.emit()
            _complete_elapsed = (time.time() - _complete_start) * 1000.0
            if _complete_elapsed > 30.0 and is_perf_metrics_enabled():
                logger.warning("[PERF] [ANIM] Slow completed.emit: %.2fms (anim=%s)",
                              _complete_elapsed, self.animation_id[:8])
            logger.debug(f"Animation completed: {self.animation_id}")
            return False
        
        return True
    
    def get_progress(self) -> float:
        """Get current progress (0.0 to 1.0)."""
        if self.duration <= 0:
            return 1.0
        return min(1.0, self.elapsed / self.duration)


class PropertyAnimator(Animation):
    """Animates a Qt property on a target object."""
    
    def __init__(self, animation_id: str, config: PropertyAnimationConfig):
        """
        Initialize property animator.
        
        Args:
            animation_id: Unique ID
            config: Property animation configuration
        """
        super().__init__(animation_id, config.duration, config.easing, config.delay)
        
        self.target = config.target
        self.property_name = config.property_name
        self.start_value = config.start_value
        self.end_value = config.end_value
        
        self.on_start_callback = config.on_start
        self.on_update_callback = config.on_update
        self.on_complete_callback = config.on_complete
        self.on_cancel_callback = config.on_cancel
        
        # Connect signals to callbacks
        if self.on_start_callback:
            self.started.connect(self.on_start_callback)
        if self.on_complete_callback:
            self.completed.connect(self.on_complete_callback)
        if self.on_cancel_callback:
            self.cancelled.connect(self.on_cancel_callback)
        
        # Connect progress to property update
        self.progress_changed.connect(self._update_property)
    
    def _update_property(self, progress: float) -> None:
        """Update the target property based on progress."""
        try:
            # Interpolate between start and end values
            if isinstance(self.start_value, (int, float)) and isinstance(self.end_value, (int, float)):
                # Numeric interpolation
                value = self.start_value + (self.end_value - self.start_value) * progress
            else:
                # For non-numeric values, just set end value when progress >= 1.0
                value = self.end_value if progress >= 1.0 else self.start_value
            
            # Set property
            if hasattr(self.target, f'set{self.property_name.capitalize()}'):
                # Use setter method (e.g., setOpacity)
                setter = getattr(self.target, f'set{self.property_name.capitalize()}')
                setter(value)
            elif hasattr(self.target, self.property_name):
                # Set attribute directly
                setattr(self.target, self.property_name, value)
            else:
                logger.warning(f"Property {self.property_name} not found on {self.target}")
            
            # Call update callback if provided
            if self.on_update_callback:
                self.on_update_callback(progress)
                
        except Exception as e:
            logger.error(f"Error updating property {self.property_name}: {e}")


class CustomAnimator(Animation):
    """Custom animation with user-provided update callback."""
    
    def __init__(self, animation_id: str, config: CustomAnimationConfig, 
                 frame_state: Optional[FrameState] = None):
        """
        Initialize custom animator.
        
        Args:
            animation_id: Unique ID
            config: Custom animation configuration
            frame_state: Optional FrameState for decoupled rendering
        """
        super().__init__(animation_id, config.duration, config.easing, config.delay, frame_state)
        
        self.update_callback = config.update_callback
        self.on_start_callback = config.on_start
        self.on_complete_callback = config.on_complete
        self.on_cancel_callback = config.on_cancel
        
        # Connect signals to callbacks
        if self.on_start_callback:
            self.started.connect(self.on_start_callback)
        if self.on_complete_callback:
            self.completed.connect(self.on_complete_callback)
        if self.on_cancel_callback:
            self.cancelled.connect(self.on_cancel_callback)
        
        # Connect progress to custom update
        self.progress_changed.connect(self.update_callback)


class AnimationManager(QObject):
    """
    Centralized animation manager.
    
    ALL animations in the application MUST go through this manager.
    NO raw QPropertyAnimation or QTimer should be used elsewhere.
    """
    
    # Signals for global animation events
    animation_started = Signal(str)  # animation_id
    animation_completed = Signal(str)  # animation_id
    animation_cancelled = Signal(str)  # animation_id
    
    def __init__(self, fps: int = 60, resource_manager: Optional["ResourceManager"] = None):
        """
        Initialize animation manager.
        
        Args:
            fps: Target frames per second for updates
        """
        super().__init__()
        
        self.fps = fps
        self.frame_time = 1.0 / fps
        
        self._animations: Dict[str, Animation] = {}
        self._animation_groups: Dict[str, AnimationGroupConfig] = {}
        self._last_update_time: Optional[float] = None

        self._tick_listeners: Dict[int, Callable[[float], None]] = {}

        # Lightweight profiling state for `[PERF] [ANIM]` metrics. These are
        # reset each time the manager's timer starts and logged once when it
        # stops so callers can correlate effective FPS and dt jitter with
        # higher-level transition metrics.
        self._profile_start_ts: Optional[float] = None
        self._profile_last_ts: Optional[float] = None
        self._profile_frame_count: int = 0
        self._profile_min_dt: float = 0.0
        self._profile_max_dt: float = 0.0
        
        # Update timer
        self._timer = QTimer()
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(int(self.frame_time * 1000))  # Convert to milliseconds
        self._timer.timeout.connect(self._update_all)
        # Register timer with ResourceManager for lifecycle tracking
        self._resources: Optional["ResourceManager"] = resource_manager
        try:
            from core.resources.manager import ResourceManager
            if self._resources is None:
                self._resources = ResourceManager()
            try:
                self._resources.register_qt(self._timer, description="AnimationManager timer")
            except Exception:
                pass
        except Exception:
            self._resources = None
        
        logger.info(f"AnimationManager initialized (fps={fps})")

    def set_target_fps(self, fps: int) -> None:
        """Update target FPS and reconfigure the timer interval safely."""
        try:
            new_fps = max(10, min(240, int(fps)))
        except Exception:
            new_fps = 60
        if new_fps == self.fps:
            return
        self.fps = new_fps
        self.frame_time = 1.0 / self.fps
        was_active = self._timer.isActive() if self._timer else False
        if was_active:
            self._timer.stop()
        self._timer.setInterval(int(self.frame_time * 1000))
        if was_active:
            self._last_update_time = time.time()
            self._timer.start()
        logger.info(f"AnimationManager target FPS set to {self.fps}")
    
    def start(self) -> None:
        """Start the animation manager's update loop."""
        if not self._timer.isActive():
            now = time.time()
            self._last_update_time = now
            # Reset profiling for this run so `[PERF] [ANIM]` metrics reflect a
            # single continuous active period.
            self._profile_start_ts = now
            self._profile_last_ts = None
            self._profile_frame_count = 0
            self._profile_min_dt = 0.0
            self._profile_max_dt = 0.0

            self._timer.start()
            logger.debug("AnimationManager started")
    
    def stop(self) -> None:
        """Stop the animation manager's update loop.
        
        Thread-safe: Uses QTimer.singleShot to ensure timer operations
        happen on the UI thread.
        """
        try:
            # Check if we're on the UI thread by checking timer's thread affinity
            if self._timer.thread() != QTimer().thread():
                # We're on a different thread - schedule stop on UI thread
                QTimer.singleShot(0, self._do_stop)
            else:
                self._do_stop()
        except Exception:
            # Fallback: try direct stop
            self._do_stop()
    
    def _do_stop(self) -> None:
        """Internal stop implementation - must be called on UI thread."""
        if self._timer.isActive():
            self._timer.stop()
            self._log_profile_summary()
            logger.debug("AnimationManager stopped")
    
    def cleanup(self) -> None:
        """Clean up animation manager resources."""
        # FIX: Add proper cleanup method for timer and animations
        logger.debug("Cleaning up AnimationManager")
        
        # Stop timer
        self.stop()
        
        # Cancel all animations
        animation_ids = list(self._animations.keys())
        for anim_id in animation_ids:
            self.cancel_animation(anim_id)
        
        # Clean up timer
        if self._timer:
            try:
                self._timer.deleteLater()
            except RuntimeError:
                pass
        
        logger.info("AnimationManager cleanup complete")

    def add_tick_listener(self, callback: Callable[[float], None]) -> int:
        """Add a tick listener that receives delta time on each frame.
        
        ARCHITECTURAL NOTE: Adding a tick listener will start the timer if not
        already running, ensuring continuous ticks for overlays like Spotify
        visualizer even when no animations are active.
        """
        listener_id = id(callback)
        self._tick_listeners[listener_id] = callback
        # Start timer if not running - tick listeners need continuous ticks
        if not self._timer.isActive():
            self.start()
        return listener_id

    def remove_tick_listener(self, callback_id: int) -> None:
        """Remove a tick listener.
        
        If this was the last listener and there are no active animations,
        the timer will stop to conserve resources.
        """
        self._tick_listeners.pop(callback_id, None)
        # Stop timer if no animations and no listeners remain
        if not self._animations and not self._tick_listeners and self._timer.isActive():
            self.stop()
    
    def animate_property(self, target: Any, property_name: str, start_value: Any, 
                        end_value: Any, duration: float, 
                        easing: EasingCurve = EasingCurve.LINEAR,
                        on_start: Optional[Callable] = None,
                        on_update: Optional[Callable] = None,
                        on_complete: Optional[Callable] = None,
                        delay: float = 0.0) -> str:
        """
        Animate a property on a target object.
        
        Args:
            target: Object to animate
            property_name: Property name (e.g., 'opacity')
            start_value: Starting value
            end_value: Ending value
            duration: Duration in seconds
            easing: Easing curve
            on_start: Callback when animation starts
            on_update: Callback on each update (receives progress 0.0-1.0)
            on_complete: Callback when animation completes
            delay: Delay before starting (seconds)
        
        Returns:
            Animation ID
        """
        animation_id = str(uuid.uuid4())
        
        config = PropertyAnimationConfig(
            duration=duration,
            easing=easing,
            on_start=on_start,
            on_update=on_update,
            on_complete=on_complete,
            delay=delay,
            target=target,
            property_name=property_name,
            start_value=start_value,
            end_value=end_value
        )
        
        animator = PropertyAnimator(animation_id, config)
        self._add_animation(animation_id, animator)
        animator.start()
        
        return animation_id
    
    def animate_custom(self, duration: float, update_callback: Callable[[float], None],
                      easing: EasingCurve = EasingCurve.LINEAR,
                      on_start: Optional[Callable] = None,
                      on_complete: Optional[Callable] = None,
                      delay: float = 0.0,
                      frame_state: Optional[FrameState] = None) -> str:
        """
        Create a custom animation with user-provided update callback.
        
        Args:
            duration: Duration in seconds
            update_callback: Called each frame with progress (0.0-1.0)
            easing: Easing curve
            on_start: Callback when animation starts
            on_complete: Callback when animation completes
            delay: Delay before starting (seconds)
            frame_state: Optional FrameState for decoupled rendering
        
        Returns:
            Animation ID
        """
        animation_id = str(uuid.uuid4())
        
        config = CustomAnimationConfig(
            duration=duration,
            easing=easing,
            on_start=on_start,
            on_complete=on_complete,
            delay=delay,
            update_callback=update_callback
        )
        
        animator = CustomAnimator(animation_id, config, frame_state=frame_state)
        self._add_animation(animation_id, animator)
        animator.start()
        
        return animation_id
    
    def pause_animation(self, animation_id: str) -> bool:
        """
        Pause an animation.
        
        Args:
            animation_id: Animation ID
        
        Returns:
            True if paused successfully
        """
        if animation_id in self._animations:
            self._animations[animation_id].pause()
            return True
        return False
    
    def resume_animation(self, animation_id: str) -> bool:
        """
        Resume a paused animation.
        
        Args:
            animation_id: Animation ID
        
        Returns:
            True if resumed successfully
        """
        if animation_id in self._animations:
            self._animations[animation_id].resume()
            return True
        return False
    
    def cancel_animation(self, animation_id: str) -> bool:
        """
        Cancel an animation.
        
        Thread-safe: Can be called from any thread.
        
        Args:
            animation_id: Animation ID
        
        Returns:
            True if cancelled successfully
        """
        if animation_id in self._animations:
            self._animations[animation_id].cancel()
            try:
                self.animation_cancelled.emit(animation_id)
            except Exception:
                pass
            # Remove from active animations
            del self._animations[animation_id]
            # Stop timer only if no animations AND no tick listeners remain
            # Use thread-safe stop() which handles cross-thread calls
            if not self._animations and not self._tick_listeners:
                try:
                    if self._timer.isActive():
                        self.stop()
                except Exception:
                    # Timer check from wrong thread - schedule stop
                    QTimer.singleShot(0, self._do_stop)
            return True
        return False
    
    def is_running(self, animation_id: str) -> bool:
        """Check if an animation is currently running."""
        if animation_id in self._animations:
            return self._animations[animation_id].state == AnimationState.RUNNING
        return False
    
    def get_progress(self, animation_id: str) -> Optional[float]:
        """Get the progress of an animation (0.0 to 1.0)."""
        if animation_id in self._animations:
            return self._animations[animation_id].get_progress()
        return None
    
    def get_active_count(self) -> int:
        """Get the number of active animations."""
        return len(self._animations)
    
    def cancel_all(self) -> None:
        """Cancel all active animations."""
        animation_ids = list(self._animations.keys())
        for anim_id in animation_ids:
            self.cancel_animation(anim_id)
        logger.info("All animations cancelled")
    
    def _add_animation(self, animation_id: str, animator: Animation) -> None:
        """Add an animation to the manager."""
        self._animations[animation_id] = animator
        
        # Connect completion/cancellation to cleanup
        # FIX: Use default args to capture animation_id by value (not by reference)
        animator.completed.connect(lambda aid=animation_id: self._on_animation_complete(aid))
        animator.cancelled.connect(lambda aid=animation_id: self._on_animation_cancelled(aid))
        
        # Start update loop if not running
        if not self._timer.isActive():
            self.start()
        
        self.animation_started.emit(animation_id)
    
    def _on_animation_complete(self, animation_id: str) -> None:
        """Handle animation completion."""
        self.animation_completed.emit(animation_id)
        # Remove completed animation
        if animation_id in self._animations:
            del self._animations[animation_id]
        
        # ARCHITECTURAL FIX: Keep timer running if there are tick listeners.
        # Tick listeners (like Spotify visualizer) need continuous ticks even
        # when no animations are active. Only stop if both animations AND
        # tick listeners are empty.
        if not self._animations and not self._tick_listeners and self._timer.isActive():
            self.stop()

    def _on_animation_cancelled(self, animation_id: str) -> None:
        """Handle animation cancellation."""
        # Already handled in cancel_animation
        pass

    def _update_all(self) -> None:
        """Update all active animations (called by timer).
        
        FRAME PACING: Uses time-based delta calculation to ensure smooth
        animations regardless of timer jitter. The delta_time is clamped
        to prevent teleporting on major stalls (>500ms) but otherwise
        reflects actual elapsed time for accurate animation progress.
        """
        current_time = time.time()

        if self._last_update_time is None:
            self._last_update_time = current_time
            return

        delta_time = current_time - self._last_update_time
        self._last_update_time = current_time

        # FRAME PACING: Clamp extreme deltas to prevent teleporting on major
        # stalls (e.g., system sleep, heavy GC). 500ms is chosen as a balance
        # between allowing catch-up and preventing jarring jumps.
        if delta_time > 0.5:
            if is_perf_metrics_enabled():
                logger.info(
                    "[PERF] [ANIM] Large frame dt=%.2fms clamped to 500ms (target=%.2fms, active=%d, listeners=%d)",
                    delta_time * 1000.0,
                    self.frame_time * 1000.0,
                    len(self._animations),
                    len(self._tick_listeners),
                )
            delta_time = 0.5  # Clamp to 500ms max

        # Profiling: track timing characteristics without altering behaviour.
        if self._profile_start_ts is None:
            self._profile_start_ts = current_time
        if delta_time > 0.0:
            if self._profile_min_dt == 0.0 or delta_time < self._profile_min_dt:
                self._profile_min_dt = delta_time
            if delta_time > self._profile_max_dt:
                self._profile_max_dt = delta_time
        self._profile_last_ts = current_time
        self._profile_frame_count += 1

        # Update all animations
        for anim_id, animator in list(self._animations.items()):
            _anim_start = time.time()
            animator.update(delta_time)
            _anim_elapsed = (time.time() - _anim_start) * 1000.0
            if _anim_elapsed > 50.0 and is_perf_metrics_enabled():
                logger.warning("[PERF] [ANIM] Slow animation update (%s): %.2fms", anim_id[:8], _anim_elapsed)

        if self._tick_listeners:
            for cb in list(self._tick_listeners.values()):
                try:
                    _cb_start = time.time()
                    cb(delta_time)
                    _cb_elapsed = (time.time() - _cb_start) * 1000.0
                    if _cb_elapsed > 50.0 and is_perf_metrics_enabled():
                        logger.warning("[PERF] [ANIM] Slow tick listener: %.2fms", _cb_elapsed)
                except Exception as e:
                    logger.debug("[ANIM] Tick listener failed: %s", e, exc_info=True)

    def _log_profile_summary(self) -> None:
        """Emit a concise `[PERF] [ANIM]` summary for the last active run."""

        try:
            if (
                self._profile_start_ts is not None
                and self._profile_last_ts is not None
                and self._profile_frame_count > 0
            ):
                elapsed = max(0.0, self._profile_last_ts - self._profile_start_ts)
                if elapsed > 0.0:
                    duration_ms = elapsed * 1000.0
                    avg_fps = self._profile_frame_count / elapsed
                    min_dt_ms = (
                        self._profile_min_dt * 1000.0
                        if self._profile_min_dt > 0.0
                        else 0.0
                    )
                    max_dt_ms = (
                        self._profile_max_dt * 1000.0
                        if self._profile_max_dt > 0.0
                        else 0.0
                    )
                    logger.info(
                        "[PERF] [ANIM] AnimationManager metrics: duration=%.1fms, "
                        "frames=%d, avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
                        "active_count=%d, fps_target=%d",
                        duration_ms,
                        self._profile_frame_count,
                        avg_fps,
                        min_dt_ms,
                        max_dt_ms,
                        self.get_active_count(),
                        self.fps,
                    )
        except Exception as e:
            logger.debug("[ANIM] Metrics logging failed: %s", e, exc_info=True)
        finally:
            self._profile_start_ts = None
            self._profile_last_ts = None
            self._profile_frame_count = 0
            self._profile_min_dt = 0.0
            self._profile_max_dt = 0.0
