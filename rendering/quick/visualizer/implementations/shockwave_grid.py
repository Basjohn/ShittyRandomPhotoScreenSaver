"""Neon Lake in the normal card, retaining the Shockwave mode identity.

One static mesh and authored height texture, the existing onset stream and lazy
SceneTarget draw reflected land then terrain/water. View pose never grows the
card target. Optional sky and bloom retire with this activation.
"""
from __future__ import annotations
from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale

import ctypes
import math
import zlib
from contextlib import contextmanager
from OpenGL import GL as gl

from rendering.gl_programs.scene3d import scene3d_detail, scene3d_grid_vertices
from rendering.gl_programs.neon_lake_basin_mesh import (
    BASIN_MESH_FINE_ROWS, BASIN_MESH_SUBDIVISION, NO_EXTENT, basin_mesh_vertices, basin_mesh_points, upload_bytes,
)
from rendering.gl_programs.neon_starscape import starscape_beat_cells
from rendering.quick import gl_query
from rendering.gl_programs.neon_lake_basin_program import (
    NEON_VERTEX_SOURCE, NEON_FRAGMENT_SOURCE, NEON_SKY_VERTEX_SOURCE, NEON_SKY_FRAGMENT_SOURCE,
    NEON_SKYLINE_VERTEX_SOURCE, NEON_SKYLINE_FRAGMENT_SOURCE,
    basin_pixel_scale, basin_view,
)
from rendering.gl_programs.neon_celestial import basin_body_position, celestial_placement
from rendering.gl_programs.neon_terrain_reaction import REACTION_SAMPLES, growth_cell_scale
from rendering.gl_programs.neon_lake_basin_options import (
    BASIN_BODY_MODES, BASIN_GROWTH_REGIONS, BASIN_SURFACE_STYLES,
)
from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_EVENTS, SHOCKWAVE_MAX_BARS, SHOCKWAVE_MAX_RIDGE,
    shockwave_amplitude, shockwave_event_records, shockwave_grid_cells, SHOCKWAVE_HALF_WIDTH,
    shockwave_idle, shockwave_wave_speed, shockwave_music_drive, shockwave_ridge_breath,
)
from rendering.quick.scene3d.frame import item_pixel_rect, orient_visualizer_scene_frame
from rendering.quick.scene3d.heightfield import HeightfieldTexture
from rendering.quick.scene3d.resources import MeshResources, warm_programs
from rendering.quick.scene3d.shafts import ShaftLight
from rendering.quick.scene3d.stream import StreamRing
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs
from widgets.spotify_visualizer.render_state import ShockwaveGridFrame
from ..implementation_values import parameter, rgba
from ..render_contract import QuickVisualizerRenderFrame
from .spectrum import prepare_spectrum_shader_levels

_EVENT_BINDING, _HEIGHT_UNIT, _OVERLAY_UNIT = 3, 4, 5
_VIEW_UNIFORMS = ("uMatrix", "uField", "uEye", "uRight", "uUp", "uBack", "uTan")
_REACTION_UNIFORMS = ("uReaction", "uReactionBands", "uReactionPhase", "uReactionMaximum", "uReactionLanes",
                      "uReactionBias", "uReactionForms", "uReactionDrives", "uGrowthPlace")
_CELESTIAL_UNIFORMS=("uBodyPosition","uBodySize","uBodyKind","uSunEnabled","uSunColor","uMoonColor",
                     "uMoonPhase","uSkyEnabled","uSkyColor","uSkyStrength","uStarColor","uStarGlowColor",
                     "uCloudColor","uHorizonColor","uClouds","uCloudDrift","uNebula","uNebulaTurn","uNebulaColorA","uNebulaColorB")
_UNIFORMS = _VIEW_UNIFORMS + (
    "uTerrainGrid", "uTerrainOrigin", "uHalfWidth", "uEventCount", "uWave", "uHorizon", "uIdle", "uBarCount", "uBars", "uHeightScale",
    "uScroll", "uLineColor", "uCrestColor", "uWaterColor", "uFloor", "uGlow", "uEdgePx",
    "uTerrain", "uTerrainDelta", "uTerrainSize", "uLand", "uTime", "uWaterDetail", "uWaterBankBand", "uReflection", "uPass", "uCurveCells",
    "uWireDisplay", "uMarks", "uPointPx","uTerrainFillColor","uVertexColor","uVertexAccentColor",
    "uVertexOutlineColor","uGlassTint","uGlass","uLightStrength","uSmoothGlass","uDepthOnly",
    "uWaterLineGlowColor","uWaterLineGlow","uWaterShine","uDepthScale","uShoreGlow","uShoreGlowColor","uContourLines",
    "uWaterGlint","uGlintLight","uWaterReact",
) + _CELESTIAL_UNIFORMS + _REACTION_UNIFORMS
_SKY_UNIFORMS = _VIEW_UNIFORMS + _CELESTIAL_UNIFORMS + (
    "uSkyPass","uShaftSpread","uMidband", "uBeatPulse", "uCelestialGlow", "uCelestialRimVertices", "uBeatStarCount", "uBeatStarCells", "uStarGlow",
    "uTerrainGrid", "uTerrainOrigin", "uHalfWidth", "uLand")
_SKYLINE_UNIFORMS = _VIEW_UNIFORMS + (
    "uTerrainGrid", "uTerrainOrigin", "uHalfWidth", "uTerrain", "uTerrainDelta", "uTerrainSize", "uLand", "uEventCount",
    "uCrestColor", "uGlow", "uMidband", "uOutlineLiftNdc", "uHorizonThickness", "uDepthScale") + _REACTION_UNIFORMS




