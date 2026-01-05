"""Performance optimization module."""
from core.performance.frame_budget import (
    FrameBudget,
    FrameBudgetConfig,
    GCController,
    get_frame_budget,
    get_gc_controller,
)

__all__ = [
    "FrameBudget",
    "FrameBudgetConfig",
    "GCController",
    "get_frame_budget",
    "get_gc_controller",
]
