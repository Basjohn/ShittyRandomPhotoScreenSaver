"""Expanded Visualizer M3, Suspension: presentation-only work under a covered display pauses and resumes exactly.

Operator (8 Nov): "I see in the logs that widgets are still doing work when they are not visible because of
fullscreen visualizer". Provider cadence and model updates keep running by design (plan 01 M3, Suspension: Media
feeds the Visualizer, backends are generation-shared, a rebuild would re-arm refresh bursts). What exists only to
draw pauses at the cover edge and resumes at the uncover edge (events, no timer or poll):

* the Clock's one-second publication: a covered Clock leaves the process-global ticker (which stops when no visible
  Clock remains); uncovering publishes the current time at once, before the lanes fade back in, then rejoins it;
* the display's refresh-edge clock (the Gmail / Reddit / Feeds / Games You Follow refresh glyph cross-fade, a
  Python-driven 240 ms animation per BUSY edge): an edge under the cover settles at once.

The production ``DisplayScene.qml`` and ``QuickSceneController`` render into a hidden GL texture through
``QQuickRenderControl`` (``tools/expanded_visualizer_evidence.HiddenDisplayHost``); no window is ever shown. The
cover is driven through the scene controller's one setter (the takeover coordinator's edge). All inputs are
test-owned; the global ticker's timer is a test stand-in (nothing is scheduled on the real ThreadManager).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy
import pytest
from PySide6.QtCore import QElapsedTimer, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

WIDTH, HEIGHT = 640, 360
FADE_S = 0.25
QML_ROOT = Path(__file__).resolve().parents[1] / "rendering" / "quick" / "qml"
ZONE = timezone(timedelta(hours=2))


@pytest.fixture
def display(qt_app):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    host = HiddenDisplayHost(WIDTH, HEIGHT, dpr=1.0)
    try:
        yield host
    finally:
        host.close()


class _TimerHandle:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    def deleteLater(self) -> None:
        pass

    def isActive(self) -> bool:
        return not self.stopped


class _ThreadManager:
    """Records the global ticker's recurring timers; the test fires ticks itself."""

    def __init__(self) -> None:
        self.handles: list[_TimerHandle] = []

    def schedule_recurring(self, **_kwargs):
        handle = _TimerHandle()
        self.handles.append(handle)
        return handle

    @property
    def running(self) -> bool:
        return any(handle.isActive() for handle in self.handles)


@pytest.fixture
def ticker():
    """The real process-global ticker, fresh for the test and reset after it."""
    from widgets.clock_ticker import GlobalClockTicker

    GlobalClockTicker.reset()
    try:
        yield GlobalClockTicker()
    finally:
        GlobalClockTicker.reset()


def _settle(display, until, timeout_ms: int = 4000) -> None:
    clock = QElapsedTimer()
    clock.start()
    while not until():
        display.render()
        if clock.elapsed() > timeout_ms:
            raise AssertionError("the scene did not settle before its deadline")


def _frame(display) -> numpy.ndarray:
    """The settled frame: unchanged over 150 ms of Qt's animation time."""
    clock = QElapsedTimer()
    clock.start()
    display.render()
    previous, since = display.read(), clock.elapsed()
    while clock.elapsed() < 6000:
        display.render()
        current = display.read()
        if not numpy.array_equal(current, previous):
            previous, since = current, clock.elapsed()
        elif clock.elapsed() - since >= 150:
            return current
    raise AssertionError("the hidden scene did not settle")


def _cover_opacity(display) -> float:
    return float(display.scene.scene_root.property("ordinaryWidgetsCoverOpacity"))