def shockwave_quality(parameters) -> tuple[int, float, tuple[int, int]]:
    detail = scene3d_detail(parameter(parameters, "scene3d_detail"))
    glow = float(parameter(parameters, "shockwave_grid_glow")) if detail.post_effects else 0.0
    cells=shockwave_grid_cells(detail.grid_cells)
    if _wire_display(parameters)&2:
        frequency=12.0+40.0*float(parameter(parameters,"shockwave_grid_density"))
        cells=(max(cells[0],math.ceil(frequency*1.5)),max(cells[1],math.ceil(frequency)))
        # Ten percent more vertices by area; keep marks on the same surface
        # lattice rather than introducing a second approximation/depth owner.
        cells=tuple(round(value*math.sqrt(1.10)) for value in cells)
    return detail.overlay_samples, glow, cells


def basin_water_bank_band(cells: tuple[int, int]) -> float:
    """Join the bank within one mesh cell without flattening a broad water strip."""
    return 0.5/min(cells)


class QuickShockwaveGridRenderer:
    mode_id = "shockwave_grid"

    def __init__(self) -> None:
        self._resources = MeshResources("Neon Lake")
        self._target = SceneTarget("Neon Lake")
        self._stream = StreamRing("Neon Lake")
        self._heightfield = HeightfieldTexture("Neon Lake", components=2)
        self._terrain_data = None
        self._mesh_cells = None
        self._mesh_data = None
        self._points_cells = None
        self._points_data = None
        self._lattice_extent = NO_EXTENT
        self._lattice_reach = None
        self._overlay = HeightfieldTexture("Neon Lake overlay", components=1)
        self._terrain_origin = (0.0, 0.0, 1.0, 1.0)
        self._terrain_grid = (0.0, 0.0, 1.0)

    def _mesh(self,cells):
        cells = (tuple(cells), self._lattice_extent, self._lattice_reach)
        if cells != self._mesh_cells:
            if self._mesh_cells is not None:
                self._resources.drop_mesh(_mesh_key(self._mesh_cells))
            # Built for this upload alone (float32 bytes): the uploaded mesh is the only copy kept.
            self._mesh_data = self._resources.mesh(
                _mesh_key(cells), upload_bytes(basin_mesh_vertices(*cells[:2], BASIN_MESH_SUBDIVISION,
                                                                   BASIN_MESH_FINE_ROWS, cells[2])), (2,))
            self._mesh_cells = cells
        return self._mesh_data

    def _points(self, cells):
        cells = (tuple(cells), self._lattice_extent)        # the marks stay on the origin's lattice
        if cells != self._points_cells:
            self._drop_points()
            self._points_data=self._resources.mesh(_point_key(cells),upload_bytes(basin_mesh_points(*cells)),(2,))
            self._points_cells=cells
        return self._points_data

    def _drop_points(self):
        if self._points_cells is not None:
            self._resources.drop_mesh(_point_key(self._points_cells))
            self._points_cells=None
            self._points_data=None

    @property
    def has_resources(self) -> bool:
        return any(owner.has_resources for owner in (self._resources, self._target, self._stream, self._heightfield,
                                                     self._overlay))

    def _adopt_terrain(self, terrain) -> None:
        """The authored origin's reach past the basin (the mark lattice), the tiles the brush has painted past it
        (the triangles' fine region; None while nothing is), the basin-to-grid transform and the origin's rect in
        grid uv."""
        self._lattice_extent = tuple(float(v) for v in terrain.get("extent", NO_EXTENT))
        painted = terrain.get("painted")
        self._lattice_reach = (None if not painted
                               else tuple(tuple(float(v) for v in tile) for tile in painted))
        self._terrain_grid = tuple(float(v) for v in terrain.get("grid", (0.0, 0.0, 1.0)))
        self._terrain_origin = tuple(float(v) for v in terrain.get("origin_rect", (0.0, 0.0, 1.0, 1.0)))

    def _ensure_heightfields(self, terrain) -> None:
        """The stored cells, and for a grown grid its overlay on the generated land (dropped again otherwise)."""
        self._heightfield.ensure(terrain["size"], terrain["data"])
        delta = terrain.get("delta")
        if delta is not None:
            self._overlay.ensure(terrain["size"], delta)
        elif self._overlay.has_resources:
            self._overlay.release()

    @staticmethod
    def _overlay_unit(terrain) -> int:
        # An ungrown grid never reads the overlay: its sampler rests on the stored cells' unit.
        return _OVERLAY_UNIT if terrain.get("delta") is not None else _HEIGHT_UNIT

    @contextmanager
    def _overlay_bound(self, terrain):
        if terrain.get("delta") is None:
            yield
            return
        with self._overlay.bound(_OVERLAY_UNIT):
            yield

    def _view(self, frame, parameters):
        field = tuple(float(value) for value in frame.logical_content_rect)
        half_width = SHOCKWAVE_HALF_WIDTH
        terrain = parameter(parameters, "shockwave_grid_terrain")
        if terrain["data"] is not self._terrain_data:
            self._terrain_data = terrain["data"]
        maximum = max(0.19, float(terrain["maximum"])
                      * float(parameter(parameters, "shockwave_grid_terrain_height")) * 1.50)
        return field, half_width, basin_view(parameters, field,
            aperture_scale=framed_aperture_scale(frame.snapshot.presentation, content=True)), maximum

    def _programs(self, parameters, samples, bloom, rotation=0):
        r = self._resources
        programs = [(r, "basin", NEON_VERTEX_SOURCE, NEON_FRAGMENT_SOURCE),
                    (r, "skyline", NEON_SKYLINE_VERTEX_SOURCE, NEON_SKYLINE_FRAGMENT_SOURCE)]
        if _sky_admitted(parameters):
            programs.append((r, "sky", NEON_SKY_VERTEX_SOURCE, NEON_SKY_FRAGMENT_SOURCE))
        programs.extend((r, *program) for program in scene_target_programs(samples, bloom, False, overlay=True,
                                                                           shafts=_rays_admitted(parameters), rotation=rotation))
        return programs

    def prepare_step(self, frame: QuickVisualizerRenderFrame) -> bool:
        frame = orient_visualizer_scene_frame(frame)
        parameters = frame.snapshot.logical.mode_state.parameters
        samples, glow, cells = shockwave_quality(parameters)
        r = self._resources
        if not warm_programs(self._programs(parameters, samples, glow > 0.0, frame.scene_output_rotation)):
            return False
        self._adopt_terrain(parameter(parameters, "shockwave_grid_terrain"))
        if not r.has_mesh(_mesh_key((tuple(cells), self._lattice_extent, self._lattice_reach))):
            self._mesh(cells)
            return False
        style=_wire_display(parameters)
        if style&2:
            prior=self._points_cells
            self._points(cells)
            if prior != self._points_cells:
                return False
        elif self._points_cells is not None:
            self._drop_points()
            return False
        if _sky_admitted(parameters) and not r.has_mesh("sky"):
            r.mesh("sky", scene3d_grid_vertices(1, 1), (2,))
            return False
        terrain = parameter(parameters, "shockwave_grid_terrain")
        uploads = self._heightfield.uploads + self._overlay.uploads
        self._ensure_heightfields(terrain)
        if self._heightfield.uploads + self._overlay.uploads != uploads:
            return False
        if not self._stream.warm():
            return False
        return self._target.warm(item_pixel_rect(frame)[2:], samples, overlay=True, bloom=glow > 0.0,
                                 shafts=_rays_admitted(parameters))

    def _bind_view(self, uniforms, frame, view):
        if "uTerrainGrid" in uniforms:          # programs that read the terrain
            gl.glUniform3f(uniforms["uTerrainGrid"], *self._terrain_grid)
            gl.glUniform4f(uniforms["uTerrainOrigin"], *self._terrain_origin)
        gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
        gl.glUniform4f(uniforms["uField"], *view.field)
        gl.glUniform3f(uniforms["uEye"], *view.eye)
        gl.glUniform3f(uniforms["uRight"], *view.right)
        gl.glUniform3f(uniforms["uUp"], *view.up)
        gl.glUniform3f(uniforms["uBack"], *view.back)
        gl.glUniform2f(uniforms["uTan"], *view.tan)

    @staticmethod
    def _bind_wave(uniforms, parameters, mode_state, half_width) -> None:
        """The lake's travelling waves and idle swell (``shockwaveHeight``)."""
        gl.glUniform2f(uniforms["uWave"], shockwave_amplitude(float(parameter(parameters, "shockwave_grid_wave_height"))),
                       shockwave_wave_speed(float(parameter(parameters, "shockwave_grid_wave_speed"))))
        gl.glUniform2f(uniforms["uIdle"], *shockwave_idle(
            float(parameter(parameters, "shockwave_grid_wave_height")), float(parameter(parameters, "shockwave_grid_idle")),
            float(mode_state.animation_time), half_width))

    @staticmethod
    def _bind_reaction(uniforms, parameters, mode_state, terrain) -> None:
        """Terrain Reaction for a program sampling the land height: amounts, lane drives, phase, the
        shaper's baked elevation tables, and Growth / Indents with their drives (strength 0 turns the
        shader's reaction off; an amount of 0 its landforms)."""
        reaction = _reaction_vector(parameters)
        if not (mode_state.events or any(mode_state.terrain_bands) or any(mode_state.terrain_forms)):
            # Nothing drives the land this frame (silence, no wave alive): every term is zero, so the shader is
            # told the reaction is off and skips its work per vertex instead of computing zeros.
            reaction = (0.0, *reaction[1:])
        gl.glUniform4f(uniforms["uReaction"], *reaction)
        gl.glUniform1fv(uniforms["uReactionBands"], len(mode_state.terrain_bands), mode_state.terrain_bands)
        gl.glUniform1f(uniforms["uReactionPhase"], float(mode_state.terrain_phase))
        gl.glUniform1f(uniforms["uReactionMaximum"], float(terrain["maximum"]))
        lanes, bias = _reaction_tables(parameter(parameters, "shockwave_grid_terrain_shaper"))
        gl.glUniform1fv(uniforms["uReactionLanes"], 5 * REACTION_SAMPLES, lanes)
        gl.glUniform1fv(uniforms["uReactionBias"], REACTION_SAMPLES, bias)
        gl.glUniform4f(uniforms["uReactionForms"],
                       reaction[0] * float(parameter(parameters, "shockwave_grid_terrain_growth")),
                       float(parameter(parameters, "shockwave_grid_terrain_growth_shape")),
                       reaction[0] * float(parameter(parameters, "shockwave_grid_terrain_indents")), 0.0)
        gl.glUniform2f(uniforms["uReactionDrives"], *mode_state.terrain_forms)
        # Growth Density as the site cell's scale (1 at the usual) and Growth Region (0 everywhere: no weighting).
        gl.glUniform2f(uniforms["uGrowthPlace"],
                       growth_cell_scale(parameter(parameters, "shockwave_grid_terrain_growth_density")),
                       float(BASIN_GROWTH_REGIONS.get(str(parameter(parameters, "shockwave_grid_terrain_growth_region")),
                                                      0)))

    @staticmethod
    def _bind_celestial(uniforms,parameters,half_width,animation_time,view):
        authored=basin_body_position(*(float(parameter(parameters,"shockwave_grid_sun_"+axis)) for axis in "xyz"),
                                     half_width,float(animation_time),bool(parameter(parameters,"shockwave_grid_sun_orbit_enabled")),
                                     float(parameter(parameters,"shockwave_grid_sun_orbit_speed")))
        # At infinity: a fixed direction and apparent size, whatever the camera does.
        position,size=celestial_placement(authored,float(parameter(parameters,"shockwave_grid_sun_size")),view.eye)
        gl.glUniform3f(uniforms["uBodyPosition"],*position)
        gl.glUniform1f(uniforms["uBodySize"],size)
        gl.glUniform1i(uniforms["uBodyKind"],BASIN_BODY_MODES[str(parameter(parameters,"shockwave_grid_sun_mode"))])
        gl.glUniform1i(uniforms["uSunEnabled"],int(bool(parameter(parameters,"shockwave_grid_sun_enabled"))))
        gl.glUniform1f(uniforms["uMoonPhase"],float(parameter(parameters,"shockwave_grid_moon_phase")))
        gl.glUniform1i(uniforms["uSkyEnabled"],int(bool(parameter(parameters,"shockwave_grid_sky_enabled"))))
        gl.glUniform1f(uniforms["uSkyStrength"],float(parameter(parameters,"shockwave_grid_sky_strength")))
        for uniform,key in (("uSunColor","sun_color"),("uMoonColor","moon_color"),("uSkyColor","sky_color"),
                            ("uStarColor","star_color"),("uStarGlowColor","star_glow_color"),
                            ("uCloudColor","cloud_color"),("uHorizonColor","horizon_color"),
                            ("uNebulaColorA","nebula_color_a"),("uNebulaColorB","nebula_color_b")):
            gl.glUniform4f(uniforms[uniform],*rgba(parameter(parameters,"shockwave_grid_"+key)))
        clouds=bool(parameter(parameters,"shockwave_grid_volumetric_clouds"))
        gl.glUniform4f(uniforms["uClouds"],*(float(parameter(parameters,"shockwave_grid_cloud_"+part))
                                             for part in ("coverage","softness","scale")),
                       float(parameter(parameters,"shockwave_grid_cloud_opacity")) if clouds else 0.0)
        drift=0.03*float(parameter(parameters,"shockwave_grid_cloud_drift"))*float(animation_time)
        gl.glUniform2f(uniforms["uCloudDrift"],drift,0.37*drift)
        gl.glUniform4f(uniforms["uNebula"],float(parameter(parameters,"shockwave_grid_nebula_intensity"))
                       if bool(parameter(parameters,"shockwave_grid_nebula_enabled")) else 0.0,
                       *(float(parameter(parameters,"shockwave_grid_nebula_"+part))
                         for part in ("scale","filaments","dust")))
        gl.glUniform1f(uniforms["uNebulaTurn"],2.0*math.pi*float(parameter(parameters,"shockwave_grid_nebula_position"))
                       +0.004*float(parameter(parameters,"shockwave_grid_nebula_drift"))*float(animation_time))
        return position,size

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        frame = orient_visualizer_scene_frame(frame)
        snapshot = frame.snapshot
        logical = snapshot.logical
        mode_state = logical.mode_state
        if not isinstance(mode_state, ShockwaveGridFrame):
            raise TypeError("Neon Lake renderer received another mode frame")
        presentation = snapshot.presentation
        if presentation.content_fade <= 0.0:
            return
        if frame.logical_content_rect[2] <= 0.0 or frame.logical_content_rect[3] <= 0.0:
            return
        parameters = mode_state.parameters
        field, half_width, view, maximum = self._view(frame, parameters)
        count = min(SHOCKWAVE_MAX_BARS, int(logical.common.bar_count))
        levels, _peaks = prepare_spectrum_shader_levels(logical.common.bars, mode_state.peaks, bar_count=count)
        events = shockwave_event_records(tuple(mode_state.events), half_width)
        # Existing capture bars, not a new vocal detector, clock or DSP pipeline.
        low, high = count // 4, max(count // 4 + 1, count * 3 // 5)
        presence = levels[low:high]
        midband = max(0.0, min(1.0, sum(presence) / len(presence))) if presence else 0.0
        # One envelope sampled from the existing captured onset ring, not a new
        # clock, DSP lane, or frame-rate-dependent accumulator.
        beat_pulse = max((min(1.0, strength) * math.exp(-age * 2.8)
                          for age, _x, _z, strength in mode_state.events if age >= 0.0), default=0.0)
        samples, glow, cells = shockwave_quality(parameters)
        style=_wire_display(parameters)
        water_amount = max(0.0, min(1.0, float(parameter(parameters, "shockwave_grid_water_reaction"))))
        music_drive = shockwave_music_drive(mode_state.events) if water_amount > 0.0 else 0.0
        r = self._resources
        program = r.program("basin", NEON_VERTEX_SOURCE, NEON_FRAGMENT_SOURCE)
        uniforms = r.uniforms("basin", _UNIFORMS)
        skyline_program = r.program("skyline", NEON_SKYLINE_VERTEX_SOURCE, NEON_SKYLINE_FRAGMENT_SOURCE)
        skyline_uniforms = r.uniforms("skyline", _SKYLINE_UNIFORMS)
        self._adopt_terrain(parameter(parameters, "shockwave_grid_terrain"))
        vao, vertices = self._mesh(cells)
        terrain = parameter(parameters, "shockwave_grid_terrain")
        self._ensure_heightfields(terrain)
        records = SHOCKWAVE_EVENTS.pack(events or [{"age": 0.0, "x": 0.0, "z": 0.0, "strength": 0.0}])
        with self._target.scope(frame, samples, r, overlay=presentation.content_fade, bloom=1.4 * glow,
                                shafts=_rays_admitted(parameters)), _scene_depth(), \
                self._heightfield.bound(_HEIGHT_UNIT), self._overlay_bound(terrain):
            sky=None
            if _sky_admitted(parameters):
                sky = r.program("sky", NEON_SKY_VERTEX_SOURCE, NEON_SKY_FRAGMENT_SOURCE)
                sky_uniforms = r.uniforms("sky", _SKY_UNIFORMS)
                sky_vao, sky_count = r.mesh("sky", scene3d_grid_vertices(1, 1), (2,))
                gl.glUseProgram(sky)
                self._bind_view(sky_uniforms, frame, view)
                body_position, body_size = self._bind_celestial(sky_uniforms,parameters,half_width,
                                                                mode_state.animation_time,view)
                gl.glUniform1f(sky_uniforms["uMidband"],midband)
                # The horizon glow rises from the land's own horizon (basinHorizonElevation reads the distant land).
                gl.glUniform1f(sky_uniforms["uHalfWidth"],half_width)
                gl.glUniform2f(sky_uniforms["uLand"],float(parameter(parameters,"shockwave_grid_terrain_height")),
                               float(parameter(parameters,"shockwave_grid_terrain_detail")))
                gl.glUniform1i(sky_uniforms["uCelestialRimVertices"],
                               int(bool(parameter(parameters,"shockwave_grid_celestial_rim_vertices"))))
                gl.glUniform1f(sky_uniforms["uBeatPulse"],beat_pulse)
                gl.glUniform2f(sky_uniforms["uCelestialGlow"],
                               float(parameter(parameters,"shockwave_grid_celestial_glow_strength"))
                               if bool(parameter(parameters,"shockwave_grid_celestial_glow_enabled")) else 0.0,
                               float(parameter(parameters,"shockwave_grid_celestial_glow_reactivity")))
                gl.glUniform3f(sky_uniforms["uStarGlow"],
                               float(parameter(parameters,"shockwave_grid_star_glow_strength")),
                               float(parameter(parameters,"shockwave_grid_star_glow_reactivity")),
                               float(parameter(parameters,"shockwave_grid_star_size")))
                star_bursts = starscape_beat_cells(
                    mode_state.events, view,
                    terrain=(terrain["size"],terrain["data"],half_width,
                             float(parameter(parameters,"shockwave_grid_terrain_height")),
                             tuple(terrain.get("grid", (0.0, 0.0, 1.0)))),
                    body=(*body_position,body_size)
                         if bool(parameter(parameters,"shockwave_grid_sun_enabled"))
                         and rgba(parameter(parameters,"shockwave_grid_"+
                             ("moon_color" if str(parameter(parameters,"shockwave_grid_sun_mode"))=="Moon" else "sun_color")))[3]>0.0
                         else None,
                ) if bool(parameter(parameters, "shockwave_grid_starscape_beat")) else ()
                gl.glUniform1i(sky_uniforms["uBeatStarCount"], len(star_bursts))
                if star_bursts:
                    gl.glUniform4fv(sky_uniforms["uBeatStarCells"], len(star_bursts),
                                    tuple(value for item in star_bursts for value in item))
                # Sky is composited AFTER a depth-only terrain admission. Otherwise
                # transparent/glass terrain lets distant stars bleed through land.
            gl.glUseProgram(program)
            self._bind_view(uniforms, frame, view)
            self._bind_celestial(uniforms,parameters,half_width,mode_state.animation_time,view)
            gl.glUniform1f(uniforms["uHalfWidth"], half_width)
            gl.glUniform1i(uniforms["uEventCount"], len(events))
            self._bind_wave(uniforms, parameters, mode_state, half_width)
            gl.glUniform1f(uniforms["uHorizon"], SHOCKWAVE_MAX_RIDGE * float(parameter(parameters, "shockwave_grid_horizon")))
            gl.glUniform1i(uniforms["uBarCount"], count)
            if count:
                gl.glUniform1fv(uniforms["uBars"], count, levels[:count])
            gl.glUniform1f(uniforms["uHeightScale"], float(parameter(parameters, "spectrum_height_scale")))
            gl.glUniform1f(uniforms["uScroll"], 0.6 * float(parameter(parameters, "shockwave_grid_scroll")) * float(mode_state.animation_time))
            for uniform, key in (("uLineColor", "line_color"), ("uCrestColor", "crest_color"), ("uWaterColor", "water_color")):
                gl.glUniform4f(uniforms[uniform], *rgba(parameter(parameters, "shockwave_grid_" + key)))
            gl.glUniform1f(uniforms["uFloor"], float(parameter(parameters, "shockwave_grid_floor")))
            gl.glUniform1f(uniforms["uGlow"], glow)
            gl.glUniform4f(uniforms["uWaterLineGlowColor"], *rgba(parameter(parameters, "shockwave_grid_water_line_glow_color")))
            gl.glUniform1f(uniforms["uWaterLineGlow"], float(parameter(parameters, "shockwave_grid_water_line_glow")))
            gl.glUniform1f(uniforms["uWaterShine"], float(parameter(parameters, "shockwave_grid_water_shine")))
            depth_scale = float(parameter(parameters, "shockwave_grid_depth_scale"))
            gl.glUniform1f(uniforms["uDepthScale"], depth_scale)
            gl.glUniform1f(uniforms["uShoreGlow"], float(parameter(parameters, "shockwave_grid_shore_glow")))
            gl.glUniform4f(uniforms["uShoreGlowColor"], *rgba(parameter(parameters, "shockwave_grid_shore_glow_color")))
            gl.glUniform1f(uniforms["uWaterGlint"], float(parameter(parameters, "shockwave_grid_water_glint")))
            gl.glUniform1f(uniforms["uContourLines"], float(parameter(parameters, "shockwave_grid_contour_lines")))
            # The glint brightens with the halo's own musical drive (existing midband and onset envelope).
            gl.glUniform4f(uniforms["uGlintLight"], *_halo_light(parameters), midband, beat_pulse)
            # Water Reaction reads the admitted waves (fixed real-music scale), not the pinned display bars.
            gl.glUniform1f(uniforms["uWaterReact"], water_amount * music_drive)
            # fwidth already measures physical fragments, including DPR/MSAA.
            gl.glUniform1f(uniforms["uEdgePx"], 0.75)
            gl.glUniform1f(uniforms["uCurveCells"], 12.0+40.0*float(parameter(parameters,"shockwave_grid_density")))
            gl.glUniform1i(uniforms["uWireDisplay"],style)
            gl.glUniform1i(uniforms["uMarks"],0)
            for uniform,key in (("uTerrainFillColor","terrain_fill_color"),("uVertexColor","vertex_color"),
                                ("uVertexAccentColor","vertex_accent_color"),("uVertexOutlineColor","vertex_outline_color"),
                                ("uGlassTint","glass_tint")):
                gl.glUniform4f(uniforms[uniform],*rgba(parameter(parameters,"shockwave_grid_"+key)))
            gl.glUniform2f(uniforms["uGlass"],float(parameter(parameters,"shockwave_grid_glass_strength")),
                           float(parameter(parameters,"shockwave_grid_glass_roughness")))
            gl.glUniform1i(uniforms["uSmoothGlass"],int(bool(style&4)
                           and float(parameter(parameters,"shockwave_grid_glass_strength"))>0.0
                           and rgba(parameter(parameters,"shockwave_grid_glass_tint"))[3]>0.0))
            light_strength=float(parameter(parameters,"shockwave_grid_sun_rays_strength")) if _rays_admitted(parameters) else 0.0
            gl.glUniform1f(uniforms["uLightStrength"],light_strength)
            self._bind_reaction(uniforms, parameters, mode_state, terrain)
            gl.glUniform1i(uniforms["uTerrain"], _HEIGHT_UNIT)
            gl.glUniform1i(uniforms["uTerrainDelta"], self._overlay_unit(terrain))
            gl.glUniform1i(uniforms["uTerrainSize"], terrain["size"])
            gl.glUniform2f(uniforms["uLand"], float(parameter(parameters, "shockwave_grid_terrain_height")),
                           float(parameter(parameters, "shockwave_grid_terrain_detail")))
            gl.glUniform1f(uniforms["uTime"], float(mode_state.animation_time))
            gl.glUniform1f(uniforms["uWaterDetail"], float(parameter(parameters, "shockwave_grid_water_detail")))
            gl.glUniform1f(uniforms["uWaterBankBand"], basin_water_bank_band(cells))
            reflection = float(parameter(parameters, "shockwave_grid_water_reflection"))
            gl.glUniform1f(uniforms["uReflection"], reflection)
            gl.glBindVertexArray(vao)
            gl.glEnable(gl.GL_DEPTH_TEST)
            with self._stream.bound(gl.GL_SHADER_STORAGE_BUFFER, _EVENT_BINDING, records):
                with self._target.emission_writes():
                    body_enabled=bool(parameter(parameters,"shockwave_grid_sun_enabled"))
                    depth_prepared = body_enabled or bool(parameter(parameters,"shockwave_grid_sky_enabled"))
                    if bool(parameter(parameters,"shockwave_grid_sky_enabled")):
                        # First establish the same sky continuously across the
                        # entire card. The terrain prepass subtracts only its
                        # opaque coverage, smoothly across its outer fade.
                        gl.glUseProgram(sky)
                        gl.glUniform1i(sky_uniforms["uSkyPass"],0)
                        gl.glDisable(gl.GL_DEPTH_TEST)
                        gl.glDepthMask(gl.GL_FALSE)
                        gl.glBindVertexArray(sky_vao)
                        gl.glDrawArrays(gl.GL_TRIANGLES,0,sky_count)
                        gl.glEnable(gl.GL_DEPTH_TEST)
                    if depth_prepared:
                        gl.glUseProgram(program)
                        gl.glUniform1i(uniforms["uDepthOnly"],1)
                        gl.glUniform1i(uniforms["uMarks"],0)
                        gl.glUniform1i(uniforms["uPass"],1)
                        gl.glDepthFunc(gl.GL_LESS)
                        gl.glDepthMask(gl.GL_TRUE)
                        gl.glBindVertexArray(vao)
                        with _terrain_sky_occlusion_blend(glow > 0.0):
                            gl.glDrawArrays(gl.GL_TRIANGLES,0,vertices)
                    gl.glUseProgram(program)
                    gl.glUniform1i(uniforms["uDepthOnly"],0)
                    self._draw_scene(frame,uniforms,vao,vertices,cells,style,
                                     reflection>0.0 and view.eye[1]>0.001,depth_prepared=depth_prepared)
                    # Screen-space displacement of the exact terrain triangles.
                    # The unshifted surface depth rejects internal colour, leaving
                    # a narrow ridge line against sky (never projected-column boxes).
                    gl.glUseProgram(skyline_program)
                    self._bind_view(skyline_uniforms,frame,view)
                    gl.glUniform1f(skyline_uniforms["uHalfWidth"],half_width)
                    gl.glUniform1i(skyline_uniforms["uTerrain"],_HEIGHT_UNIT)
                    gl.glUniform1i(skyline_uniforms["uTerrainDelta"],self._overlay_unit(terrain))
                    gl.glUniform1i(skyline_uniforms["uTerrainSize"],terrain["size"])
                    gl.glUniform2f(skyline_uniforms["uLand"],
                                   float(parameter(parameters,"shockwave_grid_terrain_height")),
                                   float(parameter(parameters,"shockwave_grid_terrain_detail")))
                    gl.glUniform1i(skyline_uniforms["uEventCount"],len(events))
                    self._bind_reaction(skyline_uniforms, parameters, mode_state, terrain)
                    gl.glUniform4f(skyline_uniforms["uCrestColor"],
                                   *rgba(parameter(parameters,"shockwave_grid_crest_color")))
                    gl.glUniform1f(skyline_uniforms["uGlow"],glow)
                    gl.glUniform1f(skyline_uniforms["uMidband"],
                                   shockwave_ridge_breath(midband, music_drive, water_amount))
                    gl.glUniform1f(skyline_uniforms["uOutlineLiftNdc"], 2.0 / max(frame.viewport[3],1))
                    gl.glUniform1f(skyline_uniforms["uHorizonThickness"],
                                   float(parameter(parameters,"shockwave_grid_horizon_thickness")))
                    gl.glUniform1f(skyline_uniforms["uDepthScale"],depth_scale)
                    gl.glEnable(gl.GL_DEPTH_TEST)
                    gl.glDepthFunc(gl.GL_LEQUAL)
                    gl.glDepthMask(gl.GL_FALSE)
                    gl.glBindVertexArray(vao)
                    gl.glDrawArrays(gl.GL_TRIANGLES,0,vertices)
                    if body_enabled:
                        # Translucent bodies and their antialiased limbs blend
                        # over the completed surface while retaining 3D depth.
                        gl.glUseProgram(sky)
                        gl.glUniform1i(sky_uniforms["uSkyPass"],2)
                        gl.glEnable(gl.GL_DEPTH_TEST)
                        gl.glDepthFunc(gl.GL_LEQUAL)
                        gl.glDepthMask(gl.GL_FALSE)
                        gl.glBindVertexArray(sky_vao)
                        gl.glDrawArrays(gl.GL_TRIANGLES,0,sky_count)
                    if _rays_admitted(parameters):
                        light = _shaft_light(parameters, view,
                                             body_position)
                        if light is not None:
                            # The light's source, behind everything already drawn; the shared shafts
                            # pass turns it into rays at the end of the scope.
                            gl.glUseProgram(sky)
                            gl.glUniform1i(sky_uniforms["uSkyPass"],3)
                            gl.glUniform1f(sky_uniforms["uShaftSpread"],
                                           float(parameter(parameters,"shockwave_grid_sun_rays_spread")))
                            gl.glEnable(gl.GL_DEPTH_TEST)
                            gl.glDepthFunc(gl.GL_LEQUAL)
                            gl.glDepthMask(gl.GL_FALSE)
                            gl.glBindVertexArray(sky_vao)
                            with self._target.shaft_writes():
                                gl.glDrawArrays(gl.GL_TRIANGLES,0,sky_count)
                            self._target.set_shaft_light(light)

    def _draw_scene(self,frame,uniforms,vao,vertices,cells,style,reflections,*,depth_prepared=False):
        points=self._points(cells) if style&2 else None
        if not style&2 and self._points_cells is not None:
            self._drop_points()
        point_size_enabled=bool(gl.glIsEnabled(gl.GL_PROGRAM_POINT_SIZE)) if points else False
        try:
            if points:
                gl.glEnable(gl.GL_PROGRAM_POINT_SIZE)
                diameter=1.9 if style&4 else (2.1 if style==2 else 1.7)
                # Keep every authored mark. The item's actual projection owns
                # physical scaling; whole-window/card ratios and population
                # culling cannot thin the field or erase its emission.
                gl.glUniform1f(uniforms["uPointPx"],diameter*basin_pixel_scale(frame.matrix_values,frame.viewport))
            if reflections:
                if depth_prepared:
                    # Mirrors are composed below the later visible surface,
                    # as when its depth buffer was initially clear.
                    gl.glDepthFunc(gl.GL_ALWAYS)
                gl.glDepthMask(gl.GL_FALSE)
                gl.glUniform1i(uniforms["uPass"],0)
                gl.glDrawArrays(gl.GL_TRIANGLES,0,vertices)
                if points:
                    self._draw_points(uniforms,points,0,depth_function=gl.GL_ALWAYS if depth_prepared else gl.GL_LEQUAL)
            if depth_prepared:
                gl.glDepthFunc(gl.GL_LEQUAL)
            elif points and reflections:
                gl.glDepthFunc(gl.GL_LESS)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glUniform1i(uniforms["uMarks"],0)
            gl.glUniform1i(uniforms["uPass"],1)
            gl.glBindVertexArray(vao)
            gl.glDrawArrays(gl.GL_TRIANGLES,0,vertices)
            if points:
                gl.glDepthMask(gl.GL_FALSE)
                self._draw_points(uniforms,points,1)
        finally:
            if points:
                gl.glDepthFunc(gl.GL_LESS)
                if not point_size_enabled:
                    gl.glDisable(gl.GL_PROGRAM_POINT_SIZE)

    @staticmethod
    def _draw_points(uniforms,points,pass_id,*,depth_function=gl.GL_LEQUAL):
        gl.glDepthFunc(depth_function)
        gl.glUniform1i(uniforms["uMarks"],1)
        gl.glUniform1i(uniforms["uPass"],pass_id)
        gl.glBindVertexArray(points[0])
        gl.glDrawArrays(gl.GL_POINTS,0,points[1])

    def release_resources(self) -> None:
        errors = []
        for release in (self._target.release, self._stream.release, self._heightfield.release, self._overlay.release,
                        self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        self._terrain_data = None
        self._mesh_cells = None
        self._mesh_data = None
        self._points_cells = None
        self._points_data = None
        if errors:
            raise RuntimeError(" | ".join(errors))


def _mesh_key(lattice) -> str:
    (columns, rows), extent, reach = lattice
    # Painted tiles (up to 256 of them): named by their count and a digest of their exact bounds.
    grown = ("" if reach is None else
             f" painted {len(reach)} tiles {zlib.crc32(repr(reach).encode('ascii')):08x}")
    return f"basin {columns}x{rows} reach {','.join(f'{v:.4f}' for v in extent)}{grown}"


def _point_key(lattice) -> str:
    (columns, rows), extent = lattice
    return f"basin vertices {columns}x{rows} reach {','.join(f'{v:.4f}' for v in extent)}"


def _wire_display(parameters):
    return BASIN_SURFACE_STYLES[str(parameter(parameters,"shockwave_grid_wire_display"))]


_REACTION_TABLES: list = [None, None]


def _reaction_tables(tables):
    """The baked shaper tables as float arrays GL takes without converting them element by element: packed once
    per baked tables (their lane tuple's identity), not on each of a frame's two uploads."""
    lanes = tables["lanes"]
    if _REACTION_TABLES[0] is not lanes:
        bias = tables["bias"]
        _REACTION_TABLES[:] = [lanes, ((ctypes.c_float * len(lanes))(*lanes), (ctypes.c_float * len(bias))(*bias))]
    return _REACTION_TABLES[1]


def _reaction_vector(parameters) -> tuple[float, float, float, float]:
    """(strength, peaks, pulses, swell); strength 0 while React to Music is off."""
    enabled = bool(parameter(parameters, "shockwave_grid_terrain_reaction_enabled"))
    strength = float(parameter(parameters, "shockwave_grid_terrain_reaction_strength")) if enabled else 0.0
    return (strength, *(float(parameter(parameters, f"shockwave_grid_terrain_{part}"))
                        for part in ("peaks", "pulses", "swell")))


def _sky_admitted(parameters):
    return bool(parameter(parameters,"shockwave_grid_sky_enabled") or parameter(parameters,"shockwave_grid_sun_enabled"))


# Ray Strength 1 is this bright at the source's heart (the shafts are the source's average along each way).
RAY_GAIN = 1.6


def _shaft_light(parameters, view, body_position):
    """This frame's ``ShaftLight``: where the Sun/Moon sits on the card (it may lie outside), how far the rays
    reach (Ray Length) and their colour times Ray Strength; ``None`` while the body is behind the camera."""
    if view.depth(body_position) < 0.05:
        return None
    point = view.item_point(body_position)
    colour = rgba(parameter(parameters, "shockwave_grid_sun_rays_color"))
    gain = RAY_GAIN * float(parameter(parameters, "shockwave_grid_sun_rays_strength")) * colour[3]
    return ShaftLight(item_point=point, reach=0.15 + 0.85 * float(parameter(parameters, "shockwave_grid_sun_rays_length")),
                      colour=(colour[0] * gain, colour[1] * gain, colour[2] * gain))


def _halo_light(parameters) -> tuple[float, float]:
    """(Halo Intensity, Halo Reactivity) while the celestial halo is on, else (0, 0)."""
    if not bool(parameter(parameters, "shockwave_grid_celestial_glow_enabled")):
        return 0.0, 0.0
    return (float(parameter(parameters, "shockwave_grid_celestial_glow_strength")),
            float(parameter(parameters, "shockwave_grid_celestial_glow_reactivity")))


def _rays_admitted(parameters):
    return bool(parameter(parameters,"shockwave_grid_sun_enabled") and parameter(parameters,"shockwave_grid_sun_rays_enabled")
                and float(parameter(parameters,"shockwave_grid_sun_rays_strength"))>0.0)


@contextmanager
def _terrain_sky_occlusion_blend(emission: bool):
    """Subtract only fading terrain coverage from the sky behind it.

    Attachment 0 holds premultiplied colour; attachment 1 is additive emission.
    The depth prepass writes terrain depth as normal, but its alpha erases the
    portion of the sky actually covered. It never alters the card or other modes.
    """
    factors = tuple(gl_query.get_int(key) for key in (
        gl.GL_BLEND_SRC_RGB, gl.GL_BLEND_DST_RGB,
        gl.GL_BLEND_SRC_ALPHA, gl.GL_BLEND_DST_ALPHA))
    try:
        gl.glBlendFuncSeparatei(0,gl.GL_ZERO,gl.GL_ONE_MINUS_SRC_ALPHA,
                                gl.GL_ZERO,gl.GL_ONE_MINUS_SRC_ALPHA)
        if emission:
            gl.glBlendFuncSeparatei(1,gl.GL_ZERO,gl.GL_ONE_MINUS_SRC_ALPHA,
                                    gl.GL_ZERO,gl.GL_ONE_MINUS_SRC_ALPHA)
        yield
    finally:
        gl.glBlendFuncSeparatei(0,*factors)
        if emission:
            gl.glBlendFuncSeparatei(1,gl.GL_ONE,gl.GL_ONE,gl.GL_ONE,gl.GL_ONE)


@contextmanager
def _scene_depth():
    prior=gl_query.get_int(gl.GL_DEPTH_FUNC)
    try:
        gl.glDepthFunc(gl.GL_LESS)
        yield
    finally:
        gl.glDepthFunc(prior)


def create_visualizer_renderer() -> QuickShockwaveGridRenderer:
    return QuickShockwaveGridRenderer()


__all__ = ["QuickShockwaveGridRenderer", "create_visualizer_renderer", "shockwave_quality"]
