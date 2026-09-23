"""Resolved-only organic controls and dormant renderers.

Production image/lifecycle checks are in test_qtquick_future_transition_gl;
old shader-string tests blessed the mask-only appearance rejected by the user.
"""
import pytest

from rendering.quick.transitions.implementations.ink_bloom import QuickInkBloomRenderer, ink_bloom_parameters
from rendering.quick.transitions.implementations.melt_drip import QuickMeltDripRenderer, melt_drip_parameters


def test_ink_bloom_requires_bounded_explicit_materials():
    resolver = ink_bloom_parameters
    valid = {"seed": 412, "detail": 1.45, "depth": .65, "gloss": .6}
    params = resolver(valid)
    assert params.seed == 412
    assert params.detail == pytest.approx(1.45)
    assert params.depth == .65 and params.gloss == .6
    for field, bad_values in (("seed", (0, 65536, True, 3.5)),
                              ("detail", (.49, 2.01, float("inf"), True, "fine")),
                              ("depth", (-.1, 1.1, float("nan"), True)),
                              ("gloss", (-.1, 1.1, float("inf"), True))):
        for invalid in bad_values:
            with pytest.raises(ValueError, match=field):
                resolver({**valid, field: invalid})
        with pytest.raises(ValueError, match=field):
            resolver({key: value for key, value in valid.items() if key != field})


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


def test_organic_renderers_are_distinct_lazy_local_surfaces():
    for constructor, name in ((QuickInkBloomRenderer, "ink_bloom"),
                              (QuickMeltDripRenderer, "melt_drip")):
        renderer = constructor()
        assert renderer.transition_id == name
        assert not renderer.has_resources
