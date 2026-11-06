"""The heightfield brush (``rendering.gl_programs.heightfield_brush``): the one owner of how a stroke paints the
authored terrain, used by the Studio's brush instrument. Pure: no Qt, no window."""
from __future__ import annotations

import pytest

from rendering.gl_programs.heightfield_brush import (
    MIN_LAND, MODES, RADIUS_RANGE, BrushSettings, HeightfieldStroke, apply_brush, brush_reach, brush_weight,
    stroke_rate,
)


def _field(size=25, value=0.0):
    return {"version": 1, "size": size, "heights": [value] * (size * size)}


def _stroke(record, settings, path):
    stroke = HeightfieldStroke(record, settings)
    stroke.press(path[0])
    for point in path[1:]:
        stroke.to(point)
    return stroke.record()


def test_raise_lower_flatten_and_water_paint_where_the_stroke_runs():
    blank = _field()
    hard = BrushSettings(falloff=0.0)
    raised = _stroke(blank, hard, [(0.5, 0.25), (0.7, 0.25)])
    heights = raised["heights"]
    assert max(heights) > 0.0
    assert sum(heights[:13 * 25]) > 0.0 and sum(heights[13 * 25:]) == 0.0, "only the near rows were painted"
    lowered = _stroke(raised, BrushSettings(mode="Lower", falloff=0.0), [(0.5, 0.25)])
    assert sum(lowered["heights"]) < sum(heights)
    flatten = BrushSettings(mode="Flatten", falloff=0.0, strength=0.5, flatten_height=0.8)
    partway = max(_stroke(lowered, flatten, [(0.5, 0.25)])["heights"])
    assert max(lowered["heights"]) < partway < 0.79, "below 100% Flatten moves toward its height gradually"
    snapped = _stroke(lowered, BrushSettings(mode="Flatten", falloff=0.0, strength=1.0, flatten_height=0.8),
                      [(0.5, 0.25)])
    assert max(snapped["heights"]) == pytest.approx(0.8), "100% snaps the core"
    # Lower keeps land above water, so only Water paints the raised area back to exact water.
    flooded = _stroke(raised, BrushSettings(mode="Water", radius=RADIUS_RANGE[1], falloff=0.0),
                      [(0.4, 0.25), (0.8, 0.25)])
    assert flooded == blank
    assert set(flooded) == {"version", "size", "heights"}


@pytest.mark.parametrize("mode", ["Raise", "Lower", "Flatten"])
def test_a_stroke_depends_on_its_path_not_on_how_many_points_carry_it(mode):
    start = _field(value=0.3)
    results = []
    for steps in (1, 4, 23):
        results.append(_stroke(start, BrushSettings(mode=mode), [(0.2 + 0.6 * i / steps, 0.5)
                                                                  for i in range(steps + 1)])["heights"])
    changed = [abs(a - b) for a, b in zip(results[0], start["heights"])]
    assert max(changed) > 0.0
    for other in results[1:]:
        assert max(abs(a - b) for a, b in zip(results[0], other)) < 1e-9


def test_low_strength_is_gradual_and_strength_scales_smoothly():
    assert stroke_rate(0.01) < 1e-4 < stroke_rate(0.2) < stroke_rate(0.5) < stroke_rate(1.0)
    gains = [max(_stroke(_field(value=0.3), BrushSettings(strength=s), [(0.3, 0.5), (0.7, 0.5)])["heights"]) - 0.3
             for s in (0.01, 0.25, 1.0)]
    assert gains[0] < 0.002, "1% barely changes the land"
    assert 0.0 < gains[0] < gains[1] < gains[2]


def test_brush_profile_falls_off_softly_and_hardens_at_zero():
    distances = [i / 40 for i in range(80)]
    for falloff in (0.0, 0.3, 0.7, 1.0):
        weights = [brush_weight(d, falloff) for d in distances]
        assert all(a >= b for a, b in zip(weights, weights[1:])), "the profile only falls"
        assert brush_weight(0.0, falloff) == 1.0 and brush_weight(brush_reach(falloff) + 1e-9, falloff) == 0.0
    assert brush_weight(0.99, 0.0) == 1.0 and brush_weight(1.01, 0.0) == 0.0, "no falloff is a hard disc"
    assert brush_weight(0.6, 1.0) < brush_weight(0.6, 0.3) == 1.0
    assert brush_weight(1.1, 1.0) > brush_weight(1.1, 0.3) > 0.0
    assert brush_reach(1.0) > brush_reach(0.3) > 1.0


def test_flatten_approaches_its_height_with_falloff_and_snaps_only_at_full_strength():
    for start in (0.1, 0.9):
        value, previous_gap = start, abs(start - 0.5)
        for _ in range(12):
            value = apply_brush(value, "Flatten", 1.0, 0.15, 0.6, 0.5)
            gap = abs(value - 0.5)
            assert gap < previous_gap and (value - 0.5) * (start - 0.5) > 0, "monotone, never overshooting"
            previous_gap = gap
    assert apply_brush(0.1, "Flatten", 1.0, 0.25, 1.0, 0.5) == pytest.approx(0.5)
    assert 0.1 < apply_brush(0.1, "Flatten", 0.4, 0.25, 1.0, 0.5) < 0.5, "the skirt blends even at 100%"
    assert apply_brush(0.1, "Flatten", 1.0, 0.25, 0.99, 0.5) < 0.5


def test_lower_never_makes_water_and_water_stays_exact():
    record = _field(value=0.05)
    for _ in range(6):
        record = _stroke(record, BrushSettings(mode="Lower", strength=1.0), [(0.2, 0.5), (0.8, 0.5), (0.2, 0.5)])
    assert min(record["heights"]) == pytest.approx(MIN_LAND) and min(record["heights"]) > 0.0
    assert 0.0 in _stroke(record, BrushSettings(mode="Water"), [(0.5, 0.5)])["heights"]
    assert apply_brush(0.0, "Lower", 1.0, 1.0, 1.0, 0.0) == 0.0, "lowering water leaves it water"


def test_a_round_brush_is_round_in_the_terrains_cells():
    size = 41
    heights = _stroke(_field(size), BrushSettings(), [(0.5, 0.5)])["heights"]
    centre = size // 2
    row = [heights[centre * size + x] for x in range(size)]
    column = [heights[y * size + centre] for y in range(size)]
    assert max(row) > 0.0
    assert row == pytest.approx(column, abs=1e-12)


def test_painting_never_resamples_the_record_and_keeps_its_basin():
    size = 17
    authored = [round((x * 7 + y * 3) % 11 / 10.0, 3) for y in range(size) for x in range(size)]
    record = {"version": 1, "size": size, "heights": list(authored), "basin": [2, 2, 12]}
    after = _stroke(record, BrushSettings(), [(0.1, 0.1)])
    assert after["size"] == size and len(after["heights"]) == size * size and after["basin"] == [2, 2, 12]
    far = (size - 1) * size + (size - 1)
    assert after["heights"][far] == authored[far]
    assert record["heights"] == authored, "the stroke paints a copy"


def test_brush_settings_admit_their_own_bounds():
    settings = BrushSettings()
    assert settings.admitted("radius", 9.0).radius == RADIUS_RANGE[1]
    assert settings.admitted("radius", -1.0).radius == RADIUS_RANGE[0]
    assert 0.0 < settings.admitted("strength", 0.0).strength
    assert settings.admitted("falloff", 2.0).falloff == 1.0
    assert settings.admitted("mode", "Not A Mode") == settings
    for mode in MODES:
        assert settings.admitted("mode", mode).mode == mode
    with pytest.raises(KeyError):
        settings.admitted("colour", 1.0)
