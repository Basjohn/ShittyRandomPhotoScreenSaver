"""Accuracy of decorative bubble masking, without extra full-screen work."""
from types import SimpleNamespace
import pytest

from widgets.spotify_visualizer.bubble_ambient_geometry import (
    ambient_occluder_quads, select_ambient_occluders,
)


def test_occlusion_uses_all_visible_bubbles_with_the_exact_rendered_radii():
    bubbles = [SimpleNamespace(is_big=False), SimpleNamespace(is_big=True),
               SimpleNamespace(is_big=True), SimpleNamespace(is_big=False)]
    positions = (0.1, 0.2, 0.009, 1.0,
                 0.3, 0.4, 0.084, 1.0,
                 0.5, 0.6, 0.075, 0.0,
                 0.7, 0.8, 0.008, 1.0)
    assert select_ambient_occluders(bubbles, positions) == (
        0.1, 0.2, 0.009, 1.0,
        0.3, 0.4, 0.084, 1.0,
        0.7, 0.8, 0.008, 1.0,
    )


@pytest.mark.parametrize('width,height,scale', [
    (420, 280, 1.0), (420, 280, 1.6), (4000, 250, 0.7), (250, 4000, 1.3),
    (2048, 300, 1.0), (300, 2048, 1.0),
])
def test_masks_remain_physical_circles_with_correct_response_scaling(width, height, scale):
    data = ambient_occluder_quads((0.4, 0.6, 0.045, 0.75), width, height, scale)
    assert len(data) == 6 * 5
    vertices = [data[i:i+5] for i in range(0, len(data), 5)]
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    assert ((max(xs) - min(xs)) * width) == pytest.approx((max(ys)-min(ys)) * height)
    assert ((max(ys)-min(ys)) * height) == pytest.approx(2 * .045 * scale * height)
    assert all(v[4] == .75 for v in vertices)


def test_empty_ambient_mask_and_invalid_contracts():
    assert ambient_occluder_quads((), 420, 280) == ()
    assert select_ambient_occluders((), ()) == ()
    with pytest.raises(ValueError):
        select_ambient_occluders([SimpleNamespace(is_big=True)], ())
    with pytest.raises(ValueError):
        ambient_occluder_quads((0.1, 0.2, 0.3), 420, 280)
    with pytest.raises(ValueError):
        ambient_occluder_quads((0.1, 0.2, float('nan'), 0.7), 420, 280)


def test_immutable_bubble_frame_requires_complete_bounded_occlusion_records():
    from widgets.spotify_visualizer.render_state import BubbleFrame
    points = (0.5, 0.5, 3.0, 0.7, 1.0, 1.0)
    frame = BubbleFrame(ambient_points=points,
                        ambient_occluders=(0.45, 0.6, 0.07, 0.9))
    assert frame.ambient_occluders == (0.45, 0.6, 0.07, 0.9)
    with pytest.raises(ValueError):
        BubbleFrame(ambient_occluders=(0.45, 0.6, 0.07, 0.9))
    with pytest.raises(ValueError):
        BubbleFrame(ambient_points=points, ambient_occluders=(0.4, 0.6))


def _per_circle_reference(occluders, width, height, response_radius_scale=1.0):
    """The original per-circle Python encoding, kept as the oracle for the vectorised one."""
    result = []
    corners = ((-1., -1.), (1., -1.), (1., 1.), (-1., -1.), (1., 1.), (-1., 1.))
    for i in range(0, len(occluders), 4):
        x, y, r, alpha = occluders[i:i + 4]
        if r <= 0.0 or alpha <= 0.0:
            continue
        radius_y = r * response_radius_scale
        radius_x = radius_y * height / width
        for dx, dy in corners:
            result.extend((x + dx * radius_x, y + dy * radius_y, dx, dy, min(1., max(0., alpha))))
    return tuple(result)


def test_vectorised_occluder_vertices_are_byte_identical_to_the_per_circle_encoding():
    import random

    import numpy as np

    from widgets.spotify_visualizer.bubble_ambient_geometry import ambient_occluder_vertices

    rng = random.Random(7)
    for _trial in range(400):
        occluders = []
        for _ in range(rng.randint(0, 110)):
            occluders += [rng.uniform(-0.2, 1.2), rng.uniform(-0.2, 1.2),
                          rng.choice([0.0, -0.01, rng.uniform(0.0, 0.2)]),
                          rng.choice([0.0, 1.0, 1.3, rng.uniform(-0.1, 1.2)])]
        width, height = rng.choice([(420, 280), (2048, 766), (300, 2400), (1, 1)])
        scale = rng.choice([1.0, 0.37, 2.9, rng.uniform(0.1, 3.0)])
        expected = _per_circle_reference(tuple(occluders), width, height, scale)
        assert ambient_occluder_quads(tuple(occluders), width, height, scale) == expected
        # The GPU upload: float32 bytes exactly as the per-circle tuple produced them.
        vertices = ambient_occluder_vertices(tuple(occluders), width, height, scale)
        assert vertices.astype(np.float32).tobytes() == np.asarray(expected, dtype=np.float32).tobytes()
