"""Extruded Bubble's scene mapping (pure) and its renderer's resource contract through the production render host on
an offscreen context (no window). No pixel goldens: looks are judged against the operator's mocks in the lab."""
from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from rendering.gl_programs import extruded_bubble_scene as scene
from tests._visualizer_frozen_settings import frozen_visualizer_settings

SETTINGS = frozen_visualizer_settings("extruded_bubble")


def _record(x=0.0, y=0.0, z=-10.0, radius=1.0, alpha=1.0, ident=1.0, cluster=-1.0):
    return (x, y, z, radius, alpha, 0.0, ident, cluster)


@pytest.mark.parametrize("turn, tilt", [(0.0, 0.0), (0.37, -0.3), (-0.8, 0.45), (1.0, 0.0)])
def test_the_camera_is_a_rotation_pitched_up_and_turned_about_the_vertical(turn, tilt):
    view_to_world, world_to_view, tan, projection = scene.camera(turn, tilt, 16 / 9)
    axes = np.asarray(view_to_world).reshape(3, 3)                    # rows: right, up, back
    assert np.allclose(axes @ axes.T, np.eye(3), atol=1e-9)
    assert np.linalg.det(axes) == pytest.approx(1.0)
    assert np.allclose(np.asarray(world_to_view).reshape(3, 3), axes.T)
    assert axes[0][1] == pytest.approx(0.0)                           # the horizon stays level (no roll)
    pitch = math.degrees(math.asin(-axes[2][1]))                      # looking along -back
    assert pitch == pytest.approx(16.0 + 90.0 * tilt)
    assert tan[0] / tan[1] == pytest.approx(16 / 9)
    assert projection[5] == pytest.approx(1.0 / tan[1])


def _physical_ndc(view, point):
    orient, wtv, eye, tan, projection = view
    offset = np.asarray(point, dtype=float) - np.asarray(eye)
    cam = np.asarray(wtv).reshape(3, 3).T @ offset
    assert cam[2] < 0.0
    return (cam[0] / -cam[2] / tan[0], cam[1] / -cam[2] / tan[1])


def test_physical_scene_zoom_dollies_without_fov_change_or_rotating():
    plain = scene.physical_camera(0.0, 0.0, 1.5)
    zoomed = scene.physical_camera(0.0, 0.0, 1.5, scale=2.0)
    assert zoomed[0] == plain[0]
    assert zoomed[3] == plain[3] and zoomed[4] == plain[4]
    assert np.linalg.norm(np.asarray(zoomed[2]) - scene.ORBIT_PIVOT) == pytest.approx(scene.ORBIT_DISTANCE / 2.0)
    assert np.linalg.norm(np.asarray(plain[2]) - scene.ORBIT_PIVOT) == pytest.approx(scene.ORBIT_DISTANCE)
    point = tuple(scene.ORBIT_PIVOT[i] + (2.0 if i == 0 else 0.0) for i in range(3))
    assert abs(_physical_ndc(zoomed, point)[0]) > abs(_physical_ndc(plain, point)[0])


def test_pan_is_physical_translation_not_an_additional_rotation_or_lens_shift():
    plain = scene.physical_camera(.2, .1, 1.6)
    panned = scene.physical_camera(.2, .1, 1.6, pan_x=.15, pan_y=-.1)
    assert panned[0] == plain[0] and panned[1] == plain[1]
    assert panned[3] == plain[3] and panned[4] == plain[4]
    assert panned[4][8] == panned[4][9] == 0.0
    assert np.linalg.norm(np.asarray(panned[2]) - plain[2]) > 0.0
    # Different camera-space distances MUST exhibit different apparent shifts.
    right = np.asarray(plain[0][:3])
    back = np.asarray(plain[0][6:9])
    eye = np.asarray(plain[2])
    nearer = eye - back * 6 + right * 1.0
    farther = eye - back * 18 + right * 1.0
    dx_near = _physical_ndc(panned, nearer)[0] - _physical_ndc(plain, nearer)[0]
    dx_far = _physical_ndc(panned, farther)[0] - _physical_ndc(plain, farther)[0]
    assert dx_near * dx_far > 0.0
    assert abs(dx_near) > abs(dx_far) * 2.0


