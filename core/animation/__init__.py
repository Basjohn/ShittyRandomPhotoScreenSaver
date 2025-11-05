"""Centralized animation framework."""

from .types import (
    AnimationState,
    AnimationType,
    EasingCurve,
    AnimationConfig,
    PropertyAnimationConfig,
    CustomAnimationConfig,
    AnimationGroupConfig
)
from .easing import ease, get_easing_function, EASING_FUNCTIONS
from .animator import Animation, PropertyAnimator, CustomAnimator, AnimationManager

__all__ = [
    # Types
    'AnimationState',
    'AnimationType',
    'EasingCurve',
    'AnimationConfig',
    'PropertyAnimationConfig',
    'CustomAnimationConfig',
    'AnimationGroupConfig',
    
    # Easing
    'ease',
    'get_easing_function',
    'EASING_FUNCTIONS',
    
    # Animators
    'Animation',
    'PropertyAnimator',
    'CustomAnimator',
    'AnimationManager',
]
