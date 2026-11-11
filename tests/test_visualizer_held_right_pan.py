"""Held-right pan of the live Visualizer, as in the Studios (plan 1B.13).

The platform's own convention (menu on button-up), scoped to the one place a drag can mean something else: over a
pan-capable card (the held-left plain orbit's admission on a mode with ``scene_transform_settings``) a right press
opens nothing and arms a pending pan; travel past the system drag distance turns it into the pan through the one
capture owner; a release without that travel opens the retained menu at the release point through the same
``context_menu_requested`` route. Everywhere else the menu opens on press exactly as before.

The routing bars use the window and input owner with a recording capture and cursor (no desktop capture, no focus
change; the plain-orbit tests' pattern); the end-to-end bars use the production card (an unshown runtime, never
shown) with its real scene, owner and Settings.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtQml import QQmlComponent, QQmlEngine

from rendering.quick.input_controller import QuickInputController
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow
from tests.test_framed_scene_input import card as production_card  # noqa: F401
from tests.test_framed_scene_input import point as card_point

RIGHT = Qt.MouseButton.RightButton
LEFT = Qt.MouseButton.LeftButton
NONE = Qt.MouseButton.NoButton
NO_MODIFIER = Qt.KeyboardModifier.NoModifier
ALT = Qt.KeyboardModifier.AltModifier


@pytest.fixture
def pan_card(qt_app, monkeypatch):
    from rendering import runtime_input

    monkeypatch.setattr(runtime_input, "suppress_runtime_pointer_input", lambda *a, **k: None)
    window = QuickDisplayWindow(screen_index=0, runtime_generation=1113, screen=qt_app.primaryScreen(),
                                policy=QuickWindowPolicy(always_on_top=False))
    window.resize(400, 300)
    controller = QuickInputController(screen_index=0, runtime_generation=1113, interaction_mode_enabled=True)
    controller.set_view_orbit_enabled(True)
    controller.set_scene_transform_enabled(True, mode_id="extruded_bubble")
    window.bind_input_controller(controller)
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b"""import QtQuick
Item { width: 300; height: 200; x: 20; y: 20
    property bool cardShellEnabled: true
    property bool presentationActive: true }""", QUrl())
    card = component.create()
    assert card is not None, component.errors()
    card.setParentItem(window.contentItem())
    card.setParent(window)
    window.watch_plain_orbit_card(card)
    window.bind_plain_orbit_target(lambda p: card if card.isVisible() and card.property("cardShellEnabled")
                                   and card.contains(card.mapFromScene(p)) else None)
    capture = SimpleNamespace(acquisitions=[], releases=0)

    class Capture:
        cleanup_pending = False

        def acquire(self, rect):
            capture.acquisitions.append(QRectF(rect))

        def release(self):
            capture.releases += 1

    monkeypatch.setattr(window, "_new_plain_orbit_capture", Capture)
    cursor = SimpleNamespace(tracks_pointer_motion=False, starts=0, ends=0)

    def begin():
        cursor.starts += 1
        return True

    def end():
        cursor.ends += 1

    cursor.begin_orbit_fade, cursor.end_orbit_fade = begin, end
    window.bind_cursor_controller(cursor)
    menus, started, pans, finished, edits, moves = [], [], [], [], [], []
    controller.context_menu_requested.connect(lambda point: menus.append(QPoint(point)))
    controller.scene_pan_started.connect(lambda: started.append(1))
    controller.scene_pan_requested.connect(lambda offset: pans.append(QPoint(offset)))
    controller.scene_pan_finished.connect(lambda: finished.append(1))
    controller.custom_layout_edit_requested.connect(lambda: edits.append(1))
    controller.visualizer_move_started.connect(lambda: moves.append(1))

    def send(kind, x, y, *, button=NONE, buttons=NONE, modifiers=NO_MODIFIER):
        position = QPointF(x, y)
        event = QMouseEvent(kind, position, QPointF(window.mapToGlobal(position.toPoint())), button, buttons,
                            modifiers)
        QCoreApplication.sendEvent(window, event)
        return event

    data = SimpleNamespace(window=window, card=card, controller=controller, capture=capture, cursor=cursor,
                           menus=menus, started=started, pans=pans, finished=finished, edits=edits, moves=moves,
                           send=send, drag=QGuiApplication.styleHints().startDragDistance())
    yield data
    import shiboken6
    if shiboken6.isValid(window):
        window.cancel_plain_orbit()
    controller.close_input()
    if shiboken6.isValid(window):
        window.deleteLater()
    controller.deleteLater()
    engine.deleteLater()
    qt_app.processEvents()


def _press(c, x=200, y=130, *, modifiers=NO_MODIFIER):
    return c.send(QEvent.Type.MouseButtonPress, x, y, button=RIGHT, buttons=RIGHT, modifiers=modifiers)


def _move(c, x, y, buttons=RIGHT):
    return c.send(QEvent.Type.MouseMove, x, y, buttons=buttons)


def _release(c, x=200, y=130):
    return c.send(QEvent.Type.MouseButtonRelease, x, y, button=RIGHT)


def _global(c, x, y) -> QPoint:
    return c.window.mapToGlobal(QPoint(x, y))


@pytest.mark.qt
def test_a_click_on_the_card_opens_the_menu_once_on_release_at_the_release_point(pan_card):
    c = pan_card
    _press(c)
    assert c.menus == [] and not c.controller.input_state.context_menu_active   # nothing on press
    _move(c, 201, 130)                                                        # inside the drag distance
    _release(c, 201, 130)
    assert c.menus == [_global(c, 201, 130)]
    assert c.started == c.pans == c.finished == [] and c.capture.acquisitions == []


@pytest.mark.qt
def test_a_drag_on_the_card_pans_and_never_opens_the_menu(pan_card):
    c = pan_card
    _press(c)
    _move(c, 200 + c.drag + 4, 130)
    assert c.started == [1] and len(c.capture.acquisitions) == 1 and c.cursor.starts == 1
    _move(c, 260, 150)
    assert c.pans[-1] == QPoint(60, 20)                         # the global offset since the press
    _release(c, 260, 150)
    assert c.finished == [1] and c.capture.releases == 1 and c.cursor.ends == 1
    assert c.menus == [] and not c.controller.input_state.context_menu_active


@pytest.mark.qt
def test_a_press_on_the_card_released_off_it_pans_without_a_menu(pan_card):
    c = pan_card
    _press(c, 300, 200)
    _move(c, 390, 290)                                          # off the card (it ends at 320 x 220)
    _release(c, 390, 290)
    assert c.started == [1] and c.finished == [1] and c.menus == []


@pytest.mark.qt
def test_everywhere_else_the_menu_opens_on_press_exactly_as_before(pan_card):
    c = pan_card
    _press(c, 360, 260)                                         # the wallpaper, off the card
    assert c.menus == [_global(c, 360, 260)]
    _release(c, 360, 260)
    assert c.menus == [_global(c, 360, 260)]                    # once, on press
    c.controller.set_context_menu_active(False)
    c.controller.set_scene_transform_enabled(False, mode_id="extruded_bubble")   # a mode that cannot pan
    _press(c)
    assert len(c.menus) == 2 and c.menus[-1] == _global(c, 200, 130)
    _release(c)
    c.controller.set_context_menu_active(False)
    c.controller.set_scene_transform_enabled(True, mode_id="extruded_bubble")
    c.controller.set_view_orbit_hit_test(lambda _p: True)
    _press(c, modifiers=ALT)                                    # Alt-right keeps its own move/pan
    assert c.moves == [1] and len(c.menus) == 2
    _release(c)


@pytest.mark.qt
def test_a_second_right_press_while_the_menu_is_open_takes_todays_path(pan_card):
    c = pan_card
    _press(c)
    _release(c)
    assert len(c.menus) == 1
    c.controller.set_context_menu_active(True)                 # the menu is showing
    _press(c, 210, 140)
    assert len(c.menus) == 2 and c.menus[-1] == _global(c, 210, 140)   # on press, as before
    assert c.window._plain_orbit_pending is None
    _release(c, 210, 140)
    assert len(c.menus) == 2


@pytest.mark.qt
def test_double_right_over_the_card_still_enters_edit(pan_card):
    c = pan_card
    _press(c)
    _release(c)
    c.controller.set_context_menu_active(True)
    _press(c)
    c.send(QEvent.Type.MouseButtonDblClick, 200, 130, button=RIGHT, buttons=RIGHT)
    _release(c)
    assert c.edits == [1]


@pytest.mark.qt
@pytest.mark.parametrize("ending", ["focus", "mode", "exit", "display"])
def test_a_pan_ended_by_focus_mode_exit_or_display_loss_releases_its_capture(pan_card, ending):
    c = pan_card
    _press(c)
    _move(c, 240, 150)
    assert c.started == [1]
    if ending == "focus":
        QCoreApplication.sendEvent(c.window, QEvent(QEvent.Type.WindowDeactivate))
    elif ending == "mode":
        c.controller.set_scene_transform_enabled(True, mode_id="shockwave_grid")
    elif ending == "exit":
        c.controller.close_input()
    else:
        QCoreApplication.sendEvent(c.window, QEvent(QEvent.Type.Hide))
    assert c.capture.releases == 1 and c.cursor.ends == 1 and c.finished == [1]
    assert c.window._plain_orbit_card is None and c.window._plain_orbit_pending is None
    _release(c, 240, 150)
    assert c.menus == [] and c.finished == [1]                  # the late release opens nothing, ends nothing


@pytest.mark.qt
def test_edit_keeps_the_menu_on_press(pan_card):
    c = pan_card
    c.window.set_custom_layout_input_blocked(True)
    _press(c)
    assert c.menus == [_global(c, 200, 130)] and c.window._plain_orbit_pending is None
    _release(c)
    c.window.set_custom_layout_input_blocked(False)


@pytest.mark.qt
def test_media_center_forces_interaction_so_the_card_follows_the_same_rule(pan_card, monkeypatch):
    import core.mc as mc

    c = pan_card
    c.controller.set_interaction_mode_enabled(False)
    _press(c)
    assert c.window._plain_orbit_pending is None                # outside interaction/Ctrl: no pan admission
    _release(c)
    monkeypatch.setattr(mc, "is_mc_build", lambda: True)
    c.controller.set_interaction_mode_enabled(mc.effective_interaction_mode(False))
    _press(c)
    assert c.menus == []
    _release(c)
    assert c.menus == [_global(c, 200, 130)]


# ------------------------------------------------------------------------- end to end on the production card


def _right(card, kind, position, buttons):
    event = QMouseEvent(kind, position, QPointF(card.window.mapToGlobal(position.toPoint())),
                        RIGHT if kind != QEvent.Type.MouseMove else NONE, buttons, NO_MODIFIER)
    QCoreApplication.sendEvent(card.window, event)


@pytest.fixture
def live_card(production_card, monkeypatch):
    card = production_card
    for signal, callback in (("scene_pan_started", card.manager._start_quick_scene_pan),
                             ("scene_pan_requested", card.manager._pan_quick_visualizer_scene),
                             ("scene_pan_finished", card.manager._finish_quick_visualizer_gesture)):
        getattr(card.unit.runtime, signal).connect(
            lambda *args, cb=callback: card.manager._route_quick_visualizer_input(card.unit, cb, *args))

    class Capture:
        cleanup_pending = False

        def acquire(self, _rect):
            pass

        def release(self):
            pass

    monkeypatch.setattr(card.window, "_new_plain_orbit_capture", Capture)
    cursor = card.window._cursor_controller
    monkeypatch.setattr(cursor, "begin_orbit_fade", lambda: True)
    monkeypatch.setattr(cursor, "end_orbit_fade", lambda: None)
    return card


def _pan_keys():
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from tests.test_framed_scene_input import MODE

    _scale, pan_x, pan_y = get_visualizer_mode_descriptor(MODE).scene_transform_settings
    return pan_x, pan_y


@pytest.mark.qt
def test_the_live_pan_moves_in_the_studios_direction_and_saves_once_on_release(live_card):
    card = live_card
    pan_x, pan_y = _pan_keys()
    state = card.visualizer.controller.presentation_state
    before = (float(getattr(state, "_" + pan_x)), float(getattr(state, "_" + pan_y)))
    start = card_point(card)
    _right(card, QEvent.Type.MouseButtonPress, start, RIGHT)
    _right(card, QEvent.Type.MouseMove, start + QPointF(30, 20), RIGHT)
    after = (float(getattr(state, "_" + pan_x)), float(getattr(state, "_" + pan_y)))
    # The Studio's pan_by: pan_x -= dx / width, pan_y += dy / height (a drag right lowers pan X, down raises Y).
    assert after[0] < before[0] and after[1] > before[1]
    assert card.writes == []                                     # nothing saved while it pans
    _right(card, QEvent.Type.MouseButtonRelease, start + QPointF(30, 20), NONE)
    assert len(card.writes) == 1                                 # the live view pose's own save, once
    assert card.writes[0][pan_x] == pytest.approx(after[0]) and card.writes[0][pan_y] == pytest.approx(after[1])
    assert not card.unit.runtime.context_menu_model.property("menuVisible")


@pytest.mark.qt
def test_a_mode_switch_mid_pan_never_writes_the_old_pan_into_the_new_mode(live_card):
    card = live_card
    start = card_point(card)
    _right(card, QEvent.Type.MouseButtonPress, start, RIGHT)
    _right(card, QEvent.Type.MouseMove, start + QPointF(40, 0), RIGHT)
    card.manager._quick_scene_view_gesture = (object(),) + card.manager._quick_scene_view_gesture[1:]  # replaced
    card.unit.runtime.input_controller.set_scene_transform_enabled(True, mode_id="extruded_bubble")
    assert card.writes == []                                     # the stale gesture never saves another view
    assert card.window._plain_orbit_card is None
