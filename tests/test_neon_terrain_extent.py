"""Neon Lake terrain reaching past its basin: edge water flows to the horizon; extension keeps the basin exactly."""
import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.heightfield import heightfield_basin, heightfield_grid_transform, normalize_heightfield
from rendering.gl_programs.neon_terrain_extent import (
    MAX_GRID_SIZE, basin_continuation, extend_heightfield, horizon_extension_cells,
)
from tests.test_neon_lake_reaction import _SurfaceProbe

pytestmark = pytest.mark.qt


def _stream_terrain(size=9):
    """Land with a water channel (columns 3..5) running from the lake to the back edge."""
    heights = []
    for row in range(size):
        for col in range(size):
            lake = 2 <= row <= 5 and 2 <= col <= 6
            channel = row >= 4 and 3 <= col <= 5
            heights.append(0.0 if lake or channel else 0.4)
    return normalize_heightfield({"version": 1, "size": size, "heights": heights})


class _GridProbe(_SurfaceProbe):
    """The production surface probe with the terrain's basin-to-grid transform bound, and for a grown grid its
    authored origin and its overlay on the generated land (as the renderer binds them)."""

    def draw(self, *args, **kwargs):
        from rendering.gl_programs.heightfield import heightfield_origin_rect
        from rendering.gl_programs.neon_terrain_extent import overlay_fields
        from rendering.quick.scene3d.heightfield import HeightfieldTexture
        gl.glUseProgram(self.program)
        gl.glUniform3f(gl.glGetUniformLocation(self.program, "uTerrainGrid"), *heightfield_grid_transform(self.terrain))
        gl.glUniform4f(gl.glGetUniformLocation(self.program, "uTerrainOrigin"), *heightfield_origin_rect(self.terrain))
        overlay = overlay_fields(self.terrain)
        if not overlay:
            gl.glUniform1i(gl.glGetUniformLocation(self.program, "uTerrainDelta"), 0)
            return super().draw(*args, **kwargs)
        if getattr(self, "overlay", None) is None:
            self.overlay = HeightfieldTexture("basin overlay probe", components=1)
        self.overlay.ensure(self.terrain["size"], overlay["delta"])
        gl.glUniform1i(gl.glGetUniformLocation(self.program, "uTerrainDelta"), 1)
        with self.overlay.bound(1):
            return super().draw(*args, **kwargs)

    def close(self):
        if getattr(self, "overlay", None) is not None:
            self.overlay.release()
        super().close()


def test_water_at_the_grids_edge_flows_on_to_the_horizon_and_dry_edges_stay_land(qt_app):
    terrain = _stream_terrain()
    probe = _GridProbe(terrain)
    try:
        # Far past the back edge (v 1.3..2.5): water exactly in the channel's columns, land elsewhere.
        far = probe.draw(uv_rect=(0.0, 1.3, 1.0, 2.5))
        water = far[..., 1] > 0.5
        channel = (3 / 8, 5 / 8)
        u = np.linspace(0.0, 1.0, probe.SIZE)
        inside = (u > channel[0] + 0.03) & (u < channel[1] - 0.03)
        outside = (u < channel[0] - 0.03) | (u > channel[1] + 0.03)
        assert water[:, inside].all()
        assert not water[:, outside].any()
    finally:
        probe.close()
    # The CPU mirror (used to seed extended cells) agrees: water in the channel, rolling land beside it.
    assert basin_continuation(terrain, 0.5, 2.0) == 0.0
    assert basin_continuation(terrain, 0.1, 2.0) > 0.0


def test_an_extended_grid_keeps_the_basin_and_renders_it_unchanged(qt_app):
    terrain = _stream_terrain()
    cells = horizon_extension_cells(terrain)
    extended = extend_heightfield(terrain, *cells)
    x0, y0, span = heightfield_basin(extended)
    n, m = terrain["size"], extended["size"]
    assert (span, m) == (n - 1, n + cells[0] + cells[1])
    # Every original cell is kept exactly, in place.
    for row in range(n):
        for col in range(n):
            assert extended["heights"][(row + y0) * m + col + x0] == terrain["heights"][row * n + col]
    # New cells start as the continuation already drawn there; the stream reaches the new back edge.
    assert extended["heights"][(m - 1) * m + x0 + 4] == 0.0
    assert extended["heights"][(m - 1) * m + 0] > 0.0
    rect = (0.15, 0.15, 0.85, 0.85)        # the basin's interior, away from its border cells
    images = []
    for record in (terrain, extended):      # one GL context at a time
        probe = _GridProbe(record)
        try:
            images.append(probe.draw(uv_rect=rect))
        finally:
            probe.close()
    a, b = images
    assert np.array_equal(a[..., 1], b[..., 1])                     # same water and land
    assert np.abs(a[..., 0] - b[..., 0]).max() < 1e-5              # same surface heights


