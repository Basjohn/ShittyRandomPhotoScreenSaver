"""
Centralized animation framework.

Provides the AnimationManager for coordinating ALL animations in the application.
NO raw QPropertyAnimation or QTimer should be used outside this module.
"""
import time
import uuid
from typing import Any, Dict, Optional, Callable
from PySide6.QtCore import QObject, QTimer, Signal, Property
from core.animation.types import (
    AnimationState, AnimationType, EasingCurve,
    PropertyAnimationConfig, CustomAnimationConfig, AnimationGroupConfig
)
from core.animation.easing import ease
from core.logging.logger import get_logger

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
                 delay: float = 0.0):
        """
        Initialize animation.
        
        Args:
            animation_id: Unique ID for this animation
            duration: Duration in seconds
            easing: Easing curve
            delay: Delay before starting (seconds)
        """
        super().__init__()
        
        self.animation_id = animation_id
        self.duration = duration
        self.easing = easing
        self.delay = delay
        
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
        
        # Update elapsed time
        self.elapsed += delta_time
        
        # Calculate progress (0.0 to 1.0)
        if self.duration <= 0:
            progress = 1.0
        else:
            progress = min(1.0, self.elapsed / self.duration)
        
        # Apply easing
        eased_progress = ease(progress, self.easing)
        
        # Emit progress
        self.progress_changed.emit(eased_progress)
        
        # Check if complete
        if progress >= 1.0:
            self.state = AnimationState.COMPLETE
            self.completed.emit()
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
    
    def __init__(self, animation_id: str, config: CustomAnimationConfig):
        """
        Initialize custom animator.
        
        Args:
            animation_id: Unique ID
            config: Custom animation configuration
        """
        super().__init__(animation_id, config.duration, config.easing, config.delay)
        
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
    
    def __init__(self, fps: int = 60):
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
        
        # Update timer
        self._timer = QTimer()
        self._timer.setInterval(int(self.frame_time * 1000))  # Convert to milliseconds
        self._timer.timeout.connect(self._update_all)
        
        logger.info(f"AnimationManager initialized (fps={fps})")
    
    def start(self) -> None:
        """Start the animation manager's update loop."""
        if not self._timer.isActive():
            self._last_update_time = time.time()
            self._timer.start()
            logger.debug("AnimationManager started")
    
    def stop(self) -> None:
        """Stop the animation manager's update loop."""
        if self._timer.isActive():
            self._timer.stop()
            logger.debug("AnimationManager stopped")
    
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
                      delay: float = 0.0) -> str:
        """
        Create a custom animation with user-provided update callback.
        
        Args:
            duration: Duration in seconds
            update_callback: Called each frame with progress (0.0-1.0)
            easing: Easing curve
            on_start: Callback when animation starts
            on_complete: Callback when animation completes
            delay: Delay before starting (seconds)
        
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
        
        animator = CustomAnimator(animation_id, config)
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
        
        Args:
            animation_id: Animation ID
        
        Returns:
            True if cancelled successfully
        """
        if animation_id in self._animations:
            self._animations[animation_id].cancel()
            self.animation_cancelled.emit(animation_id)
            # Remove from active animations
            del self._animations[animation_id]
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
        animator.completed.connect(lambda: self._on_animation_complete(animation_id))
        animator.cancelled.connect(lambda: self._on_animation_cancelled(animation_id))
        
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
        
        # Stop timer if no animations left
        if not self._animations and self._timer.isActive():
            self.stop()
    
    def _on_animation_cancelled(self, animation_id: str) -> None:
        """Handle animation cancellation."""
        # Already handled in cancel_animation
        pass
    
    def _update_all(self) -> None:
        """Update all active animations (called by timer)."""
        current_time = time.time()
        
        if self._last_update_time is None:
            self._last_update_time = current_time
            return
        
        delta_time = current_time - self._last_update_time
        self._last_update_time = current_time
        
        # Update all animations
        completed_ids = []
        for anim_id, animator in list(self._animations.items()):
            still_running = animator.update(delta_time)
            if not still_running:
                completed_ids.append(anim_id)
        
        # Note: Completed animations are removed via signal handlers
