"""Expanded Visualizer M3: the expanded display's ordinary widgets fade out, stay hidden, and come back exactly
(plan 01 §B.2, §D1.6 / §D2.2, §F, §H Milestone 3).

What these bars protect (operator, 7 Nov night, on Waveform Ribbon expanded: "Don't really hide/disable the widgets
underneath as you can see a double border on the topleft from another widget"):

* while the display is covered nothing of an ordinary widget shows (card, border or card shadow): the frame is
  exactly the frame of the same display with no ordinary widgets at all, the Visualizer card's own shadow and the
  OSD foreground lane included; uncovering restores the frame pixel for pixel;
* the cover is a display-local visual policy, never a lifetime signal: no family, model, provider or display lease
  is built, transferred or retired (every lifecycle entry point is spied), the retained roots are the same objects
  with the same family fade and startup gate, and 20 expand/collapse cycles through the takeover coordinator leave
  the QObject tree the same size;
* input stops at the cover edge, and a root created while covered joins covered.

The production ``DisplayScene.qml`` and ``QuickSceneController`` render into a hidden GL texture through
``QQuickRenderControl`` (``tools/expanded_visualizer_evidence.HiddenDisplayHost``); no window is ever shown.
All inputs are test-owned.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy
import pytest
from PySide6.QtCore import QElapsedTimer, QObject, QPointF, qInstallMessageHandler
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickItem

WIDTH, HEIGHT = 640, 360
FADE_S = 0.25
CHROME = {"border_width": 4.0, "corner_radius": 8.0, "content_inset": 0.0,
          "background_color": (20, 22, 26, 200), "border_color": (230, 234, 240, 255),
          "shadow_enabled": True, "shadow_color": (0, 0, 0, 150), "shadow_blur": 18.0,
          "shadow_offset": (4.0, 4.0), "shadow_spread": 0.0, "shadow_extensions": (0.0, 0.0, 4.0, 4.0)}


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


def _frame(display) -> numpy.ndarray:
    """The settled frame: unchanged over 150 ms of Qt's animation time (the OSD's canvas paints a frame late and its
    reveal animates for about half a second; renders in quick succession can repeat a frame mid-animation)."""
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


def _settle(display, until, timeout_ms: int = 4000) -> None:
    """Render until ``until`` holds (QML's fade advances on Qt's animation driver), bounded."""
    clock = QElapsedTimer()
    clock.start()
    while not until():
        display.render()
        if clock.elapsed() > timeout_ms:
            raise AssertionError("the fade did not finish before its deadline")


def _cover_opacity(display) -> float:
    return float(display.scene.scene_root.property("ordinaryWidgetsCoverOpacity"))


def _expanded_visualizer(display) -> None:
    """The display-wide Visualizer card (translucent, with its shadow), as the takeover draws it."""
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation,
        resolve_visualizer_presentation,
    )

    ordinary = resolve_visualizer_presentation(policy=get_visualizer_presentation_policy("extruded_bubble"),
                                               display_size=(WIDTH, HEIGHT), outer_origin=(30.0, 60.0), **CHROME)
    display.scene.apply_visualizer_presentation(
        resolve_expanded_visualizer_presentation(ordinary, display_size=(WIDTH, HEIGHT)), active=True)


def _osd(display):
    """The real OSD family in its foreground lane, shown (as a volume key would reveal it)."""
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.system_audio_osd import (
        RetainedSystemAudioOSDPresentation,
        SystemAudioOSDConfig,
        SystemAudioOSDPresentationModel,
    )

    model = SystemAudioOSDPresentationModel(SystemAudioOSDConfig.from_widgets_mapping({"system_audio_osd": {}}),
                                            runtime_generation=1)
    presentation = RetainedSystemAudioOSDPresentation(
        host=display.scene.ordinary_widget_host, model=model,
        geometry=OverlayWidgetGeometry(200.0, 280.0, 240.0, 56.0))
    # The host's initial fade (0, written before parenting) runs the OSD's own fade from QML's default first; then it
    # is revealed as a volume event reveals it (its inactivity deadline is not armed here), through its own fade.
    _settle(display, lambda: presentation.item.opacity() == 0.0)
    model._set_revealed(True)
    _settle(display, lambda: presentation.item.opacity() == 1.0)
    return presentation


def _cards(display) -> list:
    """Two ordinary cards with card shadows: one in the top-left corner under the expanded card's corner (the
    operator's double border), one lower right."""
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry

    host = display.scene.ordinary_widget_host
    style = OverlayCardStyle(background_color=QColor(190, 40, 40, 255), border_color=QColor(255, 255, 0, 255),
                             shadow_offset_x=4.0, shadow_offset_y=4.0, shadow_extend_right=4.0,
                             shadow_extend_bottom=4.0)
    return [
        host.create_widget(object_name="coverClock", model_identity="clock",
                           geometry=OverlayWidgetGeometry(10.0, 10.0, 200.0, 110.0), card_style=style),
        host.create_widget(object_name="coverWeather", model_identity="weather",
                           geometry=OverlayWidgetGeometry(400.0, 150.0, 200.0, 110.0), card_style=style),
    ]


