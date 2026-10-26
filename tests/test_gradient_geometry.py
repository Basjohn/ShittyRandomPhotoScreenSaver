"""Endpoint geometry is palette-independent and respects physical content aspect."""
import math

import pytest

from core.gradient_geometry import admit_gradient_endpoints, project_linear_gradient


@pytest.mark.parametrize("aspect", [.5, 1., 2., 4.])
def test_endpoints_hit_authored_colours_and_follow_the_physical_line(aspect):
    points = (.1, .7, .8, .2)
    gx, gy, bias = project_linear_gradient(points, aspect)
    level = lambda x, y: (x - .5) * gx + (y - .5) * gy + .5 + bias
    assert level(*points[:2]) == pytest.approx(0.)
    assert level(*points[2:]) == pytest.approx(1.)
    assert level((points[0]+points[2])/2, (points[1]+points[3])/2) == pytest.approx(.5)
    # In pixels the gradient normal is parallel to the endpoint line.
    assert (gx/aspect) * (points[3]-points[1]) == pytest.approx(gy * (points[2]-points[0]) * aspect)


def test_span_controls_gradualness_and_shift_moves_the_blend_centre():
    narrow = project_linear_gradient((.4, .5, .6, .5), 2.)
    wide = project_linear_gradient((.1, .5, .9, .5), 2.)
    shifted = project_linear_gradient((.1, .5, .5, .5), 2.)
    assert abs(narrow[0]) > abs(wide[0])
    assert shifted[2] != 0.
    assert project_linear_gradient((.2, .5, .8, .5), 1.)[2] == pytest.approx(0.)


@pytest.mark.parametrize("points", [(0, 0, 0, 0), (0, 0, .01, 0), (0, math.nan, 1, 1), (0, 1)])
def test_invalid_endpoint_inputs_are_rejected(points):
    with pytest.raises(ValueError):
        admit_gradient_endpoints(points)
