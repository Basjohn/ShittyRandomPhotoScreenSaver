"""Qt-free regression for Fullscreen Now Playing's parent artwork-border axis sizing."""

import pytest

from rendering.quick.fullscreen_artwork_resize import artwork_factor_after_frame_delta as factor


def test_horizontal_and_vertical_resizes_follow_origin_pixels_not_mutable_text_width():
    assert factor(1.0, 120.0, 60.0) == 1.5
    assert factor(1.0, 120.0, -30.0) == 0.75
    # An intermediate text wrap does not enter the equation: each sample uses the same pointer-down size.
    assert factor(1.0, 120.0, 90.0) == factor(1.0, 120.0, 90.0)


def test_edited_non_square_artwork_dimensions_remain_independent():
    assert factor(1.4, 140.0, -40.0) == 1.0
    assert factor(0.7, 70.0, 35.0) == 1.05


def test_artwork_factor_floors_and_caps_at_existing_schema_bounds():
    assert factor(1.0, 120.0, -9000.0) == 0.5
    assert factor(1.0, 120.0, 9000.0) == 3.0


@pytest.mark.parametrize("start, size, delta", [
    (1.0, 0.0, 50.0), (1.0, -10.0, 50.0),
    (float("nan"), 120.0, 3.0), (1.0, 120.0, float("inf")),
])
def test_invalid_geometry_fails_loudly(start, size, delta):
    with pytest.raises(ValueError):
        factor(start, size, delta)