def test_existing_alt_orbit_changes_camera_pose_but_pan_does_not():
    initial = scene.physical_camera(0., 0., 16 / 9)
    turned = scene.physical_camera(.25, 0., 16 / 9)
    assert turned[0] != initial[0] and turned[2] != initial[2]
    assert np.linalg.norm(np.asarray(turned[2]) - scene.ORBIT_PIVOT) == pytest.approx(scene.ORBIT_DISTANCE)
    assert scene.physical_camera(0., 0., 16 / 9, pan_x=.2)[0] == initial[0]

def test_physical_radius_has_real_perspective_and_lifetime_does_not_shrink_it():
    records = _record(z=-4.) + _record(z=-16., ident=2.) + _record(z=-4., alpha=.25, ident=3.)
    rows = scene.bubble_instances(records)
    assert rows[:,3] == pytest.approx((1.,1.,1.))
    assert rows[:,6] == pytest.approx((1.,1.,.25))
    assert rows[:,:3] == pytest.approx(np.asarray(records).reshape(-1,8)[:,:3])
    tan = scene.camera(0,0,1.6)[2]
    radii = rows[:,3] / (-rows[:,2] * tan[1])
    assert radii[0] == pytest.approx(4*radii[1])
    assert radii[0] == pytest.approx(radii[2])


def test_fused_members_and_faded_bubbles_are_not_shells_and_clusters_carry_physical_members_and_alpha():
    records = _record(x=-.8, cluster=1.) + _record(x=.8, ident=2., cluster=1., alpha=.25) + _record(alpha=0.,ident=3.)
    assert len(scene.bubble_instances(records)) == 0
    clusters = scene.cluster_instances(records,(2.,0.,1.,-1.))
    assert clusters.shape == (1,scene.CLUSTER_FLOATS)
    assert clusters[0,:4] == pytest.approx(records[:4])
    assert clusters[0,4:8] == pytest.approx(records[8:12])
    assert clusters[0,8:12].tolist() == [0.]*4
    assert clusters[0,16:] == pytest.approx((1.,.25,0.))


def test_ordinary_physical_shells_reach_shared_focus_without_synthetic_near_population():
    _v, view, _tan, _p = scene.camera(0.,0.,16/9)
    rows = scene.bubble_instances(_record(z=-3.) + _record(z=-20.,ident=2.))
    def circle(shell,focus):
        depth = -(shell[:3] @ np.asarray(view).reshape(3,3))[2]
        return 22*max(focus-(depth-shell[3]),0)/max(-(shell[:3] @ np.asarray(view).reshape(3,3))[2]-shell[3],2.5)
    assert rows[:,5].tolist() == [0.,0.]
    assert circle(rows[0],4.) > 1.5
    assert circle(rows[0],5.5) > circle(rows[0],4.)
    assert circle(rows[1],5.5) == 0.
    assert scene.bubble_instances(()).shape == (0,scene.SHELL_FLOATS)


def test_glint_proxies_follow_physical_bubbles_and_lifetime_opacity():
    rows = scene.bubble_instances(_record() + _record(alpha=.25,ident=2.))
    proxies = scene.glint_proxies(rows,(0.,1.,0.),3.)
    assert len(proxies) == 2
    assert np.all(proxies[:,1] > rows[:,1])
    assert proxies[:,4] == pytest.approx((3.,.75))


@pytest.mark.parametrize("light_type", ["Sunlit Surface", "Deep Light"])
def test_every_light_type_gives_the_knobs_the_renderer_reads(light_type):
    knobs = scene.scene_knobs({**SETTINGS, "extruded_bubble_light_type": light_type})
    for key in ("sun", "sun_below", "spec_dir", "light", "water", "deep", "sky", "shaft", "absorb", "exposure",
                "surface", "shaft_y", "focus", "aperture"):
        assert key in knobs, key
    for key in ("sun", "sun_below", "spec_dir"):
        assert np.linalg.norm(knobs[key]) == pytest.approx(1.0)
    assert knobs["sun_below"][1] > 0.0                                 # the light comes from above


