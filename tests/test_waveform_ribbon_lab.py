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
