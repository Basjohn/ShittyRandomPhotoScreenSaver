"""Depth cards (shared primitive, proved on its own): the partition tiles the picture exactly with
no overlap, is stable for a seed, keeps cards from getting thin; a pose turns a card rigidly about
its centre; a shadow falls away from the light by the point's height; the GPU equals the mirrors."""
from __future__ import annotations

import itertools
import math
import random

import pytest

from rendering.gl_programs.depth_cards import CARD_GLSL, card_partition, card_pose, card_shadow

ASPECT = 16 / 9


@pytest.mark.parametrize("count", (1, 4, 8, 14))
def test_the_partition_tiles_the_picture_exactly(count):
    rects = card_partition(5, count, ASPECT)
    assert len(rects) == count and rects == card_partition(5, count, ASPECT)
    assert sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in rects) == pytest.approx(ASPECT)
    for a, b in itertools.combinations(rects, 2):
        overlap_x = min(a[2], b[2]) - max(a[0], b[0])
        overlap_y = min(a[3], b[3]) - max(a[1], b[1])
        assert overlap_x <= 1e-12 or overlap_y <= 1e-12
    for x0, y0, x1, y1 in rects:
        assert -ASPECT / 2 - 1e-12 <= x0 < x1 <= ASPECT / 2 + 1e-12 and -0.5 - 1e-12 <= y0 < y1 <= 0.5 + 1e-12
        assert min(x1 - x0, y1 - y0) > 0.08 * (8 / max(count, 1)) ** 0.5


def test_a_pose_turns_rigidly_and_a_shadow_falls_away_from_the_light():
    corners = [(-0.3, -0.2), (0.3, -0.2), (0.3, 0.2), (-0.3, 0.2)]
    posed = [card_pose(c, (0.1, -0.1), (0.6, 0.8), 0.7, 0.5, (0.2, 0.3)) for c in corners]
    for (a, b), (pa, pb) in zip(itertools.combinations(corners, 2), itertools.combinations(posed, 2)):
        assert math.dist(pa, pb) == pytest.approx(math.dist(a, b))
    assert card_pose((0.2, 0.1), (0.0, 0.0), (1.0, 0.0), 0.0, 0.0, (0.0, 0.0)) == pytest.approx((0.2, 0.1, 0.0))
    assert card_shadow((0.0, 0.0, 0.0), (-0.3, 0.5, 1.0)) == (0.0, 0.0)
    shadow = card_shadow((0.0, 0.0, 0.4), (-0.3, 0.5, 1.0))
    assert shadow[0] > 0.0 and shadow[1] < 0.0                    # light from the top left: shadow down right


@pytest.mark.qt
def test_the_pose_and_shadow_match_their_mirrors_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(10)
        cases = []
        for _ in range(64):
            a = rng.uniform(0, 2 * math.pi)
            cases.append(((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4)), (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5)),
                          (math.cos(a), math.sin(a)), rng.uniform(-1, 1), rng.uniform(0, 1), (rng.uniform(-1, 1), rng.uniform(-1, 1))))
        gpu = probe.run("vec4 a = arg(0), b = arg(1), c = arg(2); vec3 w = cardPose(a.xy, a.zw, b.xy, b.z, b.w, c.xy);"
                        "FragColor = vec4(w, cardShadow(w, vec3(-0.3, 0.5, 1.0)).x);",
                        [[(*o, *ce), (*ax, turn, lift), slide] for o, ce, ax, turn, lift, slide in cases],
                        declarations=CARD_GLSL)
        expected = []
        for o, ce, ax, turn, lift, slide in cases:
            w = card_pose(o, ce, ax, turn, lift, slide)
            expected.append((*w, card_shadow(w, (-0.3, 0.5, 1.0))[0]))
        _check(gpu, expected)
    finally:
        probe.close()
