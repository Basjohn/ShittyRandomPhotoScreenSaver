"""Qt Quick Oscilloscope renderer: a phosphor beam drawn from the frame's traces.

Every trace (the afterglow ones and the live one, ``OscilloscopeFrame.points``) is one std430
array on the stream ring (binding 3), drawn by one instanced pass into a single-sample
``SceneTarget`` laid over the card (overlay): each segment a quad whose fragment measures its
distance to the segment, so the beam is anti-aliased at any width and joints never bead (the
traces combine by their maximum). The optional graticule is one quad drawn first. The beam
writes its light into the overlay's emission attachment and the target's bloom spreads it into
the glow (Glow 0 allocates no emission attachment or bloom, and draws the fragments without an
emission output). Shapes and reaction rules: ``rendering/gl_programs/oscilloscope_program.py``.
Nothing is allocated per frame.

The shaders are files beside the 2D modes' fragments (``widgets/spotify_visualizer/shaders/oscilloscope_*``), which the
native core draws as well (N5.1). Every block member comes from one of three sources, by its name, as the native route
fills it: the card (the item matrix, the oriented size and quarter turns), ``oscilloscope_settings_values`` (what follows
the Settings and the card) and ``oscilloscope_frame_values`` (what follows the music, from the logical frame alone: the
native record, ``core.visualizer_engine.oscilloscope_native_schema``).
"""

from __future__ import annotations

import colorsys
import math
from pathlib import Path

from OpenGL import GL as gl

from rendering.gl_programs.oscilloscope_program import MAX_TRACES, POINT_BINDING, RING_RADIUS, TRACE_POINTS
from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl, pack_block
from rendering.quick import gl_query
from rendering.quick.scene3d.frame import item_pixel_rect
from rendering.quick.scene3d.resources import MeshResources, warm_pass_blocks, warm_programs
from rendering.quick.scene3d.stream import StreamRing
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs
from rendering.gl_programs.scene3d import scene_samples
from widgets.spotify_visualizer import shaders as shader_package
from widgets.spotify_visualizer.render_state import OscilloscopeFrame

from ..implementation_values import parameter, rgba
from ..render_contract import QuickVisualizerRenderFrame

_GRATICULE_STYLES = {"Grid": 1, "Crosshair": 2}
_TRACE_BYTES = TRACE_POINTS * 8
_PADDING = 0.06               # the field's margin around the drawing (share of its smaller side)
_TRACE_HEIGHT = 0.92          # the trace's swing (share of the padded half height)
_FLARE_WIDTH = 0.9            # how much a full flare widens the beam (share of its width)
_GLOW_LIGHT = 1.8             # the light a beam pixel sends to the bloom (a thin beam needs plenty)
# The scene target's multisampling: the Oscilloscope's declared fixed request (N3.1, D14 choice D: single-sampled
# whatever the tier), through the one sampling owner.
_SCENE_SAMPLES = scene_samples(None, fixed=1)

#: The shader files both renderers draw: the beam and the graticule, each fragment with the emission output (Glow above
#: 0) and without it (``_plain``: Glow 0, a target of colour alone).
OSCILLOSCOPE_SHADER_FILES = ("oscilloscope_beam.vert", "oscilloscope_beam.frag", "oscilloscope_beam_plain.frag",
                             "oscilloscope_graticule.vert", "oscilloscope_graticule.frag",
                             "oscilloscope_graticule_plain.frag")


def _programs():
    """The shader files' sources composed as the loader composes them (one source for this renderer and the native
    core's bake, ``tools/regen_qrc.py --shaders``), and the two blocks' layouts read from their own declarations."""
    from widgets.spotify_visualizer.shaders import compose_shader_source

    folder = Path(shader_package.__file__).resolve().parent
    sources = {name: compose_shader_source(folder / name) for name in OSCILLOSCOPE_SHADER_FILES}
    beam = block_layout_from_glsl(block_declaration(sources["oscilloscope_beam.vert"], "OscilloscopeBeam"))
    graticule = block_layout_from_glsl(block_declaration(sources["oscilloscope_graticule.vert"],
                                                         "OscilloscopeGraticule"))
    return sources, beam, graticule


