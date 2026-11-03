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
