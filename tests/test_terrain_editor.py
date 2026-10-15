"""Actual pointer strokes batch authoring and keep brush/history state ephemeral."""
from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtTest import QTest

import math

import pytest

from tests._invisible_windows import keep_off_screen
from ui.tabs.media.terrain_editor import (
    MIN_LAND,
    TerrainEditor,
    apply_brush,
    brush_reach,
    brush_weight,
    stroke_rate,
)


def _point(canvas, u, v):
    rect = canvas.field_rect()
    return QPoint(round(rect.left() + rect.width() * u), round(rect.bottom() - rect.height() * v))


def _stroke(canvas, start, end=None):
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, *start))
    if end is not None:
        QTest.mouseMove(canvas, _point(canvas, *end))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, *(end or start)))


def test_actual_raise_lower_flatten_water_strokes_undo_redo_and_reset(qtbot):
    blank = {"version": 1, "size": 25, "heights": [0.0] * 625}
    editor = TerrainEditor(blank)
    qtbot.addWidget(editor)
    keep_off_screen(editor).resize(600, 420)
    editor.show()
    qtbot.waitExposed(editor)
    canvas = editor.canvas
    editor.falloff.setValue(0)   # hard discs: this sequence checks exact coverage
    assert not editor.findChildren(QTimer)
    emitted = []
    editor.terrain_changed.connect(emitted.append)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, 0.5, 0.25))
    QTest.mouseMove(canvas, _point(canvas, 0.7, 0.25))
    assert not emitted
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, 0.7, 0.25))
    assert len(emitted) == 1
    raised = editor.get_heightfield()
    assert max(raised["heights"]) > 0.0
    assert sum(raised["heights"][:13 * 25]) > 0.0 and sum(raised["heights"][13 * 25:]) == 0.0
    editor.mode.setCurrentText("Lower")
    _stroke(canvas, (0.5, 0.25))
    assert len(emitted) == 2
    assert sum(editor.get_heightfield()["heights"]) < sum(raised["heights"])
    editor.mode.setCurrentText("Flatten")
    editor.flatten_height.setValue(80)
    editor.strength.setValue(50)
    before_flatten = max(editor.get_heightfield()["heights"])
    _stroke(canvas, (0.5, 0.25))
    partway = max(editor.get_heightfield()["heights"])
    assert before_flatten < partway < 0.79, "below 100% Flatten moves toward its height gradually"
    editor.strength.setValue(100)
    _stroke(canvas, (0.5, 0.25))
    assert max(editor.get_heightfield()["heights"]) == pytest.approx(0.8), "100% snaps the core"
    editor.mode.setCurrentText("Water")
    editor.radius.setValue(35)
    # Lower keeps land above water, so the whole raised area is painted back to exact water.
    _stroke(canvas, (0.4, 0.25), (0.8, 0.25))
    assert editor.get_heightfield() == blank
    before_undo = len(emitted)
    editor.undo_button.click()
    assert len(emitted) == before_undo + 1 and max(editor.get_heightfield()["heights"]) > 0.7
    editor.redo_button.click()
    assert editor.get_heightfield() == blank
    editor.mode.setCurrentText("Raise")
    _stroke(canvas, (0.5, 0.75))
    assert sum(editor.get_heightfield()["heights"][13 * 25:]) > 0.0
    editor.reset_button.click()
    assert editor.get_heightfield() == blank
    assert set(editor.get_heightfield()) == {"version", "size", "heights"}
    # Loading is silent, clears history, and leaves the authored record detached from caller mutation.
    count = len(emitted)
    editor.set_heightfield(raised)
    raised["heights"][0] = 1.0
    assert len(emitted) == count and not canvas._undo and not canvas._redo
    assert editor.get_heightfield()["heights"][0] == 0.0


