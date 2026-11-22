"""Pure exact-class/foreground contracts; no Qt or GL required for core arithmetic."""
from __future__ import annotations

from types import SimpleNamespace
import pytest

from widgets.spotify_visualizer.bubble_hero_occlusion import (
    BIG_CLASS_WORDS, MAX_HERO_BUBBLES, admit_big_class_bits, composite_hero_layers, pack_big_class_bits,
)

_ZERO = (0,) * BIG_CLASS_WORDS


def _words(*first):
    return tuple(first) + (0,) * (BIG_CLASS_WORDS - len(first))


def test_big_class_words_cover_every_hero_with_exact_class_identity():
    last = MAX_HERO_BUBBLES - 1
    big_indices = {0, 31, 32, 63, 64, 109, 127, 128, last}
    bubbles = [SimpleNamespace(is_big=(i in big_indices)) for i in range(MAX_HERO_BUBBLES)]
    words = pack_big_class_bits(bubbles)
    assert len(words) == BIG_CLASS_WORDS
    assert BIG_CLASS_WORDS * 32 >= MAX_HERO_BUBBLES
    assert admit_big_class_bits(words, MAX_HERO_BUBBLES) == words
    for index in range(MAX_HERO_BUBBLES):
        assert bool(words[index >> 5] & (1 << (index & 31))) == (index in big_indices)


def test_big_class_not_inferred_from_radius_and_tracks_promotions():
    tiny_big = SimpleNamespace(is_big=True, radius=0.002)
    enormous_small = SimpleNamespace(is_big=False, radius=0.3)
    bubbles = [tiny_big, enormous_small]
    assert pack_big_class_bits(bubbles) == _words(1)
    enormous_small.is_big = True  # temporary promotion is still a real big hero
    assert pack_big_class_bits(bubbles) == _words(3)


def test_class_bits_reject_out_of_bounds_or_non_uint32_words():
    assert admit_big_class_bits(_ZERO, 0) == _ZERO
    # The one-uvec4 shape is admitted as the first four words.
    assert admit_big_class_bits((0, 0, 0, 0), 0) == _ZERO
    with pytest.raises(ValueError):
        pack_big_class_bits([SimpleNamespace(is_big=False)] * (MAX_HERO_BUBBLES + 1))
    for invalid in ((-1, 0, 0, 0), (0, 0, 0, 2**32), (0, 0, 0), (1, 0, 0, 0), (0,) * 5):
        with pytest.raises(ValueError):
            admit_big_class_bits(invalid, 0)
    with pytest.raises(ValueError):
        admit_big_class_bits((1 << 3, 0, 0, 0), 3)
    with pytest.raises(ValueError):
        admit_big_class_bits(_words(0, 0, 0, 0, 1), 128)


def test_big_hero_foreground_hides_only_small_bodies_not_scene_underlay():
    under = (.12, .19, .24, 1.)
    small = (.78, .75, .80, 1.)
    big = (.37, .50, .60, 1.)
    assert composite_hero_layers(under, small, under, 0.) == small
    assert composite_hero_layers(under, under, big, 0.) == big
    assert composite_hero_layers(under, small, big, 1.) == pytest.approx(big)
    halfway = composite_hero_layers(under, small, big, .5)
    assert halfway == pytest.approx(tuple(b + .5 * (s-u) for u,s,b in zip(under,small,big)))


def test_immutable_frame_rejects_unbound_big_class_bits():
    from widgets.spotify_visualizer.render_state import BubbleFrame
    frame = BubbleFrame(
        positions=(.1,.2,.01,1., .3,.4,.08,1.),
        extras=(1.,0.,0.,0., 1.,0.,0.,0.),
        bubble_count=2,
        big_class_bits=(2,0,0,0),
    )
    assert frame.big_class_bits == _words(2)
    with pytest.raises(ValueError):
        BubbleFrame(bubble_count=1, big_class_bits=(2,0,0,0))
