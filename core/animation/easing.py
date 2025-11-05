"""
Easing functions for animations.

Provides mathematical easing functions for smooth transitions.
All functions take t (time) in range [0.0, 1.0] and return a value in range [0.0, 1.0].

Based on standard easing equations:
- Robert Penner's Easing Functions
- https://easings.net/
"""
import math
from typing import Callable
from core.animation.types import EasingCurve


# Linear (no easing)
def linear(t: float) -> float:
    """Linear interpolation - no easing."""
    return t


# Quadratic easing
def quad_in(t: float) -> float:
    """Quadratic ease-in - accelerating from zero velocity."""
    return t * t


def quad_out(t: float) -> float:
    """Quadratic ease-out - decelerating to zero velocity."""
    return t * (2 - t)


def quad_in_out(t: float) -> float:
    """Quadratic ease-in-out - accelerating until halfway, then decelerating."""
    if t < 0.5:
        return 2 * t * t
    return -1 + (4 - 2 * t) * t


# Cubic easing
def cubic_in(t: float) -> float:
    """Cubic ease-in - accelerating from zero velocity."""
    return t * t * t


def cubic_out(t: float) -> float:
    """Cubic ease-out - decelerating to zero velocity."""
    t -= 1
    return t * t * t + 1


def cubic_in_out(t: float) -> float:
    """Cubic ease-in-out - accelerating until halfway, then decelerating."""
    if t < 0.5:
        return 4 * t * t * t
    t -= 1
    return 1 + 4 * t * t * t


# Quartic easing
def quart_in(t: float) -> float:
    """Quartic ease-in - accelerating from zero velocity."""
    return t * t * t * t


def quart_out(t: float) -> float:
    """Quartic ease-out - decelerating to zero velocity."""
    t -= 1
    return 1 - t * t * t * t


def quart_in_out(t: float) -> float:
    """Quartic ease-in-out - accelerating until halfway, then decelerating."""
    if t < 0.5:
        return 8 * t * t * t * t
    t -= 1
    return 1 - 8 * t * t * t * t


# Quintic easing
def quint_in(t: float) -> float:
    """Quintic ease-in - accelerating from zero velocity."""
    return t * t * t * t * t


def quint_out(t: float) -> float:
    """Quintic ease-out - decelerating to zero velocity."""
    t -= 1
    return 1 + t * t * t * t * t


def quint_in_out(t: float) -> float:
    """Quintic ease-in-out - accelerating until halfway, then decelerating."""
    if t < 0.5:
        return 16 * t * t * t * t * t
    t -= 1
    return 1 + 16 * t * t * t * t * t


# Sine easing
def sine_in(t: float) -> float:
    """Sine ease-in - accelerating using sine curve."""
    return 1 - math.cos(t * math.pi / 2)


def sine_out(t: float) -> float:
    """Sine ease-out - decelerating using sine curve."""
    return math.sin(t * math.pi / 2)


def sine_in_out(t: float) -> float:
    """Sine ease-in-out - accelerating until halfway, then decelerating."""
    return -(math.cos(math.pi * t) - 1) / 2


# Exponential easing
def expo_in(t: float) -> float:
    """Exponential ease-in - accelerating exponentially."""
    if t == 0:
        return 0
    return math.pow(2, 10 * (t - 1))


def expo_out(t: float) -> float:
    """Exponential ease-out - decelerating exponentially."""
    if t == 1:
        return 1
    return 1 - math.pow(2, -10 * t)


def expo_in_out(t: float) -> float:
    """Exponential ease-in-out - accelerating until halfway, then decelerating."""
    if t == 0 or t == 1:
        return t
    
    if t < 0.5:
        return math.pow(2, 20 * t - 10) / 2
    return (2 - math.pow(2, -20 * t + 10)) / 2


# Circular easing
def circ_in(t: float) -> float:
    """Circular ease-in - accelerating using circular curve."""
    return 1 - math.sqrt(1 - t * t)


def circ_out(t: float) -> float:
    """Circular ease-out - decelerating using circular curve."""
    t -= 1
    return math.sqrt(1 - t * t)


def circ_in_out(t: float) -> float:
    """Circular ease-in-out - accelerating until halfway, then decelerating."""
    if t < 0.5:
        return (1 - math.sqrt(1 - 4 * t * t)) / 2
    t = t * 2 - 2
    return (math.sqrt(1 - t * t) + 1) / 2


# Elastic easing
def elastic_in(t: float) -> float:
    """Elastic ease-in - elastic motion, like a spring."""
    if t == 0 or t == 1:
        return t
    
    return -math.pow(2, 10 * (t - 1)) * math.sin((t - 1.1) * 5 * math.pi)


def elastic_out(t: float) -> float:
    """Elastic ease-out - elastic motion, like a spring."""
    if t == 0 or t == 1:
        return t
    
    return math.pow(2, -10 * t) * math.sin((t - 0.1) * 5 * math.pi) + 1


