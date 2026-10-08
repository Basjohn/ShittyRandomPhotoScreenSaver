"""Qt Quick Extruded Spectrum renderer: Spectrum's bars as lit 3D boxes.

The first Visualizer on the shared Scene3D foundation: a multisampled overlay
``SceneTarget`` (frameless: no card, so the bars stand over the wallpaper), the shared unit
box drawn instanced from one std430 record per bar on a stream ring, and the shared
physically based material. It consumes only the immutable snapshot; the bars come from
Spectrum's frame runtime unchanged. With overflow allowed (3D + frameless: not contained to its
frame) the target covers everything the bars can draw for the view (``extruded_reach``), up to
the whole window.
"""

from __future__ import annotations

import struct

from OpenGL import GL as gl

from core.logging.logger import get_logger, is_geometry_logging_enabled, is_viz_diagnostics_enabled

from rendering.gl_programs.extruded_spectrum_options import EXTRUDED_COLOURINGS
from rendering.gl_programs.extruded_spectrum_program import (
    EXTRUDED_FRAGMENT_SOURCE,
    EXTRUDED_HUE_DRIFT_RATE,
    EXTRUDED_MAX_DEPTH,
    EXTRUDED_MAX_TILT,
    EXTRUDED_MAX_TURN,
    EXTRUDED_VERTEX_SOURCE,
    extruded_draw_order,
    extruded_fit,
    extruded_reach,
)
from rendering.gl_programs.scene3d import SCENE3D_BOX_ATTRIBUTES, SCENE3D_BOX_VERTICES, scene3d_detail
from rendering.quick.scene3d.environment import BackdropEnvironment
from rendering.quick.scene3d.frame import item_pixel_rect, reach_item_frame
from rendering.quick.scene3d.resources import MeshResources, warm_programs
from rendering.quick.scene3d.shadows import directional_shadow_pass, directional_shadow_vector, extruded_shadow_length
from rendering.quick.scene3d.stream import StreamRing
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs
from widgets.spotify_visualizer.render_state import ExtrudedSpectrumFrame

from ..implementation_values import parameter, rgba
from ..render_contract import QuickVisualizerRenderFrame
from .spectrum import compute_quick_spectrum_layout, prepare_spectrum_shader_levels

_MAX_BARS = 64
_BAR_BINDING = 3
logger = get_logger(__name__)
_UNIFORMS = ("uMatrix", "uField", "uCentre", "uBarGeometry", "uFit", "uView", "uHeightScale", "uBarCount",
             "uHueShift", "uColouring", "uFloorSpan", "uPass", "uFill", "uBorder", "uGloss", "uEdgePx",
             "uGhostAlpha", "uReflection", "uSmooth", "uMirror", "uBackdrop", "uBackdropMap",
             "uBackdropPrevious", "uBackdropBlend", "uShadowColor", "uShadowVector")


def extruded_quality(parameters) -> tuple[int, float]:
    """(samples, Mirror Faces strength) for the activation's 3D Detail tier: the tier's overlay
    multisampling, doubled by Smooth Edges; Mirror Faces off where the tier has no reflections or
    no wallpaper is there to reflect (the ``backdrop`` parameter)."""
    detail = scene3d_detail(parameter(parameters, "scene3d_detail"))
    smooth = bool(parameter(parameters, "extruded_spectrum_smooth_edges"))
    mirror = float(parameter(parameters, "extruded_spectrum_face_mirror")) if detail.reflections else 0.0
    if parameter(parameters, "backdrop") is None:
        mirror = 0.0
    return detail.overlay_samples * (2 if smooth else 1), mirror


def extruded_bar_records(levels, peaks, count: int, order=None) -> bytes:
    """One (level, peak, bar index) std430 record per bar in draw ``order`` (default: by index),
    levels already carrying Spectrum's upload transfer."""
    values = []
    for index in (range(count) if order is None else order):
        values.extend((levels[index], peaks[index], float(index)))
    return struct.pack(f"<{3 * count}f", *values)


