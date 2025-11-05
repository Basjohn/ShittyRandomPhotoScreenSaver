"""
Animation types, enums, and dataclasses.

Defines the core types used by the centralized animation framework.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Any, Callable, Optional


class AnimationState(Enum):
    """State of an animation."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class AnimationType(Enum):
    """Type of animation."""
    PROPERTY = "property"      # Animates a Qt property
    CUSTOM = "custom"          # Custom update function
    GROUP = "group"            # Group of animations


class EasingCurve(Enum):
    """
    Easing curve types for animations.
    
    Easing functions control the rate of change of the animated value over time.
    """
    # Basic
    LINEAR = "linear"
    
    # Quadratic
    QUAD_IN = "quad_in"
    QUAD_OUT = "quad_out"
    QUAD_IN_OUT = "quad_in_out"
    
    # Cubic
    CUBIC_IN = "cubic_in"
    CUBIC_OUT = "cubic_out"
    CUBIC_IN_OUT = "cubic_in_out"
    
    # Quartic
    QUART_IN = "quart_in"
    QUART_OUT = "quart_out"
    QUART_IN_OUT = "quart_in_out"
    
    # Quintic
    QUINT_IN = "quint_in"
    QUINT_OUT = "quint_out"
    QUINT_IN_OUT = "quint_in_out"
    
    # Sine
    SINE_IN = "sine_in"
    SINE_OUT = "sine_out"
    SINE_IN_OUT = "sine_in_out"
    
    # Exponential
    EXPO_IN = "expo_in"
    EXPO_OUT = "expo_out"
    EXPO_IN_OUT = "expo_in_out"
    
    # Circular
    CIRC_IN = "circ_in"
    CIRC_OUT = "circ_out"
    CIRC_IN_OUT = "circ_in_out"
    
    # Elastic
    ELASTIC_IN = "elastic_in"
    ELASTIC_OUT = "elastic_out"
    ELASTIC_IN_OUT = "elastic_in_out"
    
    # Back
    BACK_IN = "back_in"
    BACK_OUT = "back_out"
    BACK_IN_OUT = "back_in_out"
    
    # Bounce
    BOUNCE_IN = "bounce_in"
    BOUNCE_OUT = "bounce_out"
    BOUNCE_IN_OUT = "bounce_in_out"


@dataclass
class AnimationConfig:
    """Configuration for an animation."""
    duration: float                                    # Duration in seconds
    easing: EasingCurve = EasingCurve.LINEAR          # Easing curve
    on_start: Optional[Callable[[], None]] = None      # Called when animation starts
    on_update: Optional[Callable[[float], None]] = None  # Called each frame (progress 0.0-1.0)
    on_complete: Optional[Callable[[], None]] = None   # Called when animation completes
    on_cancel: Optional[Callable[[], None]] = None     # Called if animation is cancelled
    delay: float = 0.0                                 # Delay before starting (seconds)
    loop: bool = False                                 # Loop animation
    loop_count: int = -1                               # Number of loops (-1 = infinite)
    reverse: bool = False                              # Reverse animation on completion
    auto_destroy: bool = True                          # Auto-destroy when complete


@dataclass
class PropertyAnimationConfig(AnimationConfig):
    """Configuration for property animation."""
    target: Any = None               # Object to animate
    property_name: str = ""          # Property name (e.g., 'opacity')
    start_value: Any = None          # Starting value
    end_value: Any = None            # Ending value
    
    def __post_init__(self):
        """Validate property animation config."""
        if not self.target:
            raise ValueError("PropertyAnimationConfig requires a target")
        if not self.property_name:
            raise ValueError("PropertyAnimationConfig requires a property_name")


@dataclass
class CustomAnimationConfig(AnimationConfig):
    """Configuration for custom animation with update callback."""
    update_callback: Callable[[float], None] = None  # Called with progress 0.0-1.0
    
    def __post_init__(self):
        """Validate custom animation config."""
        if not self.update_callback:
            raise ValueError("CustomAnimationConfig requires an update_callback")


@dataclass
class AnimationGroupConfig:
    """Configuration for animation group."""
    animations: list = None                    # List of animation IDs to group
    parallel: bool = True                      # Run in parallel (True) or sequence (False)
    on_complete: Optional[Callable[[], None]] = None  # Called when all animations complete
    on_cancel: Optional[Callable[[], None]] = None    # Called if group is cancelled
    auto_destroy: bool = True                  # Auto-destroy when complete
    
    def __post_init__(self):
        """Validate animation group config."""
        if not self.animations:
            raise ValueError("AnimationGroupConfig requires at least one animation")


# Type aliases for callbacks
AnimationStartCallback = Callable[[], None]
AnimationUpdateCallback = Callable[[float], None]  # progress: 0.0-1.0
AnimationCompleteCallback = Callable[[], None]
AnimationCancelCallback = Callable[[], None]
