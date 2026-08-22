"""Small immutable render contract for lazy Qt Quick visualizer modes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from widgets.spotify_visualizer import mode_capabilities
from widgets.spotify_visualizer.render_state import VisualizerRenderSnapshot


QUICK_VISUALIZER_VERTEX_SOURCE = """#version 330 core
layout(location = 0) in vec2 aPosition;

uniform mat4 uMatrix;
uniform vec2 uItemSize;

out vec2 v_uv;

void main() {
    v_uv = aPosition;
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


@dataclass(frozen=True, slots=True)
class QuickVisualizerRenderFrame:
    snapshot: VisualizerRenderSnapshot
    viewport: tuple[int, int, int, int]
    logical_size: tuple[float, float]
    matrix_values: tuple[float, ...]
    quad_vao: int

    def __post_init__(self) -> None:
        if len(self.viewport) != 4 or min(self.viewport[2:]) <= 0:
            raise ValueError("visualizer render viewport must have positive dimensions")
        if len(self.matrix_values) != 16:
            raise ValueError("visualizer render matrix must contain 16 values")
        if min(self.logical_size) <= 0.0:
            raise ValueError("visualizer render item must have positive dimensions")
        if self.quad_vao <= 0:
            raise ValueError("visualizer render frame requires a live quad")


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
    "snapshot_has_current_reactive_source",
    "snapshot_is_render_admissible",
]