def extruded_hue_shift(animation_time: float, hue_drift: float) -> float:
    """Resolve the authored spectral hue phase without render-state side effects."""
    return (float(animation_time) * EXTRUDED_HUE_DRIFT_RATE * float(hue_drift)) % 1.0


class QuickExtrudedSpectrumRenderer:
    mode_id = "extruded_spectrum"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Extruded Spectrum")
        self._target = SceneTarget("Quick Extruded Spectrum")
        self._stream = StreamRing("Quick Extruded Spectrum")
        self._backdrop = BackdropEnvironment("Quick Extruded Spectrum")
        self._fit_key: tuple | None = None
        self._fit = (1.0, 0.0)
        self._shadow_diag_key = None

    @property
    def has_resources(self) -> bool:
        return (self._resources.has_resources or self._target.has_resources or self._stream.has_resources
                or self._backdrop.has_resources)

    def _initialize(self) -> None:
        """Compile the bar program and build the box mesh ahead of a first frame (shader admission)."""
        r = self._resources
        r.program("bars", EXTRUDED_VERTEX_SOURCE, EXTRUDED_FRAGMENT_SOURCE)
        r.uniforms("bars", _UNIFORMS)
        r.mesh("box", SCENE3D_BOX_VERTICES, SCENE3D_BOX_ATTRIBUTES)

    def _scene(self, frame: QuickVisualizerRenderFrame):
        """(layout, field, centre, depth, tilt, turn, reflection, overflow, fit) for this frame's view
        and shape, or None when there is nothing to draw; the fit is recomputed only when they change."""
        snapshot = frame.snapshot
        presentation = snapshot.presentation
        parameters = snapshot.logical.mode_state.parameters
        count = min(_MAX_BARS, int(snapshot.logical.common.bar_count))
        if count <= 0:
            return None
        layout = compute_quick_spectrum_layout(
            local_content_rect=frame.logical_content_rect,
            viewport_extent=presentation.logical_viewport_extent,
            visual_scale=presentation.uniform_visual_scale,
            bar_count=count,
        )
        content_x, content_y, content_width, content_height = layout.content_rect
        margin_y = 6.0 * presentation.uniform_visual_scale
        field = (content_x, content_y + margin_y, content_width, content_height - 2.0 * margin_y)
        height = field[3]
        if height <= 0.0:
            return None
        centre = layout.bars_left + 0.5 * layout.bar_span
        depth = min(EXTRUDED_MAX_DEPTH, layout.bar_width / height * float(parameter(parameters,
                                                                                     "extruded_spectrum_depth")))
        tilt = EXTRUDED_MAX_TILT * float(parameter(parameters, "extruded_spectrum_tilt"))
        turn = EXTRUDED_MAX_TURN * float(parameter(parameters, "extruded_spectrum_turn"))
        reflection = float(parameter(parameters, "extruded_spectrum_reflection"))
        overflow = bool(parameter(parameters, "extruded_spectrum_allow_overflow"))
        key = (round(layout.bar_span / height, 6), round(depth, 6), round(tilt, 6), round(turn, 6),
               round(reflection, 6), round(content_width / height, 6), overflow)
        if key != self._fit_key:
            self._fit = extruded_fit(0.5 * layout.bar_span / height, depth, tilt, reflection, content_width / height,
                                     turn, overflow)
            self._fit_key = key
        return layout, field, centre, depth, tilt, turn, reflection, overflow, self._fit

    def _target_frame(self, frame: QuickVisualizerRenderFrame, scene):
        """The frame the scene target covers: the item, or with overflow everything the bars can
        draw, up to the whole window (3D + frameless: not contained to its frame)."""
        if scene is None or not scene[7]:
            return frame
        layout, field, centre, depth, tilt, turn, reflection, _overflow, fit = scene
        parameters = frame.snapshot.logical.mode_state.parameters
        shadow_vector = (0.0, 0.0)
        if (bool(parameter(parameters, "extruded_spectrum_shadow_enabled"))
                and float(parameter(parameters, "extruded_spectrum_shadow_strength")) > 0.0
                and rgba(frame.snapshot.presentation.shell_style["shadow_color"])[3] > 0.0):
            shadow_vector = directional_shadow_vector(
                frame.snapshot.presentation.shell_style["shadow_offset"],
                extruded_shadow_length(str(parameter(parameters, 'extruded_spectrum_shadow_reach'))),
            )
        return reach_item_frame(frame, extruded_reach(
            field, centre, 0.5 * layout.bar_span / field[3], depth, tilt, turn, fit, reflection,
            shadow_vector=shadow_vector))

    def prepare_step(self, frame: QuickVisualizerRenderFrame) -> bool:
        """One unit of what this activation's first visible frame would otherwise compile or
        allocate (a program, the box mesh, the stream ring, the target, the backdrop copy), on a
        hidden frame; True once nothing is left."""
        parameters = frame.snapshot.logical.mode_state.parameters
        samples, mirror = extruded_quality(parameters)
        target_frame = self._target_frame(frame, self._scene(frame))
        r = self._resources
        if not warm_programs([(r, "bars", EXTRUDED_VERTEX_SOURCE, EXTRUDED_FRAGMENT_SOURCE),
                              *((r, *program) for program in scene_target_programs(samples, False, False,
                                                                                   overlay=True))]):
            return False
        if not r.has_mesh("box"):
            r.mesh("box", SCENE3D_BOX_VERTICES, SCENE3D_BOX_ATTRIBUTES)
            return False
        if not self._stream.warm():
            return False
        if not self._target.warm(item_pixel_rect(target_frame)[2:], samples, overlay=True):
            return False
        if mirror > 0.0:
            return self._backdrop.warm(parameter(parameters, "backdrop"))
        return True

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        snapshot = frame.snapshot
        logical = snapshot.logical
        mode_state = logical.mode_state
        if not isinstance(mode_state, ExtrudedSpectrumFrame):
            raise TypeError("Extruded Spectrum renderer received another mode frame")
        presentation = snapshot.presentation
        count = min(_MAX_BARS, int(logical.common.bar_count))
        if count <= 0 or presentation.content_fade <= 0.0:
            return
        if frame.content_rotation_quarters:
            raise ValueError("Extruded Spectrum does not offer content rotation")
        levels, peaks = prepare_spectrum_shader_levels(logical.common.bars, mode_state.peaks, bar_count=count)
        scene = self._scene(frame)
        if scene is None:
            return
        layout, field, centre, depth, tilt, turn, reflection, _overflow, _fit = scene
        parameters = mode_state.parameters
        style = logical.common.style
        scale = presentation.uniform_visual_scale
        height = field[3]
        colouring = EXTRUDED_COLOURINGS.index(str(parameter(parameters, "extruded_spectrum_colouring")))
        hue_shift = extruded_hue_shift(
            mode_state.animation_time,
            float(parameter(parameters, "extruded_spectrum_hue_drift")),
        )
        ghost_alpha = (max(0.0, min(1.0, float(parameter(parameters, "spectrum_ghost_alpha"))))
                       if bool(parameter(parameters, "spectrum_ghosting_enabled")) else 0.0)
        fill = rgba(style["fill_color"])
        border = rgba(style["border_color"])
        # Bar edges are independently authored. Spectral Edges supplies its own
        # fully-visible edge colour; the other modes use the border swatch alpha.
        # A transparent fill must not suppress visible edges at draw admission.
        edges_visible = colouring == 1 or border[3] > 0.0
        shadow_enabled = bool(parameter(parameters, "extruded_spectrum_shadow_enabled"))
        shadow_strength = float(parameter(parameters, "extruded_spectrum_shadow_strength"))
        if not 0.0 <= shadow_strength <= 1.0:
            raise ValueError("Extruded Spectrum shadow strength must be within [0, 1]")

        r = self._resources
        program = r.program("bars", EXTRUDED_VERTEX_SOURCE, EXTRUDED_FRAGMENT_SOURCE)
        uniforms = r.uniforms("bars", _UNIFORMS)
        vao, vertices = r.mesh("box", SCENE3D_BOX_VERTICES, SCENE3D_BOX_ATTRIBUTES)
        first = (layout.bars_left + 0.5 * layout.bar_width - centre) / height
        order = extruded_draw_order(first, (layout.bar_width + layout.bar_gap) / height, count, tilt, turn)
        records = extruded_bar_records(levels, peaks, count, order)
        target_frame = self._target_frame(frame, scene)
        smooth = bool(parameter(parameters, "extruded_spectrum_smooth_edges"))
        samples, mirror = extruded_quality(parameters)
        backdrop, previous, blend = 0, 0, 1.0
        if mirror > 0.0:
            # The displayed wallpaper, crossfading from the last one (or in from none).
            backdrop, previous, blend = self._backdrop.textures(parameter(parameters, "backdrop"),
                                                                logical.logical_timestamp,
                                                                parameter(parameters, "backdrop_blend_s"))
            if not previous:
                previous, mirror = backdrop, mirror * blend
        elif self._backdrop.has_resources:
            self._backdrop.release()                                # Mirror Faces off: hold nothing
        origin = item_pixel_rect(target_frame)
        with self._target.scope(target_frame, samples, r, overlay=presentation.content_fade):
            gl.glUseProgram(program)
            gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
            gl.glUniform4f(uniforms["uField"], *field)
            gl.glUniform2f(uniforms["uCentre"], centre, field[1] + field[3])
            gl.glUniform4f(uniforms["uBarGeometry"], (layout.bars_left + 0.5 * layout.bar_width - centre) / height,
                           (layout.bar_width + layout.bar_gap) / height, 0.5 * layout.bar_width / height, depth)
            gl.glUniform2f(uniforms["uFit"], *self._fit)
            gl.glUniform2f(uniforms["uView"], tilt, turn)
            gl.glUniform1f(uniforms["uHeightScale"], layout.height_scale)
            gl.glUniform1i(uniforms["uBarCount"], count)
            gl.glUniform1f(uniforms["uHueShift"], hue_shift)
            gl.glUniform1i(uniforms["uColouring"], colouring)
            field_bottom = field[1] + field[3]
            gl.glUniform2f(uniforms["uFloorSpan"], field_bottom - self._fit[1] * height, field_bottom)
            gl.glUniform4f(uniforms["uFill"], *fill)
            gl.glUniform4f(uniforms["uBorder"], *border)
            gl.glUniform1f(uniforms["uGloss"], float(parameter(parameters, "extruded_spectrum_gloss")))
            gl.glUniform1f(uniforms["uEdgePx"], max(1.0, scale))
            gl.glUniform1f(uniforms["uGhostAlpha"], ghost_alpha)
            gl.glUniform1f(uniforms["uReflection"], reflection)
            gl.glUniform1f(uniforms["uSmooth"], 1.0 if smooth else 0.0)
            gl.glUniform1f(uniforms["uMirror"], mirror)
            if backdrop:
                vx, vy, vw, vh = frame.viewport
                gl.glUniform4f(uniforms["uBackdropMap"], origin[0] - vx, origin[1] - vy, vw, vh)
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, backdrop)
                gl.glUniform1i(uniforms["uBackdrop"], 1)
                gl.glActiveTexture(gl.GL_TEXTURE2)
                gl.glBindTexture(gl.GL_TEXTURE_2D, previous)
                gl.glUniform1i(uniforms["uBackdropPrevious"], 2)
                gl.glUniform1f(uniforms["uBackdropBlend"], blend if previous != backdrop else 1.0)
                gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindVertexArray(vao)
            with self._stream.bound(gl.GL_SHADER_STORAGE_BUFFER, _BAR_BINDING, records):
                if shadow_enabled and shadow_strength > 0.0:
                    shadow_color = rgba(presentation.shell_style["shadow_color"])
                    # E8: Strength is the authored opacity fraction of the canonical
                    # shadow colour, not a fraction of an undocumented 0.34
                    # attenuation. At the former default 0.45 and global 0.77
                    # opacity the cast silhouette was only ~12% alpha and was
                    # effectively invisible over busy wallpaper. The dedicated
                    # Extruded slider now spans the actual available alpha range.
                    shadow_alpha = shadow_color[3] * shadow_strength
                    shadow_vector = directional_shadow_vector(
                        presentation.shell_style["shadow_offset"],
                        extruded_shadow_length(str(parameter(parameters, 'extruded_spectrum_shadow_reach'))),
                    )
                    if is_viz_diagnostics_enabled() or is_geometry_logging_enabled():
                        # An authored-setting edge, never an audio/frame cadence.
                        diag = (shadow_enabled, round(shadow_strength, 3),
                                round(shadow_alpha, 3), shadow_vector,
                                tuple(int(v) for v in presentation.shell_style["shadow_color"]),
                                bool(scene[7]))
                        if diag != self._shadow_diag_key:
                            self._shadow_diag_key = diag
                            logger.info(
                                "[EXTRUDED_SHADOW] pass_admitted=%s strength=%.3f "
                                "alpha=%.3f world_vector=%s color=%s overflow=%s",
                                shadow_alpha > 0.0 and shadow_vector != (0.0, 0.0),
                                shadow_strength, shadow_alpha, shadow_vector,
                                diag[4], bool(scene[7]),
                            )
                    if shadow_alpha > 0.0 and shadow_vector != (0.0, 0.0):
                        gl.glUniform1i(uniforms["uPass"], 4)
                        gl.glUniform4f(
                            uniforms["uShadowColor"],
                            shadow_color[0], shadow_color[1], shadow_color[2], shadow_alpha,
                        )
                        gl.glUniform2f(uniforms["uShadowVector"], *shadow_vector)
                        with directional_shadow_pass():
                            gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, vertices, count)

                if fill[3] >= 1.0:
                    gl.glEnable(gl.GL_DEPTH_TEST)
                    gl.glDepthMask(gl.GL_TRUE)
                    gl.glUniform1i(uniforms["uPass"], 0)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, vertices, count)
                elif fill[3] > 0.0 or edges_visible:
                    # A zero-alpha body may still have visible border/spectral edges.
                    # Each box keeps only faces toward the eye, then the records' far-to-near
                    # order resolves bar overlap without a per-mode OIT target.  Depth writes
                    # would otherwise hide the wallpaper and later transparent bars.
                    gl.glDisable(gl.GL_DEPTH_TEST)
                    gl.glDepthMask(gl.GL_FALSE)
                    gl.glUniform1i(uniforms["uPass"], 3)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, vertices, count)
                gl.glDepthMask(gl.GL_FALSE)              # the translucent passes after the bars
                if reflection > 0.0:
                    gl.glUniform1i(uniforms["uPass"], 2)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, vertices, count)
                if ghost_alpha > 0.0:
                    gl.glUniform1i(uniforms["uPass"], 1)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, vertices, count)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._stream.release, self._backdrop.release,
                        self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        self._fit_key = None
        self._shadow_diag_key = None
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_visualizer_renderer() -> QuickExtrudedSpectrumRenderer:
    return QuickExtrudedSpectrumRenderer()


__all__ = ["QuickExtrudedSpectrumRenderer", "create_visualizer_renderer", "extruded_bar_records",
           "extruded_quality"]
