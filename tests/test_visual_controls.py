"""Shared visual Settings controls (``ui/widgets/visual_controls.py``) and their spec types
(``Range``, ``Triangle``, ``Direction`` in ``core/settings/visualizer_mode_settings.py``): stored values are
repaired into range; real mouse and keyboard gestures move the value; each gesture or keyboard step saves once;
the spec builder builds, loads and collects them. Widgets are never shown on screen."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QVBoxLayout, QWidget

from core.settings.visualizer_mode_settings import Bucket, Direction, ModeSettings, Range, Triangle
from ui.widgets.visual_controls import DirectionMapper, RangeSlider, TriangleMapper

pytestmark = pytest.mark.qt


# --- spec admission -------------------------------------------------------------------------------------------

def test_spec_types_repair_stored_values_into_their_range():
    span = Range("k", "Span:", 1.0, 50.0, integer=True, scale=1)
    assert span.admit([30, 3], [1, 2]) == [3, 30]                  # ordered
    assert span.admit([-5, 99], [1, 2]) == [1, 50]                 # clamped
    assert span.admit("junk", [5, 9]) == [5, 9]                    # unreadable: the default
    assert span.text(span.positions([3, 30])) == "3 – 30"
    shares = Triangle("t", "Mix:", ("Fuse", "Pop", "Bounce"))
    assert shares.admit([2, 1, 1], [1, 1, 1]) == [0.5, 0.25, 0.25]  # normalised
    assert shares.admit([-1, 1, 1], [1, 0, 0]) == [1.0, 0.0, 0.0]   # a negative share is not a mix
    assert shares.text([0.5, 0.3, 0.2]) == "Fuse 50% · Pop 30% · Bounce 20%"
    direction = Direction("d", "Dir:", 0.0, 90.0)
    assert direction.admit([200, 120], [0, 45]) == [-160.0, 90.0]  # around wraps, height clamps
    assert direction.admit(None, [10, 45]) == [10.0, 45.0]


# --- widgets ----------------------------------------------------------------------------------------------------

class _Recorder:
    def __init__(self, widget):
        self.changed, self.committed = [], []
        widget.valueChanged.connect(self.changed.append)
        widget.valueCommitted.connect(self.committed.append)


def _point(p: QPointF) -> QPoint:
    return QPoint(round(p.x()), round(p.y()))


def test_range_slider_drags_one_handle_never_past_the_other_and_commits_once(qt_app):
    slider = RangeSlider(0, 100)
    slider.resize(216, 34)
    slider.setValue((20, 60))
    record = _Recorder(slider)
    low = _point(slider.handle_centre(0))
    QTest.mousePress(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, low)
    for x in range(low.x(), 210, 10):                             # drag the low handle far past the high one
        QTest.mouseMove(slider, QPoint(x, low.y()))
    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(210, low.y()))
    assert slider.value() == (60, 60)                              # stopped at the high handle
    assert len(record.changed) > 1 and record.committed == [(60, 60)]
    # Stacked handles: the drag's direction picks which one moves.
    QTest.mousePress(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _point(slider.handle_centre(1)))
    QTest.mouseMove(slider, QPoint(_point(slider.handle_centre(1)).x() + 40, low.y()))
    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton)
    assert slider.value()[0] == 60 and slider.value()[1] > 60


def test_range_slider_keyboard_moves_the_active_handle_tab_switches_and_wheel_does_nothing(qt_app):
    slider = RangeSlider(0, 100)
    slider.resize(216, 34)
    slider.setValue((20, 60))
    record = _Recorder(slider)
    QTest.keyClick(slider, Qt.Key.Key_Right)
    assert slider.value() == (21, 60) and record.committed == [(21, 60)]     # each step saves
    QTest.keyClick(slider, Qt.Key.Key_Tab)                                    # Tab: to the high handle
    QTest.keyClick(slider, Qt.Key.Key_End)
    assert slider.value() == (21, 100)
    QTest.keyClick(slider, Qt.Key.Key_PageDown)
    assert slider.value() == (21, 90)
    wheel = QWheelEvent(QPointF(100, 17), QPointF(100, 17), QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    slider.wheelEvent(wheel)
    assert slider.value() == (21, 90) and not wheel.isAccepted()


def test_triangle_mapper_places_shares_snaps_to_corners_and_clamps_outside(qt_app):
    mapper = TriangleMapper(("Fuse", "Pop", "Bounce"))
    mapper.resize(mapper.sizeHint())
    record = _Recorder(mapper)
    top, left, right = mapper.vertices()
    QTest.mousePress(mapper, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _point(top) + QPoint(2, 3))
    assert mapper.value() == (1.0, 0.0, 0.0)                      # near a corner: all of it
    QTest.mouseMove(mapper, QPoint(2, 2))                         # far outside: the nearest edge point
    QTest.mouseRelease(mapper, Qt.MouseButton.LeftButton)
    shares = mapper.value()
    assert all(s >= 0.0 for s in shares) and sum(shares) == pytest.approx(1.0) and shares[2] == pytest.approx(0.0)
    assert len(record.committed) == 1
    mid = QPointF((top.x() + left.x() + right.x()) / 3, (top.y() + left.y() + right.y()) / 3)
    mapper.setValue((0.2, 0.2, 0.6))
    QTest.mouseClick(mapper, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _point(mid))
    assert mapper.value() == pytest.approx((1 / 3, 1 / 3, 1 / 3))  # snaps to the even mix
    QTest.keyClick(mapper, Qt.Key.Key_Right)
    assert mapper.value()[2] > 1 / 3 and len(record.committed) == 3


def test_direction_mapper_reads_around_from_the_angle_and_height_from_the_radius(qt_app):
    mapper = DirectionMapper((0.0, 90.0), centre_text="Overhead", marker="light")
    mapper.resize(mapper.sizeHint())
    centre, radius = mapper.disc()
    QTest.mouseClick(mapper, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     _point(QPointF(centre.x() + radius, centre.y())))
    around, height = mapper.value()
    assert around == pytest.approx(90.0) and height == pytest.approx(0.0, abs=1.0)    # right rim: 90, horizon
    QTest.mouseClick(mapper, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     _point(QPointF(centre.x() + radius * 0.5 * 0.71, centre.y() - radius * 0.5 * 0.70)))
    around, height = mapper.value()
    assert around == pytest.approx(45.0) and height == pytest.approx(45.0, abs=2.0)   # snapped onto the spoke
    QTest.mouseClick(mapper, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _point(centre))
    assert mapper.value()[1] == 90.0                                                    # centre: overhead
    QTest.keyClick(mapper, Qt.Key.Key_Down)
    QTest.keyClick(mapper, Qt.Key.Key_Left)
    assert mapper.value() == (pytest.approx(40.0), 85.0)
    mapper.setValue((190.0, 200.0))
    assert mapper.value() == (pytest.approx(-170.0), 90.0)


# --- spec builder ------------------------------------------------------------------------------------------------

_DEFAULTS = {"t_span": [3, 30], "t_mix": [0.5, 0.3, 0.2], "t_flow": [35.0, 10.0]}
_SPEC = ModeSettings("t_mode", (Bucket("b", "B"),), (
    Range("t_span", "Span:", 1.0, 50.0, bucket="b", scale=1, integer=True),
    Triangle("t_mix", "Collision:", ("Fuse", "Pop", "Bounce"), bucket="b"),
    Direction("t_flow", "Stream Direction:", -90.0, 90.0, centre_text="Into Scene", bucket="b"),
))


def _tab():
    saves = []
    tab = SimpleNamespace(_widget_default=lambda section, key: _DEFAULTS[key], _save_settings=lambda *a: saves.append(a),
                          _force_visualizer_preset_to_custom=lambda: None)
    return tab, saves


def test_the_spec_builder_builds_loads_collects_and_saves_once_per_gesture(qt_app, monkeypatch):
    import ui.tabs.media.spec_mode_builder as builder

    monkeypatch.setattr(builder, "require_mode_settings", lambda mode_id: _SPEC)
    tab, saves = _tab()
    host = QWidget()
    layout = QVBoxLayout(host)
    for control in _SPEC.controls:
        builder._build_control(tab, layout, control)
    assert isinstance(tab.t_span, RangeSlider) and isinstance(tab.t_mix, TriangleMapper)
    assert isinstance(tab.t_flow, DirectionMapper)
    assert builder.collect_spec_mode_settings(tab, "t_mode") == {
        "t_span": [3, 30], "t_mix": [0.5, 0.3, 0.2], "t_flow": [35.0, 10.0]}
    # Loading shows (repaired) values without saving and updates the value labels.
    builder.load_spec_mode_settings(tab, "t_mode", {"t_span": [40, 10], "t_mix": [1, 1, 2], "t_flow": [-200, 5]})
    assert saves == []
    assert builder.collect_spec_mode_settings(tab, "t_mode") == {
        "t_span": [10, 40], "t_mix": [0.25, 0.25, 0.5], "t_flow": [160.0, 5.0]}
    assert tab.t_span_label.text() == "10 – 40"
    # A drag saves once, at release; the label follows every move.
    tab.t_span.resize(216, 34)
    start = _point(tab.t_span.handle_centre(1))
    QTest.mousePress(tab.t_span, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for dx in (10, 20, 30):
        QTest.mouseMove(tab.t_span, start + QPoint(dx, 0))
    assert saves == []
    QTest.mouseRelease(tab.t_span, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start + QPoint(30, 0))
    assert len(saves) == 1
    low, high = builder._current_value(tab, _SPEC.control("t_span"))
    assert tab.t_span_label.text() == f"{low} – {high}" and high > 40


def test_a_collapsed_height_range_is_a_plain_angle_dial(qt_app):
    dial = DirectionMapper((0.0, 0.0))
    dial.resize(dial.sizeHint())
    centre, radius = dial.disc()
    QTest.mouseClick(dial, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     _point(QPointF(centre.x() - radius * 0.2, centre.y())))      # near the middle still reads the angle
    assert dial.value() == (pytest.approx(-90.0), 0.0)
    assert Direction("g", "Gradient:", 0.0, 0.0).text([45, 30]) == "45°"
