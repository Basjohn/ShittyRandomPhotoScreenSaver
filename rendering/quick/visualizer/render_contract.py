"""Small immutable render contract for lazy Qt Quick visualizer modes."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Protocol

from core.performance.frame_trace import FrameTraceEvent, FrameTraceSink
from widgets.spotify_visualizer import mode_capabilities
from widgets.spotify_visualizer.render_state import VisualizerRenderSnapshot


QUICK_VISUALIZER_VERTEX_SOURCE = """#version 330 core
layout(location = 0) in vec2 aPosition;

uniform mat4 uMatrix;
uniform vec2 uItemSize;
uniform int uContentRotationQuarters;

out vec2 v_uv;

vec2 logicalUvFromPhysicalUv(vec2 physicalUv) {
    int q = uContentRotationQuarters & 3;
    if (q == 1)
        return vec2(physicalUv.y, 1.0 - physicalUv.x);
    if (q == 2)
        return vec2(1.0 - physicalUv.x, 1.0 - physicalUv.y);
    if (q == 3)
        return vec2(1.0 - physicalUv.y, physicalUv.x);
    return physicalUv;
}

void main() {
    v_uv = logicalUvFromPhysicalUv(aPosition);
    gl_Position = uMatrix * vec4(aPosition * uItemSize, 0.0, 1.0);
}
"""


def snapshot_has_current_reactive_source(
    snapshot: VisualizerRenderSnapshot,
) -> bool:
    logical = snapshot.logical
    return bool(
        logical.source_generation >= 0
        and logical.source_activation_id >= 0
        and logical.source_generation == logical.engine_generation
        and logical.source_activation_id == logical.activation_id
    )


def snapshot_is_render_admissible(snapshot: VisualizerRenderSnapshot) -> bool:
    """Apply generic presentation/source admission without mode dispatch."""

    logical = snapshot.logical
    if not logical.present_frame:
        return False
    if (
        logical.playing
        and mode_capabilities.requires_authoritative_first_source(
            logical.mode_id
        )
    ):
        return snapshot_has_current_reactive_source(snapshot)
    return True


class VisualizerModeTraceContext:
    """Deferred per-mode timestamps for one explicit frame-trace draw.

    Mode renderers sample boundaries with ``perf_counter_ns`` but never write
    the binary sink inline.  The owning render node flushes these samples only
    after the parent ``RENDER_DRAW`` marker, so adding deeper attribution does
    not contaminate the render interval being measured.  Ordinary runtime never
    constructs this object because there is no trace sink without explicit
    ``--frame-trace``.
    """

    __slots__ = (
        "sink",
        "screen_index",
        "revision",
        "logical_timestamp_ns",
        "auxiliary",
        "_samples",
    )

    def __init__(
        self,
        sink: FrameTraceSink,
        *,
        screen_index: int,
        revision: int,
        logical_timestamp_ns: int,
        auxiliary: int,
    ) -> None:
        self.sink = sink
        self.screen_index = int(screen_index)
        self.revision = int(revision)
        self.logical_timestamp_ns = int(logical_timestamp_ns)
        self.auxiliary = int(auxiliary)
        self._samples: list[tuple[FrameTraceEvent, int]] = []

    def mark(self, event: FrameTraceEvent) -> None:
        self._samples.append((event, time.perf_counter_ns()))

    def flush(self) -> None:
        samples = self._samples
        self._samples = []
        for event, timestamp_ns in samples:
            self.sink.record(
                event,
                screen_index=self.screen_index,
                revision=self.revision,
                logical_timestamp_ns=self.logical_timestamp_ns,
                auxiliary=self.auxiliary,
                timestamp_ns=timestamp_ns,
            )


@dataclass(frozen=True, slots=True)
class QuickVisualizerRenderFrame:
    snapshot: VisualizerRenderSnapshot
    viewport: tuple[int, int, int, int]
    logical_size: tuple[float, float]
    matrix_values: tuple[float, ...]
    quad_vao: int
    trace_context: VisualizerModeTraceContext | None = None

    def __post_init__(self) -> None:
        if len(self.viewport) != 4 or min(self.viewport[2:]) <= 0:
            raise ValueError("visualizer render viewport must have positive dimensions")
        if len(self.matrix_values) != 16:
            raise ValueError("visualizer render matrix must contain 16 values")
        if min(self.logical_size) <= 0.0:
            raise ValueError("visualizer render item must have positive dimensions")
        if self.quad_vao <= 0:
            raise ValueError("visualizer render frame requires a live quad")

    @property
    def content_rotation_quarters(self) -> int:
        return int(self.snapshot.presentation.content_rotation_quarters)

    @property
    def oriented_logical_size(self) -> tuple[float, float]:
        if self.content_rotation_quarters & 1:
            return (self.logical_size[1], self.logical_size[0])
        return self.logical_size

    @property
    def logical_content_rect(self) -> tuple[float, float, float, float]:
        presentation = self.snapshot.presentation
        outer_x, outer_y, _outer_width, _outer_height = presentation.outer_rect
        content_x, content_y, content_width, content_height = presentation.content_rect
        physical_rect = (
            content_x - outer_x,
            content_y - outer_y,
            content_width,
            content_height,
        )
        if self.content_rotation_quarters == 0:
            return physical_rect
        from widgets.spotify_visualizer.presentation_orientation import (
            logical_rect_from_physical_rect,
        )

        return logical_rect_from_physical_rect(
            physical_rect,
            physical_size=self.logical_size,
            content_rotation_quarters=self.content_rotation_quarters,
        )


class QuickVisualizerRenderer(Protocol):
    mode_id: str

    @property
    def has_resources(self) -> bool: ...

    def render(self, frame: QuickVisualizerRenderFrame) -> None: ...

    def release_resources(self) -> None: ...


__all__ = [
    "QUICK_VISUALIZER_VERTEX_SOURCE",
    "QuickVisualizerRenderFrame",
    "QuickVisualizerRenderer",
    "VisualizerModeTraceContext",
    "snapshot_has_current_reactive_source",
    "snapshot_is_render_admissible",
]
