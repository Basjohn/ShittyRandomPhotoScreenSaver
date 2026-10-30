"""Same-ID thin glass must not shimmer from cancellation during subpixel travel.

The scene/probe are rendered by the real host. No operator profile, mutable
curated preset, changing audio/radius, or image golden decides the oracle.
"""
from dataclasses import replace

import numpy as np
import pytest

from tests._visualizer_frozen_settings import frozen_visualizer_settings


@pytest.mark.qt
@pytest.mark.parametrize('radius_pixels', (5., 8., 12.))
def test_tiny_thin_shell_material_stays_continuous_during_subpixel_motion(qt_app, monkeypatch, radius_pixels):
    from rendering.gl_programs.extruded_bubble_scene import physical_camera
    from rendering.quick.visualizer.implementations import extruded_bubble as renderer
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.extruded_bubble_capture import _draw
    from tools.labs.render_target import OffscreenRenderTarget
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    width, height = 594, 383
    settings = {**frozen_visualizer_settings('extruded_bubble'),
        'extruded_bubble_camera_projection': 'Perspective',
        'extruded_bubble_light_type': 'Sunlit Surface', 'extruded_bubble_lighting_coverage': 'SCENE',
        'extruded_bubble_camera_fov': 45, 'extruded_bubble_turn': 0., 'extruded_bubble_tilt': 0.,
        'extruded_bubble_scene_scale': 1., 'extruded_bubble_scene_pan_x': .04,
        'extruded_bubble_scene_pan_y': .296, 'extruded_bubble_camera_position': [0., 0., -.025],
        'extruded_bubble_light_direction': [0., 1., -.5548, 0., -1., .5548],
        'extruded_bubble_water_colour': [18, 30, 48, 255],
        'extruded_bubble_depth_colour': [12, 20, 34, 255],
        'extruded_bubble_light_colour': [183, 198, 214, 255],
        'extruded_bubble_softness': .1, 'extruded_bubble_clarity': 0.,
        'extruded_bubble_sparkle': 1., 'extruded_bubble_light_strength': 1.,
        'extruded_bubble_rim_glow': 1., 'extruded_bubble_exposure': .9,
        'extruded_bubble_focus': .5, 'extruded_bubble_aperture': .4,
        'extruded_bubble_bead_chains': [0, 0], 'extruded_bubble_particles': [0., 0.]}
    snapshot = _build_spectrum_preview_snapshot(width=width, height=height,
                                               mode='extruded_bubble', settings=settings)
    state = snapshot.logical.mode_state
    p = dict(state.parameters)
    axes, _, eye, span, _ = physical_camera(
        p['extruded_bubble_turn'], p['extruded_bubble_tilt'], width / height,
        p['extruded_bubble_scene_scale'], p['extruded_bubble_scene_pan_x'], p['extruded_bubble_scene_pan_y'],
        p['extruded_bubble_camera_fov'], p['extruded_bubble_camera_position'], True)
    axes = np.asarray(axes).reshape(3, 3)
    depth = 16.5
    world_pixel = 2 * span[1] * depth / height
    # An off-axis thin shell at a normal world depth, not an enlarged near sphere.
    centre = np.asarray(eye) + axes.T @ np.asarray((.64 * span[0] * depth, .64 * span[1] * depth, -depth))
    radius = radius_pixels * world_pixel
    state = replace(state, time=6., motion_phase=0., level=0., flash=0., rays=.15,
                    emission=0., chain_activity=0., bubbles=(), clusters=(), wakes=(),
                    drift_families=(), drift_steps=b'')
    snapshot = replace(snapshot, logical=replace(snapshot.logical, mode_state=state))
    target, host = OffscreenRenderTarget(width, height), QuickVisualizerRenderHost()
    original_glass = renderer._glass
    try:
        _draw(host, target, snapshot, (width, height), (width, height))
        # Hold the actual captured scene probe, as well as source/camera/time.
        monkeypatch.setattr(renderer.QuickExtrudedBubbleRenderer, '_capture_probe', lambda *_: None)
        for diagnostic in (0, 1, 2):  # physical composition, reflection, transmission
            monkeypatch.setattr(renderer, '_glass', lambda knobs, near, d=diagnostic:
                                {**original_glass(knobs, near), 'uDiag': d})
            background, _ = _draw(host, target, snapshot, (width, height), (width, height))
            energy = []
            for frame in range(24):
                point = centre + axes[0] * (world_pixel * .1 * frame)
                record = (*point, radius, 1., 0., 147., -1.)
                moved = replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(state, bubbles=record)))
                pixels, _ = _draw(host, target, moved, (width, height), (width, height))
                energy.append(np.abs(pixels[:, :, :3].astype(float) - background[:, :, :3]).sum())
            assert min(energy) > 100, 'the material must remain present'
            step = np.max(np.abs(np.diff(energy))) / np.mean(energy)
            assert step < .06, (radius_pixels, diagnostic, step)
    finally:
        target.make_current()
        host.release_resources()
        target.close()
