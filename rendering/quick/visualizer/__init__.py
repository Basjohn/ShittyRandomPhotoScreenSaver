"""Inline visualizer content for the sole per-display Quick scene."""

from .clip_host import VisualizerClipFrame, VisualizerClipHost, VisualizerClipRun
from .implementation_registry import (
    QuickVisualizerImplementationDescriptor,
    iter_quick_visualizer_implementations,
    resolve_quick_visualizer_renderer,
)
from .item import VisualizerRenderItem
from .node import VisualizerRenderNode
from .render_contract import (
    QuickVisualizerRenderFrame,
    QuickVisualizerRenderer,
    snapshot_has_current_reactive_source,
    snapshot_is_render_admissible,
)
from .render_host import QuickVisualizerRenderHost
from .telemetry import (
    VisualizerRenderNodeSnapshot,
    VisualizerRenderNodeTelemetry,
)

__all__ = [
    "VisualizerClipFrame",
    "VisualizerClipHost",
    "VisualizerClipRun",
    "QuickVisualizerImplementationDescriptor",
    "QuickVisualizerRenderFrame",
    "QuickVisualizerRenderer",
    "QuickVisualizerRenderHost",
    "VisualizerRenderItem",
    "VisualizerRenderNode",
    "VisualizerRenderNodeSnapshot",
    "VisualizerRenderNodeTelemetry",
    "iter_quick_visualizer_implementations",
    "resolve_quick_visualizer_renderer",
    "snapshot_has_current_reactive_source",
    "snapshot_is_render_admissible",
]
