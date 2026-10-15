"""Test-owned physical pixel mapping and real shoreline GLSL admission."""
import math

import pytest

from rendering.gl_programs.neon_lake_basin_program import basin_pixel_scale, _SHORELINE_GLSL


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5, 2.0])
def test_card_pixel_scale_does_not_depend_on_window_or_item_size(dpr):
    # Same affine mapping Quick supplies for a card inside its whole window.
    for width, height in ((640, 360), (1280, 720), (2560, 1440)):
        for angle in (0.0, 0.3):
            c, s = math.cos(angle), math.sin(angle)
            matrix = (2*c/width, -2*s/height, 0, 0,
                      -2*s/width, -2*c/height, 0, 0,
                      0, 0, 1, 0, -.6, .8, 0, 1)
            assert basin_pixel_scale(matrix, (0, 0, round(width*dpr), round(height*dpr))) == pytest.approx(dpr)


def test_actual_shoreline_glsl_rejects_off_editor_land_but_preserves_authored_shore(qt_app):
    from rendering.gl_programs.heightfield_glsl import HEIGHTFIELD_GLSL
    from tests.test_scene3d_glsl_mirrors import _GlslProbe

    probe = _GlslProbe()
    # Every sample lies exactly on the old iso-height band. Only authored land
    # may light it; continuation, exact-zero water and all four outer sides may not.
    samples = [[(u, v, base, .018)] for u, v, base in (
        (.5, .5, .04), (0., .5, .04), (1., .5, .04),
        (1.7, 1.75, .04), (-.01, .5, .04), (.5, -.01, .04),
        (.5, 1.01, .04), (.5, .5, 0.),
    )]
    try:
        values = probe.run("vec4 a=arg(0); FragColor=vec4(basinShoreLight(a.xy,a.z,a.w));",
                           samples, declarations=HEIGHTFIELD_GLSL + _SHORELINE_GLSL)[:, 0]
        assert min(values[:3]) > 1.0
        assert max(values[3:]) == 0.0
    finally:
        probe.close()
