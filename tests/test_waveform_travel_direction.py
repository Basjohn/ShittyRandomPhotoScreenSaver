"""Travel Direction: the history's one sign (Flow.direction).

Every history computation (dynamics, pulses, Frozen Past, Tilt Shift, sparks, strands, end fades) works on the history
axis, so the packet is byte-identical either way; the scene mirrors that axis into the world once. Default draws
exactly the pre-option pixels; Left To Right is the mirror image (head entering at the left, the reduced fields
mirrored with it), the world colour grade stays where it is, and a live change fades the ribbons out and back in.
Test-owned controls and fixtures only; no preset value is read.
"""
from dataclasses import replace
import numpy as np
import pytest
import core.waveform_ribbon_dynamics as dyn
from core.waveform_ribbon_scene import Flow
from tests.test_waveform_ribbon_mode import parameters
from tests.test_waveform_trough_clearance import LOUD, deep_model

KEY = 'waveform_ribbon_travel_direction'


def directed(model, direction):
    scene = model.controls.scene
    return replace(model.controls, scene=replace(scene, flow=replace(scene.flow, direction=direction)))


def run(model, ticks, controls=None):
    snapshots = []
    for index in range(ticks):
        snapshots.append(model.advance(1/90, hit=1. if index % 30 == 0 else 0., controls=controls, **LOUD))
    return snapshots


def test_travel_direction_is_one_canonical_choice_resolved_into_the_flow():
    from core.settings.visualizer_mode_settings import require_mode_settings
    from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
    control = next(c for c in require_mode_settings('waveform_ribbon').controls if c.key == KEY)
    assert control.bucket == 'flow' and set(control.choices) == {'Right To Left', 'Left To Right'}
    values = parameters()
    assert values[KEY] == 'Right To Left' and CompiledWaveformSettings(values).base.flow.direction == Flow().direction == 1.
    values[KEY] = 'Left To Right'
    compiled = CompiledWaveformSettings(values)
    assert compiled.base.flow.direction == -1. and compiled.controls.scene.flow.direction == -1.
    # The recipe carries the PUBLISHED direction, not the request.
    from types import SimpleNamespace
    published = SimpleNamespace(ready=False, passage=0., drives={}, realized={}, direction=1.)
    assert compiled.scene(published).flow.direction == 1.


def test_studio_leads_the_flow_group_with_it():
    from ui.studio.waveform_adapter import build_schema
    schema = build_schema()
    prop = schema.find(KEY)
    assert (prop.workspace, prop.group) == ('composition', 'Flow')
    flow = sorted((p for p in schema.properties if p.group == 'Flow'), key=lambda p: p.priority)
    assert flow[0].id == KEY


@pytest.mark.parametrize('tilt', (False, True))
def test_packets_are_identical_either_way_and_the_direction_is_published(tilt):
    a, b = deep_model(), deep_model()
    for model in (a, b):
        model.controls = replace(model.controls, tilt_shift=tilt)
    b.controls = directed(b, -1.)
    b.direction = -1.                     # built that way: no fade
    left, right = run(a, 240), run(b, 240)
    for x, y in zip(left, right):
        assert x.packet.payload == y.packet.payload
        assert x.direction == 1. and y.direction == -1.


