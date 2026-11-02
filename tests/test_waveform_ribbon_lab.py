"""Waveform lab GL ownership and repeatable diagnostic captures; artistic recipes remain editable."""
import numpy as np
import pytest

from rendering.gl_error_policy import disable_per_call_gl_error_checking
disable_per_call_gl_error_checking()
from tools.labs import waveform_ribbon_lab as lab_module

pytestmark = pytest.mark.qt


@pytest.fixture
def lab(qt_app):
    lab = lab_module.Lab(lab_module.Recipe(), (640, 709))
    yield lab
    lab.close()


@pytest.mark.parametrize('state', ('low', 'high'))
def test_flat_envelope_survives_an_interleaved_lit_capture(lab, state):
    # A reflected additive pass once leaked blend state into the next diagnostic render.
    before = lab.render(state, flat=True)
    rgb=before[:,:,:3].astype(int)
    assert ((rgb.max(2)-rgb.min(2)==0)&(rgb.min(2)>20)).sum()>100 # floor geometry actually drew
    lab.render('low', flat=False)
    pixels = lab.render(state, flat=True)
    np.testing.assert_array_equal(pixels,before)


def test_lit_render_has_light_and_no_overflow(lab):
    pixels = lab.render('high', flat=False).astype(int)
    rgb = pixels[:, :, :3]
    garbage = (rgb.max(2) >= 250) & (np.sort(rgb, axis=2)[:, :, 1] < 20)
    assert rgb.max() > 200 and not garbage.any()


def test_perspective_far_floor_dissolves_into_the_same_background(lab):
    upper = lab.render('low', flat=False, pose='perspective')[:190, :, :3].astype(int).mean(2)
    # A different clear colour exposed the finite ground as a straight horizontal seam.
    assert np.abs(np.diff(upper, axis=0)).mean(1).max() < 2.


def test_reflected_additive_light_never_writes_depth(lab, monkeypatch):
    from OpenGL import GL as gl
    observed = []
    draw = lab.ribbons.draw

    def checked(*args, **kwargs):
        if kwargs.get('shading') in ('light', 'sparks'):
            observed.append((kwargs['shading'], bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK))))
        return draw(*args, **kwargs)

    monkeypatch.setattr(lab.ribbons, 'draw', checked)
    lab.render('high', flat=False)
    assert len(observed) == 4  # reflected light/sparks, then direct light/sparks
    assert all(not depth_write for _, depth_write in observed), observed


def test_render_admits_its_context_before_allocating_and_restores_the_caller(lab):
    from PySide6.QtGui import QOpenGLContext
    from tools.labs.render_target import OffscreenRenderTarget
    foreign = OffscreenRenderTarget(32, 32)
    try:
        assert QOpenGLContext.currentContext() == foreign.context
        pixels = lab.render('low', flat=False)
        assert pixels.max() > 200
        assert QOpenGLContext.currentContext() == foreign.context
    finally:
        foreign.close()


@pytest.mark.parametrize('missing,allocated', [('roughness',1),('height',2)])
def test_missing_floor_map_retires_preceding_textures(lab, monkeypatch, tmp_path, missing, allocated):
    from dataclasses import replace
    from OpenGL import GL as gl
    created=[]
    create=gl.glCreateTextures
    def record(*args):
        result=create(*args)
        created.append(int(args[2][0]))
        return result
    monkeypatch.setattr(gl,'glCreateTextures',record)
    with lab.target.current():
        with pytest.raises(FileNotFoundError):
            lab_module.load_floor_textures(replace(lab.recipe.floor,**{missing:str(tmp_path/'missing.png')}))
        assert len(created)==allocated and all(not gl.glIsTexture(name) for name in created)