def test_a_full_size_basin_extended_past_65_cells_uploads_and_renders_unchanged(qt_app):
    """The GPU texture admits every canonical grid: one Extend on a 65-cell basin (the shipped presets' size)
    used to raise mid-frame because the texture alone capped grids at 65."""
    from rendering.gl_programs.heightfield import HEIGHTFIELD_MAX_SIZE, basin_profile

    terrain = normalize_heightfield(basin_profile(65))
    extended = extend_heightfield(terrain, *horizon_extension_cells(terrain))
    assert 65 < extended["size"] <= HEIGHTFIELD_MAX_SIZE == MAX_GRID_SIZE
    images = []
    for record in (terrain, extended):
        probe = _GridProbe(record)
        try:
            images.append(probe.draw(uv_rect=(0.15, 0.15, 0.85, 0.85)))
        finally:
            probe.close()
    a, b = images
    assert np.array_equal(a[..., 1], b[..., 1])
    assert np.abs(a[..., 0] - b[..., 0]).max() < 1e-5


def test_extension_is_bounded_and_keeps_cells_square():
    terrain = _stream_terrain()
    with pytest.raises(ValueError):
        extend_heightfield(terrain, 1, 1, 0, 3)
    grown = terrain
    while (cells := horizon_extension_cells(grown)) is not None:
        grown = extend_heightfield(grown, *cells)
    assert grown["size"] <= MAX_GRID_SIZE
    assert heightfield_basin(grown)[2] == terrain["size"] - 1


def test_the_cpu_surface_is_the_scenes_own_and_its_continuation():
    """The CPU surface the Studio's brush picks on is the scene's: the smooth cubic land (not raw cells), water where
    the scene has it, and past the grid the scene's continuation (a stream at the edge flows on as water)."""
    from rendering.gl_programs.heightfield import sample_heightfield, sample_heightfield_curve
    from rendering.gl_programs.neon_terrain_extent import basin_continuation
    from rendering.gl_programs import neon_terrain_surface as surface
    record = _stream_terrain()
    grid = np.asarray(record["heights"]).reshape(record["size"], record["size"])
    basin = heightfield_basin(record)
    for u, v in ((0.05, 0.05), (0.2, 0.9), (0.95, 0.4)):
        land, water = surface.scene_surface(grid, basin, np.array(u), np.array(v))
        assert sample_heightfield(record, u, v) >= 0.015          # full land: no shore ramp
        assert not bool(water) and float(land) == pytest.approx(sample_heightfield_curve(record, u, v), abs=1e-9)
    for u, v in ((0.5, 1.6), (-0.4, 0.3), (1.3, 1.2)):
        _land, water = surface.scene_surface(grid, basin, np.array(u), np.array(v))
        assert bool(water) == (basin_continuation(record, u, v) == 0.0)
    assert bool(surface.scene_surface(grid, basin, np.array(0.5), np.array(1.6))[1])     # the channel runs on
    # Terrain Height scales the drawn land exactly.
    tall = surface.surface_points(record["size"], record["heights"], basin, np.array([0.1]), np.array([0.1]), 2.0)
    low = surface.surface_points(record["size"], record["heights"], basin, np.array([0.1]), np.array([0.1]), 1.0)
    assert tall[0, 1] == pytest.approx(2.0 * low[0, 1])


def test_the_camera_floor_unpacks_a_render_payload_once():
    """The renderer asks for the camera floor every frame; its frozen payload is unpacked once, not per frame
    (a 121-cell extended grid cost about 1.5 ms a frame)."""
    from rendering.gl_programs.heightfield import basin_profile, heightfield_surface_bytes
    from core.settings import neon_lake_camera

    terrain = normalize_heightfield(basin_profile(17))
    record = {"size": terrain["size"], "data": heightfield_surface_bytes(terrain)}
    neon_lake_camera._packed_heights.cache_clear()
    floors = [neon_lake_camera.terrain_floor(record, 1.0)(0.0, -1.2) for _ in range(3)]
    assert floors[0] > 0.0 and floors.count(floors[0]) == 3
    assert neon_lake_camera._packed_heights.cache_info().misses == 1