def _clock(display, now_box: list[datetime], *, identity: str = "clock"):
    """The real Clock family (model + retained presentation) on the display's production ordinary host."""
    from rendering.quick.widgets.clock import (
        ClockPresentationConfig,
        ClockPresentationModel,
        ClockPresentationStyle,
        RetainedClockPresentation,
    )
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    config = ClockPresentationConfig.from_mapping(identity, {
        "format": "24h", "show_seconds": True, "timezone": "UTC+2", "show_timezone": False,
        "show_day_of_week": False, "show_date": False, "display_mode": "digital", "font_size": 40,
        "show_background": True, "bg_color": [20, 25, 30, 255], "bg_opacity": 0.6,
        "border_color": [255, 255, 255, 255], "border_opacity": 0.8, "color": [240, 245, 250, 255]})
    model = ClockPresentationModel(
        config, ClockPresentationStyle.project(config, {
            "enabled": True, "color": [0, 0, 0, 255], "blur_radius": 18, "frame_opacity": 0.77,
            "frame_extra_offset": 0, "text_enabled": True, "soft_text_on_light_themes": False,
            "text_opacity": 0.33, "text_extra_offset": 0, "header_enabled": True, "direction": "SE"}),
        now_provider=lambda _zone: now_box[0])
    return RetainedClockPresentation(
        host=display.scene.ordinary_widget_host, model=model,
        geometry=OverlayWidgetGeometry(20.0, 20.0, 260.0, 110.0),
        display_bounds=OverlayWidgetGeometry(0.0, 0.0, float(WIDTH), float(HEIGHT)),
        display_identity="hidden")


def _shown_time(presentation) -> str:
    text = presentation.item.findChild(QQuickItem, "clockDigitalTime")
    assert text is not None
    return str(text.property("text"))


@pytest.mark.qt
def test_a_covered_clock_stops_ticking_and_uncovers_on_the_current_time(display, ticker):
    scene = display.scene
    manager = _ThreadManager()
    now = [datetime(2026, 11, 8, 5, 40, 0, tzinfo=ZONE)]
    clock = _clock(display, now)
    clock.activate(manager)
    assert manager.running and ticker.get_lifecycle_ownership_snapshot()["total"] == 1
    # Every glyph this test shows is drawn once first, so the text's glyph cache cannot differ between frames.
    for shown in (datetime(2026, 11, 8, 5, 47, 12, tzinfo=ZONE), datetime(2026, 11, 8, 5, 47, 13, tzinfo=ZONE),
                  datetime(2026, 11, 8, 5, 40, 0, tzinfo=ZONE)):
        now[0] = shown
        ticker._on_tick()
        _frame(display)
    before = _frame(display)
    assert _shown_time(clock) == "05:40:00"

    ticks: list[int] = []
    clock.model.timeChanged.connect(lambda: ticks.append(1))
    assert scene.set_ordinary_widgets_covered(True, fade_s=FADE_S) is True
    _settle(display, lambda: _cover_opacity(display) == 0.0)
    # Covered: the Clock holds no subscription and, being the only Clock, the shared one-second timer stops.
    assert clock.model.is_covered and clock.model.is_active
    assert ticker.get_lifecycle_ownership_snapshot()["total"] == 0
    assert not manager.running
    for second in range(1, 4):                      # a straggling tick (another Clock's) reaches nothing here
        now[0] = datetime(2026, 11, 8, 5, 40, second, tzinfo=ZONE)
        ticker._on_tick()
    assert ticks == [] and _shown_time(clock) == "05:40:00"

    # Uncover: the current time is published at the edge, before the lanes' first fade-in frame, then the shared
    # tick resumes (one subscription, one live timer: no burst, nothing replayed).
    now[0] = datetime(2026, 11, 8, 5, 47, 12, tzinfo=ZONE)
    assert scene.set_ordinary_widgets_covered(False, fade_s=FADE_S) is True
    assert ticks == [1] and clock.model.timeText == "05:47:12"
    _settle(display, lambda: _cover_opacity(display) > 0.0)
    assert _cover_opacity(display) < 1.0 and _shown_time(clock) == "05:47:12"   # fades back, never pops
    assert ticker.get_lifecycle_ownership_snapshot()["total"] == 1 and manager.running
    assert sum(handle.isActive() for handle in manager.handles) == 1
    now[0] = datetime(2026, 11, 8, 5, 47, 13, tzinfo=ZONE)
    ticker._on_tick()
    assert ticks == [1, 1] and _shown_time(clock) == "05:47:13"

    # The same Clock, at the time it showed before the cover, draws exactly what it drew then.
    _settle(display, lambda: _cover_opacity(display) == 1.0)
    now[0] = datetime(2026, 11, 8, 5, 40, 0, tzinfo=ZONE)
    ticker._on_tick()
    assert numpy.array_equal(_frame(display), before)
    assert clock.retire() is True
    assert ticker.get_lifecycle_ownership_snapshot()["total"] == 0


