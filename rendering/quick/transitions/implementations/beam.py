"""Lazy Quick renderer for Beam: a beam of light crosses the picture, leaving the next one."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.beam_program import (
    BEAM_FRAGMENT_SOURCE,
    BEAM_SPARK_FRAGMENT_SOURCE,
    BEAM_SPARK_VERTEX_SOURCE,
    BEAM_SPARKS,
    beam_cure,
    beam_direction,
    beam_intensity,
    beam_line,
    beam_path,
    beam_reach,
    beam_span,
    beam_spark_life_limit,
    beam_sweep_end,
)
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from ..render_contract import QuickTransitionRenderFrame

_CODES = frozenset(("left", "right", "up", "down", "diag_tl_br", "diag_tr_bl", "diag_bl_tr", "diag_br_tl"))


def beam_parameters(parameters: Mapping[str, object]
                    ) -> tuple[tuple[float, float, float], float, float, float, bool, int]:
    """The resolved colour, glow, scorch, cure time, sparks and seed, validated before any GL
    state changes."""
    color, glow, scorch = parameters.get("color"), parameters.get("glow"), parameters.get("scorch")
    cure, sparks, seed = parameters.get("cure"), parameters.get("sparks"), parameters.get("seed")
    if (not isinstance(color, (tuple, list)) or len(color) < 3
            or not all(isinstance(c, (int, float)) and 0.0 <= float(c) <= 1.0 for c in color[:3])):
        raise ValueError("Beam needs a resolved colour with channels between 0 and 1")
    for name, value in (("glow", glow), ("scorch", scorch), ("cure", cure)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Beam needs a resolved {name} between 0 and 1")
    if not isinstance(sparks, bool):
        raise ValueError("Beam needs a resolved sparks switch")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Beam needs a resolved seed")
    return (float(color[0]), float(color[1]), float(color[2])), float(glow), float(scorch), float(cure), sparks, seed


class QuickBeamRenderer:
    transition_id = "beam"

    _COMMON = ("uMatrix", "uItemSize", "uDirection", "uProgress", "uLine", "uPath", "uReach", "uColor", "uGlow",
               "uIntensity", "uSeed", "uSweepEnd")
    _BEAM_UNIFORMS = _COMMON + ("uOldTex", "uNewTex", "uScorch", "uCure")
    _SPARK_UNIFORMS = _COMMON + ("uDurationS", "uMaxLife", "uSpan")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Beam")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        code = str(frame.run.request.direction)
        if code not in _CODES:
            raise ValueError(f"unknown resolved Beam direction: {code!r}")
        color, glow, scorch, cure_time, sparks, seed = beam_parameters(frame.run.request.parameter_dict())
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            self._draw(frame, progress, code, color, glow, scorch, beam_cure(cure_time), sparks, seed)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing. Beam allocates
        nothing per run."""
        _color, _glow, _scorch, _cure, sparks, _seed = beam_parameters(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, "beam", ITEM_QUAD_VERTEX_SOURCE, BEAM_FRAGMENT_SOURCE)]
        if sparks:
            entries.append((r, "sparks", BEAM_SPARK_VERTEX_SOURCE, BEAM_SPARK_FRAGMENT_SOURCE))
        return warm_programs(entries)

    def park(self) -> None:
        """Nothing per run to drop; the programs stay warm."""

    def _common(self, uniforms, frame, progress: float, sweep_end: float, direction, line: float, path,
                reach: float, color, glow: float, seed: int) -> None:
        gl.glUniform1f(uniforms["uSweepEnd"], sweep_end)
        gl.glUniform2f(uniforms["uDirection"], *direction)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uLine"], line)
        gl.glUniform2f(uniforms["uPath"], *path)
        gl.glUniform1f(uniforms["uReach"], reach)
        gl.glUniform3f(uniforms["uColor"], *color)
        gl.glUniform1f(uniforms["uGlow"], glow)
        gl.glUniform1f(uniforms["uIntensity"], beam_intensity(progress, sweep_end))
        gl.glUniform1f(uniforms["uSeed"], float(seed))

    def _draw(self, frame, progress: float, code: str, color, glow: float, scorch: float, cure: float,
              sparks: bool, seed: int) -> None:
        width, height = frame.logical_size
        aspect = width / height
        direction = beam_direction(code, aspect)
        span = beam_span(direction, aspect)
        reach = beam_reach(glow)
        path = beam_path(*span, reach)
        sweep_end = beam_sweep_end(cure)
        line = beam_line(progress, *path, sweep_end)
        r = self._resources

        program = r.program("beam", ITEM_QUAD_VERTEX_SOURCE, BEAM_FRAGMENT_SOURCE)
        uniforms = r.uniforms("beam", self._BEAM_UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        self._common(uniforms, frame, progress, sweep_end, direction, line, path, reach, color, glow, seed)
        gl.glUniform1f(uniforms["uScorch"], scorch)
        gl.glUniform1f(uniforms["uCure"], cure)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        if not sparks:
            return

        program = r.program("sparks", BEAM_SPARK_VERTEX_SOURCE, BEAM_SPARK_FRAGMENT_SOURCE)
        # The sparks share the beam's uniforms but read only some of them.
        uniforms = r.uniforms("sparks", self._SPARK_UNIFORMS, required=False)
        bind_frame(program, uniforms, frame)
        self._common(uniforms, frame, progress, sweep_end, direction, line, path, reach, color, glow, seed)
        duration_s = frame.run.request.duration_ms / 1000.0
        gl.glUniform1f(uniforms["uDurationS"], duration_s)
        gl.glUniform1f(uniforms["uMaxLife"], beam_spark_life_limit(duration_s, sweep_end))
        gl.glUniform2f(uniforms["uSpan"], *span)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendEquation(gl.GL_FUNC_ADD)
        gl.glBlendFunc(gl.GL_ONE, gl.GL_ONE)
        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, BEAM_SPARKS)
        gl.glDisable(gl.GL_BLEND)

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickBeamRenderer:
    return QuickBeamRenderer()
