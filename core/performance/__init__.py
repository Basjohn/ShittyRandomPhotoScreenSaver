"""Performance optimization module."""
from core.performance.gc_policy import (
    GCPolicySnapshot,
    RuntimeGCPolicy,
    derive_runtime_thresholds,
)
from core.performance.frame_budget import (
    FrameBudget,
    FrameBudgetConfig,
    get_frame_budget,
)
from core.performance.widget_profiler import (
    flush_widget_perf_metrics,
    record_widget_paint_result,
    record_widget_timer_result,
    widget_paint_sample,
    widget_timer_sample,
)

__all__ = [
    "GCPolicySnapshot",
    "RuntimeGCPolicy",
    "derive_runtime_thresholds",
    "FrameBudget",
    "FrameBudgetConfig",
    "get_frame_budget",
    "widget_timer_sample",
    "widget_paint_sample",
    "record_widget_timer_result",
    "record_widget_paint_result",
    "flush_widget_perf_metrics",
]
