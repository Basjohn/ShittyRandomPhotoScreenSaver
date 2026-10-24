"""Production GL materials/body/volume contracts, using test-owned inputs."""
from dataclasses import replace
from itertools import combinations

import numpy as np
from OpenGL import GL as gl
import pytest

from tests.test_neon_lake_renderer import target, _snapshot


STYLES = ('Vertices', 'Glass', 'Glass + Vertices')


def _change(snapshot, **parameters):
    state = snapshot.logical.mode_state
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(
        state, parameters={**dict(state.parameters), **parameters})))


def _base(**parameters):
    snapshot = _snapshot(scene3d_detail='Performance', shockwave_grid_glow=0.,
        shockwave_grid_sun_orbit_enabled=False, shockwave_grid_sun_rays_enabled=False,
        shockwave_grid_scroll=0., shockwave_grid_idle=0., shockwave_grid_water_reflection=0.,
        shockwave_grid_terrain_reactivity=0., shockwave_grid_terrain_detail=0.,
        shockwave_grid_glass_strength=.85, shockwave_grid_glass_roughness=.12,
        shockwave_grid_vertex_color=[20, 255, 80, 255],
        shockwave_grid_vertex_accent_color=[255, 20, 210, 255],
        shockwave_grid_vertex_outline_color=[240, 240, 30, 255])
    state = snapshot.logical.mode_state
    snapshot = replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(state, events=())))
    return _change(snapshot, **parameters)


def _different(a, b, minimum=20):
    assert np.count_nonzero(np.max(np.abs(a-b), axis=2) > 3) > minimum


def test_three_retained_surface_styles_have_distinct_production_pixels(target):
    capture, host = target
    snapshot = _base()
    images = {style: capture.render(host, _change(snapshot, shockwave_grid_wire_display=style)) for style in STYLES}
    for first, second in combinations(STYLES, 2):
        _different(images[first], images[second])


@pytest.mark.parametrize('key,first,second', [
    ('shockwave_grid_glass_strength', .1, 1.),
    ('shockwave_grid_glass_roughness', .05, .5),
    ('shockwave_grid_glass_tint', [255, 15, 40, 255], [10, 190, 255, 255]),
    ('shockwave_grid_vertex_color', [255, 15, 40, 255], [10, 190, 255, 255]),
    ('shockwave_grid_vertex_accent_color', [255, 15, 40, 255], [10, 190, 255, 255]),
    ('shockwave_grid_vertex_outline_color', [255, 15, 40, 255], [10, 190, 255, 255]),
])
def test_glass_and_independent_point_material_inputs_change_pixels(target, key, first, second):
    capture, host = target
    style = 'Vertices' if key in ('shockwave_grid_vertex_color', 'shockwave_grid_vertex_accent_color') else 'Glass + Vertices'
    snapshot = _base(shockwave_grid_wire_display=style)
    _different(capture.render(host, _change(snapshot, **{key: first})),
               capture.render(host, _change(snapshot, **{key: second})))


def _body(**parameters):
    # Hide surface art while retaining its real depth-writing geometry.
    return _base(shockwave_grid_wire_display='Vertices', shockwave_grid_sky_enabled=False,
        shockwave_grid_sun_enabled=True, shockwave_grid_floor=0.,
        shockwave_grid_line_color=[0, 0, 0, 0], shockwave_grid_crest_color=[0, 0, 0, 0],
        # Vertices have their own colours, and the skyline its own thickness.
        shockwave_grid_vertex_color=[0, 0, 0, 0], shockwave_grid_vertex_accent_color=[0, 0, 0, 0],
        shockwave_grid_vertex_outline_color=[0, 0, 0, 0], shockwave_grid_horizon_thickness=0.,
        # The body sits at infinity in the direction its position names from the reference viewpoint:
        # look slightly up at one a little above the horizon.
        **{'shockwave_grid_tilt': -.05, 'shockwave_grid_sun_x': .4, 'shockwave_grid_sun_y': 1.3,
           'shockwave_grid_sun_z': -3.2, **parameters})


