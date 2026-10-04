"""Qt Quick Shockwave Grid renderer: a neon grid floor rippled by musical onsets.

One displaced-grid draw into a 4x multisampled ``SceneTarget`` laid over the card (overlay),
the frame's live shockwave events streamed as one std430 array (binding 3) on the stream ring,
Spectrum's bars as one uniform array for the horizon ridge. The grid lines emit their light
into the overlay's emission attachment, and the target's bloom adds their glow over the
wallpaper (Glow 0 allocates no emission or bloom at all). Shapes and mirrors:
``rendering/gl_programs/shockwave_grid_program.py``. Nothing is allocated per frame.
"""

from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import scene3d_detail, scene3d_grid_vertices
from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_EVENTS,
    SHOCKWAVE_MAX_BARS,
    SHOCKWAVE_MAX_RIDGE,
    SHOCKWAVE_MAX_TILT,
    SHOCKWAVE_MAX_TURN,
    SHOCKWAVE_FRAGMENT_SOURCE,
    SHOCKWAVE_VERTEX_SOURCE,
    shockwave_amplitude,
    shockwave_camera,
    shockwave_event_records,
    shockwave_fit,
    shockwave_grid_cells,
    shockwave_half_width,
    shockwave_idle,
    shockwave_reach,
    shockwave_wave_speed,
)
from rendering.quick.scene3d.frame import item_pixel_rect, reach_item_frame
from rendering.quick.scene3d.resources import MeshResources, warm_programs
from rendering.quick.scene3d.stream import StreamRing
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs
from widgets.spotify_visualizer.render_state import ShockwaveGridFrame

from ..implementation_values import parameter, rgba
from ..render_contract import QuickVisualizerRenderFrame
from .spectrum import prepare_spectrum_shader_levels

_EVENT_BINDING = 3
_UNIFORMS = ("uMatrix", "uField", "uView", "uCamera", "uFit", "uHalfWidth", "uEventCount", "uWave", "uHorizon", "uIdle",
             "uBarCount",
             "uBars", "uHeightScale", "uCells", "uScroll", "uLineColor", "uCrestColor", "uFloor", "uGlow",
             "uEdgePx")


def shockwave_quality(parameters) -> tuple[int, float, tuple[int, int]]:
    """(samples, glow, grid cells) for the activation's 3D Detail tier: the tier's overlay
    multisampling, the Glow only on tiers with post effects, the tier's grid density."""
    detail = scene3d_detail(parameter(parameters, "scene3d_detail"))
    glow = float(parameter(parameters, "shockwave_grid_glow")) if detail.post_effects else 0.0
    return detail.overlay_samples, glow, shockwave_grid_cells(detail.grid_cells)


