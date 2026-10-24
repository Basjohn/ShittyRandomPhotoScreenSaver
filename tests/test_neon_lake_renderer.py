"""Neon renderer resource contracts and actual GL/QSG clipping; no preset art goldens."""
from dataclasses import replace
import json
from pathlib import Path
import struct
import subprocess
import sys

import numpy as np
from OpenGL import GL as gl
import pytest

from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from rendering.gl_programs.heightfield import heightfield_surface_bytes
from tests.test_qtquick_extruded_spectrum import H, W, _Target
from tests._visualizer_frozen_settings import frozen_visualizer_settings


def _snapshot(**parameters):
    # Same production seam as the Shockwave fixture, without importing its
    # retired flat-grid shader oracles while the renderer replacement lands.
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode='shockwave_grid',
                                               settings=frozen_visualizer_settings('shockwave_grid'))
    state = snapshot.logical.mode_state
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(
        state, parameters={**dict(state.parameters), **parameters})))


@pytest.fixture
def target(qt_app):
    capture, host = _Target(), QuickVisualizerRenderHost()
    try:
        yield capture, host
    finally:
        assert capture.capture.context.makeCurrent(capture.capture.surface)
        host.release_resources()
        capture.close()


def _pose(snapshot, *, turn=.83, tilt=.7, scale=3.8, pan_x=1.7, pan_y=-1.6):
    state = snapshot.logical.mode_state
    values = {**dict(state.parameters), 'shockwave_grid_turn': turn, 'shockwave_grid_tilt': tilt,
              'shockwave_grid_scene_scale': scale, 'shockwave_grid_scene_pan_x': pan_x,
              'shockwave_grid_scene_pan_y': pan_y}
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(state, parameters=values)))


def test_warmed_neon_frames_allocate_or_upload_no_static_resources(target, monkeypatch):
    capture, host = target
    snapshot = _snapshot(shockwave_grid_glow=.8, shockwave_grid_sky_enabled=True)
    capture.render(host, snapshot)
    renderer = host._implementations['shockwave_grid']
    allocation = renderer._target.allocation
    names = dict(renderer._target._names)
    terrain_uploads = renderer._heightfield.uploads
    def forbidden(*args, **kwargs):
        pytest.fail('ordinary warmed frame allocated/uploaded static GPU resources')
    # Mapped onset/event-ring writes and GL fences remain the authored stream;
    # static meshes, shaders, terrain texture and render targets cannot rebuild.
    from rendering.quick.scene3d import resources
    monkeypatch.setattr(resources, 'compile_program', forbidden)
    monkeypatch.setattr(resources, 'compile_compute_program', forbidden)
    for name in ('glCreateProgram', 'glCreateShader', 'glCreateTextures', 'glCreateBuffers',
                 'glCreateVertexArrays', 'glCreateFramebuffers', 'glTextureStorage2D',
                 'glTextureStorage2DMultisample', 'glNamedBufferStorage', 'glTextureSubImage2D'):
        monkeypatch.setattr(gl, name, forbidden)
    for frame in (snapshot, _pose(snapshot), _pose(snapshot, scale=.3, pan_x=-1.8, pan_y=1.8), snapshot):
        capture.render(host, frame)
        assert renderer._target.allocation == allocation
        assert renderer._target._names == names
        assert renderer._heightfield.uploads == terrain_uploads


def test_authored_terrain_replacement_uploads_once_without_target_churn(target, monkeypatch):
    capture, host = target
    snapshot = _snapshot(shockwave_grid_glow=.0)
    capture.render(host, snapshot)
    renderer = host._implementations['shockwave_grid']
    names = dict(renderer._target._names)
    allocation = renderer._target.allocation
    texture = renderer._heightfield.texture_id
    uploads = renderer._heightfield.uploads
    terrain = dict(snapshot.logical.mode_state.parameters['shockwave_grid_terrain'])
    heights = list(struct.unpack(f"<{terrain['size'] ** 2 * 2}f", terrain['data'])[::2])
    middle = len(heights) // 2
    heights[middle] = .2 if heights[middle] != .2 else .4  # TEST INPUT: a bounded real authoring edit
    terrain['data'] = heightfield_surface_bytes({'size': terrain['size'], 'heights': heights})
    terrain['maximum'] = max(heights)
    state = snapshot.logical.mode_state
    changed = replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(
        state, parameters={**dict(state.parameters), 'shockwave_grid_terrain': terrain})))
    real_upload = gl.glTextureSubImage2D
    calls = []
    def upload(*args, **kwargs):
        calls.append(args[:7])
        return real_upload(*args, **kwargs)
    monkeypatch.setattr(gl, 'glTextureSubImage2D', upload)
    for frame in (changed, changed, _pose(changed), changed):
        capture.render(host, frame)
    assert len(calls) == 1 and renderer._heightfield.uploads == uploads + 1
    assert renderer._heightfield.texture_id == texture
    assert renderer._target.allocation == allocation and renderer._target._names == names



def test_raised_terrain_lifts_a_low_eye_above_the_new_land():
    """Terrain Height reaches the shared camera's floor: the eye never sinks into raised land."""
    from rendering.gl_programs.neon_lake_basin_program import basin_view
    from core.settings.neon_lake_camera import SPEC
    parameters = dict(_snapshot(shockwave_grid_terrain_reaction_enabled=False).logical.mode_state.parameters)
    terrain = dict(parameters['shockwave_grid_terrain'])
    terrain.update(data=heightfield_surface_bytes({'size': terrain['size'], 'heights': [.5] * terrain['size'] ** 2}),
                   maximum=.5)
    # Look level from straight above the land's centre, pushed far below it.
    low = {**parameters, 'shockwave_grid_terrain': terrain, 'shockwave_grid_tilt': 0., 'shockwave_grid_turn': 0.,
           'shockwave_grid_scene_scale': 8., 'shockwave_grid_scene_pan_x': 0., 'shockwave_grid_scene_pan_y': 0.,
           'shockwave_grid_camera_position': [0., -1., 0.]}
    field = (0., 0., 1600., 900.)
    eyes = [basin_view({**low, 'shockwave_grid_terrain_height': height}, field).eye for height in (.4, 1.)]
    for eye, height in zip(eyes, (.4, 1.)):
        assert eye[1] >= .5 * height + SPEC.clearance - 1e-9
    assert eyes[1][1] > eyes[0][1]


def test_actual_sun_toggle_preserves_sky_and_sky_strength_does_not_fade_sun(target):
    capture, host = target
    base = _snapshot(shockwave_grid_glow=0., shockwave_grid_sky_enabled=True,
                     shockwave_grid_sun_color=[245, 20, 175, 255],
                     shockwave_grid_turn=0., shockwave_grid_tilt=.04)
    def render(sun, strength):
        state = base.logical.mode_state
        frame = replace(base, logical=replace(base.logical, mode_state=replace(
            state, parameters={**dict(state.parameters), 'shockwave_grid_sun_enabled': sun,
                               'shockwave_grid_sky_strength': strength})))
        return capture.render(host, frame)
    sky_only = render(False, .7)
    sky_sun = render(True, .7)
    sun_only = render(True, 0.)
    neither = render(False, 0.)
    # Derive coverage from real production pixels, not a golden art layout.
    sun_change = np.max(np.abs(sun_only - neither), axis=2) > 8
    sky_change = np.max(np.abs(sky_only - neither), axis=2) > 8
    assert np.count_nonzero(sun_change) > 20
    assert np.count_nonzero(sky_change & ~sun_change) > 100
    assert np.count_nonzero(np.max(np.abs(sky_sun - sky_only), axis=2) > 8) > 20
    # Opaque Sun centres have the same colour with and without the sky layer.
    centre = sun_change & (sun_only[..., 3] == 255) & (neither[..., 3] < 5)
    assert np.count_nonzero(centre) > 10
    assert np.abs(sky_sun[centre] - sun_only[centre]).max() <= 2
    assert np.max(sun_only[centre, 0]) > 150
    assert np.max(sun_only[centre, 2]) > 100


