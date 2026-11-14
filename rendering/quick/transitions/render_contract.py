"""Small common render contract for statically registered Quick transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .state import TransitionRun, TransitionSample

# The shared item quad is ``rendering.gl_programs.item_quad``: each program declares its values (the quad's among
# them) in its own pass block (N1.6), so there is no one shared vertex text.


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
    #: The window's device pixel ratio (the item's logical size times it is the item's own pixels).
    device_pixel_ratio: float = 1.0

    @property
    def item_pixels(self) -> tuple[float, float]:
        """The item's own device pixels (``u_target_px``, N5.2a): the grid a transition takes its pixel's uv from. The
        render target can be larger (the window under the overscan placement); the native core draws into the item's
        own target, of exactly these pixels."""
        ratio = float(self.device_pixel_ratio)
        return (float(max(1, round(self.logical_size[0] * ratio))), float(max(1, round(self.logical_size[1] * ratio))))

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