def test_particles_read_their_range_at_the_emission_follower_growing_density_and_brightness_together():
    low, high = 0.2, 0.8                                           # TEST INPUT: a Particles range
    settings = {**SETTINGS, "extruded_bubble_particles": [low, high]}
    # Caller already resolved the operator's low/high Range into state.emission. Renderer must not
    # perform an additional interpolation (the old test encoded that exact double-range bug).
    quiet, loud = scene.speck_amount(settings, low), scene.speck_amount(settings, high)
    assert quiet[0] < loud[0] and quiet[1] < loud[1]
    assert loud[0] / quiet[0] == pytest.approx((high / low) ** 2)  # density shaping preserved
    assert scene.speck_amount({**settings, "extruded_bubble_particles": [1.0, 1.0]}, 0.5) == pytest.approx((0.25, 1.2))
    assert scene.speck_amount({**settings, "extruded_bubble_particles": [0.0, 0.0]}, 1.0) == pytest.approx((1.0, 2.4))

def test_ray_strength_reads_its_range_at_the_ray_driver_and_is_off_when_disabled():
    low, high = SETTINGS["extruded_bubble_rays"]
    on = {**SETTINGS, "extruded_bubble_rays_enabled": True}
    assert 0 < scene.ray_strength(on, 0.0) < low * .05  # very dim rest, not the full quiet-music endpoint
    assert scene.ray_strength(on, .15) < scene.ray_strength(on, .75) * .3
    assert scene.ray_strength(on, 1.0) == pytest.approx(high)
    assert scene.ray_strength(on, 2.0) == pytest.approx(high)
    assert scene.ray_strength({**SETTINGS, "extruded_bubble_rays_enabled": False}, 0.7) == 0.0


@pytest.mark.parametrize("light", ["Sunlit Surface", "Deep Light"])
def test_ray_softness_reaches_the_actual_marched_shaft_consumer(light):
    for value in (0., .35, 1.):
        knobs = scene.scene_knobs({**SETTINGS, "extruded_bubble_light_type": light,
                                  "extruded_bubble_ray_softness": value})
        assert knobs["shaft_soft"] == value


def test_ray_flicker_deepens_as_the_rays_rise_and_a_held_passage_reaches_further():
    on = {**SETTINGS, "extruded_bubble_rays_enabled": True, "extruded_bubble_ray_flicker": 0.5}
    quiet, loud = scene.ray_motion(on, 0.0, 0.0), scene.ray_motion(on, 1.0, 1.0)
    assert 0.0 < quiet[0] < loud[0] <= 0.5
    assert quiet[1] < loud[1]
    assert scene.ray_motion({**on, "extruded_bubble_ray_flicker": 0.0}, 1.0, 1.0)[0] == 0.0
    assert scene.ray_motion({**on, "extruded_bubble_rays_enabled": False}, 1.0, 1.0) == (0.0, 1.0)


def test_procedural_populations_resolve_each_range_once_and_keep_per_owner_quality():
    from rendering.quick.visualizer.implementations.extruded_bubble import (
        _procedural_fill,
    )

    low, high = 2, 7                                               # TEST INPUT: a Bead Chains range
    settings = {**SETTINGS, "extruded_bubble_bead_chains": [low, high], "scene3d_detail": "High"}
    quiet, snow, fizz = _procedural_fill(settings, 0.0, 0.0)
    loud, _, _ = _procedural_fill(settings, 1.0, 0.0)
    assert snow == fizz == 0 and quiet < loud  # zero Particles does not kill chain Range modulation
    assert loud / quiet == pytest.approx(high / low)
    assert _procedural_fill({**settings, "extruded_bubble_bead_chains": [0, 0]}, 1.0, 1.0)[0] == 0
    _, snow, fizz = _procedural_fill(settings, 1.0, 1.0)
    assert snow > 0 and fizz > 0
    cheaper = _procedural_fill({**settings, "scene3d_detail": "Balanced"}, 1.0, 1.0)
    assert cheaper[0] < loud and 0 < cheaper[1] < snow and 0 < cheaper[2] < fizz

# --- the renderer through the production host -------------------------------------------------------------------


