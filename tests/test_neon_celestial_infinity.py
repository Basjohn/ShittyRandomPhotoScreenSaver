"""Neon Lake's Sun and Moon sit at infinity: moving the camera never moves, grows or re-phases them."""
import math

import pytest

from rendering.gl_programs.neon_celestial import CELESTIAL_DISTANCE, CELESTIAL_REFERENCE, celestial_placement
from rendering.gl_programs.neon_lake_basin_program import orbit_view

FIELD = (0.0, 0.0, 1600.0, 900.0)


@pytest.mark.parametrize("offset", [(0.0, 0.0, 0.0), (0.12, 0.05, -0.1), (-0.2, 0.15, 0.2)])
def test_translating_the_eye_keeps_the_body_at_one_screen_point_and_size(offset):
    authored, size = (1.4, 1.6, -3.5), 0.3
    home = orbit_view(0.05, 0.08, FIELD)
    moved = orbit_view(0.05, 0.08, FIELD, position=offset)   # same orientation, translated eye
    places = []
    for view in (home, moved):
        centre, radius = celestial_placement(authored, size, view.eye)
        assert math.dist(centre, view.eye) == pytest.approx(CELESTIAL_DISTANCE)
        places.append((view.item_point(centre), radius / CELESTIAL_DISTANCE))
    (a, angular_a), (b, angular_b) = places
    assert a == pytest.approx(b, abs=1e-6) and angular_a == pytest.approx(angular_b)


def test_the_authored_position_is_the_bodys_direction_and_size_from_the_reference_viewpoint():
    authored, size = (2.0, 2.0, -6.0), 0.4
    centre, radius = celestial_placement(authored, size, CELESTIAL_REFERENCE)
    seen = [a - r for a, r in zip(authored, CELESTIAL_REFERENCE)]
    distance = math.sqrt(sum(v * v for v in seen))
    direction = [(c - r) / CELESTIAL_DISTANCE for c, r in zip(centre, CELESTIAL_REFERENCE)]
    assert direction == pytest.approx([v / distance for v in seen])
    assert radius / CELESTIAL_DISTANCE == pytest.approx(size / distance)
