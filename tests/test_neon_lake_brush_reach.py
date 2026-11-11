"""Neon Lake: all the land the Studio's preview shows is paintable with the terrain brush (1B.5).

Operator, 11 Nov: "Visible land is not editable with the brush, the limits are constrained despite it being part of the
scene." The scene draws land past the authored grid (the generated continuation and far hills), which had no stored
cells for the brush to paint. A stroke there now grows the grid under it (``neon_terrain_extent.grow_heightfield``:
invisibly, see ``tests/test_neon_terrain_growth.py``), carries its path across the growth and commits once; only land
past the largest grid's reach is refused, and that out loud.

These checks drive a live (hidden, offscreen) Neon Lake Studio at every shipped preset's terrain. The land on screen is
found independently of the brush (``_ground_hit``: the camera's ray marched against the scene's CPU surface).
"""
from __future__ import annotations

import time

import numpy as np
import pytest

MODE = "shockwave_grid"
TERRAIN = "shockwave_grid_terrain"


class _Store:
    def __init__(self, preset_index: int, overrides=None):
        from core.settings.visualizer_mode_settings import mode_settings
        from core.settings.visualizer_presets import resolve_visualizer_activation_payload
        self.values = dict(resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": preset_index},
                                                                 mode=MODE).resolved_config)
        self.values.update(overrides or {})
        spec = mode_settings(MODE)
        self.values.update({c.key: c.admit(self.values[c.key], self.values[c.key])
                            for c in spec.controls if c.key in self.values})

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return "Preset"


class _Presence:
    concealed = False

    def conceal(self):
        pass

    def reveal(self):
        pass


def _presets() -> list[int]:
    from core.settings.visualizer_presets import get_custom_preset_index
    return list(range(get_custom_preset_index(MODE)))


@pytest.fixture
def neon(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    disable_per_call_gl_error_checking()
    opened = []

    def open_preset(index, overrides=None):
        adapter = create_adapter(MODE)
        adapter.recorded_clips = lambda: ()
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(1600, 900), present_on_show=False))
            return surfaces[0]
        controller = StudioController(adapter, _Store(index, overrides), _Presence(), factory)
        assert controller.open()
        opened.append(controller)
        surface = surfaces[0]
        for _ in range(3000):
            surface.pump()
            if controller.bridge.viewportStatus == "live" and controller.last_frame is not None \
                    and not getattr(controller.evaluator, "analysing", False):
                break
            time.sleep(0.005)
        assert controller.bridge.viewportStatus == "live", controller.bridge.viewportError
        return controller, surface
    yield open_preset
    for controller in opened:
        controller.close()


def _ground_hit(frame, values, point, geometry):
    """Grid uv where the ray through ``point`` meets the drawn land (on the stored grid or past it), or None (sky):
    the camera's ray marched against the scene's CPU surface, independently of the brush's own pick."""
    from core.constants.neon_lake_world import FAR_PLANE
    from ui.studio import shockwave_grid_adapter as neon
    view = neon.terrain_view(frame, geometry)
    fx, fy, fw, fh = view.field
    u, v = (float(point[0]) - fx) / fw, (float(point[1]) - fy) / fh
    if not (0.0 <= u <= 1.0 and 0.0 <= v <= 1.0):
        return None
    terrain = neon._terrain_surface(values)
    eye, direction = np.asarray(view.eye, dtype=np.float64), np.asarray(view.ray(u, v), dtype=np.float64)

    def above(t):
        p = eye + np.multiply.outer(t, direction)
        gu, gv = neon._grid_uv(terrain.size, terrain.basin, p[..., 0], p[..., 2])
        return p[..., 1] - neon._ground(terrain, gu, gv)
    # The pick's own sampling: a finer march finds thin ridges at grazing angles the pick steps over, which is the
    # march's resolution, not the brush's reach.
    t = np.geomspace(0.01, FAR_PLANE, neon._PICK_SAMPLES)
    below = np.flatnonzero(above(t) <= 0.0)
    if below.size == 0:
        return None
    index = int(below[0])
    near, far = (0.0, float(t[0])) if index == 0 else (float(t[index - 1]), float(t[index]))
    for _ in range(neon._PICK_REFINE):
        middle = 0.5 * (near + far)
        near, far = (middle, far) if float(above(np.array([middle]))[0]) > 0.0 else (near, middle)
    hit = eye + far * direction
    gu, gv = neon._grid_uv(terrain.size, terrain.basin, float(hit[0]), float(hit[2]))
    return float(gu), float(gv)


def _on_grid(uv) -> bool:
    return 0.0 <= uv[0] <= 1.0 and 0.0 <= uv[1] <= 1.0


def _land(controller, columns=48, rows=27):
    """(screen point, grid uv) of the land on the presented frame, found without the brush."""
    frame, values, geometry = controller.brush_scene()
    width, height = geometry[0]
    out = []
    for row in range(rows):
        for col in range(columns):
            point = ((col + 0.5) * width / columns, (row + 0.5) * height / rows)
            hit = _ground_hit(frame, values, point, geometry)
            if hit is not None:
                out.append((point, hit))
    return out


