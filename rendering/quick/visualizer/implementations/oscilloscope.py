"""Qt Quick Oscilloscope renderer: a phosphor beam drawn from the frame's traces.

Every trace (the afterglow ones and the live one, ``OscilloscopeFrame.points``) is one std430
array on the stream ring (binding 3), drawn by one instanced pass into a single-sample
``SceneTarget`` laid over the card (overlay): each segment a quad whose fragment measures its
distance to the segment, so the beam is anti-aliased at any width and joints never bead (the
traces combine by their maximum). The optional graticule is one quad drawn first. The beam
writes its light into the overlay's emission attachment and the target's bloom spreads it into
the glow (Glow 0 allocates no emission attachment or bloom). Shapes and reaction rules:
``rendering/gl_programs/oscilloscope_program.py``. Nothing is allocated per frame.
"""

from __future__ import annotations

import colorsys
import math

from OpenGL import GL as gl

from rendering.gl_programs.oscilloscope_program import (
    OSC_BEAM_FRAGMENT_SOURCE,
    OSC_BEAM_VERTEX_SOURCE,
    OSC_GRATICULE_FRAGMENT_SOURCE,
    OSC_GRATICULE_VERTEX_SOURCE,
    MAX_TRACES,
    POINT_BINDING,
    RING_RADIUS,
    TRACE_POINTS,
)
from rendering.quick import gl_query
from rendering.quick.scene3d.frame import item_pixel_rect
from rendering.quick.scene3d.resources import MeshResources, warm_programs
from rendering.quick.scene3d.stream import StreamRing
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs
from widgets.spotify_visualizer.render_state import OscilloscopeFrame

from ..implementation_values import parameter, rgba
from ..render_contract import QuickVisualizerRenderFrame

_BEAM_UNIFORMS = ("uMatrix", "uField", "uScale", "uPoints", "uAlpha", "uReach", "uCore", "uPixel", "uBeam",
                  "uGlowColour", "uGlow", "uBright", "uAnalog", "uFocus", "uHot", "uCentreFade", "uOriented",
                  "uQuarters")
_GRATICULE_UNIFORMS = ("uMatrix", "uField", "uColour", "uStyle", "uDivisions", "uOriented", "uQuarters")
_GRATICULE_STYLES = {"Grid": 1, "Crosshair": 2}
_TRACE_BYTES = TRACE_POINTS * 8
_PADDING = 0.06               # the field's margin around the drawing (share of its smaller side)
_TRACE_HEIGHT = 0.92          # the trace's swing (share of the padded half height)
_FLARE_WIDTH = 0.9            # how much a full flare widens the beam (share of its width)
_GLOW_LIGHT = 1.8             # the light a beam pixel sends to the bloom (a thin beam needs plenty)


def oscilloscope_layout(field, display: str) -> tuple[tuple[float, float], float]:
    """(logical px per unit along x and y, the drawing's length in px) for a content ``field``."""
    _x, _y, width, height = (float(value) for value in field)
    pad = _PADDING * min(width, height)
    if display == "Trace":
        scale = (max(1.0, width * 0.5 - pad), max(1.0, (height * 0.5 - pad) * _TRACE_HEIGHT))
        return scale, 2.0 * scale[0]
    radius = max(1.0, min(width, height) * 0.5 - pad)
    length = 2.0 * math.pi * RING_RADIUS * radius if display == "Ring" else 2.0 * radius
    return (radius, radius), length


def tone_colour(tone: float) -> tuple[float, float, float]:
    """The beam's spectral tint: warm for bass-heavy sound, cool for bright sound."""
    return colorsys.hsv_to_rgb(0.02 + 0.55 * max(0.0, min(1.0, float(tone))), 0.85, 1.0)


def _blend_state() -> tuple:
    return (bool(gl.glIsEnabled(gl.GL_BLEND)),
            *(gl_query.get_int(name) for name in (gl.GL_BLEND_SRC_RGB, gl.GL_BLEND_DST_RGB, gl.GL_BLEND_SRC_ALPHA,
                                                   gl.GL_BLEND_DST_ALPHA, gl.GL_BLEND_EQUATION_RGB,
                                                   gl.GL_BLEND_EQUATION_ALPHA)))


