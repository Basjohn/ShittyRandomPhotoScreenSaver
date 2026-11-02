"""Waveform lab GL ownership and repeatable diagnostic captures; artistic recipes remain editable."""
import numpy as np
import pytest
from core.ribbon_packet import KNOT_ROWS

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


def test_shared_scene_rejects_foreign_retirement_before_deleting_its_handles(lab):
    from tools.labs.render_target import OffscreenRenderTarget
    lab.render('low', flat=False)
    before = lab.textures.copy()
    foreign = OffscreenRenderTarget(16, 16)
    try:
        with pytest.raises(RuntimeError, match='foreign'):
            lab.release()
        assert lab.textures == before
    finally:
        foreign.close()
    with lab.target.current():
        lab.release()
        assert not lab.has_resources


def test_shared_scene_attempts_independent_cleanup_and_retains_failed_owner_for_retry(lab, monkeypatch):
    lab.render('high', flat=False)
    original = lab.fog.release
    def fail():
        raise RuntimeError('injected retirement failure')
    monkeypatch.setattr(lab.fog, 'release', fail)
    with lab.target.current():
        with pytest.raises(ExceptionGroup, match='retry'):
            lab.release()
        assert lab.fog.has_resources and not lab.reflected_fog.has_resources
        assert not lab.textures and not lab.ribbons.has_resources and not lab.scene.has_resources
        monkeypatch.setattr(lab.fog, 'release', original)
        lab.release()
        assert not lab.has_resources


def test_atmosphere_off_retires_all_resources_and_has_no_independent_floor_haze(lab):
    from dataclasses import replace
    lab.render('low', flat=False)
    analytic = lab.recipe.environment.mist.copy()
    assert lab.fog.has_resources and lab.field.has_resources
    lab.recipe = replace(lab.recipe, fog=None)
    lab.render('low', flat=False)
    assert not any(owner.has_resources for owner in (lab.fog, lab.reflected_fog))
    assert not lab.fog_resources.has_resources
    assert not lab.field.has_resources
    assert not {'shape','envelope'} & lab.textures.keys()
    assert lab.recipe.environment.mist == analytic and analytic['uMistShape'][0]==0.