@pytest.mark.qt
@pytest.mark.parametrize("fade_s", [0.0, FADE_S], ids=["snap", "fade"])
def test_covered_shows_nothing_of_the_ordinary_widgets_and_uncovering_restores_every_pixel(display, fade_s):
    scene = display.scene
    _expanded_visualizer(display)
    _osd(display)
    reference = _frame(display)                     # the display with no ordinary widgets at all
    cards = _cards(display)
    before = _frame(display)
    assert not numpy.array_equal(before, reference)  # the cards (and their shadows) do draw

    assert scene.set_ordinary_widgets_covered(True, fade_s=fade_s) is True
    if fade_s:
        display.render()
        first = display.read()
        assert _cover_opacity(display) > 0.0 and not numpy.array_equal(first, reference)   # fades, never vanishes
        _settle(display, lambda: _cover_opacity(display) == 0.0)
    covered = _frame(display)
    assert numpy.array_equal(covered, reference)    # nothing of another widget; Visualizer shadow and OSD intact
    for widget in cards:
        assert not widget.item.isVisible() and not widget.item.isEnabled()

    assert scene.set_ordinary_widgets_covered(False, fade_s=fade_s) is True
    if fade_s:
        _settle(display, lambda: _cover_opacity(display) == 1.0)
    assert numpy.array_equal(_frame(display), before)
    for widget in cards:
        assert widget.item.isVisible() and widget.item.isEnabled()


@pytest.mark.qt
def test_the_visualizer_card_shadow_and_the_osd_lane_are_outside_the_cover(display):
    scene = display.scene
    _expanded_visualizer(display)
    osd = _osd(display)
    root = scene.scene_root
    shadow = root.findChild(QQuickItem, "visualizerCardShadowUnderlay")
    lane = root.findChild(QQuickItem, "ordinaryWidgetShadowLane")
    cards = _cards(display)
    # Every ordinary card shadow sits in the lane, painted after (above) the Visualizer card's shadow.
    assert all(widget.shadow_item.parentItem() is lane for widget in cards)
    assert lane.parentItem() is shadow.parentItem()
    assert shadow.parentItem().childItems().index(shadow) < shadow.parentItem().childItems().index(lane)
    # Mid-fade every card shadow fades with its card (never left whole to vanish when the cards hide).
    scene.set_ordinary_widgets_covered(True, fade_s=1.0)
    _settle(display, lambda: 0.2 < _cover_opacity(display) < 0.8)
    for widget in cards:
        assert _effective_opacity(widget.shadow_item) == pytest.approx(_effective_opacity(widget.item))
        assert _effective_opacity(widget.item) < 0.8
    assert _effective_opacity(shadow) == _effective_opacity(osd.item) == 1.0
    scene.set_ordinary_widgets_covered(False)
    scene.set_ordinary_widgets_covered(True)
    assert shadow.isVisible() and osd.item.isVisible()
    assert _effective_opacity(shadow) == _effective_opacity(osd.item) == 1.0
    assert _effective_opacity(lane) == 0.0 and not lane.isVisible()