@pytest.mark.parametrize('body', ['Moon', 'Sun'])
def test_real_land_depth_masks_low_celestial_disc_and_halo(target, body):
    """A celestial background body cannot paint a disc or halo through the land."""
    capture, host = target
    base = _snapshot(shockwave_grid_sun_mode=body, shockwave_grid_moon_phase=.5,
                     shockwave_grid_sky_enabled=True,
                     shockwave_grid_sun_x=1.05, shockwave_grid_sun_size=.3,
                     shockwave_grid_sun_orbit_enabled=False, shockwave_grid_sun_rays_enabled=False,
                     shockwave_grid_water_reflection=0., shockwave_grid_glow=.55,
                     shockwave_grid_celestial_glow_enabled=True, shockwave_grid_celestial_glow_strength=2.,
                     shockwave_grid_tilt=.04, shockwave_grid_turn=0., shockwave_grid_scene_scale=.75)
    state = base.logical.mode_state
    terrain = dict(state.parameters['shockwave_grid_terrain'])
    terrain.update(data=heightfield_surface_bytes({'size': terrain['size'],
                                                  'heights': [.8] * terrain['size'] ** 2}), maximum=.8)
    base = replace(base, logical=replace(base.logical, mode_state=replace(
        state, parameters={**dict(state.parameters), 'shockwave_grid_terrain': terrain})))

    def pair(y, z):
        frames = [_wire_frame(base, 'Vertices', shockwave_grid_sun_enabled=enabled,
                              shockwave_grid_sun_y=y, shockwave_grid_sun_z=z) for enabled in (False, True)]
        return [capture.render(host, frame) for frame in frames]

    absent, above = pair(3., -6.)
    assert np.count_nonzero(np.max(np.abs(above-absent), axis=2) > 8) > 30
    absent, below = pair(.1, -2.)
    assert np.max(np.abs(below-absent)) <= 2


def test_horizon_thickness_and_inherited_crest_colour_reach_real_gpu_pixels(target):
    """The authored far contour width and existing crest RGBA reach its visible silhouette."""
    capture, host = target
    base = _snapshot(shockwave_grid_sun_enabled=False, shockwave_grid_glow=0.,
                     shockwave_grid_water_reflection=0., shockwave_grid_tilt=.04,
                     shockwave_grid_turn=0., shockwave_grid_scene_scale=.75)
    def image(width, colour):
        return capture.render(host, _wire_frame(base, 'Vertices', shockwave_grid_horizon_thickness=width,
                                               shockwave_grid_crest_color=colour))
    red = [255, 0, 0, 255]
    thin, thick = image(0., red), image(4., red)
    # Only width changes here: derive the real contour's added coverage from
    # rendered pixels rather than pinning operator art or guessing a horizon row.
    added = (thick[..., 0]-thin[..., 0] > 12)
    assert np.count_nonzero(added) > 50
    blue = image(4., [0, 0, 255, 255])
    assert float(np.mean(thick[added, 0]-blue[added, 0])) > 20
    assert float(np.mean(blue[added, 2]-thick[added, 2])) > 20


def _resolved_emission_pixels(renderer, width=W, height=H):
    """Actual production MRT radiance, before bloom can conceal or spread invalid values."""
    allocated_width, allocated_height, samples = renderer._target.allocation
    pixels = np.empty((allocated_height, allocated_width, 4), dtype=np.float32)
    texture = renderer._target._names['emission_resolve' if samples > 1 else 'emission']
    gl.glGetTextureImage(texture, 0,
                         gl.GL_RGBA, gl.GL_FLOAT, pixels.nbytes, pixels)
    return pixels[:height, :width][::-1].copy()


def test_production_moon_whole_surface_emission_follows_phase_glow_and_pulse(target):
    """Actual MRT output glows across the bright body and faint shaded hemisphere."""
    capture, host = target
    base = _snapshot(shockwave_grid_sun_mode='Moon', shockwave_grid_sun_x=0.,
                     shockwave_grid_sun_y=3., shockwave_grid_sun_z=-6., shockwave_grid_sun_size=.45,
                     shockwave_grid_sun_orbit_enabled=False, shockwave_grid_sun_rays_enabled=False,
                     shockwave_grid_water_reflection=0., shockwave_grid_glow=.55,
                     shockwave_grid_sky_enabled=True, shockwave_grid_starscape_beat=False,
                     shockwave_grid_star_color=[0,0,0,0], shockwave_grid_cloud_color=[0,0,0,0],
                     shockwave_grid_moon_color=[190,210,255,255],
                     shockwave_grid_celestial_glow_enabled=True, shockwave_grid_celestial_glow_strength=1.,
                     shockwave_grid_celestial_glow_reactivity=0., shockwave_grid_celestial_rim_vertices=False,
                     shockwave_grid_tilt=.04, shockwave_grid_turn=0., shockwave_grid_scene_scale=.75)
    def draw(phase, enabled=True, halo=True, pulse=False):
        frame = _wire_frame(base, 'Vertices', shockwave_grid_moon_phase=phase,
                            shockwave_grid_sun_enabled=enabled,
                            shockwave_grid_celestial_glow_enabled=halo,
                            shockwave_grid_celestial_glow_reactivity=2. if pulse else 0.)
        if pulse:
            frame = replace(frame, logical=replace(frame.logical, mode_state=replace(
                frame.logical.mode_state, events=((0.,0.,0.,1.),))))
        colour = capture.render(host, frame)
        emitted = _resolved_emission_pixels(host._implementations['shockwave_grid'])
        assert np.isfinite(emitted).all()
        return colour, emitted

    absent_colour, absent_emission = draw(.5, False)
    full_colour, full_emission = draw(.5)
    body = np.max(np.abs(full_colour-absent_colour), axis=2) > 20
    y, x = np.nonzero(body)
    assert len(x) > 30  # Positive control: an actual visible full Moon was drawn.
    cx, cy = .5*(x.min()+x.max()), .5*(y.min()+y.max())
    radius = .5*min(x.max()-x.min(), y.max()-y.min())
    yy, xx = np.ogrid[:H, :W]
    centre = (xx-cx)**2+(yy-cy)**2 < (.20*radius)**2
    assert np.count_nonzero(centre) >= 5
    full_surface = float(np.mean((full_emission-absent_emission)[centre,:3]))
    new_colour, new_emission = draw(0.)
    assert np.count_nonzero(np.max(np.abs(new_colour-absent_colour),axis=2)>2) > 20
    shaded_surface = float(np.mean((new_emission-absent_emission)[centre,:3]))
    assert full_surface > shaded_surface*4. > 0.
    unlit_colour, unlit_emission = draw(.5,halo=False)
    assert np.count_nonzero(np.max(np.abs(unlit_colour-absent_colour),axis=2)>8) > 30
    assert np.max(np.abs(unlit_emission-absent_emission)) < 1e-3
    _, pulsed_emission = draw(.5,pulse=True)
    pulsed_surface = float(np.mean((pulsed_emission-absent_emission)[centre,:3]))
    assert full_surface*1.05 < pulsed_surface < full_surface*4.5
    for phase in (.075, .125, .25, .375, .625, .75, .875, .925, 1.):
        draw(phase)


