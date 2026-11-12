"""Lazy Quick renderer for Liquid Lens: a lens of water hops between pitstops, growing at each,
then floods the picture with the next one."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.liquid_lens_options import LIQUID_LENS_STOPS_RANGE
from rendering.gl_programs.liquid_lens_program import (
    LIQUID_LENS_BLOCK,
    LIQUID_LENS_FRAGMENT_SOURCE,
    LIQUID_LENS_VERTEX_SOURCE,
    lens_height,
    lens_plan,
    lens_state,
)
from rendering.gl_programs.portable import pack_block
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs, warm_pass_blocks
from ..render_contract import QuickTransitionRenderFrame


def liquid_lens_parameters(parameters: Mapping[str, object]) -> tuple[float, float, int, int]:
    """The resolved refraction, dispersion, stops and seed, validated before any GL state changes."""
    values = []
    for name in ("refraction", "dispersion"):
        value = parameters.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Liquid Lens needs a resolved {name} between 0 and 1")
        values.append(float(value))
    stops, seed = parameters.get("stops"), parameters.get("seed")
    if isinstance(stops, bool) or not isinstance(stops, int) or not LIQUID_LENS_STOPS_RANGE[0] <= stops <= LIQUID_LENS_STOPS_RANGE[1]:
        raise ValueError("Liquid Lens needs a resolved number of stops")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Liquid Lens needs a resolved seed")
    return values[0], values[1], stops, seed


class QuickLiquidLensRenderer:
    transition_id = "liquid_lens"

    _SAMPLERS = ("uOldTex", "uNewTex")      # every other value is in LIQUID_LENS_BLOCK

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Liquid Lens")
        self._plan_key = None
        self._plan = None

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        refraction, dispersion, stops, seed = liquid_lens_parameters(frame.run.request.parameter_dict())
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            # The water has flattened out over a lens covering everything: the new picture.
            if progress >= 1.0 or (progress > 0.9 and lens_height(progress) <= 0.0):
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            self._draw(frame, progress, refraction, dispersion, stops, seed)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing. Liquid Lens
        allocates nothing per run (its plan is a few numbers)."""
        liquid_lens_parameters(parameters)
        r = self._resources
        return warm_programs([(r, *UNDERLAY_PROGRAM),
                              (r, "liquid_lens", LIQUID_LENS_VERTEX_SOURCE, LIQUID_LENS_FRAGMENT_SOURCE)]
                             ) and warm_pass_blocks(r, size)

    def park(self) -> None:
        """Forget the run's plan; the programs stay warm."""
        self._plan_key = self._plan = None

    def _draw(self, frame, progress: float, refraction: float, dispersion: float, stops: int, seed: int) -> None:
        r = self._resources
        program = r.program("liquid_lens", LIQUID_LENS_VERTEX_SOURCE, LIQUID_LENS_FRAGMENT_SOURCE)
        uniforms = r.uniforms("liquid_lens", self._SAMPLERS)
        values = r.values("liquid_lens")
        width, height = frame.logical_size
        aspect = width / max(1e-6, height)
        key = (frame.run.run_id, stops, seed, round(aspect, 6))
        if key != self._plan_key:
            self._plan_key, self._plan = key, lens_plan(stops, seed, aspect)
        duration = frame.run.request.duration_ms / 1000.0
        state = lens_state(self._plan, progress, duration)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame, values)
        values["uTime"] = progress * duration
        values["uSeed"] = float(seed % 9973)
        values["uCentre"] = state.centre
        values["uRadius"] = state.radius
        values["uThick"] = state.thickness
        values["uReference"] = state.reference
        values["uEnvelope"] = state.envelope
        values["uRound"] = state.rounding
        values["uBulge"] = state.bulge
        values["uTwist"] = state.twist
        values["uRipple"] = state.ripple
        values["uRefraction"] = refraction
        values["uDispersion"] = dispersion
        with r.pass_blocks.bound(pack_block(LIQUID_LENS_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        self._plan_key = self._plan = None
        self._resources.release_resources()


def create_transition_renderer() -> QuickLiquidLensRenderer:
    return QuickLiquidLensRenderer()
