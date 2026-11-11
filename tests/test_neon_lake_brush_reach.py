"""Neon Lake: how much of the land the Studio's preview shows the terrain brush can paint (1B.5).

Operator, 11 Nov: "Visible land is not editable with the brush, the limits are constrained despite it being part of the
scene." The brush picks through the production framed camera (``pick_terrain``); the drawn ground is the CPU mirror of
the scene (``neon_terrain_surface.scene_surface``), which carries the land past the authored grid as the procedural
continuation and far hills to the horizon. These checks sweep the presented frame of a live (hidden, offscreen) Neon
Lake Studio at every shipped preset's terrain, find where each ray meets the drawn land, and split it:

* land on the authored grid: always paintable (any refusal there would be a clamp narrower than the grid);
* land past the grid (continuation / far hills): visible and refused today. The strict xfail states the requirement
  (every visible land point paintable) until the lead decides how the authored domain reaches it.
"""
from __future__ import annotations

import time

import numpy as np
import pytest

MODE = "shockwave_grid"


class _Store:
    def __init__(self, preset_index: int):
        from core.settings.visualizer_mode_settings import mode_settings
        from core.settings.visualizer_presets import resolve_visualizer_activation_payload
        self.values = dict(resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": preset_index},
                                                                 mode=MODE).resolved_config)
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

    def open_preset(index):
        adapter = create_adapter(MODE)
        adapter.recorded_clips = lambda: ()
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(1600, 900), present_on_show=False))
            return surfaces[0]
        controller = StudioController(adapter, _Store(index), _Presence(), factory)
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
    """Grid uv where the ray through ``point`` meets the drawn land (inside the grid or past it), or None (sky).
    The same march as ``pick_terrain`` without its grid bound."""
    from core.constants.neon_lake_world import FAR_PLANE
    from ui.studio import shockwave_grid_adapter as neon
    view = neon.terrain_view(frame, geometry)
    fx, fy, fw, fh = view.field
    u, v = (float(point[0]) - fx) / fw, (float(point[1]) - fy) / fh
    if not (0.0 <= u <= 1.0 and 0.0 <= v <= 1.0):
        return None
    size, grid, basin, height = neon._terrain_surface(values)
    eye, direction = np.asarray(view.eye, dtype=np.float64), np.asarray(view.ray(u, v), dtype=np.float64)
    def above(t):
        p = eye + np.multiply.outer(t, direction)
        gu, gv = neon._grid_uv(size, basin, p[..., 0], p[..., 2])
        return p[..., 1] - neon._ground(grid, basin, height, gu, gv)
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
    gu, gv = neon._grid_uv(size, basin, float(hit[0]), float(hit[2]))
    return float(gu), float(gv)


_MARGIN = 1e-6


def _sweep(controller, columns=48, rows=27):
    """(paintable land points, refused points on the grid, refused points past the grid with their grid uv) over the
    presented frame."""
    from ui.studio.shockwave_grid_adapter import pick_terrain
    frame, values, geometry = controller.brush_scene()
    width, height = geometry[0]
    paintable, refused, past = [], [], []
    for row in range(rows):
        for col in range(columns):
            point = ((col + 0.5) * width / columns, (row + 0.5) * height / rows)
            if pick_terrain(frame, values, point, geometry) is not None:
                paintable.append(point)
                continue
            hit = _ground_hit(frame, values, point, geometry)
            if hit is None:
                continue                                       # sky, or outside the card's field
            if -_MARGIN <= hit[0] <= 1.0 + _MARGIN and -_MARGIN <= hit[1] <= 1.0 + _MARGIN:
                refused.append(point)
            else:
                past.append((point, hit))
    return paintable, refused, past


@pytest.mark.parametrize("preset", _presets())
def test_all_land_on_the_authored_grid_is_paintable(neon, preset):
    controller, _surface = neon(preset)
    paintable, refused, _past = _sweep(controller)
    assert paintable, "no authored land on screen"
    assert refused == [], f"preset {preset + 1}: authored land the brush refuses: {refused[:5]}"


@pytest.mark.parametrize("preset", _presets())
def test_visible_land_past_the_authored_grid_is_refused_today(neon, preset):
    """The reproduction: land the scene draws past the authored grid (the continuation and far hills), which
    ``pick_terrain`` refuses, at a sizeable share of the presented land, once the preview view is dollied back (a
    preview pose, as the wheel leaves it)."""
    controller, surface = neon(preset)
    controller.bridge.zoomBy(-6.0, True)
    surface.pump(2)
    paintable, _refused, past = _sweep(controller)
    assert past, f"preset {preset + 1}: no visible land past the grid"
    share = len(past) / (len(past) + len(paintable))
    assert share > 0.05, share


@pytest.mark.xfail(strict=True, reason="1B.5 open: land past the authored grid is procedural continuation, not "
                                       "authored data; the paintable domain awaits the lead's decision")
@pytest.mark.parametrize("preset", _presets())
def test_every_visible_land_point_is_paintable(neon, preset):
    controller, surface = neon(preset)
    controller.bridge.zoomBy(-6.0, True)
    surface.pump(2)
    _paintable, refused, past = _sweep(controller)
    assert refused == [] and past == []