@pytest.mark.parametrize('state', ('low', 'high'))
def test_mist_band_contains_every_visible_sheet_and_closes_where_none_is(state):
    # The mist is shaped by the waveform: each admitted knot's counted vertical extent lies inside the clear band
    # at its x (the sheets never sit in mist); beyond the flowing head, where no sheet exists, the band closes.
    recipe = lab_module.Recipe()
    ring, now = lab_module.fill_ring(recipe, state)
    packet, flow, fog = ring.packet(), recipe.flow, recipe.fog
    translation = (flow.head_x - flow.speed*now, 0., 0.)
    age_fade = (now, flow.fade_in, (ring.capacity - 1)/flow.knot_hz, flow.fade_out)
    table = lab_module.waveform_envelope(packet, translation, age_fade, fog)
    x0, x1, samples = fog.envelope_range
    xs = np.linspace(x0, x1, int(samples))
    lower, upper, presence = table[0, :, 0], table[0, :, 1], table[0, :, 2]
    rows = np.frombuffer(packet.payload, np.float32).reshape(packet.instances, -1, 4)
    checked = 0
    for path in rows:
        count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
        knots = path[4:].reshape(-1, lab_module.KNOT_ROWS, 4)[(start + np.arange(count)) % capacity]
        x = knots[:, 0, 0] + packet.world_origin[0] + translation[0]
        y = knots[:, 0, 1] + packet.world_origin[1] - lab_module.VIEW_SLOPE*(knots[:, 0, 2] + packet.world_origin[2])
        half = fog.envelope_width*knots[:, 0, 3]
        visible = (np.abs(x) < 6.) & (knots[:, 1, 2] > .5)
        band_low, band_high = np.interp(x[visible], xs, lower), np.interp(x[visible], xs, upper)
        # The band is smoothed along x; a smoothing width's worth of slack, never more.
        assert (y[visible] - half[visible] >= band_low - .15).all() and (y[visible] + half[visible] <= band_high + .15).all()
        checked += visible.sum()
    assert checked > 50
    beyond = xs > flow.head_x + 2.
    assert (presence[beyond] == 0.).all() and np.allclose(upper[beyond], lower[beyond])
    assert (upper[np.abs(xs) < 6.] - lower[np.abs(xs) < 6.] > .5).all()


def test_retained_history_capture_never_rebuilds_or_appends_and_accents_can_be_off(lab, monkeypatch):
    from dataclasses import replace
    from tools.labs.waveform_ribbon_reactivity import HeadHistory, PRE_ROLL
    lab.recipe = replace(lab.recipe, sparks=None, strays=None, bloom=0.)
    model = HeadHistory('A', lab.recipe)
    model.advance(PRE_ROLL+3)
    before = model.ring.packet().payload
    tick = model.tick
    def forbidden(*args, **kwargs):
        raise AssertionError('Rendering mutated/reconstructed logical history')
    monkeypatch.setattr(lab_module, 'fill_ring', forbidden)
    monkeypatch.setattr(model.ring, 'append', forbidden)
    observed = []
    draw = lab.ribbons.draw
    def checked(*args, **kwargs):
        observed.append(kwargs.get('shading'))
        return draw(*args, **kwargs)
    monkeypatch.setattr(lab.ribbons, 'draw', checked)
    pixels = lab.render_history(model.ring, PRE_ROLL+3)
    assert pixels[:, :, :3].max() > 100
    assert 'sparks' not in observed and 'strays' not in observed
    assert model.tick == tick and model.ring.packet().payload == before


def test_existing_visible_body_responds_before_new_head_history_is_admitted(lab):
    from tools.labs.waveform_ribbon_reactivity import HeadHistory,PRE_ROLL,Signal
    class Step:
        events=()
        def sample(self,t):return Signal(bass=.8,loudness=1.) if t>0 else Signal()
    active=HeadHistory('A',lab.recipe,input_source=Step(),body_envelope=True)
    idle=HeadHistory('A',lab.recipe,fixture='idle',body_envelope=True)
    active.advance(PRE_ROLL+.1);idle.advance(PRE_ROLL+.1)
    assert active.ring.packet().payload==idle.ring.packet().payload
    a=lab.render_history(active.snapshot(),PRE_ROLL+.1,flat=True)
    b=lab.render_history(idle.snapshot(),PRE_ROLL+.1,flat=True)
    def mask(p):
        rgb=p[:,:,:3].astype(int)
        return (rgb[:,:,0]>120)&(rgb[:,:,2]>120)&(rgb[:,:,1]<60)
    assert np.count_nonzero(mask(a)^mask(b))>1000