def elastic_in_out(t: float) -> float:
    """Elastic ease-in-out - elastic motion."""
    if t == 0 or t == 1:
        return t
    
    t = t * 2 - 1
    
    if t < 0:
        return -0.5 * math.pow(2, 10 * t) * math.sin((t - 0.1) * 5 * math.pi)
    return 0.5 * math.pow(2, -10 * t) * math.sin((t - 0.1) * 5 * math.pi) + 1


# Back easing
def back_in(t: float) -> float:
    """Back ease-in - backing up slightly before accelerating."""
    c = 1.70158
    return t * t * ((c + 1) * t - c)


def back_out(t: float) -> float:
    """Back ease-out - overshooting slightly before settling."""
    c = 1.70158
    t -= 1
    return t * t * ((c + 1) * t + c) + 1


def back_in_out(t: float) -> float:
    """Back ease-in-out - backing up, then overshooting."""
    c = 1.70158 * 1.525
    
    if t < 0.5:
        return (2 * t) * (2 * t) * ((c + 1) * 2 * t - c) / 2
    
    t = t * 2 - 2
    return (t * t * ((c + 1) * t + c) + 2) / 2


# Bounce easing
def bounce_out(t: float) -> float:
    """Bounce ease-out - bouncing motion."""
    n1 = 7.5625
    d1 = 2.75
    
    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


def bounce_in(t: float) -> float:
    """Bounce ease-in - bouncing motion."""
    return 1 - bounce_out(1 - t)


def bounce_in_out(t: float) -> float:
    """Bounce ease-in-out - bouncing motion."""
    if t < 0.5:
        return (1 - bounce_out(1 - 2 * t)) / 2
    return (1 + bounce_out(2 * t - 1)) / 2


# Easing function lookup table
EASING_FUNCTIONS: dict[EasingCurve, Callable[[float], float]] = {
    EasingCurve.LINEAR: linear,
    
    EasingCurve.QUAD_IN: quad_in,
    EasingCurve.QUAD_OUT: quad_out,
    EasingCurve.QUAD_IN_OUT: quad_in_out,
    
    EasingCurve.CUBIC_IN: cubic_in,
    EasingCurve.CUBIC_OUT: cubic_out,
    EasingCurve.CUBIC_IN_OUT: cubic_in_out,
    
    EasingCurve.QUART_IN: quart_in,
    EasingCurve.QUART_OUT: quart_out,
    EasingCurve.QUART_IN_OUT: quart_in_out,
    
    EasingCurve.QUINT_IN: quint_in,
    EasingCurve.QUINT_OUT: quint_out,
    EasingCurve.QUINT_IN_OUT: quint_in_out,
    
    EasingCurve.SINE_IN: sine_in,
    EasingCurve.SINE_OUT: sine_out,
    EasingCurve.SINE_IN_OUT: sine_in_out,
    
    EasingCurve.EXPO_IN: expo_in,
    EasingCurve.EXPO_OUT: expo_out,
    EasingCurve.EXPO_IN_OUT: expo_in_out,
    
    EasingCurve.CIRC_IN: circ_in,
    EasingCurve.CIRC_OUT: circ_out,
    EasingCurve.CIRC_IN_OUT: circ_in_out,
    
    EasingCurve.ELASTIC_IN: elastic_in,
    EasingCurve.ELASTIC_OUT: elastic_out,
    EasingCurve.ELASTIC_IN_OUT: elastic_in_out,
    
    EasingCurve.BACK_IN: back_in,
    EasingCurve.BACK_OUT: back_out,
    EasingCurve.BACK_IN_OUT: back_in_out,
    
    EasingCurve.BOUNCE_IN: bounce_in,
    EasingCurve.BOUNCE_OUT: bounce_out,
    EasingCurve.BOUNCE_IN_OUT: bounce_in_out,
}


def get_easing_function(curve: EasingCurve) -> Callable[[float], float]:
    """
    Get the easing function for a given curve.
    
    Args:
        curve: Easing curve enum
    
    Returns:
        Easing function that takes t in [0, 1] and returns value in [0, 1]
    
    Raises:
        ValueError: If curve is not found
    """
    if curve not in EASING_FUNCTIONS:
        raise ValueError(f"Unknown easing curve: {curve}")
    
    return EASING_FUNCTIONS[curve]


def ease(t: float, curve: EasingCurve) -> float:
    """
    Apply easing function to a time value.
    
    Args:
        t: Time value in range [0.0, 1.0]
        curve: Easing curve to apply
    
    Returns:
        Eased value in range [0.0, 1.0]
    """
    # Clamp t to [0, 1]
    t = max(0.0, min(1.0, t))
    
    easing_fn = get_easing_function(curve)
    return easing_fn(t)