def test_maximum_moon_response_preserves_bright_face_ldr_headroom(target):
    """A bright test-owned Moon must keep its face below sustained RGB white clipping."""
    capture, host = target
    base = _snapshot(shockwave_grid_sun_mode='Moon', shockwave_grid_sun_x=0.,
                     shockwave_grid_sun_y=3., shockwave_grid_sun_z=-6., shockwave_grid_sun_size=.45,
                     shockwave_grid_moon_phase=.5, shockwave_grid_moon_color=[225,240,255,255],
                     shockwave_grid_sun_orbit_enabled=False, shockwave_grid_sun_rays_enabled=False,
                     shockwave_grid_water_reflection=0., shockwave_grid_glow=.55,
                     shockwave_grid_sky_enabled=True, shockwave_grid_starscape_beat=False,
                     shockwave_grid_star_color=[0,0,0,0], shockwave_grid_cloud_color=[0,0,0,0],
                     shockwave_grid_celestial_glow_enabled=True, shockwave_grid_celestial_glow_strength=2.,
                     shockwave_grid_celestial_glow_reactivity=2., shockwave_grid_celestial_rim_vertices=False,
                     shockwave_grid_tilt=.04, shockwave_grid_turn=0., shockwave_grid_scene_scale=.75)
    base = replace(base, logical=replace(base.logical, mode_state=replace(
        base.logical.mode_state, events=((0.,0.,0.,1.),))))
    absent = capture.render(host,_wire_frame(base,'Vertices',shockwave_grid_sun_enabled=False))
    albedo = capture.render(host,_wire_frame(base,'Vertices',shockwave_grid_sun_enabled=True,
                                            shockwave_grid_celestial_glow_enabled=False))
    # Derive the real body from Glow OFF, so changing a bloom footprint cannot
    # move or inflate this face observation region.
    mask = np.max(np.abs(albedo-absent),axis=2)>30
    y,x = np.nonzero(mask)
    assert len(x)>30
    cx,cy = .5*(x.min()+x.max()),.5*(y.min()+y.max())
    radius = .5*min(x.max()-x.min(),y.max()-y.min())
    yy,xx = np.ogrid[:H,:W]
    core = (xx-cx)**2+(yy-cy)**2 < (.35*radius)**2
    assert np.count_nonzero(core)>10
    assert float(np.mean(np.all(albedo[core,:3]>=250,axis=1))) < .05
    shown = capture.render(host,_wire_frame(base,'Vertices',shockwave_grid_sun_enabled=True))
    assert float(np.mean(np.all(shown[core,:3]>=250,axis=1))) < .05


def test_production_solid_moon_masks_stars_on_lit_and_shaded_hemispheres(target, monkeypatch):
    """A real beat star cannot punch through the solid Moon at any phase."""
    import math
    from rendering.quick.visualizer.implementations.shockwave_grid import (
        NEON_SKY_VERTEX_SOURCE, NEON_SKY_FRAGMENT_SOURCE, _SKY_UNIFORMS)

    capture, host = target
    base = _snapshot(shockwave_grid_sun_mode='Moon', shockwave_grid_sun_x=0.,
                     shockwave_grid_sun_y=3., shockwave_grid_sun_z=-6., shockwave_grid_sun_size=.45,
                     shockwave_grid_sun_orbit_enabled=False, shockwave_grid_sun_rays_enabled=False,
                     shockwave_grid_water_reflection=0., shockwave_grid_glow=.55,
                     shockwave_grid_sky_enabled=True, shockwave_grid_starscape_beat=False,
                     shockwave_grid_star_color=[255,255,255,0], shockwave_grid_star_glow_strength=2.,
                     shockwave_grid_star_glow_reactivity=2., shockwave_grid_celestial_glow_enabled=False,
                     shockwave_grid_tilt=-.05, shockwave_grid_turn=0., shockwave_grid_scene_scale=.75)
    capture.render(host, base)
    renderer = host._implementations['shockwave_grid']
    program = renderer._resources.program('sky', NEON_SKY_VERTEX_SOURCE, NEON_SKY_FRAGMENT_SOURCE)
    uniforms = renderer._resources.uniforms('sky', _SKY_UNIFORMS)
    eye, position = np.zeros(3,np.float32), np.zeros(3,np.float32)
    # The production eye and body the sky program actually drew with, not a hand-positioned screen dot.
    gl.glGetUniformfv(program,uniforms['uEye'],eye)
    gl.glGetUniformfv(program,uniforms['uBodyPosition'],position)
    ray = position-eye
    ray /= np.linalg.norm(ray)
    def cell_at(offset):
        offset_ray = ray+np.array([offset*.45/np.linalg.norm(position-eye),0.,0.])
        offset_ray /= np.linalg.norm(offset_ray)
        return np.array([math.floor(math.atan2(offset_ray[0],-offset_ray[2])*420.),
                         math.floor(math.asin(offset_ray[1])*420.),1.,0.],dtype=np.float32)
    cell = [cell_at(0.)]
    draw_count, draw_cells = gl.glUniform1i, gl.glUniform4fv
    enabled = [False]
    def star_count(location,value):
        if location == uniforms['uBeatStarCount'] and int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)) == program:
            draw_cells(uniforms['uBeatStarCells'],1,cell[0])
            value = int(enabled[0])
        return draw_count(location,value)
    monkeypatch.setattr(gl,'glUniform1i',star_count)
    def image(body,phase,star):
        enabled[0] = star
        return capture.render(host,_wire_frame(base,'Vertices',shockwave_grid_sun_enabled=body,
                                               shockwave_grid_moon_phase=phase))
    for offset in (-.65,.65):
        cell[0] = cell_at(offset)
        absent, bright = image(False,0.,False), image(False,0.,True)
        star_pixels = np.max(np.abs(bright-absent),axis=2) > 30
        assert np.count_nonzero(star_pixels) > 5
        for phase in (0.,.25,.75):
            without, with_star = image(True,phase,False), image(True,phase,True)
            difference = np.max(np.abs(with_star-without),axis=2)
            assert np.max(difference[star_pixels]) <= 2


