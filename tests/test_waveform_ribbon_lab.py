"""The Waveform Ribbon lab's camera fit holds against the WR-00 targets (offscreen, flat render)."""
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


def test_flat_render_puts_floor_and_low_envelope_on_the_targets(lab):
    pixels = lab.render('low', flat=True)
    # Floor at the bottom (an upside-down readback once put it on top), on the traced contact line.
    assert (pixels[-5, :, :3].astype(int) == pixels[-5, 0, :3]).all() and not (pixels[5, :, :3] == pixels[-5, 0, :3]).all()
    report = lab_module.landmark_report(lab_module.measure_flat(pixels), 'low')
    assert abs(report['floor']['lab'] - report['floor']['target']) < .005
    for lab_edge, target_edge in zip(report['lab_envelope'], report['target_envelope']):
        assert abs(lab_edge - target_edge) < .03


def test_lit_render_has_light_and_no_overflow(lab):
    pixels = lab.render('high', flat=False).astype(int)
    rgb = pixels[:, :, :3]
    garbage = (rgb.max(2) >= 250) & (np.sort(rgb, axis=2)[:, :, 1] < 20)
    assert rgb.max() > 200 and not garbage.any()
