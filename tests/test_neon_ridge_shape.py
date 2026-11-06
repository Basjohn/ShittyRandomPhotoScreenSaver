"""Neon Lake's ridge (skyline) lines stay lines.

The skyline pass draws a copy of the land lifted a few physical pixels and leaves it only where it is not behind
the real surface. Pass 6 shaped each ridge along its length (wider, thinner, fading); a lift grown too far exposed
the lifted copy over the near land's own face as a solid molten lobe under a Preset 3 dune (lead review,
2026-11-06). With bloom off, the crest colour's own pixels must stay a thin band in every column."""
from dataclasses import replace

import numpy as np

from rendering.gl_programs.heightfield import heightfield_surface_bytes
from tests.test_neon_lake_renderer import _snapshot, target  # noqa: F401  (pytest fixture)


def _dunes(crest_alpha, depth_scale=0.3, thickness=1.8):
    """Rolling land (no water) in rows of dunes, seen low over the near ones (Preset 3-like Depth Scale and thickness)."""
    snapshot = _snapshot(
        scene3d_detail="High", shockwave_grid_wire_display="Glass", shockwave_grid_water_reflection=0.0,
        shockwave_grid_idle=0.0, shockwave_grid_scroll=0.0, shockwave_grid_terrain_reaction_enabled=False,
        shockwave_grid_glow=0.0, shockwave_grid_depth_scale=depth_scale, shockwave_grid_horizon_thickness=thickness,
        shockwave_grid_terrain_height=1.2, shockwave_grid_contour_lines=0.0,
        shockwave_grid_crest_color=[255, 200, 40, crest_alpha],
        shockwave_grid_tilt=0.1, shockwave_grid_turn=0.0, shockwave_grid_scene_scale=1.8,
        shockwave_grid_scene_pan_x=0.0, shockwave_grid_scene_pan_y=0.2)
    state = snapshot.logical.mode_state
    terrain = dict(state.parameters["shockwave_grid_terrain"])
    size = terrain["size"]
    heights = [0.12 + 0.3 * (0.5 + 0.5 * np.sin(row / (size - 1) * 9.0 * np.pi + 0.6 * np.sin(col * 0.4)))
               for row in range(size) for col in range(size)]
    terrain.update(data=heightfield_surface_bytes({"size": size, "heights": heights}), maximum=max(heights))
    for key in ("basin", "grid", "extent"):
        terrain.pop(key, None)
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(
        state, parameters={**dict(state.parameters), "shockwave_grid_terrain": terrain})))


def _longest_runs(mask):
    best = np.zeros(mask.shape[1], dtype=int)
    run = np.zeros(mask.shape[1], dtype=int)
    for row in mask:
        run = np.where(row, run + 1, 0)
        best = np.maximum(best, run)
    return best


def test_ridge_lines_stay_thin_bands_over_near_dunes(target):
    capture, host = target
    capture.render(host, _dunes(0))
    off = capture.render(host, _dunes(0)).astype(int)
    capture.render(host, _dunes(255))
    on = capture.render(host, _dunes(255)).astype(int)
    ridge = np.abs(on - off).sum(axis=-1) > 24
    assert ridge.any(), "the dunes draw ridge lines"
    runs = _longest_runs(ridge)
    # Thickest legitimate ridge: 3 px authored thickness x 3 (Depth Scale growth) x 1.45 (shaping) ~ 13 px, plus
    # antialiasing. The lobe was several times that.
    assert np.percentile(runs[runs > 0], 99) <= 16, sorted(runs)[-10:]


def test_ridge_lines_stay_thin_bands_at_full_depth_scale_and_thickness(target):
    """The extreme corner (Depth Scale 1, Horizon Thickness 3, grazing over dunes): the lifted copy's depth offset
    must stay behind the near land's own face, or it shows over it as a broad translucent sheet (found 6 Nov)."""
    capture, host = target
    capture.render(host, _dunes(0, 1.0, 3.0))
    off = capture.render(host, _dunes(0, 1.0, 3.0)).astype(int)
    capture.render(host, _dunes(255, 1.0, 3.0))
    on = capture.render(host, _dunes(255, 1.0, 3.0)).astype(int)
    ridge = np.abs(on - off).sum(axis=-1) > 24
    assert ridge.any(), "the dunes draw ridge lines"
    runs = _longest_runs(ridge)
    # 3 px thickness x 3 (Depth Scale growth) x 1.45 (shaping) ~ 13 px, plus antialiasing, measured down a column
    # through a ridge that falls steeply across the view (26 px with the fix). The sheet measured 95 px (pass-6
    # shader, the negative control).
    assert np.percentile(runs[runs > 0], 99) <= 30, sorted(runs)[-10:]
