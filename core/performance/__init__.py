"""Performance optimization module."""
from core.performance.frame_budget import (
    FrameBudget,
    FrameBudgetConfig,
    GCController,
    get_frame_budget,
    get_gc_controller,
)
from core.performance.widget_profiler import (
    flush_widget_perf_metrics,
    record_widget_paint_result,
    record_widget_timer_result,
    widget_paint_sample,
    widget_timer_sample,
)

__all__ = [
    "FrameBudget",
    "FrameBudgetConfig",
    "GCController",
    "get_frame_budget",
    "get_gc_controller",
    "widget_timer_sample",
    "widget_paint_sample",
    "record_widget_timer_result",
    "record_widget_paint_result",
    "flush_widget_perf_metrics",
]
