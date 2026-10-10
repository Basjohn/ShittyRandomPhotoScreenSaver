"""Lazy Quick renderer for Liquid Lens: a growing lens of water shows the next picture through it."""

from __future__ import annotations

import math
from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.liquid_lens_program import (
    LENS_BULGE,
    LIQUID_LENS_FRAGMENT_SOURCE,
    lens_cover,
    lens_height,
    lens_path,
)
from rendering.gl_programs.liquid_lens_options import LIQUID_LENS_ORIGINS
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from ..render_contract import QuickTransitionRenderFrame


def liquid_lens_parameters(parameters: Mapping[str, object]) -> tuple[float, float, bool, int]:
    """The resolved refraction, dispersion, droplets and seed, validated before any GL state changes."""
    values = []
    for name in ("refraction", "dispersion"):
        value = parameters.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Liquid Lens needs a resolved {name} between 0 and 1")
        values.append(float(value))
    droplets, seed = parameters.get("droplets"), parameters.get("seed")
    if not isinstance(droplets, bool):
        raise ValueError("Liquid Lens needs a resolved droplets choice")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Liquid Lens needs a resolved seed")
    return values[0], values[1], droplets, seed


class QuickLiquidLensRenderer:
    transition_id = "liquid_lens"

    _UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uNewTex", "uProgress", "uTime", "uDuration", "uSeed",
                 "uStart", "uEnd", "uTravel", "uBulge", "uCover", "uRefraction", "uDispersion", "uDroplets")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Liquid Lens")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        origin = str(frame.run.request.direction)
        if origin not in LIQUID_LENS_ORIGINS.values():
            raise ValueError(f"unknown resolved Liquid Lens origin: {origin!r}")
        refraction, dispersion, droplets, seed = liquid_lens_parameters(frame.run.request.parameter_dict())
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            # The water has flattened out over a lens covering everything: the new picture.
            if progress >= 1.0 or (progress > 0.9 and lens_height(progress) <= 0.0):
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            self._draw(frame, progress, origin, refraction, dispersion, droplets, seed)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing. Liquid Lens
        allocates nothing per run."""
        liquid_lens_parameters(parameters)
        r = self._resources
        return warm_programs([(r, *UNDERLAY_PROGRAM),
                              (r, "liquid_lens", ITEM_QUAD_VERTEX_SOURCE, LIQUID_LENS_FRAGMENT_SOURCE)])

    def park(self) -> None:
        """Nothing per run to drop; the programs stay warm."""

    def _draw(self, frame, progress: float, origin: str, refraction: float, dispersion: float,
              droplets: bool, seed: int) -> None:
        r = self._resources
        program = r.program("liquid_lens", ITEM_QUAD_VERTEX_SOURCE, LIQUID_LENS_FRAGMENT_SOURCE)
        uniforms = r.uniforms("liquid_lens", self._UNIFORMS)
        width, height = frame.logical_size
        aspect = width / max(1e-6, height)
        start, end = lens_path(origin, aspect)
        travel = math.atan2(end[1] - start[1], end[0] - start[0]) if origin != "center" else (seed % 628) / 100.0
        duration = frame.run.request.duration_ms / 1000.0
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uTime"], progress * duration)
        gl.glUniform1f(uniforms["uDuration"], duration)
        gl.glUniform1f(uniforms["uSeed"], float(seed % 9973))
        gl.glUniform2f(uniforms["uStart"], *start)
        gl.glUniform2f(uniforms["uEnd"], *end)
        gl.glUniform1f(uniforms["uTravel"], travel)
        gl.glUniform1f(uniforms["uBulge"], 0.0 if origin == "center" else LENS_BULGE)
        gl.glUniform1f(uniforms["uCover"], lens_cover(end, aspect))
        gl.glUniform1f(uniforms["uRefraction"], refraction)
        gl.glUniform1f(uniforms["uDispersion"], dispersion)
        gl.glUniform1i(uniforms["uDroplets"], 1 if droplets else 0)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickLiquidLensRenderer:
    return QuickLiquidLensRenderer()
