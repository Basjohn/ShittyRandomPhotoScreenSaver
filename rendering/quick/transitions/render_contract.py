"""Small common render contract for statically registered Quick transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE

from .state import TransitionRun, TransitionSample


# The shared item quad (rendering.quick.scene3d.frame owns the source).
QUICK_TRANSITION_VERTEX_SOURCE = ITEM_QUAD_VERTEX_SOURCE


@dataclass(frozen=True, slots=True)
class QuickTransitionRenderFrame:
    run: TransitionRun
    sample: TransitionSample
    viewport: tuple[int, int, int, int]
    logical_size: tuple[float, float]
    matrix_values: tuple[float, ...]
    quad_vao: int
    source_texture_id: int
    destination_texture_id: int

    def __post_init__(self) -> None:
        if self.sample.run_id != self.run.run_id:
            raise ValueError("transition sample run does not match render frame")
        if (
            self.sample.runtime_generation
            != self.run.request.runtime_generation
        ):
            raise ValueError("transition sample generation does not match render frame")
        if len(self.viewport) != 4 or min(self.viewport[2:]) <= 0:
            raise ValueError("transition render viewport must have positive dimensions")
        if len(self.matrix_values) != 16:
            raise ValueError("transition render matrix must contain 16 values")
        if min(self.logical_size) <= 0.0:
            raise ValueError("transition render item must have positive dimensions")
        if min(
            self.quad_vao,
            self.source_texture_id,
            self.destination_texture_id,
        ) <= 0:
            raise ValueError("transition render frame requires live GL resources")


class QuickTransitionRenderer(Protocol):
    transition_id: str

    @property
    def has_resources(self) -> bool: ...

    def render(self, frame: QuickTransitionRenderFrame) -> None: ...

    def release_resources(self) -> None: ...