@pytest.mark.parametrize('mode,key,first,second', [
    ('Sun', 'shockwave_grid_sun_color', [255, 10, 30, 255], [20, 120, 255, 255]),
    ('Moon', 'shockwave_grid_moon_color', [255, 10, 30, 255], [20, 120, 255, 255]),
    ('Sun', 'shockwave_grid_sun_x', .4, -.4),
    ('Sun', 'shockwave_grid_sun_y', .5, 1.3),
    ('Sun', 'shockwave_grid_sun_z', -2., -4.),
    ('Sun', 'shockwave_grid_sun_size', .2, .8),
    ('Moon', 'shockwave_grid_moon_phase', .1, .8),
])
def test_body_colour_position_size_and_moon_phase_are_visible_without_sky(target, mode, key, first, second):
    capture, host = target
    snapshot = _body(shockwave_grid_sun_mode=mode)
    a = capture.render(host, _change(snapshot, **{key: first}))
    b = capture.render(host, _change(snapshot, **{key: second}))
    _different(a, b)
    assert max(a[..., 3].max(), b[..., 3].max()) > 0


def test_disabled_moon_has_no_sun_or_body_when_sky_is_disabled(target):
    capture, host = target
    # Look nearly level: steeper views also frame the faded distant land at the horizon (the same in
    # the pre-framed-camera renderer), which is terrain, not a celestial body.
    snapshot = _body(shockwave_grid_sun_mode='Moon', shockwave_grid_tilt=.1)
    moon = capture.render(host, snapshot)
    disabled = capture.render(host, _change(snapshot, shockwave_grid_sun_enabled=False))
    _different(moon, disabled)
    assert np.count_nonzero(disabled[..., 3]) == 0


def test_orbit_reuses_target_and_disabled_orbit_is_time_invariant(target):
    capture, host = target
    snapshot = _body(shockwave_grid_sun_mode='Sun')
    def at(frame, time):
        return replace(frame, logical=replace(frame.logical, mode_state=replace(frame.logical.mode_state, animation_time=time)))
    first = capture.render(host, at(snapshot, 0.))
    renderer = host._implementations['shockwave_grid']
    names, allocation = dict(renderer._target._names), renderer._target.allocation
    assert np.array_equal(first, capture.render(host, at(snapshot, 4.)))
    moving = _change(snapshot, shockwave_grid_sun_orbit_enabled=True, shockwave_grid_sun_orbit_speed=.03)
    _different(capture.render(host, at(moving, 0.)), capture.render(host, at(moving, 4.)))
    assert renderer._target._names == names and renderer._target.allocation == allocation
    assert snapshot.presentation == moving.presentation


def test_ray_admission_is_event_driven_and_colour_strength_change_the_actual_rays(target, monkeypatch):
    capture, host = target
    snapshot = _base(shockwave_grid_wire_display='Glass + Vertices', shockwave_grid_sun_enabled=True)
    capture.render(host, snapshot)
    renderer = host._implementations['shockwave_grid']
    from rendering.quick.visualizer.implementations.shockwave_grid import _SKY_UNIFORMS
    location = renderer._resources.uniforms('sky', _SKY_UNIFORMS)['uSkyPass']
    actual = gl.glUniform1i
    passes = []
    def record(uniform, value):
        if uniform == location and int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)) == renderer._resources._programs['sky']:
            passes.append(value)
        return actual(uniform, value)
    monkeypatch.setattr(gl, 'glUniform1i', record)
    names, meshes = dict(renderer._target._names), dict(renderer._resources._meshes)
    disabled = capture.render(host, snapshot)
    assert 3 not in passes and 1 not in passes
    passes.clear()
    zero = capture.render(host, _change(snapshot, shockwave_grid_sun_rays_enabled=True, shockwave_grid_sun_rays_strength=0.))
    assert 3 not in passes and np.array_equal(disabled, zero)
    assert renderer._target._names == names          # rays that cannot show allocate nothing
    passes.clear()
    capture.render(host, _change(snapshot, shockwave_grid_sun_enabled=False,
                                shockwave_grid_sun_rays_enabled=True, shockwave_grid_sun_rays_strength=1.))
    assert 3 not in passes
    rays = _change(snapshot, shockwave_grid_sun_rays_enabled=True, shockwave_grid_sun_rays_strength=1.)
    strong = capture.render(host, rays)
    assert 3 in passes and 1 not in passes                 # the shaft source; the old haze pass is gone
    _different(strong, disabled)
    for change in ({"shockwave_grid_sun_rays_strength": .15}, {"shockwave_grid_sun_rays_length": .0},
                   {"shockwave_grid_sun_rays_spread": 1.0}):
        _different(strong, capture.render(host, _change(rays, **change)))
    _different(capture.render(host, _change(rays, shockwave_grid_sun_rays_color=[255, 15, 20, 255])),
               capture.render(host, _change(rays, shockwave_grid_sun_rays_color=[10, 80, 255, 255])))
    assert renderer._resources._meshes == meshes
    # Turning the rays off again draws exactly as before they were on.
    assert np.array_equal(disabled, capture.render(host, snapshot))


