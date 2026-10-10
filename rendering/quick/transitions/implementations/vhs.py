"""Lazy Quick renderer for VHS Distortion: tracking is lost and the picture rolls to the next one."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.vhs_program import VHS_FRAGMENT_SOURCE, VHS_PERIOD, vhs_envelope, vhs_roll
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from ..render_contract import QuickTransitionRenderFrame

_ROLL_SIGN = {"up": 1.0, "down": -1.0}


def vhs_parameters(parameters: Mapping[str, object]) -> tuple[float, float, float, int]:
    """The resolved tracking, colour bleed, noise and seed, validated before any GL state changes."""
    values = []
    for name in ("tracking", "bleed", "noise"):
        value = parameters.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"VHS Distortion needs a resolved {name} between 0 and 1")
        values.append(float(value))
    seed = parameters.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("VHS Distortion needs a resolved seed")
    return values[0], values[1], values[2], seed


class QuickVhsRenderer:
    transition_id = "vhs"

    _UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uNewTex", "uEnvelope", "uRoll", "uRollSign", "uTime",
                 "uSeed", "uTracking", "uBleed", "uNoise")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick VHS Distortion")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        code = str(frame.run.request.direction)
        if code not in _ROLL_SIGN:
            raise ValueError(f"unknown resolved VHS Distortion direction: {code!r}")
        tracking, bleed, noise, seed = vhs_parameters(frame.run.request.parameter_dict())
        envelope, roll = vhs_envelope(progress), vhs_roll(progress)
        try:
            # Clean signal before the roll and after hold and tracking have settled: the photographs.
            if envelope <= 0.0 and roll <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if envelope <= 0.0 and roll >= VHS_PERIOD:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            self._draw(frame, progress, envelope, roll, _ROLL_SIGN[code], tracking, bleed, noise, seed)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing. VHS Distortion
        allocates nothing per run."""
        vhs_parameters(parameters)
        r = self._resources
        return warm_programs([(r, *UNDERLAY_PROGRAM), (r, "vhs", ITEM_QUAD_VERTEX_SOURCE, VHS_FRAGMENT_SOURCE)])

    def park(self) -> None:
        """Nothing per run to drop; the programs stay warm."""

    def _draw(self, frame, progress: float, envelope: float, roll: float, sign: float, tracking: float,
              bleed: float, noise: float, seed: int) -> None:
        r = self._resources
        program = r.program("vhs", ITEM_QUAD_VERTEX_SOURCE, VHS_FRAGMENT_SOURCE)
        uniforms = r.uniforms("vhs", self._UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glUniform1f(uniforms["uEnvelope"], envelope)
        gl.glUniform1f(uniforms["uRoll"], roll)
        gl.glUniform1f(uniforms["uRollSign"], sign)
        gl.glUniform1f(uniforms["uTime"], progress * frame.run.request.duration_ms / 1000.0)
        gl.glUniform1f(uniforms["uSeed"], float(seed))
        gl.glUniform1f(uniforms["uTracking"], tracking)
        gl.glUniform1f(uniforms["uBleed"], bleed)
        gl.glUniform1f(uniforms["uNoise"], noise)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickVhsRenderer:
    return QuickVhsRenderer()
