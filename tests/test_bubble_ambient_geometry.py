"""Pure viewport contract: no native Qt/GL required for shape and scaling gates."""
from __future__ import annotations

import pytest
from widgets.spotify_visualizer.bubble_ambient_geometry import (
    ambient_target_size, ambient_sprite_scale, MAX_AMBIENT_TEXTURE_EDGE,
)


@pytest.mark.parametrize('width,height,dpr', [
    (420, 280, 1), (420, 280, 2), (280, 420, 1),
    (4000, 250, 1), (250, 4000, 1), (9000, 3000, 2),
    (3000, 9000, 2), (320, 6000, 1.5), (6000, 320, 1.5),
])
def test_transparent_texture_follows_content_aspect_with_bounded_size(width, height, dpr):
    tw, th, scale = ambient_target_size((24, 24, width, height), dpr)
    assert 0 < tw <= MAX_AMBIENT_TEXTURE_EDGE
    assert 0 < th <= MAX_AMBIENT_TEXTURE_EDGE
    assert 0 < scale <= dpr
    assert abs(tw / th - width / height) < max(0.03, (width / height) * 2 / min(tw, th))
    assert abs(tw - width * scale) <= 0.51
    assert abs(th - height * scale) <= 0.51
    # Content origin does not change the authored background geometry.
    assert (tw,th,scale) == ambient_target_size((170, 340, width, height), dpr)


def test_equal_area_presentation_never_stretches_decoration_by_card_aspect():
    assert ambient_sprite_scale(1) == 1
    assert ambient_sprite_scale(4) == 2
    assert ambient_sprite_scale(20) == 2
    assert ambient_sprite_scale(.01) == .75
    assert ambient_sprite_scale(1.5) == pytest.approx(1.5**.5)


@pytest.mark.parametrize('invalid', [(0, 5, 1), (12, -5, 1), (3, 4, 0),
                                     (float('nan'), 5, 1), (3, 4, float('inf'))])
def test_invalid_viewport_rejected(invalid):
    width, height, dpr = invalid
    with pytest.raises(ValueError):
        ambient_target_size((0,0,width,height),dpr)
