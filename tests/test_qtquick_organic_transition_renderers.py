"""Resolved-only Melt Drip controls and its dormant renderer.

Production image/lifecycle checks are in test_qtquick_future_transition_gl;
old shader-string tests blessed the mask-only appearance rejected by the user.
"""
import pytest

from rendering.quick.transitions.implementations.melt_drip import QuickMeltDripRenderer, melt_drip_parameters


@pytest.mark.parametrize("origin,expected", (
    ("top_left", ((0., 0.), 0.)), ("top_center", ((.5, 0.), 0.)),
    ("top_right", ((1., 0.), 0.)), ("center_out", ((.5, .5), 0.)),
    ("center_in", ((.5, .5), 1.)),
))
def test_melt_drip_requires_one_resolved_melt_origin(origin, expected):
    valid = {"seed": 12, "detail": .5, "depth": .7, "gloss": .65}
    params = melt_drip_parameters(valid, origin)
    assert (params.origin, params.origin_mode) == expected
    # Settings labels, "Random" and the retired edge directions resolve before
    # the request; the renderer only admits a resolved origin.
    for invalid in (None, "Random", "Top Left", "down", "left", "diag_tl_br", 3):
        with pytest.raises(ValueError, match="resolved origin"):
            melt_drip_parameters(valid, invalid)
    for field in ("depth", "gloss"):
        with pytest.raises(ValueError, match=field):
            melt_drip_parameters({**valid, field: float("nan")}, origin)


def test_the_melt_renderer_is_a_lazy_local_surface():
    renderer = QuickMeltDripRenderer()
    assert renderer.transition_id == "melt_drip"
    assert not renderer.has_resources
