"""Neon Lake Basin in the normal card, retaining the Shockwave mode identity.

One static mesh and authored height texture, the existing onset stream and lazy
SceneTarget draw reflected land then terrain/water. View pose never grows the
card target. Optional sky and bloom retire with this activation.
"""
from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import scene3d_detail, scene3d_grid_vertices
from rendering.gl_programs.neon_lake_basin_program import (
    NEON_VERTEX_SOURCE, NEON_FRAGMENT_SOURCE, NEON_SKY_VERTEX_SOURCE, NEON_SKY_FRAGMENT_SOURCE,
    basin_camera, basin_fit, basin_bounds,
)
from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_EVENTS, SHOCKWAVE_MAX_BARS, SHOCKWAVE_MAX_RIDGE, SHOCKWAVE_MAX_TILT, SHOCKWAVE_MAX_TURN,
    shockwave_amplitude, shockwave_event_records, shockwave_grid_cells, shockwave_half_width,
    shockwave_idle, shockwave_wave_speed,
)
from rendering.quick.scene3d.frame import item_pixel_rect
from rendering.quick.scene3d.heightfield import HeightfieldTexture
from rendering.quick.scene3d.resources import MeshResources, warm_programs
from rendering.quick.scene3d.stream import StreamRing
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs
from widgets.spotify_visualizer.render_state import ShockwaveGridFrame
from ..implementation_values import parameter, rgba
from ..render_contract import QuickVisualizerRenderFrame
from .spectrum import prepare_spectrum_shader_levels

_EVENT_BINDING, _HEIGHT_UNIT = 3, 4
_VIEW_UNIFORMS = ("uMatrix", "uField", "uView", "uCamera", "uFit", "uScenePose")
_UNIFORMS = _VIEW_UNIFORMS + (
    "uHalfWidth", "uEventCount", "uWave", "uHorizon", "uIdle", "uBarCount", "uBars", "uHeightScale",
    "uScroll", "uLineColor", "uCrestColor", "uWaterColor", "uFloor", "uGlow", "uEdgePx",
    "uTerrain", "uTerrainSize", "uLand", "uTime", "uWaterDetail", "uWaterBankBand", "uReflection", "uPass", "uCurveCells", "uTerrainGrowth",
)
_SKY_UNIFORMS = _VIEW_UNIFORMS + ("uSkyColor", "uSkyStrength", "uSunEnabled", "uSunColor")


def shockwave_quality(parameters) -> tuple[int, float, tuple[int, int]]:
    detail = scene3d_detail(parameter(parameters, "scene3d_detail"))
    glow = float(parameter(parameters, "shockwave_grid_glow")) if detail.post_effects else 0.0
    return detail.overlay_samples, glow, shockwave_grid_cells(detail.grid_cells)