_SOURCES, OSC_BEAM_BLOCK, OSC_GRATICULE_BLOCK = _programs()
OSC_BEAM_VERTEX_SOURCE = _SOURCES["oscilloscope_beam.vert"]
OSC_BEAM_FRAGMENT_SOURCE = _SOURCES["oscilloscope_beam.frag"]
OSC_BEAM_PLAIN_FRAGMENT_SOURCE = _SOURCES["oscilloscope_beam_plain.frag"]
OSC_GRATICULE_VERTEX_SOURCE = _SOURCES["oscilloscope_graticule.vert"]
OSC_GRATICULE_FRAGMENT_SOURCE = _SOURCES["oscilloscope_graticule.frag"]
OSC_GRATICULE_PLAIN_FRAGMENT_SOURCE = _SOURCES["oscilloscope_graticule_plain.frag"]


def oscilloscope_layout(field, display: str, item_width: float | None = None,
                        overrun: float = 0.0) -> tuple[tuple[float, float], float]:
    """(logical px per unit along x and y, the drawing's length in px) for a content ``field``.

    Given the item's width (in the field's oriented space), the Trace runs ``overrun`` px past both
    of its edges, so the card's clip cuts it under the border instead of the trace ending short of it."""
    x, _y, width, height = (float(value) for value in field)
    pad = _PADDING * min(width, height)
    if display == "Trace":
        half = width * 0.5 - pad
        if item_width is not None:
            centre = x + 0.5 * width
            half = max(centre, float(item_width) - centre) + float(overrun)
        scale = (max(1.0, half), max(1.0, (height * 0.5 - pad) * _TRACE_HEIGHT))
        return scale, 2.0 * scale[0]
    radius = max(1.0, min(width, height) * 0.5 - pad)
    length = 2.0 * math.pi * RING_RADIUS * radius if display == "Ring" else 2.0 * radius
    return (radius, radius), length


def tone_colour(tone: float) -> tuple[float, float, float]:
    """The beam's spectral tint: warm for bass-heavy sound, cool for bright sound."""
    return colorsys.hsv_to_rgb(0.02 + 0.55 * max(0.0, min(1.0, float(tone))), 0.85, 1.0)


def _oscilloscope_frame(logical) -> OscilloscopeFrame:
    state = logical.mode_state
    if not isinstance(state, OscilloscopeFrame):
        raise TypeError("Oscilloscope renderer received another mode frame")
    return state


def _graticule_screen(field, display: str) -> tuple[float, float, float, float]:
    """The graticule covers the scope's screen, centred in the field (the Trace itself runs on under the card's
    border; its screen keeps the field's margin)."""
    scale = oscilloscope_layout(field, display)[0]
    centre_x, centre_y = field[0] + 0.5 * field[2], field[1] + 0.5 * field[3]
    return centre_x - scale[0], centre_y - scale[1], 2.0 * scale[0], 2.0 * scale[1]


def oscilloscope_settings_values(logical, field, oriented_size, dpr: float, visual_scale: float) -> dict[str, object]:
    """Every member of the beam's and the graticule's blocks that follows the Settings and the card, by name, as this
    renderer writes it and the native route sends it as settings. ``field``: the content rect in the oriented item
    (``frame.logical_content_rect``; the native card's ``content_rect``); ``oriented_size``: the item's oriented logical
    size; ``dpr`` and ``visual_scale``: the drawn card's. With Glow above 0 the composite's exposure (0: no tone map)."""
    parameters = _oscilloscope_frame(logical).parameters
    display = str(parameter(parameters, "osc_display"))
    field = tuple(float(value) for value in field)
    x, _y, width, height = field
    if display == "Trace":
        # The Trace's horizontal scale runs past the item by the beam's reach (per frame: the shader adds it).
        pad = _PADDING * min(width, height)
        centre = x + 0.5 * width
        layout = (max(centre, float(oriented_size[0]) - centre),
                  max(1.0, (height * 0.5 - pad) * _TRACE_HEIGHT), 0.0, 0.0)
    else:
        (radius, _radius), length = oscilloscope_layout(field, display)
        layout = (0.0, 0.0, radius, length)
    graticule = str(parameter(parameters, "osc_graticule"))
    values: dict[str, object] = {
        "uField": field,
        "uLayout": layout,
        "uTrace": 1 if display == "Trace" else 0,
        "uPixel": 1.0 / max(0.5, float(dpr)),
        "uCoreBase": 0.5 * float(parameter(parameters, "osc_beam_width")) * float(visual_scale),
        "uGlowColour": tuple(rgba(parameter(parameters, "osc_beam_glow_color"))),
        "uGlow": _GLOW_LIGHT,
        "uAnalog": float(parameter(parameters, "osc_analog")),
        "uCentreFade": 1.0 if display == "Phase" else 0.0,
        "uScreen": _graticule_screen(field, display),
        "uGraticuleColour": tuple(rgba(parameter(parameters, "osc_graticule_color"))),
        "uStyle": _GRATICULE_STYLES.get(graticule, 0),
        "uDivisions": (10.0, 8.0) if display == "Trace" else (8.0, 8.0),
    }
    if float(parameter(parameters, "osc_glow")) > 0.0:
        values["u_hdr_exposure"] = 0.0
    return values


