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


@pytest.mark.parametrize('pose', ('turned', 'perspective'))
def test_navigation_draws_the_fixed_world_where_the_shared_camera_projects_it(lab, pose):
    # World-first: pillars are authored in world units, so every visible front pillar sits exactly where the shared
    # framed camera projects its world base, from any pose (nothing is placed relative to the view or the card).
    width, height = lab.size
    pixels = lab.render('low', flat=True, pose=pose)[:, :, :3].astype(int)
    front = (np.abs(pixels - np.array(lab_module.FLAT['front_pillar'])*255).max(2) <= 6)
    view, projection, _ = lab_module.camera(lab_module.POSES[pose], width/height)
    checked = 0
    for x, z, row, _seed in lab_module.pillar_positions(lab.recipe.hall):
        if row:
            continue
        clip = projection @ view @ np.array((x, .3, z, 1.))
        px, py = (clip[0]/clip[3] + 1)*width/2, (1 - clip[1]/clip[3])*height/2
        if 4 <= px < width - 4 and 4 <= py < height - 4:
            window = front[int(py) - 3:int(py) + 4, int(px) - 3:int(px) + 4]
            assert window.any(), (x, z, px, py)
            checked += 1
    assert checked >= 4