def _effective_opacity(item) -> float:
    value = 1.0
    while item is not None:
        value *= item.opacity()
        item = item.parentItem()
    return value


@pytest.mark.qt
def test_the_cover_is_a_visual_policy_never_a_lifetime_signal(display):
    """Family fades, the startup gate and Edit visibility are untouched; input stops at the cover edge; a root built
    while covered joins covered."""
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    scene = display.scene
    host = scene.ordinary_widget_host
    cards = _cards(display)
    cards[0].set_fade_opacity(0.6)
    host.set_startup_reveal_opacity(0.8)
    cards[1].item.setProperty("semanticDoubleClickEnabled", True)
    inside = QPointF(500.0, 200.0)
    assert host.handles_semantic_double_click_at(inside)
    owned = [(w.item.property("fadeOpacity"), w.item.property("startupRevealOpacity"), w.item.opacity())
             for w in cards]

    scene.set_ordinary_widgets_covered(True, fade_s=FADE_S)
    assert not host.handles_semantic_double_click_at(inside)        # at the edge, not at the end of the fade
    late = host.create_widget(object_name="coverLate", model_identity="steam_late",
                              geometry=OverlayWidgetGeometry(250.0, 20.0, 120.0, 80.0))
    _settle(display, lambda: _cover_opacity(display) == 0.0)
    assert not late.item.isVisible()
    assert [(w.item.property("fadeOpacity"), w.item.property("startupRevealOpacity"), w.item.opacity())
            for w in cards] == owned
    assert scene.set_ordinary_widgets_covered(True) is False        # idempotent

    scene.set_ordinary_widgets_covered(False)
    assert host.handles_semantic_double_click_at(inside) and late.item.isVisible()
    assert [(w.item.property("fadeOpacity"), w.item.property("startupRevealOpacity"), w.item.opacity())
            for w in cards] == owned


class _Owner:
    """The Visualizer owner's route as the coordinator sees it; an animated change completes on ``finish``."""

    expanded_display_fade_half_s = FADE_S

    def __init__(self) -> None:
        self.controller = SimpleNamespace(mode_id="extruded_bubble",
                                          engine=SimpleNamespace(get_activation_id=lambda: 1))
        self.is_retired = False
        self.expanded_display = False
        self.expanded_display_transition_active = False
        self._pending = None

    def set_expanded_display(self, expanded, *, animate=False, on_complete=None):
        self._pending = (bool(expanded), on_complete)
        if not animate:
            self.finish()
        return True

    def finish(self) -> None:
        pending, self._pending = self._pending, None
        if pending is not None:
            self.expanded_display = pending[0]
            if pending[1] is not None:
                pending[1]()


_LIFECYCLE = (
    ("rendering.quick.widgets.host", "OrdinaryWidgetPresentationHost",
     ("create_widget", "create_family_widget", "retire_widget", "transfer_widget_to", "retire_all")),
    ("rendering.quick.widgets.host", "RetainedOverlayWidget", ("_retire", "set_fade_opacity",
                                                               "set_startup_reveal_opacity", "set_working_visible")),
    ("rendering.quick.widgets.family_binder", "OrdinaryFamilyPresentationBinder",
     ("bind", "retire_widget", "retire_all", "transfer_presentation_to")),
    ("rendering.widget_runtime_manager", "WidgetRuntimeManager",
     ("ensure_widget_service", "retire_widget_service", "retire_all_services", "transfer_widget_service_to",
      "activate_widget", "deactivate_widget", "cleanup_widget")),
    ("rendering.quick.display_presenter", "QuickDisplayPresenter",
     ("bind_families", "retire_live_custom_layout_item", "transfer_live_custom_layout_item_to", "retire")),
)