def _snapshot(fade=1.0, **parameters):
    from tests.test_qtquick_extruded_spectrum import H, W
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode="extruded_bubble", settings=SETTINGS)
    state = snapshot.logical.mode_state
    state = dataclasses.replace(state, parameters={**dict(state.parameters), **parameters})
    logical = dataclasses.replace(snapshot.logical, mode_state=state)
    presentation = dataclasses.replace(snapshot.presentation, content_fade=fade)
    return dataclasses.replace(snapshot, logical=logical, presentation=presentation)


@pytest.fixture
def target(qt_app):
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tests.test_qtquick_extruded_spectrum import _Target

    capture, host = _Target(), QuickVisualizerRenderHost()
    try:
        yield capture, host
    finally:
        assert capture.capture.context.makeCurrent(capture.capture.surface)
        host.release_resources()
        capture.close()


@pytest.mark.qt
def test_a_prepared_renderer_draws_without_compiling_or_allocating_and_releases_everything(target, monkeypatch):
    from OpenGL import GL as gl

    from rendering.quick.render import gl_resources
    from rendering.quick.scene3d import defocus, probe, resources
    from rendering.quick.visualizer.implementations.extruded_bubble import QuickExtrudedBubbleRenderer

    capture, host = target
    snapshot = _snapshot()
    renderer = QuickExtrudedBubbleRenderer()
    host._implementations["extruded_bubble"] = renderer
    capture.render(host, _snapshot(fade=0.0))                          # establishes the frame; draws nothing
    frame = _frame(snapshot, capture.capture.vao)
    for _ in range(80):
        if renderer.prepare_step(frame):
            break
    else:
        pytest.fail("the renderer never finished preparing")
    names, allocation = dict(renderer._target._names), renderer._target.allocation

    def forbidden(*_args, **_kwargs):
        pytest.fail("a prepared frame compiled or allocated")
    for module in (resources, defocus, probe, gl_resources):
        if hasattr(module, "compile_program"):
            monkeypatch.setattr(module, "compile_program", forbidden)
    for name in ("glCreateProgram", "glCreateShader", "glCreateTextures", "glGenTextures", "glCreateBuffers",
                 "glCreateVertexArrays", "glCreateFramebuffers", "glCreateRenderbuffers", "glTextureStorage2D",
                 "glTexStorage2D", "glTextureStorage2DMultisample", "glNamedBufferStorage"):
        monkeypatch.setattr(gl, name, forbidden)
    turned = _snapshot(extruded_bubble_turn=0.4, extruded_bubble_tilt=0.2, extruded_bubble_scene_scale=1.7)
    pictures = [capture.render(host, frame_) for frame_ in (snapshot, turned, snapshot)]
    assert renderer._target._names == names and renderer._target.allocation == allocation
    assert np.abs(pictures[0] - pictures[0][0, 0]).max() > 0           # it draws
    assert np.array_equal(pictures[0], pictures[2])                    # the same frame draws the same picture
    assert np.abs(pictures[1] - pictures[0]).mean() > 1.0              # turning the view changes it
    monkeypatch.undo()
    host.release_resources()
    assert not renderer.has_resources


@pytest.mark.qt
def test_the_rays_follow_the_simulation_driver_never_the_raw_level(target):
    """The passage level holds at 1 through loud music: the picture reads the simulation's ray driver instead."""
    capture, host = target

    def with_state(**fields):
        snapshot = _snapshot(extruded_bubble_rays_enabled=True, extruded_bubble_rays=[0.0, 1.0],
                             extruded_bubble_particles=[0., 0.],
                             extruded_bubble_bead_chains=[0., 0.])  # isolate rays from modest level-driven bead sizing
        state = dataclasses.replace(snapshot.logical.mode_state, wakes=(), emission=0., **fields)
        return dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))
    for _ in range(4):                                                  # prepared and warm
        capture.render(host, with_state(level=0.0, rays=0.2))
    base = capture.render(host, with_state(level=0.0, rays=0.2))
    assert np.array_equal(capture.render(host, with_state(level=1.0, rays=0.2)), base)
    assert np.abs(capture.render(host, with_state(level=0.0, rays=0.9)) - base).mean() > 0.5


