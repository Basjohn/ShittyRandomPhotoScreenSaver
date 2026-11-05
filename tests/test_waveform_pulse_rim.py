"""Pulse Rim: the Waveform ribbons' rims brighten further where the travelling pulse is.

The logical owner publishes its pulse appearance field (``pulse_at`` on ``PULSE_GRID``, history-axis x) in every
snapshot; the scene uploads it once per frame and only the light pass's rims (crisp line and rim glow) read it, at the
fragment's history-axis x. Off (0) is pixel-identical to the light pass without any of the Pulse Rim source. On, the
added light lies exactly where the published field is, for both Travel Directions and every Reaction Mode, and
nothing but the rims changes. Test-owned fields, controls and strengths only; no preset value is read.
"""
from dataclasses import replace
import numpy as np
import pytest
from core.ribbon_packet import KNOT_ROWS
from core.waveform_ribbon_dynamics import PULSE_GRID, WaveformDynamics
from rendering.quick.scene3d.pulse_rim import CEILING, REFERENCE, SPREAD
from tests.test_waveform_floor_give import frame_of
from tests.test_waveform_ribbon_mode import parameters

STRENGTH = 3.


def _gl():
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    return gl


def _camera(values):
    return {key: value for key, value in values.items() if key.startswith('waveform_ribbon_camera_')
            or key in ('waveform_ribbon_turn', 'waveform_ribbon_tilt', 'waveform_ribbon_scene_scale',
                       'waveform_ribbon_scene_pan_x', 'waveform_ribbon_scene_pan_y')}


def _model(**overrides):
    from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
    values = parameters()
    values['waveform_ribbon_mist_enabled'] = True
    values.update({'waveform_ribbon_'+key: value for key, value in overrides.items()})
    configuration = CompiledWaveformSettings(values)
    return values, configuration, WaveformDynamics(configuration.controls)


def _state(values, configuration, snapshot, pulse=None):
    from widgets.spotify_visualizer.render_state import WaveformRibbonFrame, freeze_render_fields
    return WaveformRibbonFrame(snapshot.packet, configuration.scene(snapshot), snapshot.time, snapshot.travel,
        snapshot.rotation_angle, snapshot.rotation_speed, snapshot.drives, snapshot.realized, ready=True,
        parameters=freeze_render_fields(_camera(values)), pulse=snapshot.pulse if pulse is None else pulse)


def _settled(**overrides):
    values, configuration, model = _model(**overrides)
    for _ in range(80):
        snapshot = model.advance(1/90, bands=(.6, .4, .3), intensity=.6, presence=1.)
    return values, configuration, model, snapshot


def gaussian_field(centre, sigma=.9, level=.2):
    return (level*np.exp(-.5*((PULSE_GRID-centre)/sigma)**2)).astype(np.float32).tobytes()


def _render(renderer, target, frame, state, strength):
    frame.snapshot.logical.mode_state = replace(state, scene=replace(state.scene, pulse_rim=strength))
    for _ in range(80):
        if renderer.prepare_step(frame):
            break
    target.bind(); renderer.render(frame)
    return target.read_rgba().copy()