def test_a_live_change_fades_out_swaps_hidden_and_fades_back_without_touching_the_history():
    steady, switched = deep_model(), deep_model()
    run(steady, 120); run(switched, 120)
    want = directed(switched, -1.)
    shares, published, alphas = [], [], []
    for index in range(270):
        hit = 1. if index % 30 == 0 else 0.
        reference = steady.advance(1/90, hit=hit, **LOUD)
        snapshot = switched.advance(1/90, hit=hit, controls=want, **LOUD)
        shares.append(switched.direction_share); published.append(snapshot.direction)
        alphas.append(np.frombuffer(snapshot.packet.payload, np.float32).reshape(dyn.RIBBON_CAPACITY, -1, 4)[0, 2, 3])
    shares, published = np.asarray(shares), np.asarray(published)
    swap = int(np.argmax(published < 0.))
    assert 0 < swap and (published[swap:] == -1.).all()
    assert shares[swap] == 0. and (shares[:swap] > 0.).all()                                       # swapped hidden
    assert (np.diff(shares[:swap+1]) <= 0.).all() and (np.diff(shares[swap:]) >= 0.).all()        # out, then in
    assert np.abs(np.diff(shares)).max() < 2.*(1/90)/dyn.DIRECTION_FADE                           # never a pop
    assert shares[-1] == 1.
    # Negative control: during the change the packet differs; after it the history is exactly the untouched one.
    assert reference.packet.payload == snapshot.packet.payload
    assert min(alphas) < .02


def _fixture(target, lower=1.5):
    from tests.test_waveform_floor_give import lowered_states, frame_of
    state, = lowered_states(target, lower=lower)
    return state, frame_of(target, state)


def _render(renderer, target, frame, state, *, direction=1., give=0.):
    from tests.test_waveform_floor_give import _render as render
    scene = state.scene
    state = replace(state, scene=replace(scene, flow=replace(scene.flow, direction=direction)))
    return render(renderer, target, frame, state, give)


def test_default_draws_exactly_the_unmirrored_programs(qt_app, monkeypatch):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    import rendering.quick.scene3d.ribbon as ribbon_module
    import rendering.quick.scene3d.waveform as waveform_module
    import rendering.quick.scene3d.waveform_field as field_module
    import rendering.quick.scene3d.floor_give as give_module
    import rendering.quick.visualizer.implementations.waveform_ribbon as implementation_module
    target = OffscreenRenderTarget(240, 160)
    try:
        state, frame = _fixture(target)
        images = {}
        for stripped in (False, True):
            with monkeypatch.context() as patch:
                if stripped:
                    replaced = 0
                    for module, names in ((ribbon_module, ('RIBBON_VERTEX', 'RIBBON_CONTINUOUS_VERTEX', 'RIBBON_SPARK_VERTEX',
                                                           'RIBBON_STRAY_VERTEX', 'RIBBON_COHORT_STRAY_VERTEX')),
                                          (waveform_module, ('FLOOR_FRAGMENT', 'MEDIUM_INJECT_SOURCE')),
                                          (field_module, ('FIELD_COMPUTE',)),
                                          (give_module, ('FLOOR_GIVE_SECTION_COMPUTE',)),
                                          (implementation_module, ('FLOOR_FRAGMENT', 'MEDIUM_INJECT_SOURCE'))):
                        for name in names:
                            source = getattr(module, name)
                            for branch in ('uFieldSide<0.0', 'uFloorGiveFrame.z<0.0'):
                                replaced += source.count(branch)
                                source = source.replace(branch, 'false')
                            patch.setattr(module, name, source)
                    assert replaced >= 10
                renderer = QuickWaveformRibbonRenderer()
                try:
                    images[stripped] = [_render(renderer, target, frame, state, give=give) for give in (0., 1.)]
                finally:
                    with target.current():
                        renderer.release_resources(); gl.glUseProgram(0)
        # Repeat renders through the 4x target vary by a level on a pixel or two, rigid floor or Floor Give (driver MSAA
        # noise, tests/_msaa_render_noise.py; 6 Nov the rigid floor flipped one channel of one pixel under load), so the
        # bound is that measured noise, not identity: a real program difference changes far more than four pixels.
        for give in (0, 1):
            difference = np.abs(images[False][give].astype(int)-images[True][give])
            assert difference.max() <= 1 and (difference.max(-1) > 0).sum() <= 4, give
    finally:
        target.close()