class QuickShockwaveGridRenderer:
    mode_id = "shockwave_grid"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Shockwave Grid")
        self._target = SceneTarget("Quick Shockwave Grid")
        self._stream = StreamRing("Quick Shockwave Grid")
        self._fit_key: tuple | None = None
        self._fit = (1.0, 0.5)

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._stream.has_resources

    def _initialize(self) -> None:
        """Compile the grid program and build its mesh ahead of a first frame (shader admission)."""
        r = self._resources
        r.program("grid", SHOCKWAVE_VERTEX_SOURCE, SHOCKWAVE_FRAGMENT_SOURCE)
        r.uniforms("grid", _UNIFORMS)
        cells = shockwave_grid_cells(10 ** 6)                 # the densest (High) grid
        r.mesh(_mesh_key(cells), scene3d_grid_vertices(*cells), (2,))

    def _view(self, frame: QuickVisualizerRenderFrame, parameters):
        """(field, half width, tilt, turn, ridge, fit) for this frame's view and shape; the fit is
        recomputed only when the view or shape changes."""
        field = tuple(float(value) for value in frame.logical_content_rect)
        half_width = shockwave_half_width(field[2] / field[3]) if field[3] > 0.0 else 1.0
        tilt = SHOCKWAVE_MAX_TILT * float(parameter(parameters, "shockwave_grid_tilt"))
        turn = SHOCKWAVE_MAX_TURN * float(parameter(parameters, "shockwave_grid_turn"))
        ridge = SHOCKWAVE_MAX_RIDGE * float(parameter(parameters, "shockwave_grid_horizon"))
        key = (round(tilt, 6), round(turn, 6), round(half_width, 6), round(ridge, 6))
        if key != self._fit_key:
            self._fit = shockwave_fit(tilt, turn, half_width, ridge)
            self._fit_key = key
        return field, half_width, tilt, turn, ridge, self._fit

    def _target_frame(self, frame: QuickVisualizerRenderFrame, parameters):
        """The frame the scene target covers: the item, or with overflow everything the grid can
        draw, up to the whole window (3D + frameless: not contained to its frame)."""
        if not bool(parameter(parameters, "shockwave_grid_allow_overflow")):
            return frame
        field, half_width, tilt, turn, ridge, fit = self._view(frame, parameters)
        if field[3] <= 0.0:
            return frame
        return reach_item_frame(frame, shockwave_reach(
            field, fit, tilt, turn, half_width, ridge, float(parameter(parameters, "shockwave_grid_wave_height")),
            float(parameter(parameters, "shockwave_grid_idle"))))

    def prepare_step(self, frame: QuickVisualizerRenderFrame) -> bool:
        """One unit of what this activation's first visible frame would otherwise compile or
        allocate (a program, the grid mesh, the stream ring, the target and its glow), on a hidden
        frame; True once nothing is left."""
        parameters = frame.snapshot.logical.mode_state.parameters
        samples, glow, cells = shockwave_quality(parameters)
        bloom = glow > 0.0
        target_frame = self._target_frame(frame, parameters)
        r = self._resources
        if not warm_programs([(r, "grid", SHOCKWAVE_VERTEX_SOURCE, SHOCKWAVE_FRAGMENT_SOURCE),
                              *((r, *program) for program in scene_target_programs(samples, bloom, False,
                                                                                   overlay=True))]):
            return False
        if not r.has_mesh(_mesh_key(cells)):
            r.mesh(_mesh_key(cells), scene3d_grid_vertices(*cells), (2,))
            return False
        if not self._stream.warm():
            return False
        return self._target.warm(item_pixel_rect(target_frame)[2:], samples, overlay=True, bloom=bloom)

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        snapshot = frame.snapshot
        logical = snapshot.logical
        mode_state = logical.mode_state
        if not isinstance(mode_state, ShockwaveGridFrame):
            raise TypeError("Shockwave Grid renderer received another mode frame")
        presentation = snapshot.presentation
        if presentation.content_fade <= 0.0:
            return
        if frame.content_rotation_quarters:
            raise ValueError("Shockwave Grid does not offer content rotation")
        field = tuple(float(value) for value in frame.logical_content_rect)
        if field[2] <= 0.0 or field[3] <= 0.0:
            return
        parameters = mode_state.parameters
        count = min(SHOCKWAVE_MAX_BARS, int(logical.common.bar_count))
        levels, _peaks = prepare_spectrum_shader_levels(logical.common.bars, mode_state.peaks, bar_count=count)
        field, half_width, tilt, turn, ridge, _fit = self._view(frame, parameters)
        events = shockwave_event_records(tuple(mode_state.events), half_width)
        samples, glow, cells = shockwave_quality(parameters)
        scale = presentation.uniform_visual_scale

        r = self._resources
        program = r.program("grid", SHOCKWAVE_VERTEX_SOURCE, SHOCKWAVE_FRAGMENT_SOURCE)
        uniforms = r.uniforms("grid", _UNIFORMS)
        vao, vertices = r.mesh(_mesh_key(cells), scene3d_grid_vertices(*cells), (2,))
        # An empty event list still binds one (unread) record.
        records = SHOCKWAVE_EVENTS.pack(events or [{"age": 0.0, "x": 0.0, "z": 0.0, "strength": 0.0}])
        target_frame = self._target_frame(frame, parameters)
        bloom = 1.4 * glow
        with self._target.scope(target_frame, samples, r, overlay=presentation.content_fade, bloom=bloom):
            gl.glUseProgram(program)
            gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
            gl.glUniform4f(uniforms["uField"], *field)
            gl.glUniform2f(uniforms["uView"], tilt, turn)
            gl.glUniform1f(uniforms["uCamera"], shockwave_camera(half_width))
            gl.glUniform2f(uniforms["uFit"], *self._fit)
            gl.glUniform1f(uniforms["uHalfWidth"], half_width)
            gl.glUniform1i(uniforms["uEventCount"], len(events))
            gl.glUniform2f(uniforms["uWave"],
                           shockwave_amplitude(float(parameter(parameters, "shockwave_grid_wave_height"))),
                           shockwave_wave_speed(float(parameter(parameters, "shockwave_grid_wave_speed"))))
            gl.glUniform1f(uniforms["uHorizon"], ridge)
            gl.glUniform2f(uniforms["uIdle"], *shockwave_idle(
                float(parameter(parameters, "shockwave_grid_wave_height")),
                float(parameter(parameters, "shockwave_grid_idle")), float(mode_state.animation_time), half_width))
            gl.glUniform1i(uniforms["uBarCount"], count)
            if count:
                gl.glUniform1fv(uniforms["uBars"], count, levels[:count])
            gl.glUniform1f(uniforms["uHeightScale"], float(parameter(parameters, "spectrum_height_scale")))
            gl.glUniform1f(uniforms["uCells"], 4.0 + 10.0 * float(parameter(parameters, "shockwave_grid_density")))
            gl.glUniform1f(uniforms["uScroll"], 0.6 * float(parameter(parameters, "shockwave_grid_scroll"))
                           * float(mode_state.animation_time))
            gl.glUniform4f(uniforms["uLineColor"], *rgba(parameter(parameters, "shockwave_grid_line_color")))
            gl.glUniform4f(uniforms["uCrestColor"], *rgba(parameter(parameters, "shockwave_grid_crest_color")))
            gl.glUniform1f(uniforms["uFloor"], float(parameter(parameters, "shockwave_grid_floor")))
            gl.glUniform1f(uniforms["uGlow"], glow)
            gl.glUniform1f(uniforms["uEdgePx"], 1.2 * max(1.0, scale))
            gl.glBindVertexArray(vao)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_TRUE)
            with self._stream.bound(gl.GL_SHADER_STORAGE_BUFFER, _EVENT_BINDING, records):
                with self._target.emission_writes():
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, vertices)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._stream.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        self._fit_key = None
        if errors:
            raise RuntimeError(" | ".join(errors))


def _mesh_key(cells: tuple[int, int]) -> str:
    return f"grid {cells[0]}x{cells[1]}"


def create_visualizer_renderer() -> QuickShockwaveGridRenderer:
    return QuickShockwaveGridRenderer()


__all__ = ["QuickShockwaveGridRenderer", "create_visualizer_renderer", "shockwave_quality"]