def test_terrain_erases_beat_star_colour_and_emission_even_with_transparent_material(target, monkeypatch):
    import math
    from contextlib import contextmanager
    from rendering.quick.visualizer.implementations import shockwave_grid as module
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_DEPTH

    capture,host=target
    terrain={'size':5,'maximum':.6,
             'data':heightfield_surface_bytes({'size':5,'heights':[.6]*25})}
    base=_wire_frame(_snapshot(shockwave_grid_terrain=terrain,
        shockwave_grid_sun_enabled=False,shockwave_grid_water_reflection=0.,
        shockwave_grid_glow=.8,shockwave_grid_starscape_beat=True,
        shockwave_grid_star_color=[255,255,255,255],shockwave_grid_star_glow_strength=2.,
        shockwave_grid_star_glow_reactivity=2.,shockwave_grid_floor=0.,
        shockwave_grid_glass_strength=0.,shockwave_grid_crest_color=[0,0,0,0],
        shockwave_grid_tilt=.3,shockwave_grid_turn=0.),'Glass')
    capture.render(host,base)
    renderer=host._implementations['shockwave_grid']
    from rendering.gl_programs.neon_lake_basin_program import basin_view
    eye=np.array(basin_view(dict(base.logical.mode_state.parameters),(0.,0.,float(W),float(H))).eye)
    # Aim a real sky star at a point below the authored solid surface.
    ray=np.array([0.,0.,-.5*SHOCKWAVE_DEPTH])-eye
    ray/=np.linalg.norm(ray)
    cell=(math.floor(math.atan2(ray[0],-ray[2])*420),math.floor(math.asin(ray[1])*420),1.,0.)
    enabled=[False]
    monkeypatch.setattr(module,'starscape_beat_cells',lambda *a,**kw:(cell,) if enabled[0] else ())
    def draw(star):
        enabled[0]=star
        colour=capture.render(host,base)
        return colour,_resolved_emission_pixels(renderer)
    absent,off=draw(False)
    shown,on=draw(True)
    assert np.max(np.abs(on[...,:3]-off[...,:3]))<1e-4
    assert np.max(np.abs(shown-absent))<=1
    actual=module._terrain_sky_occlusion_blend
    @contextmanager
    def leaking_emission(emission):
        # Reproduce the old missing source alpha on the emission output:
        # colour erases correctly, while additive glow survives the surface.
        with actual(emission):
            if emission:
                gl.glBlendFuncSeparatei(1,gl.GL_ZERO,gl.GL_ONE,gl.GL_ZERO,gl.GL_ONE)
            yield
    monkeypatch.setattr(module,'_terrain_sky_occlusion_blend',leaking_emission)
    _,leaked=draw(True)
    assert np.max(leaked[...,:3]-off[...,:3])>.1


def test_maximum_water_highlights_have_bounded_float_coverage(target, monkeypatch):
    from rendering.quick.scene3d.target import SceneTarget
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_MAX_STRENGTH
    capture, host = target
    allocate = SceneTarget._allocate_attachment
    def floating_colour(owner, key, samples, width, height, internal):
        # The production colour attachment is RGBA8 and would hide alpha >1.
        # Change only its observation precision; shaders, blending, mesh and
        # all renderer/target ownership remain the actual production paths.
        return allocate(owner, key, samples, width, height,
                        gl.GL_RGBA16F if key == 'colour' else internal)
    monkeypatch.setattr(SceneTarget, '_allocate_attachment', floating_colour)
    snapshot = _snapshot(scene3d_detail='Performance', shockwave_grid_glow=0.,
                         shockwave_grid_sky_enabled=False, shockwave_grid_water_detail=1.,
                         shockwave_grid_wave_height=1., shockwave_grid_wave_speed=1.,
                         shockwave_grid_floor=0., shockwave_grid_water_reflection=0.,
                         shockwave_grid_line_color=[255, 255, 255, 255],
                         shockwave_grid_crest_color=[255, 255, 255, 255])
    state = snapshot.logical.mode_state
    terrain = dict(state.parameters['shockwave_grid_terrain'])
    terrain.update(data=heightfield_surface_bytes({'size': terrain['size'],
                                                  'heights': [0.] * terrain['size'] ** 2}), maximum=0.)
    # Loudest admitted onset strength and minimum onset gap: overlapping crests
    # reach the shader's 2.5 clamp while detail/sheens are at their legal maximum.
    events = tuple((.1 + index * .09, 0., -1.2, SHOCKWAVE_MAX_STRENGTH) for index in range(16))
    snapshot = replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(
        state, parameters={**dict(state.parameters), 'shockwave_grid_terrain': terrain}, events=events)))
    capture.render(host, snapshot)
    scene = host._implementations['shockwave_grid']._target
    width, height, samples = scene.allocation
    assert samples == 1
    gl.glBindTexture(gl.GL_TEXTURE_2D, scene._names['colour'])
    try:
        raw = gl.glGetTexImage(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, gl.GL_FLOAT)
    finally:
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    pixels = np.frombuffer(raw, np.float32).reshape(height, width, 4)
    assert np.isfinite(pixels).all()
    alpha = pixels[..., 3]
    assert alpha.min() >= 0. and alpha.max() <= 1.
    assert np.count_nonzero(alpha > .5) > 20
    assert np.max(pixels[..., :3]) > .5  # Actual luminous water, not an empty target.

def test_unresolved_and_faded_renderer_are_lazy_then_release_cleanly(target):
    from rendering.quick.visualizer.implementations.shockwave_grid import QuickShockwaveGridRenderer
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
    capture, host = target
    renderer = QuickShockwaveGridRenderer()
    assert not renderer.has_resources and not host.has_resources and not host.resolved_mode_ids
    snapshot = _snapshot()
    hidden = replace(snapshot, presentation=replace(snapshot.presentation, content_fade=0.))
    renderer.render(QuickVisualizerRenderFrame(hidden, (0, 0, W, H), (float(W), float(H)), (1.,) * 16, capture.capture.vao))
    assert not renderer.has_resources
    capture.render(host, snapshot)
    live = host._implementations['shockwave_grid']
    assert live.has_resources
    host.release_resources()
    assert not live.has_resources and not host.has_resources