#: The record's fields (``oscilloscope_frame_values``): the blocks' per-frame members, the traces' points with their used
#: length, the beam's instance count and the graticule's vertex count.
OSCILLOSCOPE_FRAME_MEMBERS = ("u_alpha", "u_points", "u_widen", "u_bright", "u_hot", "u_beam", "u_bloom_strength")


def oscilloscope_frame_values(logical) -> dict[str, object]:
    """Every per-frame value of the Oscilloscope's native record, by name, from the logical frame alone, in double
    precision (the core rounds each to float as the Python block packer does): each trace's alpha (zero past the count),
    the points per trace, the flare's widening of the beam, its brightness and white-hot centre, its colour (the tone's
    tint under Spectral), the bloom strength (0 at Glow 0), the traces' points as the float32 bytes this renderer
    uploads with their used length in floats, the beam's instances (a quad a segment) and the graticule's vertices (4
    when its style draws one, else 0)."""
    state = _oscilloscope_frame(logical)
    parameters = state.parameters
    flare = float(state.flare) * float(parameter(parameters, "osc_flare"))
    pulse = float(parameter(parameters, "osc_pulse"))
    drive = float(state.drive)
    glow = float(parameter(parameters, "osc_glow"))
    beam = rgba(parameter(parameters, "osc_beam_color"))[:3]
    spectral = float(parameter(parameters, "osc_spectral"))
    if spectral > 0.0:
        tint = tone_colour(state.tone)
        beam = tuple(b + (t - b) * spectral for b, t in zip(beam, tint))
    count = len(state.trace_alphas)
    points = state.trace_points
    graticule = str(parameter(parameters, "osc_graticule"))
    return {
        "u_alpha": tuple(float(alpha) for alpha in state.trace_alphas) + (0.0,) * (MAX_TRACES - count),
        "u_points": points,
        "u_widen": 1.0 + _FLARE_WIDTH * flare,
        "u_bright": (1.0 - pulse + pulse * (0.5 + 0.5 * drive)) * (1.0 + 0.6 * flare),
        "u_hot": min(0.6, 0.12 + 0.18 * drive + 0.3 * flare),
        "u_beam": (*(float(v) for v in beam), 0.0),
        "u_bloom_strength": glow * (0.55 + 0.3 * pulse * drive + 0.45 * flare) if glow > 0.0 else 0.0,
        "osc_points": state.points,
        "osc_point_floats": len(state.points) // 4,
        "osc_segments": count * (points - 1) if count else 0,
        "osc_graticule_vertices": 4 if graticule in _GRATICULE_STYLES and count else 0,
    }


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


def _sources(glow: bool) -> tuple[tuple[str, str, str], tuple[str, str, str]]:
    """The (name, vertex, fragment) of the beam's and the graticule's programs: with the emission output under Glow."""
    if glow:
        return (("beam", OSC_BEAM_VERTEX_SOURCE, OSC_BEAM_FRAGMENT_SOURCE),
                ("graticule", OSC_GRATICULE_VERTEX_SOURCE, OSC_GRATICULE_FRAGMENT_SOURCE))
    return (("beam_plain", OSC_BEAM_VERTEX_SOURCE, OSC_BEAM_PLAIN_FRAGMENT_SOURCE),
            ("graticule_plain", OSC_GRATICULE_VERTEX_SOURCE, OSC_GRATICULE_PLAIN_FRAGMENT_SOURCE))


