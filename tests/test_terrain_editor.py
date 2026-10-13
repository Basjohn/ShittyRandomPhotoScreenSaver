"""Actual pointer strokes batch authoring and keep brush/history state ephemeral."""
from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtTest import QTest

from tests._invisible_windows import keep_off_screen
from ui.tabs.media.terrain_editor import TerrainEditor


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
    _stroke(canvas, (0.5, 0.25))
    assert max(editor.get_heightfield()["heights"]) > 0.7
    editor.mode.setCurrentText("Water")
    editor.radius.setValue(35)
    _stroke(canvas, (0.6, 0.25))
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