@pytest.mark.qt
def test_twenty_expand_collapse_cycles_through_the_coordinator_change_nothing_but_the_cover(display, monkeypatch):
    """The plan's M3 exit gate on the production scene: the takeover coordinator (real reducer and actions) with the
    display manager's own cover service, 20 user expand/collapse cycles with the fade. No lifecycle entry point of
    any family, binder, runtime manager or presenter is reached, so no consumer or lease (Media, OSD, Gmail, Feeds,
    Steam) can change; the retained roots are the same objects; the QObject tree does not grow; the frame returns."""
    import importlib

    from engine.display_manager import _cover_ordinary_widgets, _publish_expand_glyph
    from widgets.spotify_visualizer.expanded_display_coordinator import (
        ExpandedDisplayCoordinator,
        ExpandedDisplayServices,
    )

    scene = display.scene
    _expanded_visualizer(display)
    _osd(display)
    _cards(display)
    host = scene.ordinary_widget_host
    roots = [(identity, host.presentation_for_model_identity(identity),
              host.presentation_for_model_identity(identity).item) for identity in host.model_identities()]
    before = _frame(display)
    calls: list[str] = []
    for module_name, class_name, methods in _LIFECYCLE:
        owner_class = getattr(importlib.import_module(module_name), class_name)
        for name in methods:
            original = getattr(owner_class, name)

            def spy(*args, _original=original, _label=f"{class_name}.{name}", **kwargs):
                calls.append(_label)
                return _original(*args, **kwargs)
            monkeypatch.setattr(owner_class, name, spy)

    owner = _Owner()
    unit = SimpleNamespace(screen_index=0, is_retired=False, runtime=SimpleNamespace(
        display_identity=SimpleNamespace(screen_key="hidden", geometry=(0, 0, WIDTH, HEIGHT)),
        scene_controller=scene))
    state = {"requested": False}
    coordinator = ExpandedDisplayCoordinator(ExpandedDisplayServices(
        admitted_owner=lambda: owner, admitted_unit=lambda: unit, requested=lambda: state["requested"],
        persist_requested=lambda value: state.update(requested=bool(value)),
        mode_capable=lambda _mode: True, edit_active=lambda: False,
        publish_glyph=_publish_expand_glyph, cover_widgets=_cover_ordinary_widgets))
    coordinator.generation_ready()

    def tree_size() -> int:
        return len(display.window.findChildren(QObject))

    def cycle() -> int:
        assert coordinator.glyph_pressed(unit, True)
        assert scene.ordinary_widgets_covered
        owner.finish()
        _settle(display, lambda: _cover_opacity(display) == 0.0)
        assert coordinator.glyph_pressed(unit, False)
        assert not scene.ordinary_widgets_covered
        owner.finish()
        _settle(display, lambda: _cover_opacity(display) == 1.0)
        return tree_size()

    # One warm-up cycle: the cover's Behavior instantiates its (deferred) NumberAnimation once, on first use.
    counts = [cycle()]
    messages: list[str] = []
    previous = qInstallMessageHandler(lambda _mode, _context, text: messages.append(text))
    try:
        counts += [cycle() for _ in range(20)]
    finally:
        qInstallMessageHandler(previous)

    assert messages == []                                     # no binding, opacity or QML warnings
    assert calls == []
    assert len(set(counts)) == 1, counts
    assert [(identity, host.presentation_for_model_identity(identity),
             host.presentation_for_model_identity(identity).item) for identity in host.model_identities()] == roots
    assert numpy.array_equal(_frame(display), before)
    assert state["requested"] is False and not scene.ordinary_widgets_covered