@pytest.mark.parametrize('style', ['Glass', 'Glass + Vertices'])
def test_warmed_material_body_volume_frames_do_no_static_gpu_work(target, monkeypatch, style):
    from rendering.quick.scene3d import resources
    capture, host = target
    snapshot = _base(shockwave_grid_wire_display=style, shockwave_grid_sun_rays_enabled=True,
                     shockwave_grid_sun_rays_strength=.7)
    capture.render(host, snapshot)
    renderer = host._implementations['shockwave_grid']
    names, allocation = dict(renderer._target._names), renderer._target.allocation
    uploads = renderer._heightfield.uploads
    def forbidden(*args, **kwargs):
        pytest.fail('warmed material/body/volume frame did static GPU work')
    monkeypatch.setattr(resources, 'compile_program', forbidden)
    monkeypatch.setattr(resources, 'compile_compute_program', forbidden)
    for name in ('glCreateProgram', 'glCreateShader', 'glCreateTextures', 'glCreateBuffers',
                 'glCreateVertexArrays', 'glCreateFramebuffers', 'glTextureStorage2D',
                 'glTextureStorage2DMultisample', 'glNamedBufferStorage', 'glTextureSubImage2D'):
        monkeypatch.setattr(gl, name, forbidden)
    for mode in ('Sun', 'Moon', 'Sun'):
        capture.render(host, _change(snapshot, shockwave_grid_sun_mode=mode))
        assert renderer._target.allocation == allocation and renderer._target._names == names
        assert renderer._heightfield.uploads == uploads


def _qsg_material_probe(nested=False):
    from tests import test_neon_lake_renderer as original
    build = original._snapshot
    original._snapshot = lambda **parameters: build(**{**parameters,
        'shockwave_grid_wire_display': 'Glass + Vertices', 'shockwave_grid_glass_strength': 1.,
        'shockwave_grid_sun_enabled': True, 'shockwave_grid_sun_rays_enabled': True,
        'shockwave_grid_sun_rays_strength': 1.})
    original._qsg_clip_probe(nested=nested)


@pytest.mark.parametrize('nested', [False, True])
def test_actual_qsg_glass_volume_pixels_respect_local_and_inherited_card_clip(nested):
    import json
    from pathlib import Path
    import subprocess
    import sys
    completed = subprocess.run([sys.executable, '-c',
        f'from tests.test_neon_scene_materials import _qsg_material_probe; _qsg_material_probe(nested={nested})'],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=25)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout[completed.stdout.index('{'):])
    assert report['error'] is None, report
    assert report['changed_pixels'] > 100 and report['draw_count'] > 0
    assert report['outside_delta'] <= 2 and report['rounded_corner_delta'] <= 2
    assert report['release_count'] > 0
    if nested:
        assert report['incoming_scissor'] is True


def _unoccluded_body_reference(target, snapshot, monkeypatch):
    """Actual body shader/camera, with only basin triangles omitted as a control."""
    capture, host = target
    capture.render(host, snapshot)
    program = host._implementations['shockwave_grid']._resources._programs['basin']
    draw = gl.glDrawArrays
    def omit_basin(mode, first, count):
        if int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)) != program:
            return draw(mode, first, count)
    with monkeypatch.context() as patch:
        patch.setattr(gl, 'glDrawArrays', omit_basin)
        return capture.render(host, snapshot)