def _cells(record) -> np.ndarray:
    return np.asarray(record["heights"], dtype=np.float64).reshape(record["size"], record["size"])


def _drawn_height(record, values, uv) -> float:
    """The drawn ground's height at grid uv of ``record`` (the scene's own CPU surface)."""
    from ui.studio import shockwave_grid_adapter as neon
    return float(neon._ground(neon._terrain_surface({**values, TERRAIN: record}), np.array(uv[0]), np.array(uv[1])))


def _stroke(controller, surface, points, mode="Raise"):
    """Paint through the bridge as the viewport does: a press, moves and a release, frames pumped between."""
    bridge = controller.bridge
    bridge.setBrushActive(True)
    bridge.setBrushValue("mode", mode)
    bridge.setBrushValue("strength", 1.0)
    bridge.setBrushValue("radius", 0.08)
    bridge.brushPress(*points[0])
    surface.pump(2)
    for point in points[1:]:
        bridge.brushMove(*point)
        surface.pump(2)
    bridge.brushRelease()
    surface.pump(2)
    bridge.setBrushActive(False)


@pytest.mark.parametrize("preset", _presets())
def test_every_visible_land_point_is_paintable(neon, preset):
    """Dollied back (a preview pose, as the wheel leaves it) a sizeable share of the land on screen lies past the
    authored grid; the brush lands on every land point, on the grid or past it, and can paint there."""
    from ui.studio.shockwave_grid_adapter import pick_terrain, terrain_reachable
    controller, surface = neon(preset)
    controller.bridge.zoomBy(-6.0, True)
    surface.pump(2)
    frame, values, geometry = controller.brush_scene()
    size = int(values[TERRAIN]["size"])
    land = _land(controller)
    past = [hit for _point, hit in land if not _on_grid(hit)]
    assert len(past) / len(land) > 0.05, f"preset {preset + 1}: no visible land past the grid"
    missed, refused = [], []
    for point, hit in land:
        uv = pick_terrain(frame, values, point, geometry)
        if uv is None or max(abs(uv[0] - hit[0]), abs(uv[1] - hit[1])) > 1e-6:
            missed.append((point, hit, uv))
        elif not (_on_grid(uv) or terrain_reachable(size, uv)):
            refused.append((point, uv))
    assert missed == [], f"preset {preset + 1}: land the brush does not land on: {missed[:5]}"
    assert refused == [], f"preset {preset + 1}: land the brush refuses: {refused[:5]}"


@pytest.mark.parametrize("preset", _presets())
def test_a_stroke_on_far_land_grows_the_grid_and_is_one_undoable_step(neon, preset):
    from rendering.gl_programs.heightfield import heightfield_basin, heightfield_origin
    from ui.studio.shockwave_grid_adapter import pick_terrain
    controller, surface = neon(preset)
    controller.bridge.zoomBy(-6.0, True)
    surface.pump(2)
    session = controller.session
    before = session.values[TERRAIN]
    n = int(before["size"])
    frame, values, geometry = controller.brush_scene()
    # The land point farthest past the grid (in cells): the stroke must grow the grid to reach it.
    point, hit = max(((p, h) for p, h in _land(controller) if not _on_grid(h)),
                     key=lambda item: max(-item[1][0], item[1][0] - 1.0, -item[1][1], item[1][1] - 1.0))
    ground = _drawn_height(before, values, hit)
    commits = session.commit_count
    _stroke(controller, surface, [point, (point[0] + 3.0, point[1]), (point[0] + 6.0, point[1])])
    after = session.values[TERRAIN]
    m = int(after["size"])
    assert n < m <= 257 and session.commit_count == commits + 1
    assert controller.bridge.brush.refusals == 0
    # The growth kept the basin's cells in place and recorded the grid it grew from as the authored origin.
    x0, y0, span = heightfield_basin(after)
    ox, oy, origin_span = heightfield_origin(after)
    bx, by, _span = heightfield_basin(before)
    assert span == heightfield_basin(before)[2] and origin_span == heightfield_origin(before)[2]
    left, front = x0 - bx, y0 - by
    assert (ox, oy) == (heightfield_origin(before)[0] + left, heightfield_origin(before)[1] + front)
    # The land under the pointer rose (the picture's own surface, at the same place on the ground) ...
    placed = ((hit[0] * (n - 1) + left) / (m - 1), (hit[1] * (n - 1) + front) / (m - 1))
    assert _drawn_height(after, values, placed) > ground + 0.02
    # ... and the brush now lands there on stored cells.
    frame, values, geometry = controller.brush_scene()
    assert _on_grid(pick_terrain(frame, values, point, geometry))
    # Every old cell out of the brush's reach is exactly as stored.
    old, new = _cells(before), _cells(after)[front:front + n, left:left + n]
    yy, xx = np.mgrid[0:n, 0:n]
    far = np.hypot(xx - hit[0] * (n - 1), yy - hit[1] * (n - 1)) > 0.16 * span + 4
    assert far.any() and np.array_equal(old[far], new[far])
    # One undo takes the paint and the growth back together.
    assert session.undo() and session.values[TERRAIN] == before
    assert session.redo() and session.values[TERRAIN] == after


