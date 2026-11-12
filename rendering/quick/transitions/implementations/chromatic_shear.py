"""Lazy Quick renderer for Chromatic Shear: slices shear apart into spectral layers and back."""

from __future__ import annotations

import math
from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.chromatic_shear_program import (
    CHROMATIC_SHEAR_BLOCK,
    CHROMATIC_SHEAR_FRAGMENT_SOURCE,
    CHROMATIC_SHEAR_VERTEX_SOURCE,
    SHEAR_AXES,
    SHEAR_SLICES_RANGE,
)
from rendering.gl_programs.portable import pack_block
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs, warm_pass_blocks
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

    _SAMPLERS = ("uOldTex", "uNewTex")      # every other value is in CHROMATIC_SHEAR_BLOCK

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
                              (r, "chromatic_shear", CHROMATIC_SHEAR_VERTEX_SOURCE, CHROMATIC_SHEAR_FRAGMENT_SOURCE)]
                             ) and warm_pass_blocks(r, size)

    def park(self) -> None:
        """Nothing per run to drop; the programs stay warm."""

    def _draw(self, frame, progress: float, axis, spread: float, slices: int, seed: int) -> None:
        r = self._resources
        program = r.program("chromatic_shear", CHROMATIC_SHEAR_VERTEX_SOURCE, CHROMATIC_SHEAR_FRAGMENT_SOURCE)
        uniforms = r.uniforms("chromatic_shear", self._SAMPLERS)
        values = r.values("chromatic_shear")
        length = math.hypot(*axis)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame, values)
        values["uProgress"] = progress
        values["uAxis"] = (axis[0] / length, axis[1] / length)
        values["uSpread"] = spread
        values["uSlices"] = float(slices)
        values["uSeed"] = float(seed % 997)
        with r.pass_blocks.bound(pack_block(CHROMATIC_SHEAR_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickChromaticShearRenderer:
    return QuickChromaticShearRenderer()