def test_failed_neon_release_is_loud_and_keeps_its_handle_for_legal_retry(target, monkeypatch):
    capture, host = target
    capture.render(host, _snapshot())
    renderer = host._implementations['shockwave_grid']
    texture = renderer._heightfield.texture_id
    actual_delete = gl.glDeleteTextures
    def fail_heightfield(names, *args, **kwargs):
        if texture in list(names):
            raise RuntimeError('injected terrain deletion failure')
        return actual_delete(names, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(gl, 'glDeleteTextures', fail_heightfield)
        with pytest.raises(RuntimeError, match='injected terrain deletion failure'):
            host.release_resources()
        assert renderer._heightfield.texture_id == texture and renderer.has_resources
        assert host._implementations['shockwave_grid'] is renderer
    host.release_resources()
    assert not renderer.has_resources and not host.has_resources


def test_two_contexts_keep_neon_resources_independent(qt_app):
    first, first_host = _Target(), QuickVisualizerRenderHost()
    second, second_host = None, None
    try:
        snapshot = _snapshot()
        first_pixels = first.render(first_host, snapshot)
        first_renderer = first_host._implementations['shockwave_grid']
        second, second_host = _Target(), QuickVisualizerRenderHost()
        second.render(second_host, snapshot)
        second_pixels = second.render(second_host, snapshot)  # warmed baseline, same immutable input
        second_renderer = second_host._implementations['shockwave_grid']
        assert first_renderer is not second_renderer and first_renderer._heightfield is not second_renderer._heightfield
        assert first.capture.context.makeCurrent(first.capture.surface)
        first_host.release_resources()
        assert not first_renderer.has_resources and second_renderer.has_resources
        assert second.capture.context.makeCurrent(second.capture.surface)
        after = second.render(second_host, snapshot)
        # RGBA8 quantization permits one least-significant bit of driver rounding.
        assert np.abs(after - second_pixels).max() <= 1
        assert first_pixels[..., 3].max() > 0
    finally:
        if second is not None:
            assert second.capture.context.makeCurrent(second.capture.surface)
            second_host.release_resources()
            second.close()
        assert first.capture.context.makeCurrent(first.capture.surface)
        first_host.release_resources()
        first.close()


def _qsg_clip_probe(nested=False, sky_focus=False):
    """Run the actual production QSG node/clip host in an isolated Qt process."""
    import time
    from PySide6.QtCore import QMetaObject, QTimer, Qt
    from PySide6.QtGui import QColor, QGuiApplication
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from rendering.quick.bootstrap import configure_quick_graphics
    from rendering.quick.visualizer import VisualizerRenderItem, VisualizerRenderNode, VisualizerRenderNodeTelemetry
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
    from widgets.spotify_visualizer.render_bridge import VisualizerRenderIdentity, VisualizerSnapshotBridge
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests._invisible_windows import keep_off_screen
    configure_quick_graphics(reason='neon-qsg-clip-regression')
    app = QGuiApplication.instance() or QGuiApplication([])
    width, height = 460, 330
    background = (17, 23, 31)
    window = QQuickWindow()
    window.setColor(QColor(*background))
    window.resize(width, height)
    window.setPersistentGraphics(False)
    window.setPersistentSceneGraph(False)
    keep_off_screen(window)
    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy('shockwave_grid'), display_size=(width, height),
        outer_origin=(45., 40.), viewport_extent=(360., 240.), border_width=6., corner_radius=38.,
        content_inset=0., background_color=(0, 0, 0, 0), border_color=(0, 0, 0, 0),
        shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0., shadow_offset=(0., 0.),
        shadow_spread=0., shadow_extensions=(0., 0., 0., 0.))
    snapshot = _pose(_snapshot(shockwave_grid_sky_enabled=True), scale=4., pan_x=.9, pan_y=-.9)
    if sky_focus:
        snapshot = _pose(snapshot, turn=-.2, tilt=.17, scale=1.90333,
                         pan_x=.25, pan_y=1.1432654)
    snapshot = replace(snapshot, presentation=presentation)
    telemetry = VisualizerRenderNodeTelemetry()
    captured = {}
    class Node(VisualizerRenderNode):
        def render(self, state):
            super().render(state)
            info = telemetry.snapshot()
            if info.error is not None:
                captured['error'] = info.error
                return
            if info.draw_count < 1 or captured:
                return
            try:
                target_size = self.renderTarget().pixelSize()
                tw, th = target_size.width(), target_size.height()
                raw = gl.glReadPixels(0, 0, tw, th, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
                pixels = np.flipud(np.frombuffer(bytes(raw), np.uint8).reshape(th, tw, 4))
                yy, xx = np.mgrid[:th, :tw]
                lx, ly = (xx + .5) * width / tw, (yy + .5) * height / th
                x, y, cw, ch = presentation.content_rect
                # Stay two pixels off the antialiased boundary. Rounded corner
                # exclusions use the same resolved radius, not a painted fake.
                outside = (lx < x - 2) | (lx > x + cw + 2) | (ly < y - 2) | (ly > y + ch + 2)
                radius = float(presentation.shell_style['inner_corner_radius'])
                qx = np.maximum(np.maximum(x + radius - lx, lx - (x + cw - radius)), 0.)
                qy = np.maximum(np.maximum(y + radius - ly, ly - (y + ch - radius)), 0.)
                rounded_outside = (qx * qx + qy * qy) > (radius + 2.) ** 2
                if nested:
                    outside |= lx > presentation.outer_rect[0] + 210. + 2.
                rounded_corners = rounded_outside & (lx >= x) & (lx <= x + cw) & (ly >= y) & (ly <= y + ch)
                rgb_delta = np.abs(pixels[..., :3].astype(np.int16) - np.array(background))
                captured.update(outside_delta=int(rgb_delta[outside].max()),
                                rounded_corner_delta=int(rgb_delta[rounded_corners].max()),
                                rounded_corner_pixels=int(rounded_corners.sum()),
                                changed_pixels=int(np.count_nonzero(rgb_delta.max(axis=2) > 3)),
                                draw_count=info.draw_count, mode=info.drawn_mode_id,
                                incoming_scissor=bool(state.scissorEnabled()), error=None)
            except Exception as exc:
                captured['error'] = f'{type(exc).__name__}: {exc}'
    class Item(VisualizerRenderItem):
        def _create_render_node(self):
            return Node(telemetry)
    outer_x, outer_y, outer_w, outer_h = presentation.outer_rect
    parent = QQuickItem(window.contentItem())
    parent.setX(outer_x); parent.setY(outer_y)
    parent.setWidth(210. if nested else outer_w); parent.setHeight(outer_h)
    parent.setClip(bool(nested))
    item = Item(parent, telemetry=telemetry)
    item.set_presentation(presentation)
    logical = snapshot.logical
    bridge = VisualizerSnapshotBridge()
    identity = VisualizerRenderIdentity(runtime_generation=logical.runtime_generation,
        engine_generation=logical.engine_generation, activation_id=logical.activation_id, mode_id=logical.mode_id)
    bridge.begin_activation(runtime_generation=logical.runtime_generation,
                            engine_generation=logical.engine_generation, activation_id=logical.activation_id, mode_id=logical.mode_id)
    assert bridge.publish(snapshot)
    item.bind_render_source(bridge, identity)
    deadline = time.monotonic() + 12.
    closing = [False]
    def poll():
        if captured and not closing[0]:
            closing[0] = True
            for method in ('hide', 'releaseResources', 'close'):
                QMetaObject.invokeMethod(window, method, Qt.ConnectionType.QueuedConnection)
        if closing[0] and telemetry.snapshot().release_count:
            captured['release_count'] = telemetry.snapshot().release_count
            print(json.dumps(captured), flush=True)
            app.quit()
            return
        if time.monotonic() > deadline:
            captured['error'] = captured.get('error') or 'actual QSG clip capture timed out'
            print(json.dumps(captured), flush=True)
            app.quit()
            return
        QTimer.singleShot(20, poll)
    window.show()
    window.update()
    QTimer.singleShot(20, poll)
    app.exec()


@pytest.mark.parametrize('nested,sky_focus', [(False,False),(True,False),(False,True),(True,True)])
def test_actual_neon_qsg_pixels_respect_card_interior_and_rounded_corners(nested, sky_focus):
    completed = subprocess.run([sys.executable, '-c',
        f'from tests.test_neon_lake_renderer import _qsg_clip_probe; _qsg_clip_probe(nested={nested},sky_focus={sky_focus})'],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=25)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout[completed.stdout.index('{'):])
    assert report['error'] is None, report
    assert report['mode'] == 'shockwave_grid' and report['draw_count'] > 0
    assert report['changed_pixels'] > 100
    assert report['outside_delta'] <= 2 and report['rounded_corner_delta'] <= 2
    assert report['rounded_corner_pixels'] > 0 and report['release_count'] > 0
    if nested:
        assert report['incoming_scissor'] is True


def _wire_frame(snapshot, style, **parameters):
    state = snapshot.logical.mode_state
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(state,
        parameters={**dict(state.parameters), 'shockwave_grid_wire_display': style, **parameters})))


def test_retained_surface_styles_and_point_mesh_lifecycle(target):
    capture, host = target
    snapshot = _snapshot(shockwave_grid_glow=0., shockwave_grid_sky_enabled=False,
                         shockwave_grid_floor=0., shockwave_grid_water_reflection=0.,
                         shockwave_grid_wire_display='Vertices')  # TEST INPUT, not an authored preset default
    vertices = capture.render(host, snapshot)
    renderer = host._implementations['shockwave_grid']
    assert renderer._points_cells is not None and renderer._points_data is not None
    glass = capture.render(host, _wire_frame(snapshot, 'Glass'))
    assert renderer._points_cells is None and renderer._points_data is None
    mixed = capture.render(host, _wire_frame(snapshot, 'Glass + Vertices'))
    assert renderer._points_cells is not None and renderer._points_data is not None
    for a, b in ((vertices, glass), (vertices, mixed), (glass, mixed)):
        assert np.count_nonzero(np.max(np.abs(a-b), axis=2) > 8) > 100
    host.release_resources()
    assert not renderer.has_resources and renderer._points_cells is None and not renderer._resources._meshes