class Renders:
    """One production renderer on one offscreen target; ``rgb`` renders a state at a strength."""
    def __init__(self, width=320, height=200):
        from rendering.quick.offscreen_target import OffscreenRenderTarget
        from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
        _gl()
        self.target = OffscreenRenderTarget(width, height)
        self.renderer = QuickWaveformRibbonRenderer()
        self.frame = None

    def rgb(self, state, strength):
        if self.frame is None:
            self.frame = frame_of(self.target, state)
        return _render(self.renderer, self.target, self.frame, state, strength)[..., :3].astype(float)

    def columns(self, state):
        """Screen column of each history-axis x along the ribbons (the renderer's own camera and Travel Direction)."""
        from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
        from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale
        width, height = self.target.width, self.target.height
        view, projection, _eye, _lens = physical_view(state.parameters, width/height,
            framed_aperture_scale(self.frame.snapshot.presentation, content=True), zoom=state.zoom)
        packet, flow = state.packet, state.scene.flow
        data = np.frombuffer(packet.payload, np.float32).reshape(packet.instances, -1, 4)
        points = []
        for path in data:
            count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
            knots = path[4:].reshape(-1, KNOT_ROWS, 4)[(start+np.arange(count)) % capacity, 0, :3].astype(float)
            points.append(knots+np.asarray(packet.world_origin)+(flow.head_x-state.travel, 0., 0.))
        history = np.concatenate(points)
        world = history*((-1. if flow.direction < 0. else 1.), 1., 1.)
        clip = (projection@view@np.concatenate((world, np.ones((len(world), 1))), 1).T).T
        screen = (clip[:, 0]/clip[:, 3]*.5+.5)*width
        order = np.argsort(screen)
        return np.interp(np.arange(width)+.5, screen[order], history[order, 0])

    def close(self):
        with self.target.current():
            self.renderer.release_resources()
            _gl().glUseProgram(0)
        self.target.close()


def column_gain(on, off):
    """Added light per screen column (whole image: the reflection lies under the same columns)."""
    return np.clip(on-off, 0., None).sum(axis=(0, 2))


def peak_column(gain):
    kernel = np.ones(5)/5.
    return int(np.argmax(np.convolve(gain, kernel, mode='same')))


def test_pulse_rim_is_one_canonical_logical_setting_resolved_into_the_scene():
    from core.settings.visualizer_mode_settings import require_mode_settings
    from core.waveform_ribbon_scene import Recipe
    from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
    control = next(c for c in require_mode_settings('waveform_ribbon').controls
                   if c.key == 'waveform_ribbon_pulse_rim')
    assert control.bucket == 'pulse' and control.logical
    assert Recipe().pulse_rim == 0.
    from types import SimpleNamespace as NS
    snapshot = NS(ready=False, passage=0., drives={}, realized={})
    values = parameters()
    for strength in (0., .5, 3.):
        values['waveform_ribbon_pulse_rim'] = strength
        assert CompiledWaveformSettings(values).scene(snapshot).pulse_rim == strength


def test_snapshot_publishes_the_pulse_appearance_field_and_the_frame_carries_it():
    from widgets.spotify_visualizer.render_state import WaveformRibbonFrame
    values, configuration, model, snapshot = _settled()
    for tick in range(40):
        snapshot = model.advance(1/90, bands=(.6, .4, .3), intensity=.6, presence=1., hit=1. if tick < 3 else 0.)
    field = np.frombuffer(snapshot.pulse, np.float32)
    assert field.shape == PULSE_GRID.shape and field.max() > .05
    np.testing.assert_array_equal(field, model.pulse_at(PULSE_GRID).astype(np.float32))
    state = _state(values, configuration, snapshot)
    assert state.pulse == snapshot.pulse
    with pytest.raises(ValueError):
        replace(state, pulse=b'\0'*12)


def _strip_pulse_rim(monkeypatch):
    """The light pass's exact source without any Pulse Rim text (the shader as it was before the option)."""
    import rendering.gl_programs.ribbon as programs
    import rendering.quick.scene3d.ribbon as ribbon_module
    import rendering.quick.visualizer.implementations.waveform_ribbon as implementation
    source = programs.RIBBON_LIGHT_FRAGMENT
    assert source.count(programs.PULSE_RIM_GLSL) == 1 and source.count(programs.PULSE_RIM_LINE) == 1
    stripped = source.replace(programs.PULSE_RIM_GLSL, '').replace(programs.PULSE_RIM_LINE, '')
    assert 'PulseRim' not in stripped
    monkeypatch.setattr(ribbon_module, 'RIBBON_LIGHT_FRAGMENT', stripped)
    monkeypatch.setitem(ribbon_module._FRAGMENTS, 'light', stripped)
    monkeypatch.setattr(implementation, 'RIBBON_LIGHT_FRAGMENT', stripped)