@pytest.mark.qt
def test_idle_population_uniforms_preserve_counts_and_wakes_but_fade_free_chains_and_particle_glow(target, monkeypatch):
    from rendering.quick.visualizer.implementations.extruded_bubble import _Uniforms
    capture, host = target
    recorded=[]
    original=_Uniforms.set
    def observe(bank, program, values):
        if 'uChainFill' in values or 'uSpeckSize' in values or 'uRowMajor' in values:
            recorded.append(dict(values))
        return original(bank, program, values)
    monkeypatch.setattr(_Uniforms,'set',observe)
    samples=[]
    for level in (0.,.05,.1,1.):
        recorded.clear()
        snapshot=_snapshot(extruded_bubble_bead_chains=[2.,2.],extruded_bubble_particles=[.4,.4])
        snapshot=dataclasses.replace(snapshot,logical=dataclasses.replace(snapshot.logical,
            mode_state=dataclasses.replace(snapshot.logical.mode_state,level=level,emission=.4)))
        capture.render(host,snapshot)
        chains=next(v for v in recorded if 'uChainFill' in v)
        specks=next(v for v in recorded if 'uSpeckSize' in v)
        proxies=next(v for v in recorded if v.get('uRowMajor')==1)
        samples.append((chains,specks))
        assert proxies['uParticleActivity']==1.
    assert samples[0][0]['uChainFill']==samples[-1][0]['uChainFill']>0
    assert [c['uChainActivity'] for c,s in samples] == pytest.approx((0.,.5,1.,1.))
    assert [s['uParticleActivity'] for c,s in samples] == pytest.approx((0.,.5,1.,1.))
    assert 0 < samples[0][1]['uSpeckSize'] < .5*samples[-1][1]['uSpeckSize']
    assert len({s['uSpecks'] for c,s in samples})==1  # opacity/size do not remap density


@pytest.mark.qt
@pytest.mark.parametrize('light_type', ('Sunlit Surface', 'Deep Light'))
def test_light_strength_scales_glint_proxy_hdr_without_moving_physical_records(target, monkeypatch, light_type):
    from OpenGL import GL as gl
    from rendering.quick.visualizer.implementations import extruded_bubble as implementation

    capture, host = target
    renderer = implementation.QuickExtrudedBubbleRenderer()
    host._implementations['extruded_bubble'] = renderer
    original = implementation.glint_proxies
    rows = []

    def observed(*args, **kwargs):
        data = original(*args, **kwargs)
        rows.append(data.copy())
        return data

    monkeypatch.setattr(implementation, 'glint_proxies', observed)

    def probe_pixels():
        previous = int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_CUBE_MAP))
        try:
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, renderer._probe.texture)
            return np.concatenate([np.frombuffer(bytes(gl.glGetTexImage(
                gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, 0, gl.GL_RGB, gl.GL_FLOAT)), dtype='f4')
                for face in range(6)])
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, previous)

    energy = []
    for strength in (0., .5, 1.):
        snapshot = _snapshot(extruded_bubble_light_type=light_type, extruded_bubble_light_strength=strength)
        state = dataclasses.replace(snapshot.logical.mode_state,
                                    bubbles=_record(z=0., radius=1.), clusters=(), wakes=())
        snapshot = dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))
        capture.render(host, snapshot)
        lit = probe_pixels()
        # Keep all ambient/emitter uniforms identical; remove only proxy radiance.
        with monkeypatch.context() as control:
            control.setattr(implementation, 'glint_proxies', lambda shells, direction, power, **kw:
                            original(shells, direction, 0., **kw))
            capture.render(host, snapshot)
            unlit = probe_pixels()
        energy.append(float((lit - unlit).sum()))
    assert len(rows) == 3
    assert all(np.array_equal(rows[0][:, :4], row[:, :4]) for row in rows[1:])
    assert rows[0][:, 4].sum() == 0.
    assert rows[2][:, 4] == pytest.approx([10. if light_type == 'Sunlit Surface' else 2.5])
    assert rows[1][:, 4] == pytest.approx(rows[2][:, 4] * .5)
    assert energy[0] == 0. and energy[1] > 0.
    assert energy[2] == pytest.approx(energy[1] * 2., rel=.03)  # half-float probe quantisation