@pytest.mark.parametrize('style', ['Vertices', 'Glass + Vertices'])
def test_warmed_vertex_frames_reuse_static_resources_and_target(target, monkeypatch, style):
    from rendering.quick.scene3d import resources
    capture, host = target
    snapshot = _wire_frame(_snapshot(shockwave_grid_glow=0.), style)
    capture.render(host, snapshot)
    renderer = host._implementations['shockwave_grid']
    points = renderer._points_data
    allocation, names = renderer._target.allocation, dict(renderer._target._names)
    uploads = renderer._heightfield.uploads
    def forbidden(*args, **kwargs):
        pytest.fail('warmed vertex frame allocated/uploaded static resources')
    monkeypatch.setattr(resources, 'compile_program', forbidden)
    monkeypatch.setattr(resources, 'compile_compute_program', forbidden)
    for name in ('glCreateProgram', 'glCreateShader', 'glCreateTextures', 'glCreateBuffers',
                 'glCreateVertexArrays', 'glCreateFramebuffers', 'glTextureStorage2D',
                 'glTextureStorage2DMultisample', 'glNamedBufferStorage', 'glTextureSubImage2D'):
        monkeypatch.setattr(gl, name, forbidden)
    for frame in (snapshot, _pose(snapshot), snapshot):
        capture.render(host, frame)
        assert renderer._points_data == points
        assert renderer._target.allocation == allocation and renderer._target._names == names
        assert renderer._heightfield.uploads == uploads


@pytest.mark.parametrize('style', ['Vertices', 'Glass + Vertices'])
@pytest.mark.parametrize('dpr', [1, 2])
def test_same_physical_card_pixels_survive_embedding_in_a_larger_viewport(qt_app, style, dpr):
    """Window extent cannot magnify marks/curves or change bloom on an unchanged card."""
    from tools.transition_contact_sheet import TransitionCapture

    snapshot = _wire_frame(_snapshot(shockwave_grid_glow=.55), style)
    card_w, card_h = W * dpr, H * dpr
    images = []
    for window_factor in (1, 2):
        pixel_w, pixel_h = card_w * window_factor, card_h * window_factor
        capture = TransitionCapture(pixel_w, pixel_h)
        host = QuickVisualizerRenderHost()
        try:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glClearColor(.1, .12, .16, 1.)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            # Item-local W x H maps to the same physical size in both windows.
            # The matrix translation centres it at integer physical coordinates.
            matrix = (2 / (W * window_factor), 0, 0, 0,
                      0, -2 / (H * window_factor), 0, 0, 0, 0, 1, 0,
                      -1 / window_factor, 1 / window_factor, 0, 1)
            host.render(snapshot=snapshot, viewport=(0, 0, pixel_w, pixel_h),
                        logical_size=(float(W), float(H)), matrix_values=matrix)
            pixels = gl.glReadPixels(0, 0, pixel_w, pixel_h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            rgba = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(pixel_h, pixel_w, 4)[::-1]
            x, y = (pixel_w - card_w) // 2, (pixel_h - card_h) // 2
            images.append(rgba[y:y+card_h, x:x+card_w].astype(np.int16))
        finally:
            host.release_resources()
            capture.close()
    assert np.count_nonzero(images[0][..., :3] > 60) > 100
    delta = np.max(np.abs(images[0] - images[1]), axis=2)
    # NDC translation changes float rounding at individual MSAA edge samples.
    # Bound total error and emitted picture energy, rather than requiring the
    # brightest individual edge sample to match bit-for-bit. Doubling marker
    # diameter through the old whole-window scale fails both bounds.
    assert float(delta.mean()) < .3
    radiance = [float(image[..., :3].sum()) for image in images]
    assert abs(radiance[0] - radiance[1]) / radiance[0] < .003


@pytest.mark.parametrize('style', ['Vertices', 'Glass + Vertices'])
@pytest.mark.parametrize('dpr', [1.,1.25,1.5,2.])
def test_actual_small_points_keep_body_and_emission_at_fractional_pixels(qt_app, monkeypatch, style, dpr):
    """Every selected real lattice point survives normal sizing and subpixel raster phases."""
    from tools.transition_contact_sheet import TransitionCapture
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
    from rendering.gl_programs.neon_lake_basin_mesh import basin_lattice
    from rendering.gl_programs.neon_lake_basin_program import SHOCKWAVE_DEPTH
    from rendering.gl_programs.heightfield import sample_heightfield_curve

    width,height = 640,400
    pixel_w,pixel_h = round(width*dpr),round(height*dpr)
    grid = {'size':5,'heights':[.25+.12*((x+2*y)%5)/4 for y in range(5) for x in range(5)]}
    base = _wire_frame(_snapshot(scene3d_detail='Balanced',shockwave_grid_density=0.,shockwave_grid_glow=.55,
        shockwave_grid_sun_enabled=False,shockwave_grid_sky_enabled=False,shockwave_grid_water_reflection=0.,
        shockwave_grid_floor=0.,shockwave_grid_glass_strength=0.,shockwave_grid_terrain_reactivity=0.,
        shockwave_grid_terrain_detail=0.,shockwave_grid_scene_scale=.65,shockwave_grid_scene_pan_y=0.,
        shockwave_grid_line_color=[0,0,0,0],shockwave_grid_crest_color=[0,0,0,0],
        shockwave_grid_terrain_fill_color=[0,0,0,255],
        shockwave_grid_vertex_color=[255,255,255,255],shockwave_grid_vertex_accent_color=[255,255,255,255],
        shockwave_grid_vertex_outline_color=[255,255,255,255]),style)
    state = base.logical.mode_state
    terrain = {**dict(state.parameters['shockwave_grid_terrain']), 'size':grid['size'],
               'data':heightfield_surface_bytes(grid),'maximum':max(grid['heights'])}
    base = _wire_frame(base,style,shockwave_grid_terrain=terrain)
    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy('shockwave_grid'),
        display_size=(width,height),viewport_extent=(width,height),
        border_width=0.,corner_radius=0.,content_inset=0.,background_color=(0,0,0,0),
        border_color=(0,0,0,0),shadow_enabled=False,shadow_color=(0,0,0,0),shadow_blur=0.,
        shadow_offset=(0.,0.),shadow_spread=0.,shadow_extensions=(0.,0.,0.,0.))
    snapshot = replace(base,presentation=presentation)
    capture,host = TransitionCapture(pixel_w,pixel_h),QuickVisualizerRenderHost()
    try:
        matrix = (2/width,0,0,0,0,-2/height,0,0,0,0,1,0,-1,1,0,1)
        def render(matrix):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glClearColor(0.,0.,0.,0.)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            host.render(snapshot=snapshot,viewport=(0,0,pixel_w,pixel_h),
                        logical_size=(float(width),float(height)),matrix_values=matrix)
            renderer = host._implementations['shockwave_grid']
            # Resolve actual scene colour before bloom, so a neighbouring
            # glow cannot pass the body's separate coverage observation.
            gl.glNamedFramebufferReadBuffer(renderer._target._names['fbo'],gl.GL_COLOR_ATTACHMENT0)
            gl.glBlitNamedFramebuffer(renderer._target._names['fbo'],capture.fbo,
                0,0,pixel_w,pixel_h,0,0,pixel_w,pixel_h,gl.GL_COLOR_BUFFER_BIT,gl.GL_NEAREST)
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER,capture.fbo)
            pixels = gl.glReadPixels(0,0,pixel_w,pixel_h,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE)
            return (np.frombuffer(bytes(pixels),dtype=np.uint8).reshape(pixel_h,pixel_w,4)[::-1].astype(np.int16),
                    _resolved_emission_pixels(renderer,pixel_w,pixel_h))
        render(matrix)
        renderer = host._implementations['shockwave_grid']
        frame = QuickVisualizerRenderFrame(snapshot,(0,0,pixel_w,pixel_h),(width,height),matrix,host._quad_vao)
        field,half_width,view,maximum = renderer._view(frame,base.logical.mode_state.parameters)
        xs,ys = basin_lattice(renderer._points_cells)
        selected = [(min(range(len(xs)),key=lambda i:abs(xs[i]-u)),
                     min(range(len(ys)),key=lambda i:abs(ys[i]-v))) for u,v in ((.25,.2),(.5,.5),(.75,.8))]
        index = [None]
        actual_draw = gl.glDrawArrays
        def one_point(mode,first,count):
            if mode!=gl.GL_POINTS:
                return actual_draw(mode,first,count)
            if index[0] is not None:
                gl.glDisable(gl.GL_DEPTH_TEST)
                try:return actual_draw(mode,index[0],1)
                finally:gl.glEnable(gl.GL_DEPTH_TEST)
        monkeypatch.setattr(gl,'glDrawArrays',one_point)
        for phase in (0.,.25,.5,.75):
            shifted = (*matrix[:12],matrix[12]+2*phase/pixel_w,matrix[13]-2*phase/pixel_h,*matrix[14:])
            index[0] = None
            empty_colour,empty_emission = render(shifted)
            for column,row in selected:
                index[0] = row*len(xs)+column
                colour,emission = render(shifted)
                u,v = xs[column],ys[row]
                world = ((2*u-1)*half_width,sample_heightfield_curve(grid,u,v)*state.parameters['shockwave_grid_terrain_height'],-v*SHOCKWAVE_DEPTH)
                x,y = view.item_point(world)
                px,py = round(x*dpr+phase),round(y*dpr+phase)
                roi = np.s_[py-5:py+6,px-5:px+6,:3]
                assert np.max(np.abs(colour-empty_colour)[roi])>8,(style,dpr,phase,u,v,(px,py),
                    np.unravel_index(np.abs(colour-empty_colour)[...,:3].argmax(),colour[...,:3].shape),
                    np.max(np.abs(colour-empty_colour)))
                assert np.max(np.abs(emission-empty_emission)[roi])>1e-4,(style,dpr,phase,u,v)
    finally:
        host.release_resources()
        capture.close()