class QuickShockwaveGridRenderer:
    mode_id = "shockwave_grid"

    def __init__(self) -> None:
        self._resources = MeshResources("Neon Lake Basin")
        self._target = SceneTarget("Neon Lake Basin")
        self._stream = StreamRing("Neon Lake Basin")
        self._heightfield = HeightfieldTexture("Neon Lake Basin", components=2)
        self._fit_key = None
        self._fit = (1.0, 0.5)
        self._terrain_data = None
        self._terrain_bounds = ()
        self._mesh_cells = None
        self._mesh_data = None

    def _mesh(self,cells):
        if cells != self._mesh_cells:
            if self._mesh_cells is not None:
                self._resources.drop_mesh(_mesh_key(self._mesh_cells))
            self._mesh_data = self._resources.mesh(_mesh_key(cells),scene3d_grid_vertices(*cells),(2,))
            self._mesh_cells = cells
        return self._mesh_data

    @property
    def has_resources(self) -> bool:
        return any(owner.has_resources for owner in (self._resources, self._target, self._stream, self._heightfield))

    def _view(self, frame, parameters):
        field = tuple(float(value) for value in frame.logical_content_rect)
        half_width = shockwave_half_width(field[2] / field[3])
        tilt = SHOCKWAVE_MAX_TILT * float(parameter(parameters, "shockwave_grid_tilt"))
        turn = SHOCKWAVE_MAX_TURN * float(parameter(parameters, "shockwave_grid_turn"))
        terrain = parameter(parameters, "shockwave_grid_terrain")
        if terrain["data"] is not self._terrain_data:
            self._terrain_bounds = basin_bounds(terrain["size"], terrain["data"])
            self._terrain_data = terrain["data"]
        maximum = max(0.19, float(terrain["maximum"])
                      * float(parameter(parameters, "shockwave_grid_terrain_height")) * 1.50)
        key = (tilt, turn, half_width, maximum, field[2] / field[3], id(self._terrain_data),
               float(parameter(parameters, "shockwave_grid_terrain_height")))
        if key != self._fit_key:
            self._fit = basin_fit(tilt, turn, half_width, maximum, field[2] / field[3], self._terrain_bounds,
                                  float(parameter(parameters, "shockwave_grid_terrain_height"))*1.50)
            self._fit_key = key
        return field, half_width, tilt, turn, maximum

    def _programs(self, parameters, samples, bloom):
        r = self._resources
        programs = [(r, "basin", NEON_VERTEX_SOURCE, NEON_FRAGMENT_SOURCE)]
        if bool(parameter(parameters, "shockwave_grid_sky_enabled")):
            programs.append((r, "sky", NEON_SKY_VERTEX_SOURCE, NEON_SKY_FRAGMENT_SOURCE))
        programs.extend((r, *program) for program in scene_target_programs(samples, bloom, False, overlay=True))
        return programs

    def prepare_step(self, frame: QuickVisualizerRenderFrame) -> bool:
        parameters = frame.snapshot.logical.mode_state.parameters
        samples, glow, cells = shockwave_quality(parameters)
        r = self._resources
        if not warm_programs(self._programs(parameters, samples, glow > 0.0)):
            return False
        if not r.has_mesh(_mesh_key(cells)):
            self._mesh(cells)
            return False
        if bool(parameter(parameters, "shockwave_grid_sky_enabled")) and not r.has_mesh("sky"):
            r.mesh("sky", scene3d_grid_vertices(1, 1), (2,))
            return False
        terrain = parameter(parameters, "shockwave_grid_terrain")
        uploads = self._heightfield.uploads
        self._heightfield.ensure(terrain["size"], terrain["data"])
        if self._heightfield.uploads != uploads:
            return False
        if not self._stream.warm():
            return False
        return self._target.warm(item_pixel_rect(frame)[2:], samples, overlay=True, bloom=glow > 0.0)

    def _bind_view(self, uniforms, frame, parameters, field, half_width, tilt, turn, maximum):
        gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
        gl.glUniform4f(uniforms["uField"], *field)
        gl.glUniform2f(uniforms["uView"], tilt, turn)
        gl.glUniform1f(uniforms["uCamera"], basin_camera(half_width, maximum))
        gl.glUniform2f(uniforms["uFit"], *self._fit)
        gl.glUniform3f(uniforms["uScenePose"],
                       float(parameter(parameters, "shockwave_grid_scene_scale")),
                       float(parameter(parameters, "shockwave_grid_scene_pan_x")),
                       float(parameter(parameters, "shockwave_grid_scene_pan_y")))

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        snapshot = frame.snapshot
        logical = snapshot.logical
        mode_state = logical.mode_state
        if not isinstance(mode_state, ShockwaveGridFrame):
            raise TypeError("Neon Lake Basin renderer received another mode frame")
        presentation = snapshot.presentation
        if presentation.content_fade <= 0.0:
            return
        if frame.content_rotation_quarters:
            raise ValueError("Neon Lake Basin does not offer content rotation")
        if frame.logical_content_rect[2] <= 0.0 or frame.logical_content_rect[3] <= 0.0:
            return
        parameters = mode_state.parameters
        field, half_width, tilt, turn, maximum = self._view(frame, parameters)
        count = min(SHOCKWAVE_MAX_BARS, int(logical.common.bar_count))
        levels, _peaks = prepare_spectrum_shader_levels(logical.common.bars, mode_state.peaks, bar_count=count)
        events = shockwave_event_records(tuple(mode_state.events), half_width)
        samples, glow, cells = shockwave_quality(parameters)
        r = self._resources
        program = r.program("basin", NEON_VERTEX_SOURCE, NEON_FRAGMENT_SOURCE)
        uniforms = r.uniforms("basin", _UNIFORMS)
        vao, vertices = self._mesh(cells)
        terrain = parameter(parameters, "shockwave_grid_terrain")
        self._heightfield.ensure(terrain["size"], terrain["data"])
        records = SHOCKWAVE_EVENTS.pack(events or [{"age": 0.0, "x": 0.0, "z": 0.0, "strength": 0.0}])
        with self._target.scope(frame, samples, r, overlay=presentation.content_fade, bloom=1.4 * glow):
            if bool(parameter(parameters, "shockwave_grid_sky_enabled")):
                sky = r.program("sky", NEON_SKY_VERTEX_SOURCE, NEON_SKY_FRAGMENT_SOURCE)
                sky_uniforms = r.uniforms("sky", _SKY_UNIFORMS)
                sky_vao, sky_count = r.mesh("sky", scene3d_grid_vertices(1, 1), (2,))
                gl.glUseProgram(sky)
                self._bind_view(sky_uniforms, frame, parameters, field, half_width, tilt, turn, maximum)
                gl.glUniform4f(sky_uniforms["uSkyColor"], *rgba(parameter(parameters, "shockwave_grid_sky_color")))
                gl.glUniform1f(sky_uniforms["uSkyStrength"], float(parameter(parameters, "shockwave_grid_sky_strength")))
                gl.glUniform1i(sky_uniforms["uSunEnabled"], int(bool(parameter(parameters,"shockwave_grid_sun_enabled"))))
                gl.glUniform4f(sky_uniforms["uSunColor"],*rgba(parameter(parameters,"shockwave_grid_sun_color")))
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_FALSE)
                gl.glBindVertexArray(sky_vao)
                with self._target.emission_writes():
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, sky_count)
            gl.glUseProgram(program)
            self._bind_view(uniforms, frame, parameters, field, half_width, tilt, turn, maximum)
            gl.glUniform1f(uniforms["uHalfWidth"], half_width)
            gl.glUniform1i(uniforms["uEventCount"], len(events))
            gl.glUniform2f(uniforms["uWave"], shockwave_amplitude(float(parameter(parameters, "shockwave_grid_wave_height"))),
                           shockwave_wave_speed(float(parameter(parameters, "shockwave_grid_wave_speed"))))
            gl.glUniform1f(uniforms["uHorizon"], SHOCKWAVE_MAX_RIDGE * float(parameter(parameters, "shockwave_grid_horizon")))
            gl.glUniform2f(uniforms["uIdle"], *shockwave_idle(
                float(parameter(parameters, "shockwave_grid_wave_height")), float(parameter(parameters, "shockwave_grid_idle")),
                float(mode_state.animation_time), half_width))
            gl.glUniform1i(uniforms["uBarCount"], count)
            if count:
                gl.glUniform1fv(uniforms["uBars"], count, levels[:count])
            gl.glUniform1f(uniforms["uHeightScale"], float(parameter(parameters, "spectrum_height_scale")))
            gl.glUniform1f(uniforms["uScroll"], 0.6 * float(parameter(parameters, "shockwave_grid_scroll")) * float(mode_state.animation_time))
            for uniform, key in (("uLineColor", "line_color"), ("uCrestColor", "crest_color"), ("uWaterColor", "water_color")):
                gl.glUniform4f(uniforms[uniform], *rgba(parameter(parameters, "shockwave_grid_" + key)))
            gl.glUniform1f(uniforms["uFloor"], float(parameter(parameters, "shockwave_grid_floor")))
            gl.glUniform1f(uniforms["uGlow"], glow)
            gl.glUniform1f(uniforms["uEdgePx"], 0.75 * frame.viewport[2]/frame.logical_size[0])
            gl.glUniform1f(uniforms["uCurveCells"], 12.0+40.0*float(parameter(parameters,"shockwave_grid_density")))
            gl.glUniform1fv(uniforms["uTerrainGrowth"],8,mode_state.terrain_growth)
            gl.glUniform1i(uniforms["uTerrain"], _HEIGHT_UNIT)
            gl.glUniform1i(uniforms["uTerrainSize"], terrain["size"])
            gl.glUniform3f(uniforms["uLand"], float(parameter(parameters, "shockwave_grid_terrain_height")),
                           float(parameter(parameters, "shockwave_grid_terrain_reactivity")),
                           float(parameter(parameters, "shockwave_grid_terrain_detail")))
            gl.glUniform1f(uniforms["uTime"], float(mode_state.animation_time))
            gl.glUniform1f(uniforms["uWaterDetail"], float(parameter(parameters, "shockwave_grid_water_detail")))
            gl.glUniform1f(uniforms["uWaterBankBand"], 2.5/min(cells))
            reflection = float(parameter(parameters, "shockwave_grid_water_reflection"))
            gl.glUniform1f(uniforms["uReflection"], reflection)
            gl.glBindVertexArray(vao)
            gl.glEnable(gl.GL_DEPTH_TEST)
            with self._heightfield.bound(_HEIGHT_UNIT), self._stream.bound(gl.GL_SHADER_STORAGE_BUFFER, _EVENT_BINDING, records):
                with self._target.emission_writes():
                    if reflection > 0.0 and tilt > 0.001:
                        gl.glDepthMask(gl.GL_FALSE)
                        gl.glUniform1i(uniforms["uPass"], 0)
                        gl.glDrawArrays(gl.GL_TRIANGLES, 0, vertices)
                    gl.glDepthMask(gl.GL_TRUE)
                    gl.glUniform1i(uniforms["uPass"], 1)
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, vertices)

    def release_resources(self) -> None:
        errors = []
        for release in (self._target.release, self._stream.release, self._heightfield.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        self._fit_key = None
        self._terrain_data = None
        self._terrain_bounds = ()
        self._mesh_cells = None
        self._mesh_data = None
        if errors:
            raise RuntimeError(" | ".join(errors))


def _mesh_key(cells: tuple[int, int]) -> str:
    return f"basin {cells[0]}x{cells[1]}"


def create_visualizer_renderer() -> QuickShockwaveGridRenderer:
    return QuickShockwaveGridRenderer()


__all__ = ["QuickShockwaveGridRenderer", "create_visualizer_renderer", "shockwave_quality"]