@pytest.mark.qt
def test_deep_light_softness_changes_native_shaft_pixels(target):
    capture, host = target
    def at(softness):
        snapshot = _snapshot(extruded_bubble_light_type="Deep Light",
                             extruded_bubble_ray_softness=softness,
                             extruded_bubble_rays_enabled=True, extruded_bubble_rays=[.2, .8])
        state = dataclasses.replace(snapshot.logical.mode_state, rays=.8)
        return dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))
    sharp = capture.render(host, at(0.))
    soft = capture.render(host, at(1.))
    assert np.abs(soft - sharp).mean() > .5  # previous consumer produced byte-identical images


@pytest.mark.qt
def test_camera_changes_only_projection_and_keeps_uploaded_world_populations_and_stream(target,monkeypatch):
    from rendering.quick.visualizer.implementations.extruded_bubble import QuickExtrudedBubbleRenderer, _Instances, _Uniforms
    capture,host=target
    renderer=QuickExtrudedBubbleRenderer();host._implementations['extruded_bubble']=renderer
    uploads={};streams=[]
    upload=_Instances.upload
    def observed(instance,data):
        for name in ('_shells','_wakes','_clusters','_proxies'):
            if instance is getattr(renderer,name):uploads.setdefault(name,[]).append(np.array(data,copy=True))
        return upload(instance,data)
    monkeypatch.setattr(_Instances,'upload',observed)
    uniforms=_Uniforms.set
    def observed_uniforms(bank,program,mapping):
        if 'uStreamWorld' in mapping:streams.append(mapping['uStreamWorld'])
        return uniforms(bank,program,mapping)
    monkeypatch.setattr(_Uniforms,'set',observed_uniforms)
    snapshot=_snapshot()
    state=dataclasses.replace(snapshot.logical.mode_state,
        bubbles=_record(z=-8.)+_record(x=.5,z=-8.,ident=2,cluster=3)+_record(x=2.,z=-8.,ident=3,cluster=3),
        clusters=(2.,1.,2.,-1.),wakes=(0.,0.,-8.,1.,1.,.3,.7,1.),stream=(.6,.8,0.))
    for turn,tilt,scale,pan in ((0.,0.,1.,0.),(.7,-.4,.6,.2),(-1.,.5,2.,-.1)):
        parameters={**dict(state.parameters),'extruded_bubble_turn':turn,'extruded_bubble_tilt':tilt,
                    'extruded_bubble_scene_scale':scale,'extruded_bubble_scene_pan_x':pan}
        current=dataclasses.replace(state,parameters=parameters)
        capture.render(host,dataclasses.replace(snapshot,logical=dataclasses.replace(snapshot.logical,mode_state=current)))
    assert set(uploads)=={'_shells','_wakes','_clusters','_proxies'}
    for samples in uploads.values():
        assert len(samples)==3 and all(np.array_equal(samples[0],row) for row in samples[1:])
    assert streams and all(tuple(v)==(.6,.8,0.) for v in streams)


@pytest.mark.qt
def test_particle_emission_thins_each_wake_at_balanced_instead_of_dropping_owners(target,monkeypatch):
    from OpenGL import GL as gl
    from rendering.quick.visualizer.implementations.extruded_bubble import QuickExtrudedBubbleRenderer
    capture,host=target
    renderer=QuickExtrudedBubbleRenderer();host._implementations['extruded_bubble']=renderer
    values={};draws=[]
    original=type(renderer._uniforms).set
    def uniforms(bank,program,mapping):
        if 'uWakeCount' in mapping:values.update(mapping);values['program']=program
        return original(bank,program,mapping)
    monkeypatch.setattr(type(renderer._uniforms),'set',uniforms)
    draw=gl.glDrawArraysInstanced
    def observed(*args):
        if values.get('program')==int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)):draws.append(args[-1])
        return draw(*args)
    monkeypatch.setattr(gl,'glDrawArraysInstanced',observed)
    snapshot=_snapshot(scene3d_detail='Balanced',extruded_bubble_bead_chains=[0,0])
    sources=(0.,0.,.3,.1,7.,-1.,1.,.1, .2,0.,.3,.1,9.,.4,1.,.1)
    def at(emission):
        state=dataclasses.replace(snapshot.logical.mode_state,wakes=sources,emission=emission)
        return dataclasses.replace(snapshot,logical=dataclasses.replace(snapshot.logical,mode_state=state))
    capture.render(host,at(1.))
    assert values['uWakeCount']==2 and 0<values['uFizzPer']<64
    assert draws[-1]==values['uBeadCount']+values['uSnowCount']+2*values['uFizzPer']
    draws.clear();capture.render(host,at(0.))
    assert values['uFizzPer']==values['uSnowCount']==0 and not draws