def test_vertex_density_and_tiers_keep_one_unique_active_mesh_and_glass_retires_it(target):
    from rendering.gl_programs.neon_lake_basin_mesh import basin_mesh_points, basin_mesh_vertices, BASIN_OVERSCAN
    capture, host = target
    snapshot = _snapshot(shockwave_grid_glow=0.)
    for tier, density in (('High', 0.), ('High', 1.), ('Performance', 1.), ('KAK', 0.)):
        capture.render(host, _wire_frame(snapshot, 'Vertices', scene3d_detail=tier,
                                        shockwave_grid_density=density))
        renderer = host._implementations['shockwave_grid']
        columns, rows = renderer._points_cells
        keys = [key for key in renderer._resources._meshes if key.startswith('basin vertices ')]
        assert len(keys) == 1
        assert columns >= (12+40*density)*1.5 and rows >= 12+40*density
        assert columns <= np.ceil(192*np.sqrt(1.10)) and rows <= np.ceil(128*np.sqrt(1.10))
        assert renderer._points_cells == renderer._mesh_cells
        assert renderer._points_data[1] == len(basin_mesh_points((columns, rows)))//2
        packed = np.array(basin_mesh_points((columns, rows))).reshape(-1, 2)
        triangles = np.array(basin_mesh_vertices((columns, rows))).reshape(-1, 2)
        assert len(np.unique(packed, axis=0)) == len(packed)
        assert set(map(tuple, packed)) <= set(map(tuple, triangles))
        assert packed[:, 1].min() == -BASIN_OVERSCAN[2]
        assert packed[:, 1].max() == 1.0 + BASIN_OVERSCAN[3]
        assert packed[:, 0].min() == -BASIN_OVERSCAN[0]
        assert packed[:, 0].max() == 1.0 + BASIN_OVERSCAN[1]
    capture.render(host, _wire_frame(snapshot, 'Glass', scene3d_detail='KAK'))
    assert renderer._points_cells is None and renderer._points_data is None
    assert not any(key.startswith('basin vertices ') for key in renderer._resources._meshes)


@pytest.mark.parametrize('initial_enabled,fail', [(False, False), (True, False), (False, True), (True, True)])
def test_point_draw_restores_inherited_size_and_depth_state_even_on_error(target, monkeypatch, initial_enabled, fail):
    capture, host = target
    snapshot = _wire_frame(_snapshot(shockwave_grid_glow=0., shockwave_grid_sky_enabled=False,
                                    shockwave_grid_water_reflection=0.), 'Glass + Vertices')
    capture.render(host, snapshot)
    inherited_depth = gl.GL_GREATER
    gl.glDepthFunc(inherited_depth)
    (gl.glEnable if initial_enabled else gl.glDisable)(gl.GL_PROGRAM_POINT_SIZE)
    actual_draw = gl.glDrawArrays
    draws = []
    def draw(mode, first, count):
        if mode == gl.GL_POINTS:
            assert gl.glIsEnabled(gl.GL_PROGRAM_POINT_SIZE)
            assert int(gl.glGetIntegerv(gl.GL_DEPTH_FUNC)) == gl.GL_LEQUAL
            draws.append(count)
            if fail:
                raise RuntimeError('injected point draw failure')
        return actual_draw(mode, first, count)
    monkeypatch.setattr(gl, 'glDrawArrays', draw)
    try:
        if fail:
            with pytest.raises(RuntimeError, match='injected point draw failure'):
                capture.render(host, snapshot)
        else:
            capture.render(host, snapshot)
        assert draws
        assert bool(gl.glIsEnabled(gl.GL_PROGRAM_POINT_SIZE)) == initial_enabled
        assert int(gl.glGetIntegerv(gl.GL_DEPTH_FUNC)) == inherited_depth
    finally:
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_PROGRAM_POINT_SIZE)


