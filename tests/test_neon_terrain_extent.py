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
    """The production surface probe with the terrain's basin-to-grid transform bound."""

    def draw(self, *args, **kwargs):
        gl.glUseProgram(self.program)
        gl.glUniform3f(gl.glGetUniformLocation(self.program, "uTerrainGrid"), *heightfield_grid_transform(self.terrain))
        return super().draw(*args, **kwargs)


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


def test_extension_is_bounded_and_keeps_cells_square():
    terrain = _stream_terrain()
    with pytest.raises(ValueError):
        extend_heightfield(terrain, 1, 1, 0, 3)
    grown = terrain
    while (cells := horizon_extension_cells(grown)) is not None:
        grown = extend_heightfield(grown, *cells)
    assert grown["size"] <= MAX_GRID_SIZE
    assert heightfield_basin(grown)[2] == terrain["size"] - 1


def test_extend_in_the_editor_is_one_undoable_step(qtbot):
    from tests._invisible_windows import keep_off_screen
    from ui.tabs.media.terrain_editor import TerrainEditor
    terrain = _stream_terrain()
    editor = TerrainEditor(terrain)
    qtbot.addWidget(editor)
    keep_off_screen(editor).resize(600, 420)
    editor.show()
    qtbot.waitExposed(editor)
    emitted = []
    editor.terrain_changed.connect(emitted.append)
    assert editor.extend_button.isEnabled()
    editor.extend_button.click()
    grown = editor.get_heightfield()
    assert grown["size"] > terrain["size"] and grown["basin"] == list(heightfield_basin(grown))
    assert emitted and emitted[-1] == grown
    editor.undo_button.click()
    assert editor.get_heightfield() == terrain


def _angled_editor(qtbot, terrain):
    from tests._invisible_windows import keep_off_screen
    from ui.tabs.media.terrain_editor import TerrainEditor
    editor = TerrainEditor(terrain)
    qtbot.addWidget(editor)
    keep_off_screen(editor).resize(600, 560)
    editor.show()
    qtbot.waitExposed(editor)
    editor.view.setCurrentText("Angled")
    return editor, editor.canvas


def _screen_of(canvas, u, v):
    from PySide6.QtCore import QPointF
    from rendering.gl_programs.heightfield import sample_heightfield
    from ui.tabs.media import terrain_angled_view as angled
    projection = canvas._angled_view()[1]
    record = canvas.get_heightfield()
    world = angled.surface_points(record["size"], record["heights"], heightfield_basin(record), np.array(u),
                                  np.array(v), canvas._terrain_height)
    x, y = projection.project(world)[0]
    return QPointF(float(x), float(y))


def test_the_angled_view_picks_the_surface_it_draws_and_paints_there(qtbot):
    from PySide6.QtCore import QPoint, Qt
    from rendering.gl_programs.heightfield import sample_heightfield
    terrain = extend_heightfield(_stream_terrain(), *horizon_extension_cells(_stream_terrain()))
    editor, canvas = _angled_editor(qtbot, terrain)
    # Near vertices that top their own row and the row in front (nothing nearer can hide them; the rows behind are
    # farther) pick back to their own uv; one at a cliff's foot would rightly pick the wall in front of it.
    from PySide6.QtCore import QPointF
    projection = canvas._angled_view()[1]
    heights = projection.world[..., 1]
    flat = [(row, col) for row in (0, 1, 2) for col in range(1, heights.shape[1] - 1)
            if heights[max(0, row - 1):row + 1, col - 1:col + 2].max() <= heights[row, col] + 1e-9]
    assert len(flat) >= 3
    for row, col in flat:
        picked = canvas._uv(QPointF(*projection.screen[row, col]))
        assert picked == pytest.approx(tuple(projection.uv[row, col]), abs=1e-3)
    assert canvas._uv(QPoint(canvas.width() // 2, 30)) is None       # the sky above the terrain
    # Painting through the angled view raises the picked ground, as one undoable stroke.
    emitted = []
    canvas.terrain_changed.connect(emitted.append)
    target = _screen_of(canvas, 0.2, 0.15)
    before = sample_heightfield(canvas.get_heightfield(), 0.2, 0.15)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=target.toPoint())
    assert sample_heightfield(canvas.get_heightfield(), 0.2, 0.15) > before
    assert len(emitted) == 1
    # A click on the sky paints nothing.
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(canvas.width() // 2, 30))
    assert len(emitted) == 1


def test_turning_the_angled_view_never_changes_the_terrain(qtbot):
    from PySide6.QtCore import QPoint, Qt
    terrain = _stream_terrain()
    editor, canvas = _angled_editor(qtbot, terrain)
    emitted = []
    canvas.terrain_changed.connect(emitted.append)
    yaw = canvas._yaw
    start = QPoint(canvas.width() // 2, canvas.height() // 2)
    qtbot.mousePress(canvas, Qt.MouseButton.RightButton, pos=start)
    qtbot.mouseMove(canvas, start + QPoint(60, -20))
    qtbot.mouseRelease(canvas, Qt.MouseButton.RightButton, pos=start + QPoint(60, -20))
    assert canvas._yaw != yaw
    assert not emitted and canvas.get_heightfield() == terrain
    editor.view.setCurrentText("Top")                  # the top map is unchanged by the angled view
    assert canvas.get_heightfield() == terrain


def test_the_angled_view_draws_the_scenes_own_surface_and_its_continuation():
    """The 3/4 view's surface is the scene's: the smooth cubic land (not raw cells), water where the scene has it, and
    past the grid the scene's continuation (a stream at the edge flows on as water)."""
    from rendering.gl_programs.heightfield import sample_heightfield, sample_heightfield_curve
    from rendering.gl_programs.neon_terrain_extent import basin_continuation
    from ui.tabs.media import terrain_angled_view as angled
    record = _stream_terrain()
    grid = np.asarray(record["heights"]).reshape(record["size"], record["size"])
    basin = heightfield_basin(record)
    for u, v in ((0.05, 0.05), (0.2, 0.9), (0.95, 0.4)):
        land, water = angled.scene_surface(grid, basin, np.array(u), np.array(v))
        assert sample_heightfield(record, u, v) >= 0.015          # full land: no shore ramp
        assert not bool(water) and float(land) == pytest.approx(sample_heightfield_curve(record, u, v), abs=1e-9)
    for u, v in ((0.5, 1.6), (-0.4, 0.3), (1.3, 1.2)):
        _land, water = angled.scene_surface(grid, basin, np.array(u), np.array(v))
        assert bool(water) == (basin_continuation(record, u, v) == 0.0)
    assert bool(angled.scene_surface(grid, basin, np.array(0.5), np.array(1.6))[1])     # the channel runs on
    # Terrain Height scales the drawn land exactly.
    tall = angled.surface_points(record["size"], record["heights"], basin, np.array([0.1]), np.array([0.1]), 2.0)
    low = angled.surface_points(record["size"], record["heights"], basin, np.array([0.1]), np.array([0.1]), 1.0)
    assert tall[0, 1] == pytest.approx(2.0 * low[0, 1])