def _restore_blend(state: tuple) -> None:
    enabled, source_rgb, destination_rgb, source_alpha, destination_alpha, equation_rgb, equation_alpha = state
    gl.glBlendFuncSeparate(source_rgb, destination_rgb, source_alpha, destination_alpha)
    gl.glBlendEquationSeparate(equation_rgb, equation_alpha)
    (gl.glEnable if enabled else gl.glDisable)(gl.GL_BLEND)


class QuickOscilloscopeRenderer:
    mode_id = "oscilloscope"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Oscilloscope")
        self._target = SceneTarget("Quick Oscilloscope")
        self._stream = StreamRing("Quick Oscilloscope", slots=4, slot_bytes=MAX_TRACES * _TRACE_BYTES * 4,
                                  hold_bytes=MAX_TRACES * _TRACE_BYTES)

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._stream.has_resources

    def _initialize(self) -> None:
        """Compile both programs ahead of a first frame (shader admission)."""
        r = self._resources
        r.program("beam", OSC_BEAM_VERTEX_SOURCE, OSC_BEAM_FRAGMENT_SOURCE)
        r.uniforms("beam", _BEAM_UNIFORMS)
        r.program("graticule", OSC_GRATICULE_VERTEX_SOURCE, OSC_GRATICULE_FRAGMENT_SOURCE)
        r.uniforms("graticule", _GRATICULE_UNIFORMS)

    def prepare_step(self, frame: QuickVisualizerRenderFrame) -> bool:
        """One unit of what this activation's first visible frame would otherwise compile or
        allocate (a program, the stream ring, the target and its glow), on a hidden frame; True
        once nothing is left."""
        parameters = frame.snapshot.logical.mode_state.parameters
        bloom = float(parameter(parameters, "osc_glow")) > 0.0
        r = self._resources
        if not warm_programs([(r, "beam", OSC_BEAM_VERTEX_SOURCE, OSC_BEAM_FRAGMENT_SOURCE),
                              (r, "graticule", OSC_GRATICULE_VERTEX_SOURCE, OSC_GRATICULE_FRAGMENT_SOURCE),
                              *((r, *program) for program in scene_target_programs(1, bloom, False, overlay=True))]):
            return False
        if not self._stream.warm():
            return False
        return self._target.warm(item_pixel_rect(frame)[2:], 1, overlay=True, bloom=bloom)

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        snapshot = frame.snapshot
        state = snapshot.logical.mode_state
        if not isinstance(state, OscilloscopeFrame):
            raise TypeError("Oscilloscope renderer received another mode frame")
        presentation = snapshot.presentation
        if presentation.content_fade <= 0.0 or not state.trace_alphas:
            return
        field = tuple(float(value) for value in frame.logical_content_rect)
        if field[2] <= 0.0 or field[3] <= 0.0:
            return
        parameters = state.parameters
        display = str(parameter(parameters, "osc_display"))
        scale, length = oscilloscope_layout(field, display)
        visual_scale = float(presentation.uniform_visual_scale)
        flare = float(state.flare) * float(parameter(parameters, "osc_flare"))
        pulse = float(parameter(parameters, "osc_pulse"))
        drive = float(state.drive)
        glow = float(parameter(parameters, "osc_glow"))
        core = 0.5 * float(parameter(parameters, "osc_beam_width")) * visual_scale * (1.0 + _FLARE_WIDTH * flare)
        pixel = 1.0 / max(0.5, float(presentation.dpr))
        beam = rgba(parameter(parameters, "osc_beam_color"))[:3]
        spectral = float(parameter(parameters, "osc_spectral"))
        if spectral > 0.0:
            tint = tone_colour(state.tone)
            beam = tuple(b + (t - b) * spectral for b, t in zip(beam, tint))
        brightness = (1.0 - pulse + pulse * (0.5 + 0.5 * drive)) * (1.0 + 0.6 * flare)
        bloom = glow * (0.55 + 0.3 * pulse * drive + 0.45 * flare) if glow > 0.0 else 0.0
        count = len(state.trace_alphas)
        points = state.trace_points
        alphas = list(state.trace_alphas) + [0.0] * (MAX_TRACES - count)

        r = self._resources
        beam_program = r.program("beam", OSC_BEAM_VERTEX_SOURCE, OSC_BEAM_FRAGMENT_SOURCE)
        beam_uniforms = r.uniforms("beam", _BEAM_UNIFORMS)
        graticule = str(parameter(parameters, "osc_graticule"))
        with self._target.scope(frame, 1, r, overlay=presentation.content_fade, bloom=bloom):
            inherited = _blend_state()
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendEquationSeparatei(0, gl.GL_MAX, gl.GL_MAX)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
            try:
                gl.glBindVertexArray(frame.quad_vao)
                if graticule in _GRATICULE_STYLES:
                    program = r.program("graticule", OSC_GRATICULE_VERTEX_SOURCE, OSC_GRATICULE_FRAGMENT_SOURCE)
                    uniforms = r.uniforms("graticule", _GRATICULE_UNIFORMS)
                    gl.glUseProgram(program)
                    gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
                    gl.glUniform4f(uniforms["uField"], *self._graticule_field(field, scale))
                    gl.glUniform4f(uniforms["uColour"], *rgba(parameter(parameters, "osc_graticule_color")))
                    gl.glUniform1i(uniforms["uStyle"], _GRATICULE_STYLES[graticule])
                    gl.glUniform2f(uniforms["uDivisions"], *((10.0, 8.0) if display == "Trace" else (8.0, 8.0)))
                    gl.glUniform2f(uniforms["uOriented"], *frame.oriented_logical_size)
                    gl.glUniform1i(uniforms["uQuarters"], frame.content_rotation_quarters)
                    gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
                gl.glUseProgram(beam_program)
                gl.glUniformMatrix4fv(beam_uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
                gl.glUniform4f(beam_uniforms["uField"], *field)
                gl.glUniform2f(beam_uniforms["uScale"], *scale)
                gl.glUniform1i(beam_uniforms["uPoints"], points)
                gl.glUniform1fv(beam_uniforms["uAlpha"], MAX_TRACES, alphas)
                gl.glUniform1f(beam_uniforms["uReach"], core + 2.0 * pixel)
                gl.glUniform1f(beam_uniforms["uCore"], core)
                gl.glUniform1f(beam_uniforms["uPixel"], pixel)
                gl.glUniform3f(beam_uniforms["uBeam"], *beam)
                gl.glUniform3f(beam_uniforms["uGlowColour"], *rgba(parameter(parameters, "osc_beam_glow_color"))[:3])
                gl.glUniform1f(beam_uniforms["uGlow"], _GLOW_LIGHT)
                gl.glUniform1f(beam_uniforms["uBright"], brightness)
                gl.glUniform1f(beam_uniforms["uAnalog"], float(parameter(parameters, "osc_analog")))
                gl.glUniform1f(beam_uniforms["uFocus"], 2.5 * length / max(1, points - 1))
                gl.glUniform1f(beam_uniforms["uCentreFade"], 1.0 if display == "Phase" else 0.0)
                # CUSTOM quarter turns: the trace is laid out in the rotated content (its field is
                # the logical content rect) and turned into the item's physical space at the vertex.
                gl.glUniform2f(beam_uniforms["uOriented"], *frame.oriented_logical_size)
                gl.glUniform1i(beam_uniforms["uQuarters"], frame.content_rotation_quarters)
                gl.glUniform1f(beam_uniforms["uHot"], min(0.6, 0.12 + 0.18 * drive + 0.3 * flare))
                with self._stream.bound(gl.GL_SHADER_STORAGE_BUFFER, POINT_BINDING, state.points):
                    with self._target.emission_writes():
                        # The light combines by its maximum as the beam does: overlapping segments
                        # and afterglow traces never stack glow (the helper's default adds).
                        gl.glBlendEquationSeparatei(1, gl.GL_MAX, gl.GL_MAX)
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, count * (points - 1))
            finally:
                _restore_blend(inherited)

    @staticmethod
    def _graticule_field(field, scale) -> tuple[float, float, float, float]:
        """The graticule covers the drawing's extent, centred in the field."""
        centre_x, centre_y = field[0] + 0.5 * field[2], field[1] + 0.5 * field[3]
        return centre_x - scale[0], centre_y - scale[1], 2.0 * scale[0], 2.0 * scale[1]

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._stream.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_visualizer_renderer() -> QuickOscilloscopeRenderer:
    return QuickOscilloscopeRenderer()


__all__ = ["QuickOscilloscopeRenderer", "create_visualizer_renderer", "oscilloscope_layout", "tone_colour"]
