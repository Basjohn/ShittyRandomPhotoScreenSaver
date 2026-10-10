"""Lazy Quick renderer for Chromatic Shear: slices shear apart into spectral layers and back."""

from __future__ import annotations

import math
from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.chromatic_shear_program import (
    CHROMATIC_SHEAR_FRAGMENT_SOURCE,
    SHEAR_AXES,
    SHEAR_SLICES_RANGE,
)
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from ..render_contract import QuickTransitionRenderFrame


def chromatic_shear_parameters(parameters: Mapping[str, object]) -> tuple[float, int, int]:
    """The resolved spread, slice count and seed, validated before any GL state changes."""
    spread, slices, seed = parameters.get("spread"), parameters.get("slices"), parameters.get("seed")
    if isinstance(spread, bool) or not isinstance(spread, (int, float)) or not 0.0 <= float(spread) <= 1.0:
        raise ValueError("Chromatic Shear needs a resolved spread between 0 and 1")
    low, high = SHEAR_SLICES_RANGE
    if isinstance(slices, bool) or not isinstance(slices, int) or not low <= slices <= high:
        raise ValueError(f"Chromatic Shear needs a resolved slice count between {low} and {high}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Chromatic Shear needs a resolved seed")
    return float(spread), slices, seed


class QuickChromaticShearRenderer:
    transition_id = "chromatic_shear"

    _UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uNewTex", "uProgress", "uAxis", "uSpread", "uSlices", "uSeed")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Chromatic Shear")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        axis = SHEAR_AXES.get(str(frame.run.request.direction))
        if axis is None:
            raise ValueError(f"unknown resolved Chromatic Shear axis: {frame.run.request.direction!r}")
        spread, slices, seed = chromatic_shear_parameters(frame.run.request.parameter_dict())
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            self._draw(frame, progress, axis, spread, slices, seed)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing. Chromatic Shear
        allocates nothing per run."""
        chromatic_shear_parameters(parameters)
        r = self._resources
        return warm_programs([(r, *UNDERLAY_PROGRAM),
                              (r, "chromatic_shear", ITEM_QUAD_VERTEX_SOURCE, CHROMATIC_SHEAR_FRAGMENT_SOURCE)])

    def park(self) -> None:
        """Nothing per run to drop; the programs stay warm."""

    def _draw(self, frame, progress: float, axis, spread: float, slices: int, seed: int) -> None:
        r = self._resources
        program = r.program("chromatic_shear", ITEM_QUAD_VERTEX_SOURCE, CHROMATIC_SHEAR_FRAGMENT_SOURCE)
        uniforms = r.uniforms("chromatic_shear", self._UNIFORMS)
        length = math.hypot(*axis)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform2f(uniforms["uAxis"], axis[0] / length, axis[1] / length)
        gl.glUniform1f(uniforms["uSpread"], spread)
        gl.glUniform1f(uniforms["uSlices"], float(slices))
        gl.glUniform1f(uniforms["uSeed"], float(seed % 997))
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickChromaticShearRenderer:
    return QuickChromaticShearRenderer()