@pytest.mark.parametrize('style', ['Vertices', 'Glass'])
def test_actual_celestial_body_is_occluded_by_solid_terrain(target, monkeypatch, style):
    from rendering.gl_programs.heightfield import heightfield_surface_bytes
    capture, host = target
    snapshot = _base(shockwave_grid_wire_display=style, shockwave_grid_sky_enabled=False,
        shockwave_grid_sun_enabled=True, shockwave_grid_sun_x=0., shockwave_grid_sun_y=.1,
        shockwave_grid_sun_z=-1.2, shockwave_grid_sun_size=.25, shockwave_grid_floor=1.,
        shockwave_grid_terrain_height=1.5)
    def body_frame(height):
        state = snapshot.logical.mode_state
        size = 9
        terrain = {'size': size, 'maximum': height,
                   'data': heightfield_surface_bytes({'size': size, 'heights': [height] * size**2})}
        frame = _change(snapshot, shockwave_grid_terrain=terrain)
        return frame
    # The Sun is celestial background, not an in-lake sphere. A flat lake also
    # masks it, so an allegedly unobstructed height=0 render was a false oracle.
    reference = _unoccluded_body_reference(target, body_frame(0.), monkeypatch)
    unobstructed = np.count_nonzero(reference[...,0] > 40)
    frame = body_frame(.8)
    on = capture.render(host, frame)
    off = capture.render(host, _change(frame, shockwave_grid_sun_enabled=False))
    blocked = np.count_nonzero(np.max(np.abs(on-off), axis=2) > 3)
    assert unobstructed > 20 and blocked < unobstructed * .1


@pytest.mark.parametrize('mode', ['Sun', 'Moon'])
def test_translucent_celestial_body_blends_over_unobstructed_sky(target, mode):
    from rendering.gl_programs.heightfield import heightfield_surface_bytes
    capture, host = target
    snapshot = _base(shockwave_grid_wire_display='Vertices', shockwave_grid_sun_mode=mode,
        shockwave_grid_sky_enabled=True, shockwave_grid_sun_enabled=True,
        shockwave_grid_sun_x=0., shockwave_grid_sun_y=.8, shockwave_grid_sun_z=-2.,
        shockwave_grid_sun_size=.4, shockwave_grid_floor=1., shockwave_grid_terrain_height=1.,
        shockwave_grid_sky_color=[0, 210, 20, 255], shockwave_grid_sky_strength=1.,
        shockwave_grid_volumetric_clouds=False, shockwave_grid_nebula_enabled=False,
        shockwave_grid_star_color=[0,0,0,0], shockwave_grid_celestial_glow_enabled=False,
        shockwave_grid_line_color=[0, 0, 0, 0], shockwave_grid_crest_color=[0, 0, 0, 0],
        shockwave_grid_water_color=[0, 210, 20, 255], shockwave_grid_terrain_fill_color=[0, 210, 20, 255],
        shockwave_grid_moon_phase=.5)
    size = 9
    terrain = {'size': size, 'maximum': .4,
               'data': heightfield_surface_bytes({'size': size, 'heights': [.4] * size**2})}
    snapshot = _change(snapshot, shockwave_grid_terrain=terrain)
    key = 'shockwave_grid_sun_color' if mode == 'Sun' else 'shockwave_grid_moon_color'
    clear = capture.render(host, _change(snapshot, **{key: [240, 10, 20, 0]}))
    half = capture.render(host, _change(snapshot, **{key: [240, 10, 20, 128]}))
    opaque = capture.render(host, _change(snapshot, **{key: [240, 10, 20, 255]}))
    # Alpha is still a real blending contract, but the celestial background
    # must never be put in front of land to exercise it.
    sky = (clear[..., 3] == 255) & (clear[..., 0] < 20)
    body_centre = sky & (opaque[..., 0] > 100) & (opaque[..., 1] < 30)
    assert np.count_nonzero(body_centre) > 20
    factor = 128./255.
    expected = opaque[..., :3]*factor + clear[..., :3]*(1.-factor)
    error = np.abs(half[..., :3]-expected)
    assert np.quantile(error[body_centre], .95) <= 2.
    assert np.all(half[..., 3][body_centre] == 255)
    limb = sky & (opaque[..., 0] > 20) & (opaque[..., 1] > 30) & (opaque[..., 1] < 150)
    assert np.count_nonzero(limb) > 20
    assert np.quantile(error[limb], .95) <= 2.
    assert np.all(half[..., 3][limb] == 255)