@pytest.mark.qt
def test_pulse_rim_off_is_pixel_identical_to_the_light_pass_without_it(qt_app, monkeypatch):
    values, configuration, model, snapshot = _settled()
    state = _state(values, configuration, snapshot, pulse=gaussian_field(0.))
    renders = Renders()
    try:
        off = renders.rgb(state, 0.)
        assert not renders.renderer._scene.pulse_rim.has_resources
        on = renders.rgb(state, STRENGTH)
        assert renders.renderer._scene.pulse_rim.has_resources and np.abs(on-off).max() > 8
        again = renders.rgb(state, 0.)
        assert not renders.renderer._scene.pulse_rim.has_resources
        np.testing.assert_array_equal(again, off)        # nothing of the rim field leaks into a later frame
        # An empty published field (a not-ready snapshot) draws exactly the rims without it at any strength.
        np.testing.assert_array_equal(renders.rgb(replace(state, pulse=b''), STRENGTH), off)
    finally:
        renders.close()
    with monkeypatch.context() as patch:
        _strip_pulse_rim(patch)
        reference = Renders()
        try:
            np.testing.assert_array_equal(reference.rgb(state, 0.), off)
        finally:
            reference.close()


@pytest.mark.qt
def test_only_the_rims_change(qt_app):
    """With the rim line and rim glow dark, Pulse Rim adds nothing: sheet, strands, lattice and glints are unchanged."""
    values, configuration, model, snapshot = _settled()
    state = _state(values, configuration, snapshot, pulse=gaussian_field(0., sigma=3., level=.5))
    material = replace(state.scene.material, rim_light=0., rim_glow_light=0.)
    dark = replace(state, scene=replace(state.scene, material=material))
    renders = Renders()
    try:
        np.testing.assert_array_equal(renders.rgb(dark, STRENGTH), renders.rgb(dark, 0.))
    finally:
        renders.close()


def placed(renders, state, centre, tolerance):
    """Whether the added light's brightest columns lie on the published field's peak (in screen space)."""
    columns = renders.columns(state)
    shown = replace(state, pulse=gaussian_field(centre))
    gain = column_gain(renders.rgb(shown, STRENGTH), renders.rgb(shown, 0.))
    expected = int(np.argmin(np.abs(columns-centre)))
    return abs(peak_column(gain)-expected) <= tolerance, peak_column(gain), expected


@pytest.mark.qt
@pytest.mark.parametrize('travel', ('Right To Left', 'Left To Right'))
def test_the_brightening_sits_on_the_pulse_for_both_travel_directions(qt_app, monkeypatch, travel):
    values, configuration, model, snapshot = _settled(travel_direction=travel)
    state = _state(values, configuration, snapshot)
    renders = Renders()
    tolerance = renders.target.width//40
    try:
        renders.rgb(state, 0.)
        columns = renders.columns(state)
        # The history axis runs across the view in the Travel Direction's sense.
        assert (columns[-1] > columns[0]) == (travel == 'Right To Left')
        for centre in (-2.5, 1.5):
            ok, found, expected = placed(renders, state, centre, tolerance)
            assert ok, (travel, centre, found, expected)
    finally:
        renders.close()
    # Negative control: a light pass that reads the field at the mirrored x puts the brightening elsewhere, and the
    # same placement check catches it.
    import rendering.gl_programs.ribbon as programs
    import rendering.quick.scene3d.ribbon as ribbon_module
    import rendering.quick.visualizer.implementations.waveform_ribbon as implementation
    wrong = programs.RIBBON_LIGHT_FRAGMENT.replace('pulseRimResponse(vWorld.x+uMistOrigin.x)',
                                                   'pulseRimResponse(-(vWorld.x+uMistOrigin.x))')
    assert wrong != programs.RIBBON_LIGHT_FRAGMENT
    monkeypatch.setattr(ribbon_module, 'RIBBON_LIGHT_FRAGMENT', wrong)
    monkeypatch.setitem(ribbon_module._FRAGMENTS, 'light', wrong)
    monkeypatch.setattr(implementation, 'RIBBON_LIGHT_FRAGMENT', wrong)
    renders = Renders()
    try:
        renders.rgb(state, 0.)
        ok, found, expected = placed(renders, state, -2.5, tolerance)
        assert not ok, (found, expected)
    finally:
        renders.close()