def test_history_is_bounded_per_completed_stroke_and_escape_cancels(qtbot):
    blank = {"version": 1, "size": 25, "heights": [0.0] * 625}
    editor = TerrainEditor(blank)
    qtbot.addWidget(editor)
    keep_off_screen(editor).resize(600, 420)
    editor.show()
    qtbot.waitExposed(editor)
    canvas = editor.canvas
    emitted = []
    editor.terrain_changed.connect(emitted.append)
    for _ in range(canvas.HISTORY_LIMIT + 3):
        editor.mode.setCurrentText("Raise")
        _stroke(canvas, (0.5, 0.5))
        editor.mode.setCurrentText("Water")
        _stroke(canvas, (0.5, 0.5))
    assert len(canvas._undo) == canvas.HISTORY_LIMIT
    before = editor.get_heightfield()
    count = len(emitted)
    editor.mode.setCurrentText("Raise")
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, 0.5, 0.5))
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, 0.5, 0.5))
    assert editor.get_heightfield() == before and len(emitted) == count

    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, 0.5, 0.5))
    editor.hide()
    assert editor.get_heightfield() == before and len(emitted) == count


def _editor(qtbot, heights=None, size=25):
    editor = TerrainEditor({"version": 1, "size": size, "heights": heights or [0.0] * (size * size)})
    qtbot.addWidget(editor)
    keep_off_screen(editor).resize(600, 420)
    editor.show()
    qtbot.waitExposed(editor)
    return editor


def _drag(canvas, points):
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, *points[0]))
    for point in points[1:]:
        QTest.mouseMove(canvas, _point(canvas, *point))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, *points[-1]))


@pytest.mark.parametrize("mode", ["Raise", "Lower", "Flatten"])
def test_a_stroke_depends_on_its_path_not_on_mouse_speed(qtbot, mode):
    start = [0.3] * (25 * 25)
    results = []
    for steps in (1, 4, 23):
        editor = _editor(qtbot, list(start))
        editor.mode.setCurrentText(mode)
        _drag(editor.canvas, [(0.2 + 0.6 * i / steps, 0.5) for i in range(steps + 1)])
        results.append(editor.get_heightfield()["heights"])
    changed = [abs(a - b) for a, b in zip(results[0], start)]
    assert max(changed) > 0.0
    for other in results[1:]:
        # Integer pointer positions can move a dab by under a pixel; the result is otherwise the same.
        assert max(abs(a - b) for a, b in zip(results[0], other)) < 0.02 * max(changed) + 1e-9


def test_low_strength_is_gradual_and_strength_scales_smoothly(qtbot):
    assert stroke_rate(0.01) < 1e-4 < stroke_rate(0.2) < stroke_rate(0.5) < stroke_rate(1.0)
    gains = []
    for strength in (1, 25, 100):
        editor = _editor(qtbot, [0.3] * (25 * 25))
        editor.strength.setValue(strength)
        _drag(editor.canvas, [(0.3, 0.5), (0.7, 0.5)])
        gains.append(max(editor.get_heightfield()["heights"]) - 0.3)
    assert gains[0] < 0.002, "1% barely changes the land"
    assert 0.0 < gains[0] < gains[1] < gains[2]


def test_brush_profile_falls_off_softly_and_hardens_at_zero():
    distances = [i / 40 for i in range(80)]
    for falloff in (0.0, 0.3, 0.7, 1.0):
        weights = [brush_weight(d, falloff) for d in distances]
        assert all(a >= b for a, b in zip(weights, weights[1:])), "the profile only falls"
        assert brush_weight(0.0, falloff) == 1.0 and brush_weight(brush_reach(falloff) + 1e-9, falloff) == 0.0
    assert brush_weight(0.99, 0.0) == 1.0 and brush_weight(1.01, 0.0) == 0.0, "no falloff is a hard disc"
    # More falloff starts easing sooner and reaches further.
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


def test_lower_never_makes_water_and_water_stays_exact(qtbot):
    editor = _editor(qtbot, [0.05] * (25 * 25))
    editor.mode.setCurrentText("Lower")
    editor.strength.setValue(100)
    for _ in range(6):
        _drag(editor.canvas, [(0.2, 0.5), (0.8, 0.5), (0.2, 0.5)])
    heights = editor.get_heightfield()["heights"]
    assert min(heights) == pytest.approx(MIN_LAND) and min(heights) > 0.0
    editor.mode.setCurrentText("Water")
    _drag(editor.canvas, [(0.5, 0.5)])
    assert 0.0 in editor.get_heightfield()["heights"]
    assert apply_brush(0.0, "Lower", 1.0, 1.0, 1.0, 0.0) == 0.0, "lowering water leaves it water"