def test_a_stroke_carries_on_across_a_growth(neon):
    """A stroke that starts on the stored grid and runs out past it: the grid grows mid-stroke, the path painted so
    far stays where it was on the ground, and the whole stroke is one commit."""
    from rendering.gl_programs.heightfield import heightfield_basin
    controller, surface = neon(_presets()[-1])
    controller.bridge.zoomBy(-6.0, True)
    surface.pump(2)
    session = controller.session
    before = session.values[TERRAIN]
    n = int(before["size"])
    _frame, values, _geometry = controller.brush_scene()
    land = _land(controller)
    # From a land point well inside the grid to the nearest land point well past it, along the screen.
    inside = [(p, h) for p, h in land if 0.15 < h[0] < 0.85 and 0.15 < h[1] < 0.85
              and _drawn_height(before, values, h) > 0.0]
    outside = [(p, h) for p, h in land if not (-0.3 < h[0] < 1.3 and -0.3 < h[1] < 1.3)]
    assert inside and outside
    start, start_hit = inside[len(inside) // 2]
    end, end_hit = min(outside, key=lambda item: np.hypot(item[0][0] - start[0], item[0][1] - start[1]))
    path = [(start[0] + (end[0] - start[0]) * k / 12.0, start[1] + (end[1] - start[1]) * k / 12.0) for k in range(13)]
    grounds = (_drawn_height(before, values, start_hit), _drawn_height(before, values, end_hit))
    commits, previews = session.commit_count, controller.bridge.brush.previews
    _stroke(controller, surface, path)
    after = session.values[TERRAIN]
    m = int(after["size"])
    assert m > n and session.commit_count == commits + 1
    assert controller.bridge.brush.previews - previews <= len(path) + 1          # one preview a frame at most
    left, front = (heightfield_basin(after)[k] - heightfield_basin(before)[k] for k in (0, 1))

    def placed(hit):
        return (hit[0] * (n - 1) + left) / (m - 1), (hit[1] * (n - 1) + front) / (m - 1)
    assert _drawn_height(after, values, placed(start_hit)) > grounds[0] + 0.02     # the stroke's first dabs, in place
    assert _drawn_height(after, values, placed(end_hit)) > grounds[1] + 0.02       # and its last, past the old grid
    assert session.undo() and session.values[TERRAIN] == before


def test_land_past_the_largest_grids_reach_is_refused_out_loud(neon):
    """At the cap the brush says so: the cursor's refused state while the pointer is over land it cannot reach, and
    one notice when a stroke is tried there; nothing is painted or saved. Reachable land paints as ever."""
    from rendering.gl_programs.neon_terrain_extent import MAX_GRID_SIZE, grow_heightfield
    preset = _presets()[-1]
    terrain = _Store(preset).values[TERRAIN]
    room = MAX_GRID_SIZE - int(terrain["size"])
    assert room > 0
    capped = grow_heightfield(terrain, 0, room, 0, room)           # all the room spent to the right and the back
    controller, surface = neon(preset, {TERRAIN: capped})
    controller.bridge.zoomBy(-6.0, True)
    surface.pump(2)
    bridge, session = controller.bridge, controller.session
    land = _land(controller)
    unreachable = [p for p, h in land if h[0] < -0.01 or h[1] < -0.01]
    reachable = [p for p, h in land if 0.1 < h[0] < 0.9 and 0.1 < h[1] < 0.9]
    assert unreachable and reachable
    bridge.setBrushActive(True)
    bridge.brushHover(*reachable[0])
    surface.pump(2)
    assert bridge.brushState["refused"] is False and bridge.brushCursor
    bridge.brushHover(*unreachable[0])
    surface.pump(2)
    assert bridge.brushState["refused"] is True and bridge.brushCursor        # the footprint is still drawn there
    before, commits = session.values[TERRAIN], session.commit_count
    refusal = bridge.brush.target.refusal
    assert refusal and bridge.message != refusal
    bridge.brushPress(*unreachable[0])
    surface.pump(2)
    bridge.brushMove(unreachable[0][0] + 4.0, unreachable[0][1])
    surface.pump(2)
    bridge.brushRelease()
    surface.pump(2)
    assert bridge.message == refusal and bridge.brush.refusals > 0
    assert session.values[TERRAIN] == before and session.commit_count == commits and not session.gesture_active
    # Back over reachable land the state clears, and a stroke there paints (clipped at the cap, never refused).
    bridge.brushHover(*reachable[0])
    surface.pump(2)
    assert bridge.brushState["refused"] is False
    bridge.setBrushActive(False)
    _stroke(controller, surface, [reachable[0], (reachable[0][0] + 5.0, reachable[0][1])])
    assert session.commit_count == commits + 1 and int(session.values[TERRAIN]["size"]) == MAX_GRID_SIZE