def response(field, x):
    """The light pass's rim response to a published field at history x (its three taps, square and soft cap)."""
    taps = sum(w*np.interp(x+offset, PULSE_GRID, field) for w, offset in ((.25, -SPREAD), (.5, 0.), (.25, SPREAD)))
    return CEILING*np.tanh((np.maximum(taps, 0.)/REFERENCE)**2/CEILING)


def _mode_state(mode, travel):
    """A production frame with the published field of ``mode`` in view: beats launched near the view so a travelling
    band (and, in Frozen Past, the held look of the cloth an earlier band shaped) is on screen."""
    values, configuration, model, snapshot = _settled(reaction_mode=mode, travel_direction=travel,
                                                     pulse_width=2.5, pulse_speed=6., pulse_fade=4.)
    for tick in range(int(.9*90)):
        snapshot = model.advance(1/90, bands=(.6, .4, .3), intensity=.6, presence=1.,
                                 hit=1. if tick in (0, 1, 50, 51) else 0.)
    return _state(values, configuration, snapshot)


@pytest.mark.qt
@pytest.mark.parametrize('travel', ('Right To Left', 'Left To Right'))
@pytest.mark.parametrize('mode', ('Travelling Pulse', 'Frozen Past', 'Group Wave', 'Whole Swell'))
def test_every_reaction_mode_brightens_its_own_published_field(qt_app, monkeypatch, mode, travel):
    import core.waveform_ribbon_dynamics as dyn
    monkeypatch.setattr(dyn, 'PULSE_ORIGIN', 7.)   # launch just beyond the test camera's view
    state = _mode_state(mode, travel)
    field = np.frombuffer(state.pulse, np.float32).astype(float)
    renders = Renders()
    try:
        off = renders.rgb(state, 0.)
        gain = column_gain(renders.rgb(state, STRENGTH), off)
        # The rims' own response to a uniform field: what each column would gain for the same field everywhere.
        full = np.full(PULSE_GRID.size, 4.*REFERENCE, np.float32).tobytes()   # a saturated response everywhere
        uniform = column_gain(renders.rgb(replace(state, pulse=full), STRENGTH), off)
        columns = renders.columns(state)
    finally:
        renders.close()
    # The outermost columns take a trace of light from the opposite edge in the bloom; they carry no rim of their own.
    rims = uniform > .2*uniform.max()
    rims[:3] = rims[-3:] = False
    share = gain[rims]/uniform[rims]                       # this column's share of its full (uniform) brightening
    assert gain.max() > 0.
    expected = response(field, columns)
    if mode == 'Whole Swell':
        assert np.ptp(expected) < 1e-6                     # uniform field: the same share everywhere
        assert share.std() < .15*share.mean()
        return
    expected = expected[rims]/CEILING
    assert np.ptp(expected) > .15                          # the field varies across the view
    # Each column's share follows the published field's response there; the brightened columns are the pulse's and
    # the columns away from it stay as they were. Mirroring the field breaks the agreement (negative control).
    agreement = np.corrcoef(share, expected)[0, 1]
    mirrored = np.corrcoef(share, response(field, -columns)[rims]/CEILING)[0, 1]
    assert agreement > .9, agreement
    assert agreement > mirrored+.3, (agreement, mirrored)
    assert share[expected < .05].max(initial=0.) < .3     # (the bloom carries a little light sideways)
    assert share[expected > .9].min(initial=1.) > .6