def test_left_to_right_is_the_mirror_image_with_its_fields_and_grade_in_place(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target = OffscreenRenderTarget(240, 160); renderer = QuickWaveformRibbonRenderer()

    def fields():
        scene = renderer._scene
        out = []
        with target.current():
            for texture, rows, samples in ((scene.field.texture, 8, int(scene.recipe.fog.field_span[2])),
                                           (scene.floor_give.texture, 3, int(scene.recipe.floor.give_span[2]))):
                data = np.empty((rows, samples, 4), np.float32)
                gl.glGetTextureImage(texture, 0, gl.GL_RGBA, gl.GL_FLOAT, data.nbytes, data)
                out.append(data)
        return out
    try:
        state, frame = _fixture(target, lower=2.)
        # Geometry alone (no world grade): the picture mirrors; the floor/mist texture is world-fixed, so not exactly.
        plain = replace(state, scene=replace(state.scene, grade_share=(0., 0.)))
        rtl = _render(renderer, target, frame, plain, give=1.).astype(float)
        rtl_fields = fields()
        ltr = _render(renderer, target, frame, plain, direction=-1., give=1.).astype(float)
        ltr_fields = fields()
        # The mirror is one read-only constant, never rebuilt per frame (np.diag cost ~1.5 us a frame, 11 Nov).
        from rendering.quick.scene3d import waveform as waveform_scene
        assert renderer._scene._history_mirror is waveform_scene._HISTORY_X_MIRROR
        assert not waveform_scene._HISTORY_X_MIRROR.flags.writeable
        mirrored, unmirrored = np.abs(ltr-rtl[:, ::-1]).mean(), np.abs(ltr-rtl).mean()
        assert mirrored < .25*unmirrored, (mirrored, unmirrored)
        # The reduced fields (mist light/shape, floor give) are world-space: mirrored about x = 0 with the history.
        for a, b in zip(rtl_fields, ltr_fields):
            assert np.abs(a).max() > 0.
            np.testing.assert_allclose(b[:, ::-1], a, atol=2e-3*np.abs(a).max())
            assert np.abs(b-a).max() > .05*np.abs(a).max()          # negative control: they did move
    finally:
        with target.current(): renderer.release_resources()
        target.close()


def test_the_world_grade_stays_in_the_world():
    from core.waveform_ribbon_scene import Recipe
    from rendering.quick.scene3d.waveform import WaveformScene, colour_grade, gradient_at
    scene = WaveformScene(); scene._history_mirror = np.diag((-1., 1., 1., 1.))
    nodes, (x0, x1), share = colour_grade(Recipe(grade_range=(-4., 9.)), .6)[:3]
    mirrored, (m0, m1), _ = scene._history_grade((nodes, (x0, x1), share))
    world = np.linspace(-12., 12., 97)
    def at(stops, low, high, x): return gradient_at(stops, np.clip((x-low)/(high-low), 0., 1.))
    np.testing.assert_allclose(at(mirrored, m0, m1, -world), at(nodes, x0, x1, world), atol=1e-12)
    assert np.abs(at(nodes, x0, x1, -world)-at(nodes, x0, x1, world)).max() > .1   # negative control
    scene._history_mirror = None
    assert scene._history_grade((nodes, (x0, x1), share)) == (nodes, (x0, x1), share)


def test_head_enters_on_the_left_through_the_studio_projection():
    from types import SimpleNamespace
    from ui.studio.waveform_adapter import ribbon_world_points
    model = deep_model(); snapshot = run(model, 30)[-1]
    from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
    base = CompiledWaveformSettings(parameters()).base
    for direction in (1., -1.):
        frame = SimpleNamespace(packet=snapshot.packet, travel=snapshot.travel,
                                scene=replace(base, flow=replace(model.controls.scene.flow, direction=direction)))
        points = ribbon_world_points(frame, 0)
        head, tail = points[-1, 0], points[0, 0]         # axial (chronological) order: newest last
        assert np.sign(head) == direction and np.sign(head-tail) == direction