def _frame(snapshot, quad_vao):
    """The frame the host hands the renderer for the capture's card (as ``_Target.render`` draws it)."""
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
    from tests.test_qtquick_extruded_spectrum import H, W

    return QuickVisualizerRenderFrame(snapshot=snapshot, viewport=(0, 0, W, H), logical_size=(float(W), float(H)),
                                      matrix_values=(2 / W, 0, 0, 0, 0, -2 / H, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                                      quad_vao=quad_vao)


@pytest.mark.qt
@pytest.mark.parametrize("stage", ["bubble", "particle"])
def test_an_instance_of_no_size_draws_no_quad(qt_app, stage):
    """Generated instances left out (or faded to nothing) carry radius 0. The vertex stages' size floors (half a pixel
    so specks resolve) once drew each as a shaded dot; with no size there is no quad at all."""
    from OpenGL import GL as gl

    from rendering.gl_programs.extruded_bubble_program import BUBBLE_VERTEX, PARTICLE_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    width, height = 96, 64
    capture = TransitionCapture(width, height)
    try:
        assert capture.context.makeCurrent(capture.surface)
        _v, _w, tan, projection = scene.camera(0.0, 0.0, width / height)
        program = compile_program(BUBBLE_VERTEX if stage == "bubble" else PARTICLE_VERTEX,
                                  "#version 460 core\nout vec4 colour;\nvoid main() { colour = vec4(1.0); }\n",
                                  label="no-size test")
        gl.glUseProgram(program)
        for name, value in (("uFocus", 10.0), ("uAperture", 0.0), ("uCrisp", 0.0), ("uNearLayer", 0.0),
                            ("uPixel", 2.0 * tan[1] / height), ("uSpecks", 1.0)):
            location = gl.glGetUniformLocation(program, name)
            if location >= 0:
                gl.glUniform1f(location, value)
        gl.glUniformMatrix3fv(gl.glGetUniformLocation(program, "uWorldToView"), 1, False,
                              np.eye(3, dtype=np.float32))
        gl.glUniformMatrix4fv(gl.glGetUniformLocation(program, "uProjection"), 1, False,
                              np.asarray(projection, dtype=np.float32))
        vao = int(np.asarray(gl.glGenVertexArrays(1)).ravel()[0])
        gl.glBindVertexArray(vao)

        def lit(radius):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
            gl.glViewport(0, 0, width, height)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDisable(gl.GL_BLEND)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glVertexAttrib4f(0, 0.0, 0.0, -5.0, radius)      # straight ahead
            gl.glVertexAttrib4f(1, 1.0, 0.0, 0.5, 0.0)
            gl.glVertexAttrib1f(2, 1.0)                    # explicit lifetime attribute for ordinary shells
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, 1)
            gl.glFinish()
            pixels = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            return int(np.count_nonzero(np.frombuffer(bytes(pixels), dtype=np.uint8)))

        assert lit(1e-6) > 0                                    # the smallest size still resolves (the floor)
        assert lit(0.0) == 0
        gl.glBindVertexArray(0)
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)
    finally:
        capture.close()


def test_a_deep_light_tints_the_water_it_lights_more_than_a_sunlit_surface_does():
    """Inside the water the light's own colour carries its glow, beams and veils; under a surface the sky's light is
    mostly the water's."""
    orange = {**SETTINGS, "extruded_bubble_light_colour": [255, 130, 50, 255],
              "extruded_bubble_water_colour": [8, 30, 40, 255]}
    light = np.asarray(scene._rgb(orange["extruded_bubble_light_colour"]))

    def distance(light_type, key):
        knobs = scene.scene_knobs({**orange, "extruded_bubble_light_type": light_type})
        tint = np.asarray(knobs[key]) / max(knobs[key])
        return float(np.abs(tint - light / light.max()).sum())
    for key in ("sky", "shaft"):
        assert distance("Deep Light", key) < 0.5 * distance("Sunlit Surface", key)
