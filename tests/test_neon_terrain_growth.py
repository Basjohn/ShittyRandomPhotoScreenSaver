"""Neon Lake: the terrain brush's grid growth is invisible (1B.5).

The brush reaches land past the authored grid by growing the grid under it (``neon_terrain_extent.grow_heightfield``).
A growth must change nothing on screen until something is painted: the record keeps its authored origin (the square
the generated landscape starts from), every existing cell stays as stored, and a new cell holds the height the scene
already drew at its point, of which the scene adds only the departure from the generated land (zero until painted).

Each claim has its negative control: the Studio's Extend Toward Horizon (the same owner's authored growth, which moves
the generated landscape's start to the new edge) by the same cells does change the picture.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
import pytest

from rendering.gl_programs.heightfield import (
    HEIGHTFIELD_MAX_SIZE, basin_profile, heightfield_basin, heightfield_origin, normalize_heightfield,
)
from rendering.gl_programs.neon_terrain_extent import (
    GROW_STEP, MAX_GRID_SIZE, extend_heightfield, grow_heightfield, growth_cells, overlay_fields,
)

MODE = "shockwave_grid"


def _hilly(size: int = 17) -> dict:
    """Land with a lake, a stream to the back edge and rough borders (every continuation branch is exercised)."""
    rng = np.random.default_rng(7)
    heights = (0.12 + 0.5 * rng.random((size, size))).round(6)
    heights[5:9, 4:11] = 0.0                       # a lake
    heights[8:, 7:9] = 0.0                         # its stream, out through the back edge
    return normalize_heightfield({"version": 1, "size": size, "heights": heights.ravel().tolist()})


def _preset_terrains() -> list[tuple[str, dict]]:
    from core.settings.visualizer_presets import get_custom_preset_index, resolve_visualizer_activation_payload
    out = []
    for index in range(get_custom_preset_index(MODE)):
        activation = resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": index}, mode=MODE)
        out.append((str(activation.preset_path), activation.resolved_config["shockwave_grid_terrain"]))
    return out


def _stored_heightfields(node) -> list[dict]:
    """Every heightfield record in a preset file, exactly as the file stores it."""
    if isinstance(node, dict):
        if {"version", "size", "heights"} <= set(node):
            return [node]
        return [found for value in node.values() for found in _stored_heightfields(value)]
    if isinstance(node, list):
        return [found for value in node for found in _stored_heightfields(value)]
    return []


# ------------------------------------------------------------------------------------------- the record
def test_every_shipped_presets_terrain_loads_exactly_as_stored():
    """Existing cells stay exactly as stored: admission adds no origin to, and changes no height of, any shipped
    preset's terrain (the float32 texels the renderer uploads are those of the file's own numbers)."""
    presets = _preset_terrains()
    assert presets
    for path, resolved in presets:
        stored = _stored_heightfields(json.loads(Path(path).read_text(encoding="utf-8")))
        assert len(stored) == 1, path
        raw = stored[0]
        admitted = normalize_heightfield(raw)
        assert set(admitted) == set(raw), path                                  # no field added or dropped
        assert struct.pack(f"<{len(raw['heights'])}d", *admitted["heights"]) == \
            struct.pack(f"<{len(raw['heights'])}d", *(float(h) for h in raw["heights"])), path
        assert [int(v) for v in raw.get("basin", admitted.get("basin", []))] == admitted.get("basin", [])
        assert heightfield_origin(admitted) == (0, 0, admitted["size"] - 1)      # the whole grid is the origin
        assert overlay_fields(admitted) == {}                                    # no overlay work or texture
        assert normalize_heightfield(resolved) == admitted, path


def test_a_growth_keeps_every_cell_the_basin_and_the_origin():
    terrain = _hilly()
    n = terrain["size"]
    grown = grow_heightfield(terrain, 3, 5, 6, 2)
    m = grown["size"]
    assert m == n + 8 and heightfield_basin(grown) == (3, 6, n - 1) and heightfield_origin(grown) == (3, 6, n - 1)
    kept = np.asarray(grown["heights"]).reshape(m, m)[6:6 + n, 3:3 + n]
    assert kept.tobytes() == np.asarray(terrain["heights"]).reshape(n, n).tobytes()      # bit for bit
    # Growing again keeps the first origin, wherever the grid's edge has moved to.
    again = grow_heightfield(grown, 4, 0, 0, 4)
    assert heightfield_origin(again) == (7, 6, n - 1) and heightfield_basin(again) == (7, 6, n - 1)
    assert np.asarray(again["heights"]).reshape(m + 4, m + 4)[0:m, 4:4 + m].tobytes() == \
        np.asarray(grown["heights"]).tobytes()
    # The record survives canonical admission and a JSON round trip unchanged.
    assert normalize_heightfield(json.loads(json.dumps(again))) == again
    # A stream at the origin's edge is water in the new cells too, and beside it land.
    cells = np.asarray(grown["heights"]).reshape(m, m)
    assert (cells[6 + n:, 3 + 7:3 + 9] == 0.0).all() and (cells[6 + n:, 3:3 + 6] > 0.0).all()


def test_an_unpainted_growth_has_no_overlay_and_draws_the_same_surface_on_the_cpu():
    from rendering.gl_programs.neon_terrain_surface import scene_surface, terrain_delta
    terrain = _hilly()
    n = terrain["size"]
    grown = grow_heightfield(terrain, 3, 5, 6, 2)
    m = grown["size"]
    old = np.asarray(terrain["heights"]).reshape(n, n)
    new = np.asarray(grown["heights"]).reshape(m, m)
    delta = terrain_delta(new, heightfield_basin(grown), heightfield_origin(grown))
    assert not delta.any()                                           # nothing painted: nothing added
    fields = overlay_fields(grown)
    assert fields["painted"] is None and not any(fields["delta"]) and fields["maximum"] == old.max()
    rng = np.random.default_rng(3)
    u, v = rng.uniform(-2.5, 3.5, 4000), rng.uniform(-2.5, 3.5, 4000)             # old grid uv: on it and far past
    before_land, before_water = scene_surface(old, heightfield_basin(terrain), u, v)
    after_land, after_water = scene_surface(new, heightfield_basin(grown), (u * (n - 1) + 3) / (m - 1),
                                            (v * (n - 1) + 6) / (m - 1), heightfield_origin(grown))
    assert np.array_equal(before_water, after_water)
    assert np.abs(before_land - after_land).max() < 1e-12
    # Negative control: the authored extension (Extend Toward Horizon) by the same cells does move the land.
    extended = extend_heightfield(terrain, 3, 5, 6, 2)
    assert "origin" not in extended
    moved_land, _water = scene_surface(np.asarray(extended["heights"]).reshape(m, m), heightfield_basin(extended),
                                       (u * (n - 1) + 3) / (m - 1), (v * (n - 1) + 6) / (m - 1))
    assert np.abs(before_land - moved_land).max() > 1e-2


def test_painted_cells_are_an_overlay_that_eases_out_past_the_grids_edge():
    """Paint on a grown cell adds its departure from the generated land (smoothed like the land), the painted bounds
    step out to whole grow steps, and past the grid's edge the edge's paint eases to nothing (never a wall)."""
    from rendering.gl_programs.neon_terrain_surface import scene_surface
    terrain = _hilly()
    n = terrain["size"]
    grown = grow_heightfield(terrain, 0, 16, 0, 16)
    m = grown["size"]
    cells = np.asarray(grown["heights"]).reshape(m, m).copy()
    cells[10, m - 1] += 0.2                                          # a painted cell on the grown grid's very edge
    painted = normalize_heightfield({**grown, "heights": cells.ravel().tolist()})
    fields = overlay_fields(painted)
    delta = np.frombuffer(fields["delta"], dtype="<f4").reshape(m, m)
    assert delta[10, m - 1] == pytest.approx(0.2, abs=1e-6) and np.count_nonzero(delta) == 1
    left, front, right, back = fields["painted"]
    span = n - 1
    assert left * span == pytest.approx(GROW_STEP * ((m - 1 - 2) // GROW_STEP)) and right * span == m - 1
    assert front * span == pytest.approx(GROW_STEP * ((10 - 2) // GROW_STEP)) and back * span >= 12
    basin, origin = heightfield_basin(painted), heightfield_origin(painted)
    plain = np.asarray(grown["heights"]).reshape(m, m)
    v = 10 / (m - 1)
    lift = []
    for past in (0.0, 0.01, 0.1, 0.2, 0.31, 0.6):                    # basin uv past the grid's right edge
        u = 1.0 + past * span / (m - 1)
        with_paint, _w = scene_surface(cells, basin, np.array(u), np.array(v), origin)
        without, _w = scene_surface(plain, basin, np.array(u), np.array(v), origin)
        lift.append(float(with_paint - without))
    assert lift[0] > 0.1 and lift[1] == pytest.approx(lift[0], rel=1e-6)          # continuous across the edge
    assert lift[0] > lift[2] > lift[3] > 0.0 and lift[4] == 0.0 and lift[5] == 0.0   # eased out by the descent


# ------------------------------------------------------------------------------------------- how far it grows
def test_the_grid_grows_square_in_whole_steps_toward_the_brush_until_the_cap():
    terrain = normalize_heightfield(basin_profile(65))
    assert growth_cells(terrain, 0.5, 0.5, 0.1) == (0, 0, 0, 0)                   # already fits
    left, right, front, back = growth_cells(terrain, -0.2, 0.5, 0.05)             # past the left edge only
    assert left >= 0.25 * 64 + 2 and right == 0 and left + right == front + back
    assert (left + right) % GROW_STEP == 0 and front == 0                         # rows nobody asked for: backward
    left, right, front, back = growth_cells(terrain, 1.3, -0.4, 0.05)
    assert right >= 0.35 * 64 and front >= 0.45 * 64 and left + right == front + back
    # The cap: the point itself must fit; its footprint is clipped, not refused.
    room = MAX_GRID_SIZE - 65
    edge = 1.0 + room / 64.0
    assert growth_cells(terrain, edge + 0.02, 0.5, 0.05) is None                  # out of the largest grid's reach
    cells = growth_cells(terrain, edge - 0.01, 0.5, 0.2)
    assert cells is not None and cells[0] + cells[1] == room == cells[2] + cells[3]
    full = grow_heightfield(terrain, *cells)
    assert full["size"] == MAX_GRID_SIZE == HEIGHTFIELD_MAX_SIZE
    assert growth_cells(full, 0.5, 0.5, 0.4) == (0, 0, 0, 0)                      # nothing left to grow by
    assert growth_cells(full, -0.01, 0.5, 0.0) is None
    with pytest.raises(ValueError):
        grow_heightfield(full, 1, 0, 0, 1)


# ------------------------------------------------------------------------------------------- the camera floor
def test_growing_the_grid_never_moves_the_camera_floor():
    """The eye rests on the camera floor; an unpainted growth leaves it exactly where it was (painted far land can
    only raise it)."""
    from core.settings.neon_lake_camera import terrain_floor
    terrain = _hilly()
    grown = grow_heightfield(terrain, 16, 16, 0, 32)
    before, after = terrain_floor(terrain, 1.2), terrain_floor(grown, 1.2)
    rng = np.random.default_rng(11)
    points = np.column_stack([rng.uniform(-9.0, 9.0, 600), rng.uniform(-9.0, 4.0, 600)])
    assert max(abs(before(x, z) - after(x, z)) for x, z in points) < 1e-12
    from core.constants.neon_lake_world import DEPTH, NOMINAL_HALF_WIDTH
    m = grown["size"]
    x0, y0, span = heightfield_basin(grown)
    cells = np.asarray(grown["heights"]).reshape(m, m).copy()
    cells[m - 3, 4] = 0.95                                            # a painted peak in the far corner
    raised = terrain_floor(normalize_heightfield({**grown, "heights": cells.ravel().tolist()}), 1.2)
    assert all(raised(x, z) >= after(x, z) - 1e-12 for x, z in points)
    peak = (((4 - x0) / span * 2.0 - 1.0) * NOMINAL_HALF_WIDTH, -((m - 3 - y0) / span) * DEPTH)
    assert raised(*peak) > after(*peak) + 0.5                         # the eye clears the painted peak


# ------------------------------------------------------------------------------------------- the mesh
def _edges(vertices) -> dict:
    triangles = np.asarray(vertices, dtype=np.float64).reshape(-1, 3, 2)
    counts: dict = {}
    for triangle in triangles:
        points = [tuple(point) for point in triangle]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = (points[a], points[b]) if points[a] <= points[b] else (points[b], points[a])
            counts[key] = counts.get(key, 0) + 1
    return counts


def test_the_mesh_changes_only_under_painted_far_land_and_never_cracks():
    from rendering.gl_programs.neon_lake_basin_mesh import (
        BASIN_MESH_FINE_ROWS, BASIN_MESH_SUBDIVISION, basin_lattice, basin_mesh_points, basin_mesh_vertices,
    )
    cells, extent = (24, 16), (0.375, 0.375, 0.75, 0.0)
    plain = basin_mesh_vertices(cells, extent, BASIN_MESH_SUBDIVISION, BASIN_MESH_FINE_ROWS)
    # An unpainted growth asks for no finer region: the very same mesh (and the marks never depend on it).
    assert basin_mesh_vertices(cells, extent, BASIN_MESH_SUBDIVISION, BASIN_MESH_FINE_ROWS, None) == plain

    def triangle_set(mesh):
        return sorted(tuple(map(tuple, triangle)) for triangle in np.asarray(mesh).reshape(-1, 3, 2))
    # Painted bounds that reach no cell past the origin split nothing: the same triangles, whatever their order.
    idle = basin_mesh_vertices(cells, extent, BASIN_MESH_SUBDIVISION, BASIN_MESH_FINE_ROWS, (0.2, 0.2, 0.8, 0.8))
    assert triangle_set(idle) == triangle_set(plain)
    painted = (-1.4, -1.2, -0.5, 0.4)                                # left of the origin, across the camera-side band
    fine = basin_mesh_vertices(cells, extent, BASIN_MESH_SUBDIVISION, BASIN_MESH_FINE_ROWS, painted)
    assert len(fine) > len(plain)
    xs, ys = basin_lattice(cells, extent)
    # No crack: every edge is shared by exactly two triangles, except the mesh's own outer border.
    for (a, b), count in _edges(fine).items():
        border = (a[0] == b[0] and a[0] in (xs[0], xs[-1])) or (a[1] == b[1] and a[1] in (ys[0], ys[-1]))
        assert count == (1 if border else 2), (a, b, count)
    # Every mark is still a triangle vertex.
    vertices = {tuple(point) for point in np.asarray(fine).reshape(-1, 2)}
    assert {tuple(point) for point in np.asarray(basin_mesh_points(cells, extent)).reshape(-1, 2)} <= vertices
    # Triangles away from the painted bounds (and one lattice cell round them) are exactly the plain mesh's.
    def outside(mesh):
        triangles = np.asarray(mesh, dtype=np.float64).reshape(-1, 3, 2)
        far = ((triangles[..., 0].max(axis=1) < painted[0] - 0.7) | (triangles[..., 0].min(axis=1) > painted[2] + 0.2)
               | (triangles[..., 1].max(axis=1) < painted[1] - 0.7) | (triangles[..., 1].min(axis=1) > painted[3] + 0.2))
        return {tuple(map(tuple, triangle)) for triangle in triangles[far]}
    assert outside(fine) == outside(plain) and outside(plain)
    # Inside the painted bounds, past the origin, no triangle is wider than the tier's own cell.
    triangles = np.asarray(fine, dtype=np.float64).reshape(-1, 3, 2)
    inside = ((triangles[..., 0].min(axis=1) >= painted[0]) & (triangles[..., 0].max(axis=1) <= painted[2])
              & (triangles[..., 1].min(axis=1) >= painted[1]) & (triangles[..., 1].max(axis=1) <= painted[3])
              & (triangles[..., 0].max(axis=1) <= -extent[0]))
    assert inside.any()
    assert np.ptp(triangles[inside][..., 0], axis=1).max() <= 1.0 / cells[0] + 1e-9
    assert np.ptp(triangles[inside][..., 1], axis=1).max() <= 1.0 / cells[1] + 1e-9


# ------------------------------------------------------------------------------------------- the GPU surface
@pytest.mark.qt
def test_an_unpainted_growth_draws_the_same_gpu_surface_on_the_grid_and_past_it(qt_app):
    """The production height function (``basinSurface``), evaluated over the basin and far past it: the same heights
    and the same water before and after an unpainted growth; the authored extension moves them."""
    from tests.test_neon_terrain_extent import _GridProbe
    terrain = _hilly()
    grown = grow_heightfield(terrain, 16, 16, 0, 32)
    extended = extend_heightfield(terrain, 16, 16, 0, 32)
    rects = ((0.05, 0.05, 0.95, 0.95), (-1.6, -0.9, 2.6, 3.4), (1.02, -0.4, 4.5, 1.4))
    images = {}
    for name, record in (("before", terrain), ("grown", grown), ("extended", extended)):
        probe = _GridProbe(record)                       # one GL context at a time
        try:
            images[name] = [probe.draw(uv_rect=rect) for rect in rects]
        finally:
            probe.close()
    changed = 0.0
    for before, after, control in zip(images["before"], images["grown"], images["extended"]):
        assert np.array_equal(before[..., 1], after[..., 1])                    # the same water and land
        assert np.abs(before[..., 0] - after[..., 0]).max() < 2e-5              # the same heights (float32 texels)
        changed = max(changed, float(np.abs(before[..., 0] - control[..., 0]).max()))
    assert changed > 0.02                                                       # the control is not invisible


@pytest.mark.qt
def test_paint_on_grown_land_is_drawn_by_the_gpu_as_the_cpu_surface_has_it(qt_app):
    """The brush picks on the CPU surface: with paint on grown cells (and on the grown grid's very edge) the GPU's
    drawn land is that surface, so the cursor and the stroke land where the picture shows them."""
    from rendering.gl_programs.neon_terrain_surface import scene_surface
    from tests.test_neon_terrain_extent import _GridProbe
    terrain = _hilly()
    n = terrain["size"]
    grown = grow_heightfield(terrain, 0, 16, 0, 16)
    m = grown["size"]
    cells = np.asarray(grown["heights"]).reshape(m, m).copy()
    yy, xx = np.mgrid[0:m, 0:m]
    cells += 0.25 * np.exp(-((xx - 26) ** 2 + (yy - 22) ** 2) / 18.0) * (cells > 0.0)      # a painted mound
    cells[9:13, m - 1] = np.minimum(1.0, cells[9:13, m - 1] + 0.2)                        # paint on the grid's edge
    painted = normalize_heightfield({**grown, "heights": np.clip(cells, 0.0, 1.0).ravel().tolist()})
    rect = (0.6, 0.2, 2.6, 2.2)                                        # basin uv: the origin's corner, the ring, past it
    probe = _GridProbe(painted)
    try:
        image = probe.draw(uv_rect=rect)
    finally:
        probe.close()
    span = n - 1
    u = np.linspace(rect[0], rect[2], probe.SIZE) * span / (m - 1)
    v = np.linspace(rect[1], rect[3], probe.SIZE) * span / (m - 1)
    gu, gv = np.meshgrid(u, v)
    stored = np.asarray(painted["heights"]).reshape(m, m)
    basin, origin = heightfield_basin(painted), heightfield_origin(painted)
    land, water = scene_surface(stored, basin, gu, gv, origin)
    flat, _water = scene_surface(np.zeros_like(stored), basin, gu, gv, origin)   # the distant curvature alone
    expected = 1.5 * (land - flat) + flat                              # the probe's Terrain Height scales the land
    assert np.array_equal(image[..., 1] > 0.5, water)
    # Within the GPU's filtered reads (its bilinear weights are 8-bit; the steep bank ramp magnifies a step).
    assert np.abs(image[..., 0] - expected)[~water].max() < 1.5e-3
    assert np.median(np.abs(image[..., 0] - expected)[~water]) < 1e-5
    # The paint is in the picture: without it the same surface is lower by the mound and the edge's lift.
    plain, _water = scene_surface(np.asarray(grown["heights"]).reshape(m, m), basin, gu, gv, origin)
    assert (land - plain).max() > 0.15


# ------------------------------------------------------------------------------------------- the picture
def _picture(overrides: dict, preset: int, size=(960, 540)) -> np.ndarray:
    """One production frame (the real render host, off screen) of a shipped preset with settings overridden."""
    from PySide6.QtGui import QImage  # noqa: F401  (the capture's Qt image path)
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from tools.neon_lake_capture import _draw
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.transition_contact_sheet import TransitionCapture

    activation = resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": preset}, mode=MODE)
    settings = {**activation.resolved_config, **overrides}
    snapshot = _build_spectrum_preview_snapshot(width=size[0], height=size[1], mode=MODE, settings=settings)
    target = TransitionCapture(*size)
    host = QuickVisualizerRenderHost()
    try:
        rgba, _matrix = _draw(host, target, snapshot, size[0], size[1], size)
        return rgba[..., :3].astype(np.int16)
    finally:
        host.release_resources()
        target.close()


@pytest.mark.qt
@pytest.mark.parametrize("preset", range(len(_preset_terrains())))
def test_an_unpainted_growth_to_the_largest_grid_renders_the_same_picture(qt_app, preset):
    """Before / after frames of every shipped preset, dollied back so the far land fills the frame, with its grid
    grown to the cap and nothing painted: the same picture (a handful of single pixels move by the filtered read of a
    larger texture); the authored extension by the same cells is visibly another picture."""
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    terrain = _preset_terrains()[preset][1]
    room = MAX_GRID_SIZE - int(terrain["size"])
    cells = (room // 2, room - room // 2, room // 2, room - room // 2)
    pose = {"shockwave_grid_scene_scale": 0.6, "shockwave_grid_turn": 0.2}
    before = _picture(pose, preset)
    again = _picture(pose, preset)
    grown = _picture({**pose, "shockwave_grid_terrain": grow_heightfield(terrain, *cells)}, preset)
    extended = _picture({**pose, "shockwave_grid_terrain": extend_heightfield(terrain, *cells)}, preset)

    def change(a, b):
        difference = np.abs(a - b).max(axis=2)
        return float(difference.mean()), float((difference > 8).mean())

    floor, growth, control = change(before, again), change(before, grown), change(before, extended)
    assert growth[0] <= floor[0] + 0.02, (floor, growth)                  # mean change, in 8-bit levels
    assert growth[1] <= 2e-4, (floor, growth)                             # share of pixels moved by more than 8
    assert control[0] > 20 * max(growth[0], 0.01) and control[1] > 0.01, (growth, control)