class QuickOscilloscopeRenderer:
    mode_id = "oscilloscope"

    def __init__(self) -> None:
        # The programs' values are std140 pass blocks (N1.6), the beam's the larger.
        self._resources = MeshResources("Quick Oscilloscope",
                                        block_bytes=max(OSC_BEAM_BLOCK.size, OSC_GRATICULE_BLOCK.size))
        self._target = SceneTarget("Quick Oscilloscope")
        self._stream = StreamRing("Quick Oscilloscope", slots=4, slot_bytes=MAX_TRACES * _TRACE_BYTES * 4,
                                  hold_bytes=MAX_TRACES * _TRACE_BYTES)

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._stream.has_resources

    def _initialize(self) -> None:
        """Compile the glowing programs ahead of a first frame (shader admission)."""
        for name, vertex, fragment in _sources(True):
            self._resources.program(name, vertex, fragment)

    def prepare_step(self, frame: QuickVisualizerRenderFrame) -> bool:
        """One unit of what this activation's first visible frame would otherwise compile or
        allocate (a program, the stream ring, the target and its glow), on a hidden frame; True
        once nothing is left."""
        parameters = frame.snapshot.logical.mode_state.parameters
        bloom = float(parameter(parameters, "osc_glow")) > 0.0
        r = self._resources
        if not warm_programs([*((r, *program) for program in _sources(bloom)),
                              *((r, *program) for program in scene_target_programs(_SCENE_SAMPLES, bloom, False, overlay=True))]):
            return False
        if not warm_pass_blocks(r, item_pixel_rect(frame)[2:]):
            return False
        if not self._stream.warm():
            return False
        return self._target.warm(item_pixel_rect(frame)[2:], _SCENE_SAMPLES, overlay=True, bloom=bloom)

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        snapshot = frame.snapshot
        state = _oscilloscope_frame(snapshot.logical)
        presentation = snapshot.presentation
        if presentation.content_fade <= 0.0 or not state.trace_alphas:
            return
        field = tuple(float(value) for value in frame.logical_content_rect)
        if field[2] <= 0.0 or field[3] <= 0.0:
            return
        settings = oscilloscope_settings_values(snapshot.logical, field, frame.oriented_logical_size, presentation.dpr,
                                                presentation.uniform_visual_scale)
        per_frame = oscilloscope_frame_values(snapshot.logical)
        bloom = float(per_frame["u_bloom_strength"])
        (beam_name, beam_vertex, beam_fragment), (graticule_name, graticule_vertex, graticule_fragment) = \
            _sources(bloom > 0.0)
        # The card's members (the native core's conventions): the item matrix, the oriented size, the quarter turns.
        card = {"uMatrix": frame.matrix_values, "u_resolution": tuple(frame.oriented_logical_size),
                "uContentRotationQuarters": frame.content_rotation_quarters}
        r = self._resources
        beam_program = r.program(beam_name, beam_vertex, beam_fragment)
        with self._target.scope(frame, _SCENE_SAMPLES, r, overlay=presentation.content_fade, bloom=bloom):
            inherited = _blend_state()
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendEquationSeparatei(0, gl.GL_MAX, gl.GL_MAX)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
            try:
                gl.glBindVertexArray(frame.quad_vao)
                if per_frame["osc_graticule_vertices"]:
                    gl.glUseProgram(r.program(graticule_name, graticule_vertex, graticule_fragment))
                    values = r.values("graticule")
                    values.update(settings)
                    values.update(card)
                    with r.pass_blocks.bound(pack_block(OSC_GRATICULE_BLOCK, values)):
                        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, int(per_frame["osc_graticule_vertices"]))
                gl.glUseProgram(beam_program)
                values = r.values("beam")
                values.update(settings)
                values.update(per_frame)
                values.update(card)
                with r.pass_blocks.bound(pack_block(OSC_BEAM_BLOCK, values)), \
                        self._stream.bound(gl.GL_SHADER_STORAGE_BUFFER, POINT_BINDING, per_frame["osc_points"]):
                    with self._target.emission_writes():
                        # The light combines by its maximum as the beam does: overlapping segments
                        # and afterglow traces never stack glow (the helper's default adds).
                        gl.glBlendEquationSeparatei(1, gl.GL_MAX, gl.GL_MAX)
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, int(per_frame["osc_segments"]))
            finally:
                _restore_blend(inherited)

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


__all__ = ["OSCILLOSCOPE_FRAME_MEMBERS", "OSCILLOSCOPE_SHADER_FILES", "QuickOscilloscopeRenderer",
           "create_visualizer_renderer", "oscilloscope_frame_values", "oscilloscope_layout",
           "oscilloscope_settings_values", "tone_colour"]