@pytest.mark.parametrize('mode', ['Sun', 'Moon'])
@pytest.mark.parametrize('style', ['Vertices', 'Glass'])
@pytest.mark.parametrize('body_alpha', [128, 255])
def test_celestial_body_stays_hidden_behind_water_or_glass_at_any_alpha(target, monkeypatch, mode, style, body_alpha):
    from rendering.gl_programs.heightfield import heightfield_surface_bytes
    capture, host = target
    snapshot = _base(shockwave_grid_wire_display=style, shockwave_grid_sun_mode=mode,
        shockwave_grid_sky_enabled=False, shockwave_grid_sun_enabled=True,
        shockwave_grid_sun_x=0., shockwave_grid_sun_y=.1, shockwave_grid_sun_z=-1.2,
        shockwave_grid_sun_size=.25, shockwave_grid_floor=0., shockwave_grid_glass_strength=0.,
        shockwave_grid_sun_color=[240, 10, 20, body_alpha], shockwave_grid_moon_color=[240, 10, 20, body_alpha],
        shockwave_grid_moon_phase=.5, shockwave_grid_glass_tint=[20, 80, 210, 255],
        shockwave_grid_line_color=[0, 0, 0, 0], shockwave_grid_crest_color=[0, 0, 0, 0],
        shockwave_grid_water_color=[0, 40, 220, 255], shockwave_grid_water_detail=0.)
    size = 9
    terrain = {'size': size, 'maximum': 0.,
               'data': heightfield_surface_bytes({'size': size, 'heights': [0.] * size**2})}
    snapshot = _change(snapshot, shockwave_grid_terrain=terrain)
    reference = _unoccluded_body_reference(target, snapshot, monkeypatch)
    body_centres = (reference[..., 3] >= body_alpha-3) & (reference[..., 0] > 40)
    assert np.count_nonzero(body_centres) > 20
    # Independent geometric mask: the same surface with no body, painted opaque
    # green. It identifies coverage without deriving expected occlusion from the
    # body-on result we are testing. Markers and skyline cannot supply this mask.
    mask = capture.render(host, _change(snapshot, shockwave_grid_sun_enabled=False,
        shockwave_grid_floor=1., shockwave_grid_water_color=[0,255,0,255],
        shockwave_grid_terrain_fill_color=[0,255,0,255], shockwave_grid_glass_strength=0.,
        shockwave_grid_vertex_color=[0,0,0,0], shockwave_grid_vertex_accent_color=[0,0,0,0],
        shockwave_grid_vertex_outline_color=[0,0,0,0], shockwave_grid_horizon_thickness=0.))
    hidden = body_centres & (mask[...,1] > 40) & (mask[...,0] < 20)
    assert np.count_nonzero(hidden) > 20
    key = 'shockwave_grid_floor' if style == 'Vertices' else 'shockwave_grid_glass_strength'
    for opacity in (0., .5, 1.):
        frame = _change(snapshot, **{key: opacity})
        on = capture.render(host, frame)
        # Omit only the visible body draw, retaining exactly the same material
        # illumination/reflections. Sky and shaft backgrounds are disabled here.
        sky_program = host._implementations['shockwave_grid']._resources._programs['sky']
        draw = gl.glDrawArrays
        def omit_visible_body(mode, first, count):
            if int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)) != sky_program:
                return draw(mode, first, count)
        with monkeypatch.context() as patch:
            patch.setattr(gl, 'glDrawArrays', omit_visible_body)
            off = capture.render(host, frame)
        assert np.quantile(np.abs(on-off)[hidden], .95) <= 2.
