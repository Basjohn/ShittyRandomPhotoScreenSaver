"""Neon Lake's volumetric clouds and nebula, through the production renderer."""
from dataclasses import replace

import numpy as np

from tests.test_neon_lake_renderer import _snapshot, target  # noqa: F401  (pytest fixture)


def _scene(time=12.0, **parameters):
    snapshot = _snapshot(**{**dict(
        scene3d_detail="High", shockwave_grid_sky_enabled=True, shockwave_grid_sky_strength=1.0,
        shockwave_grid_sky_color=[20, 30, 70, 255], shockwave_grid_cloud_color=[200, 200, 220, 255],
        shockwave_grid_sun_enabled=True, shockwave_grid_sun_mode="Moon",
        shockwave_grid_volumetric_clouds=False, shockwave_grid_nebula_enabled=False,
        # Nothing else moves with the animation clock, so a drift is the only change over time.
        shockwave_grid_scroll=0.0, shockwave_grid_idle=0.0, shockwave_grid_water_detail=0.0,
        shockwave_grid_water_reflection=0.0,
        shockwave_grid_sun_orbit_enabled=False, shockwave_grid_starscape_beat=False), **parameters})
    state = snapshot.logical.mode_state
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(state, events=(),
                                                                                 animation_time=time)))


def _changed(a, b):
    return int(np.count_nonzero(np.max(np.abs(a.astype(int) - b.astype(int)), axis=2) > 3))


def test_clouds_and_nebula_change_only_what_they_should(target):
    capture, host = target
    plain = _scene()
    capture.render(host, plain)
    base = capture.render(host, plain)
    clouds = capture.render(host, _scene(shockwave_grid_volumetric_clouds=True, shockwave_grid_cloud_coverage=0.7))
    nebula = capture.render(host, _scene(shockwave_grid_nebula_enabled=True, shockwave_grid_nebula_intensity=1.0))
    assert _changed(base, clouds) > 500 and _changed(base, nebula) > 500
    # Without a sky there is nothing to put them in.
    no_sky = _scene(shockwave_grid_sky_enabled=False)
    plain_no_sky = capture.render(host, no_sky)
    assert _changed(plain_no_sky, capture.render(host, _scene(shockwave_grid_sky_enabled=False,
                                                              shockwave_grid_volumetric_clouds=True,
                                                              shockwave_grid_nebula_enabled=True))) == 0
    # Settings that are off leave the picture as it was (intensity, coverage and drift alone do nothing).
    idle = capture.render(host, _scene(shockwave_grid_cloud_coverage=0.9, shockwave_grid_nebula_intensity=1.0,
                                       shockwave_grid_cloud_drift=1.0, shockwave_grid_nebula_drift=1.0))
    assert _changed(base, idle) == 0


def test_cloud_and_nebula_drift_move_with_the_animation_clock_only_when_set(target):
    capture, host = target
    for still, moving in (({"shockwave_grid_volumetric_clouds": True, "shockwave_grid_cloud_coverage": 0.7,
                            "shockwave_grid_cloud_drift": 0.0},
                           {"shockwave_grid_volumetric_clouds": True, "shockwave_grid_cloud_coverage": 0.7,
                            "shockwave_grid_cloud_drift": 1.0}),
                          ({"shockwave_grid_nebula_enabled": True, "shockwave_grid_nebula_intensity": 1.0,
                            "shockwave_grid_nebula_drift": 0.0},
                           {"shockwave_grid_nebula_enabled": True, "shockwave_grid_nebula_intensity": 1.0,
                            "shockwave_grid_nebula_drift": 1.0})):
        capture.render(host, _scene(10.0, **still))
        assert _changed(capture.render(host, _scene(10.0, **still)), capture.render(host, _scene(60.0, **still))) == 0
        assert _changed(capture.render(host, _scene(10.0, **moving)), capture.render(host, _scene(60.0, **moving))) > 200