@pytest.mark.qt
def test_a_clock_built_or_moved_under_the_cover_joins_it_paused(display, ticker, qt_app):
    """A root built while covered (a Settings generation restored covered before reveal) shows the current time
    but never subscribes; a Clock moved onto a covered display pauses, and off it resumes."""
    from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost

    scene = display.scene
    manager = _ThreadManager()
    now = [datetime(2026, 11, 8, 5, 40, 0, tzinfo=ZONE)]
    assert scene.set_ordinary_widgets_covered(True) is True
    late = _clock(display, now, identity="clock2")
    late.activate(manager)
    assert late.model.is_covered and late.model.timeText == "05:40:00"
    assert ticker.get_lifecycle_ownership_snapshot()["total"] == 0 and not manager.running
    assert scene.set_ordinary_widgets_covered(False) is True
    assert ticker.get_lifecycle_ownership_snapshot()["total"] == 1 and manager.running

    # A second display's ordinary host (same engine, as displays share it), covered: a CUSTOM display move.
    root = scene.scene_root
    lanes = [QQuickItem(), QQuickItem()]
    for lane in lanes:
        lane.setParentItem(root)
    other = OrdinaryWidgetPresentationHost(
        host_item=lanes[0], shadow_host_item=lanes[1], context=QQmlEngine.contextForObject(root),
        create_overlay_item=display.factory.create_overlay_widget,
        create_shadow_item=display.factory.create_overlay_card_shadow,
        create_family_item=display.factory.create_ordinary_widget_family)
    try:
        assert other.set_ordinary_widgets_covered(True) is True
        host = scene.ordinary_widget_host
        widget = host.presentation_for_model_identity("clock2")
        assert host.transfer_widget_to(widget, other) is True
        assert late.model.is_covered and ticker.get_lifecycle_ownership_snapshot()["total"] == 0
        assert other.transfer_widget_to(widget, host) is True
        assert not late.model.is_covered and ticker.get_lifecycle_ownership_snapshot()["total"] == 1
    finally:
        late.retire()
        other.retire_all()
        for lane in lanes:
            lane.setParentItem(None)
            lane.deleteLater()
        qt_app.processEvents()


def _refresh_glyph(display):
    """The production ``RefreshStateGlyph.qml`` in the covered lane, joined to the display's refresh-edge clock."""
    engine = QQmlEngine.contextForObject(display.scene.scene_root).engine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_ROOT / "RefreshStateGlyph.qml")))
    glyph = component.createWithInitialProperties(
        {"transitionClock": display.scene.ordinary_widget_host.refresh_transition_clock, "width": 24, "height": 24},
        QQmlEngine.contextForObject(display.scene.scene_root))
    assert glyph is not None, component.errors()
    lane = display.scene.scene_root.findChild(QQuickItem, "ordinaryWidgetHost")
    glyph.setParentItem(lane)
    glyph.setParent(lane)
    return glyph


@pytest.mark.qt
def test_refresh_edges_under_the_cover_settle_at_once_and_animate_again_after(display):
    scene = display.scene
    clock = scene.ordinary_widget_host.refresh_transition_clock
    glyph = _refresh_glyph(display)
    phases: list[float] = []
    clock.phaseChanged.connect(lambda: phases.append(clock.phase))

    glyph.setProperty("busy", True)                  # visible: the edge cross-fades over the clock's epoch
    assert clock.active and float(glyph.property("transitionProgress")) < 1.0
    _settle(display, lambda: not clock.active)
    assert float(glyph.property("transitionProgress")) == 1.0 and len(phases) > 2

    scene.set_ordinary_widgets_covered(True, fade_s=FADE_S)
    _settle(display, lambda: _cover_opacity(display) == 0.0)
    phases.clear()
    epoch = clock.epoch
    for busy in (False, True, False):               # e.g. a Gmail or Reddit refresh while covered
        glyph.setProperty("busy", busy)
        assert not clock.active and float(glyph.property("transitionProgress")) == 1.0
    display.render()
    assert phases == [] and clock.epoch == epoch     # no animation epoch, no per-frame Python

    scene.set_ordinary_widgets_covered(False, fade_s=FADE_S)
    # The glyph shows its current (idle) state as the lane fades back in; nothing replays.
    assert not clock.active and float(glyph.property("transitionProgress")) == 1.0
    glyph.setProperty("busy", True)
    assert clock.active and clock.epoch == epoch + 1
    _settle(display, lambda: not clock.active)
    glyph.setParentItem(None)
    glyph.setParent(None)
    glyph.deleteLater()