def test_production_point_fragment_rasterizes_round_marks(target, monkeypatch):
    capture, host = target
    snapshot = _wire_frame(_snapshot(scene3d_detail='KAK', shockwave_grid_glow=0.,
        shockwave_grid_sky_enabled=False, shockwave_grid_density=0., shockwave_grid_floor=0.,
        shockwave_grid_sun_enabled=False,
        shockwave_grid_scene_scale=.65, shockwave_grid_scene_pan_y=0.,
        shockwave_grid_water_reflection=0., shockwave_grid_terrain_reactivity=0.,
        shockwave_grid_terrain_detail=0., shockwave_grid_line_color=[255, 255, 255, 255]), 'Vertices')
    capture.render(host, snapshot)
    renderer = host._implementations['shockwave_grid']
    from rendering.quick.visualizer.implementations.shockwave_grid import _UNIFORMS, NEON_VERTEX_SOURCE, NEON_FRAGMENT_SOURCE
    basin_program = renderer._resources.program('basin', NEON_VERTEX_SOURCE, NEON_FRAGMENT_SOURCE)
    point_uniform = renderer._resources.uniforms('basin', _UNIFORMS)['uPointPx']
    uniform = gl.glUniform1f
    def magnify(location, value):
        # Observe the same production gl_PointCoord coverage at enough pixels
        # to discriminate rounded marks from squares; no substitute shader.
        if int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)) == basin_program:
            value = 13. if location == point_uniform else value
        return uniform(location, value)
    monkeypatch.setattr(gl, 'glUniform1f', magnify)
    actual_draw = gl.glDrawArrays
    from rendering.gl_programs.neon_lake_basin_mesh import basin_lattice
    xs, ys = basin_lattice(renderer._points_cells)
    # Overscan adds nonuniform rows/columns around the authored sub-lattice.
    # Observe authored points with enough projected separation for magnified discs.
    selected_columns = [i for i, u in enumerate(xs) if .1 < u < .9][::14]
    authored_rows = [i for i, v in enumerate(ys) if .1 < v < .9]
    selected_rows = [authored_rows[0], authored_rows[-1]]
    # Opaque terrain coverage now legitimately fills the alpha channel beneath
    # marks. Subtract the same production surface without marks to isolate their
    # raster coverage instead of confusing terrain alpha with point shape.
    monkeypatch.setattr(gl, 'glDrawArrays', lambda mode, first, count:
                        None if mode == gl.GL_POINTS else actual_draw(mode, first, count))
    without_points = capture.render(host, snapshot)
    def separated_points(mode, first, count):
        if mode == gl.GL_POINTS:
            observed = np.zeros(1, dtype=np.float32)
            gl.glGetUniformfv(basin_program, point_uniform, observed)
            assert observed[0] == 13.
            # Select well separated indices from the actual uploaded lattice.
            # The full triangle surface and shared displacement remain intact.
            for row in selected_rows:
                for column in selected_columns:
                    # Magnified discs cross adjacent triangle depth slopes;
                    # shape observation excludes that unrelated occlusion.
                    gl.glDisable(gl.GL_DEPTH_TEST)
                    try:
                        actual_draw(mode, row*len(xs)+column, 1)
                    finally:
                        gl.glEnable(gl.GL_DEPTH_TEST)
            return
        return actual_draw(mode, first, count)
    monkeypatch.setattr(gl, 'glDrawArrays', separated_points)
    pixels = capture.render(host, snapshot)
    coverage = np.max(np.abs(pixels[..., :3] - without_points[..., :3]), axis=2)
    candidates = np.argwhere(coverage > 30)
    assert len(candidates) > 20, (coverage.max(), selected_columns, selected_rows)
    rounded = 0
    for y, x in candidates:
        if y < 6 or x < 6 or y+6 >= H or x+6 >= W:
            continue
        # A 13px circular marker has an opaque centre but all diagonal 5px
        # offsets are outside its circle. A square fragment covers those.
        corners = coverage[np.array([y-5, y-5, y+5, y+5]), np.array([x-5, x+5, x-5, x+5])]
        axes = coverage[np.array([y-4, y+4, y, y]), np.array([x, x, x-4, x+4])]
        if np.min(axes) > 0 and np.max(corners) <= 1:
            rounded += 1
    assert rounded >= 5


def test_reflected_point_marks_survive_the_depth_writing_water_surface(target, monkeypatch):
    capture, host = target
    snapshot = _wire_frame(_snapshot(scene3d_detail='Performance', shockwave_grid_glow=0.,
        shockwave_grid_sky_enabled=False, shockwave_grid_floor=.25, shockwave_grid_tilt=.6,
        shockwave_grid_water_reflection=1., shockwave_grid_terrain_detail=0.), 'Vertices')
    state = snapshot.logical.mode_state
    size = 9
    heights = [(.6 if row >= 4 else 0.) for row in range(size) for column in range(size)]
    terrain = {'size': size, 'maximum': .6,
               'data': heightfield_surface_bytes({'size': size, 'heights': heights})}
    snapshot = replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(
        state, parameters={**dict(state.parameters), 'shockwave_grid_terrain': terrain})))
    normal = capture.render(host, snapshot)
    renderer = host._implementations['shockwave_grid']
    actual = renderer._draw_points
    calls = []
    def no_reflection(uniforms, points, pass_id, **kwargs):
        calls.append(pass_id)
        if pass_id != 0:
            actual(uniforms, points, pass_id, **kwargs)
    monkeypatch.setattr(renderer, '_draw_points', no_reflection)
    omitted = capture.render(host, snapshot)
    assert sorted(calls) == [0, 1]
    changed = np.max(np.abs(normal-omitted), axis=2) > 3
    assert np.count_nonzero(changed) > 20  # Reflection is visible through real water/depth.


@pytest.mark.parametrize('surface', ['curved', 'wavy'])
def test_direct_point_samples_survive_depth_on_the_shared_displaced_surface(target, monkeypatch, surface):
    capture, host = target
    snapshot = _wire_frame(_snapshot(scene3d_detail='Performance', shockwave_grid_glow=0.,
        shockwave_grid_sky_enabled=False, shockwave_grid_floor=.25,
        shockwave_grid_water_reflection=0., shockwave_grid_terrain_detail=1.,
        shockwave_grid_wave_height=1., shockwave_grid_water_detail=1.,
        shockwave_grid_terrain_height=.12), 'Vertices')
    state = snapshot.logical.mode_state
    size = 9
    heights = [(.15+.55*(.5+.5*np.sin(column*1.7+row*.9)) if surface == 'curved' else 0.)
               for row in range(size) for column in range(size)]
    terrain = {'size': size, 'maximum': max(heights),
               'data': heightfield_surface_bytes({'size': size, 'heights': heights})}
    snapshot = replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(state,
        parameters={**dict(state.parameters), 'shockwave_grid_terrain': terrain},
        events=tuple((.1+i*.09, 0., -1.2, 2.) for i in range(16)))))
    capture.render(host, snapshot)
    renderer = host._implementations['shockwave_grid']
    actual = renderer._draw_points
    counts = []
    query = int(np.asarray(gl.glGenQueries(1)).reshape(-1)[0])
    def counted(uniforms, points, pass_id):
        gl.glBeginQuery(gl.GL_SAMPLES_PASSED, query)
        try:
            actual(uniforms, points, pass_id)
        finally:
            gl.glEndQuery(gl.GL_SAMPLES_PASSED)
        counts.append(int(gl.glGetQueryObjectuiv(query, gl.GL_QUERY_RESULT)))
    monkeypatch.setattr(renderer, '_draw_points', counted)
    try:
        capture.render(host, snapshot)
        depth_visible = counts[-1]
        def without_depth(uniforms, points, pass_id):
            gl.glDisable(gl.GL_DEPTH_TEST)
            try:
                counted(uniforms, points, pass_id)
            finally:
                gl.glEnable(gl.GL_DEPTH_TEST)
        monkeypatch.setattr(renderer, '_draw_points', without_depth)
        capture.render(host, snapshot)
        full_coverage = counts[-1]
        assert full_coverage > 100
        assert depth_visible > full_coverage * .40
    finally:
        gl.glDeleteQueries(1, [query])
