"""Spectrum's rim glow and the border band it sits inside (plan 1D.14).

Renders go through the production ``QuickVisualizerRenderHost`` -> ``QuickSpectrumRenderer`` into an offscreen FBO
(``tests/test_spectrum_decor.py``'s ``render`` fixture: synthetic bars, test colours, never a preset). The border band
is one authored unit in from each edge on both sides (the old floored ``<=`` test drew two columns on the left and
bottom against one on the right and top, covering the rim's brightest columns on the left), and the rim glow lifts the
two sides of a bar alike.
"""
from __future__ import annotations

import pytest

from tests.test_spectrum_decor import BORDER, COUNT, FILL, render  # noqa: F401  (the fixture)

GLOW = {"spectrum_glow_enabled": True, "spectrum_glow_color": [0, 255, 0, 255], "spectrum_glow_intensity": 0.55}


def _runs(mask):
    runs, start = [], None
    for x, value in enumerate(mask):
        if value and start is None:
            start = x
        elif not value and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def _border(pixels):
    import numpy as np
    return (pixels == np.array(BORDER)).all(axis=2)


def _bar_row(pixels):
    """The middle of the rows crossing every bar with fill inside (far from the bars' tops and bottoms)."""
    import numpy as np
    fill = (pixels == np.array(FILL)).all(axis=2)
    counts = [len(_runs(pixels[y, :, 3] > 0)) if fill[y].any() else 0 for y in range(pixels.shape[0])]
    rows = [y for y, count in enumerate(counts) if count == max(counts)]
    return rows[len(rows) // 2]


def _side_counts(pixels, row):
    border = _border(pixels)
    counts = []
    for a, b in _runs(pixels[row, :, 3] > 0):
        band = border[row, a:b]
        inner = [i for i, value in enumerate(band) if not value]
        if inner:
            counts.append((inner[0], len(band) - 1 - inner[-1]))
    return counts


@pytest.mark.qt
def test_the_border_band_is_as_wide_on_the_left_as_on_the_right(render):
    pixels = render(ghosting=False)
    counts = _side_counts(pixels, _bar_row(pixels))
    assert len(counts) == COUNT
    assert all(left == right >= 1 for left, right in counts), counts


@pytest.mark.qt
def test_a_segment_ring_is_as_wide_on_every_edge(render):
    """Segmented bars: the ring's left and right columns and its bottom and top rows match."""
    import numpy as np
    pixels = render(ghosting=False, solid=False)
    border = _border(pixels)
    fill = (pixels == np.array(FILL)).all(axis=2)
    # Segments with fill inside (taller than their ring), down one bar's middle column.
    column = max(range(pixels.shape[1]), key=lambda x: int(fill[:, x].sum()))
    rows = []
    for top, bottom in _runs(pixels[:, column, 3] > 0):
        band = border[top:bottom, column]
        inner = [i for i, value in enumerate(band) if not value]
        if inner:
            rows.append((inner[0], len(band) - 1 - inner[-1]))
    assert len(rows) >= 3
    assert all(upper == lower >= 1 for upper, lower in rows), rows
    filled = _runs(fill[:, column])
    a, b = filled[len(filled) // 2]
    sides = _side_counts(pixels, (a + b) // 2)
    assert sides and all(left == right >= 1 for left, right in sides), sides


@pytest.mark.qt
def test_the_rim_glow_lifts_both_sides_of_a_bar_alike(render):
    """The glow's lift (glow on minus off) summed over the outer columns of every bar, left against right: equal
    within the bars' own pixel phases (the bars sit on fractional positions). The old border band hid the left
    side's brightest columns (left about half of right)."""
    # 37 bars: about 20.2 px wide, a small fractional part, where the old band (two units on the left, one plus the
    # width's fraction on the right) was most lopsided.
    bars = (0.6,) * 37
    off = render(ghosting=False, bars=bars, peaks=bars)
    on = render(GLOW, ghosting=False, bars=bars, peaks=bars)
    row = _bar_row(off)
    lift = (on[row, :, :3] - off[row, :, :3]).clip(0).sum(-1)
    left = right = 0
    for a, b in _runs(off[row, :, 3] > 0):
        k = min(6, (b - a) // 2)              # the rim's own columns
        left += int(lift[a:a + k].sum())
        right += int(lift[b - k:b].sum())
    assert left > 0 and right > 0
    assert abs(left - right) <= 0.1 * max(left, right), (left, right)


# ------------------------------------------------------------------------------------------- Rim Placement, Sharpness
BARS = (0.6,) * 37


def _placements():
    from core.settings.visualizer_mode_settings import require_mode_settings
    return require_mode_settings("spectrum").control("spectrum_glow_placement").choices


def _side_lift(render, overrides):
    """(left, right) glow lift summed over every bar's outer six columns, on the middle row of the bars."""
    off = render(ghosting=False, bars=BARS, peaks=BARS)
    on = render({**GLOW, **overrides}, ghosting=False, bars=BARS, peaks=BARS)
    row = _bar_row(off)
    lift = (on[row, :, :3] - off[row, :, :3]).clip(0).sum(-1)
    left = right = 0
    for a, b in _runs(off[row, :, 3] > 0):
        k = min(6, (b - a) // 2)
        left += int(lift[a:a + k].sum())
        right += int(lift[b - k:b].sum())
    return left, right


@pytest.mark.qt
def test_rim_placement_puts_the_rim_on_the_chosen_sides(render):
    """Each one-sided placement lights its side and leaves the other dark (the top keeps its rim); the default
    placement lights both, exactly as the render with no placement given."""
    import numpy as np
    from core.settings.default_contract import require_canonical_default
    default = require_canonical_default("widgets.spotify_visualizer.spectrum_glow_placement")
    both_sides = _side_lift(render, {"spectrum_glow_placement": default})
    assert min(both_sides) > 0
    one_sided = [p for p in _placements() if p != default]
    assert len(one_sided) == 2
    lifts = {p: _side_lift(render, {"spectrum_glow_placement": p}) for p in one_sided}
    first, second = (lifts[p] for p in one_sided)
    # One placement lights only the left, the other only the right, each as brightly as Both does there.
    assert {(first[0] > 0, first[1] > 0), (second[0] > 0, second[1] > 0)} == {(True, False), (False, True)}
    lit = [side for lift in (first, second) for side in lift if side > 0]
    assert sorted(lit) == sorted(both_sides)
    bars = dict(ghosting=False, bars=BARS, peaks=BARS)
    assert np.array_equal(render(GLOW, **bars), render({**GLOW, "spectrum_glow_placement": default}, **bars))


@pytest.mark.qt
def test_rim_sharpness_reshapes_only_the_rim(render):
    """Sharpness moves only pixels the rim lifts (at either setting); sharper is a brighter, more solid band near the
    edge. Its default draws the render with no sharpness given."""
    import numpy as np
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_settings import require_mode_settings
    control = require_mode_settings("spectrum").control("spectrum_glow_sharpness")
    bars = dict(ghosting=False, bars=BARS, peaks=BARS)
    off = render(**bars)
    soft = render({**GLOW, "spectrum_glow_sharpness": control.low}, **bars)
    sharp = render({**GLOW, "spectrum_glow_sharpness": control.high}, **bars)
    lifted = (np.abs(soft - off).max(axis=2) > 0) | (np.abs(sharp - off).max(axis=2) > 0)
    changed = np.abs(sharp - soft).max(axis=2) > 0
    assert changed.sum() > 500 and not (changed & ~lifted).any()
    assert sum(_side_lift(render, {"spectrum_glow_sharpness": control.high})) > sum(
        _side_lift(render, {"spectrum_glow_sharpness": control.low}))
    default = require_canonical_default("widgets.spotify_visualizer.spectrum_glow_sharpness")
    assert np.array_equal(render(GLOW, **bars), render({**GLOW, "spectrum_glow_sharpness": default}, **bars))


def test_a_placement_change_fades_the_side_in_and_out():
    """Rim Placement's sides are envelopes on the capture clock: a side leaving fades out, never vanishes."""
    from tests.test_spectrum_decor import _owner
    from widgets.spotify_visualizer.spectrum_decor import FADE_SECONDS, SpectrumDecorFade
    first, second, both = _placements()[0], _placements()[1], _placements()[2]
    owner = _owner(spectrum_glow_placement=both)
    fade = SpectrumDecorFade(owner)
    fade.advance(owner, 0.0)
    assert (fade.mixes()["spectrum_glow_left_mix"], fade.mixes()["spectrum_glow_right_mix"]) == (1.0, 1.0)
    owner._spectrum_glow_placement = first
    levels, t = [], 0.0
    while t < FADE_SECONDS + 0.2:
        t += 1.0 / 60.0
        fade.advance(owner, t)
        levels.append((fade.mixes()["spectrum_glow_left_mix"], fade.mixes()["spectrum_glow_right_mix"]))
    kept = 0 if levels[-1][0] == 1.0 else 1
    assert all(pair[kept] == 1.0 for pair in levels)               # the side the placement keeps never moves
    leaving = [pair[1 - kept] for pair in levels]
    assert leaving == sorted(leaving, reverse=True) and leaving[-1] == 0.0
    assert any(0.3 < v < 0.7 for v in leaving)                     # a real ramp, not a cut
    owner._spectrum_glow_placement = second
    fade.advance(owner, t + 0.1)
    assert 0.0 < min(fade.mixes()["spectrum_glow_left_mix"], fade.mixes()["spectrum_glow_right_mix"]) < 1.0
