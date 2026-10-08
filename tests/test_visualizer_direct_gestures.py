"""Direct 3D Visualizer gestures outside Edit (H5): Alt + right drag moves it, Alt + wheel resizes
it, Alt + left still orbits. The input owner admits them only on the shown 3D Visualizer in
interaction/Ctrl mode, keeps the context menu and the volume wheel out of them, and finishes each
gesture once. The custom-layout owner runs them through Edit's own session code with no edit
chrome and no input blocking, the live picture follows, and the gesture's end commits once through
Edit's Save (nothing when nothing changed); Edit never inherits one."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent

import pytest

from rendering.runtime_input import RuntimeInputOwner

pytestmark = pytest.mark.qt

ALT = Qt.KeyboardModifier.AltModifier
NONE = Qt.KeyboardModifier.NoModifier
INSIDE, OUTSIDE = QPointF(200.0, 150.0), QPointF(900.0, 700.0)


def _owner(qt_app, *, interaction=True, enabled=True):
    owner = RuntimeInputOwner(interaction_mode_provider=lambda: interaction)
    owner.set_view_orbit_enabled(enabled)
    owner.set_view_orbit_hit_test(lambda point: point.x() < 500 and point.y() < 400)
    events = []
    owner.visualizer_move_requested.connect(lambda offset, cursor: events.append(("move", offset, cursor)))
    owner.visualizer_scale_requested.connect(lambda step: events.append(("scale", step)))
    owner.visualizer_gesture_finished.connect(lambda: events.append(("finished",)))
    owner.context_menu_requested.connect(lambda _point: events.append(("menu",)))
    owner.view_orbit_requested.connect(lambda *_steps: events.append(("orbit",)))
    return owner, events


def _mouse(kind, position, button, modifiers, global_offset=QPointF(1000.0, 0.0)):
    buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else button
    return QMouseEvent(kind, position, position + global_offset, button, buttons, modifiers)


def _wheel(position, delta, modifiers, horizontal=False):
    angle = QPoint(delta, 0) if horizontal else QPoint(0, delta)
    return QWheelEvent(position, position, QPoint(), angle, Qt.MouseButton.NoButton, modifiers,
                       Qt.ScrollPhase.NoScrollPhase, False)


def test_alt_right_drag_moves_and_never_opens_the_menu(qt_app):
    owner, events = _owner(qt_app)
    assert owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, INSIDE, Qt.MouseButton.RightButton, ALT))
    assert owner.handle_mouse_move(_mouse(QEvent.Type.MouseMove, INSIDE + QPointF(30, -12), Qt.MouseButton.RightButton,
                                          ALT))
    assert owner.handle_mouse_release(_mouse(QEvent.Type.MouseButtonRelease, INSIDE + QPointF(30, -12),
                                             Qt.MouseButton.RightButton, ALT))
    assert events == [("move", QPoint(30, -12), QPoint(1230, 138)), ("finished",)]
    # Without Alt, or off the Visualizer, the right button is the context menu as before.
    events.clear()
    owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, INSIDE, Qt.MouseButton.RightButton, NONE))
    owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, OUTSIDE, Qt.MouseButton.RightButton, ALT))
    assert events == [("menu",), ("menu",)]
    # Alt + left keeps orbiting.
    events.clear()
    owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, INSIDE, Qt.MouseButton.LeftButton, ALT))
    owner.handle_mouse_move(_mouse(QEvent.Type.MouseMove, INSIDE + QPointF(8, 0), Qt.MouseButton.LeftButton, ALT))
    assert events == [("orbit",)]


def test_alt_wheel_resizes_until_alt_is_released_and_plain_wheels_pass_on(qt_app):
    owner, events = _owner(qt_app)
    assert owner.handle_wheel(_wheel(INSIDE, 120, ALT))
    assert owner.handle_wheel(_wheel(INSIDE, -120, ALT, horizontal=True))     # Qt's Alt swap
    assert events == [("scale", 120), ("scale", -120)]
    assert not owner.handle_wheel(_wheel(INSIDE, 120, NONE))                  # the volume wheel's
    assert not owner.handle_wheel(_wheel(OUTSIDE, 120, ALT))
    assert owner.handle_key_release(QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Alt, NONE))
    assert events[-1] == ("finished",) and events.count(("finished",)) == 1
    # A wheel step during a drag: one gesture, finished once, at whichever ends last.
    events.clear()
    owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, INSIDE, Qt.MouseButton.RightButton, ALT))
    owner.handle_wheel(_wheel(INSIDE, 120, ALT))
    owner.handle_mouse_release(_mouse(QEvent.Type.MouseButtonRelease, INSIDE, Qt.MouseButton.RightButton, ALT))
    assert ("finished",) not in events
    owner.handle_key_release(QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Alt, NONE))
    assert events.count(("finished",)) == 1


@pytest.mark.parametrize("case", ("not_interactive", "not_3d"))
def test_gestures_need_interaction_mode_and_a_shown_3d_visualizer(qt_app, case):
    owner, events = _owner(qt_app, interaction=case != "not_interactive", enabled=case != "not_3d")
    owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, INSIDE, Qt.MouseButton.RightButton, ALT))
    assert not owner.handle_wheel(_wheel(INSIDE, 120, ALT))
    assert ("move",) not in [event[:1] for event in events] and ("scale", 120) not in events


def test_closing_input_or_hiding_the_mode_ends_a_gesture_once(qt_app):
    owner, events = _owner(qt_app)
    owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, INSIDE, Qt.MouseButton.RightButton, ALT))
    owner.cleanup()
    assert events == [("finished",)]
    owner, events = _owner(qt_app)
    owner.handle_wheel(_wheel(INSIDE, 120, ALT))
    owner.set_view_orbit_enabled(False)
    owner.set_view_orbit_enabled(False)
    assert events == [("scale", 120), ("finished",)]


def test_a_direct_gesture_moves_and_resizes_live_and_commits_once_through_edits_save(qt_app, monkeypatch):
    from rendering.quick.custom_layout_hydration import resolve_quick_committed_geometry
    from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
    from rendering.quick.display_unit import create_quick_display_unit
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from rendering import runtime_input
    from tests.test_qtquick_custom_layout_owner import _configure_visualizer, _LiveCommitEngine, _Settings
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda _o, _n: (True, True))
    monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda _o, _n: None)
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _o, _n: None)
    suppressions = []
    monkeypatch.setattr(runtime_input, "suppress_runtime_pointer_input",
                        lambda *args, **kwargs: suppressions.append(args))
    screen = qt_app.primaryScreen()
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(
        screen=screen, screen_index=0, runtime_generation=931, scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=SharedCtrlCoordinator(), adapters=(),
    )
    visualizer = QuickDisplayVisualizerOwner(
        unit.runtime, bar_count=24, initial_mode="extruded_spectrum",
        card_shadow_kwargs={
            "background_color": (0, 0, 0, 0), "border_color": (255, 255, 255, 255),
            "border_width": 4., "corner_radius": 6., "content_inset": 14.,
            "shadow_enabled": False, "shadow_color": (0, 0, 0, 0),
            "shadow_blur": 0., "shadow_offset": (0., 0.), "shadow_spread": 0.,
            "shadow_extensions": (0., 0., 0., 0.),
        },
        engine_factory=lambda _count: _LiveCommitEngine(),
    )
    unit.attach_visualizer_owner(visualizer)
    settings = _Settings({"spotify_visualizer": {
        "enabled": True, "position": "Custom", "monitor": "1",
        "mode": "extruded_spectrum",
    }})
    reloads, config_commits = [], []
    layout = QuickCustomLayoutOwner(
        settings_manager=settings, participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (visualizer, unit), reload_request=reloads.append,
        live_config_commit=config_commits.append,             # DisplayManager's snapshot hook
    )
    scene = unit.runtime.scene_controller
    try:
        _configure_visualizer(visualizer, playing=True)
        visualizer.configure_committed_layout(local_rect=(120.0, 90.0, 480.0, 270.0), viewport_extent=(160.0, 90.0))
        identity = visualizer.bind(engine_generation=3, activation_id=5)
        visualizer._apply_resolved_presentation(visualizer._resolve_current_presentation())
        visualizer.start(interval_s=10.0)
        state = visualizer.controller.logical_tick_state
        state._mode_teardown_block_until_ready = False
        state._mode_transition_ready = True
        state._waiting_for_fresh_engine_frame = False
        state._display_bars_source_generation = 3
        state._display_bars_source_activation = 5
        assert tick_pipeline.logical_tick(state) is not None and visualizer.sync_present()
        before = tuple(scene.visualizer_item.presentation.outer_rect)

        # A click without movement writes nothing.
        assert layout.begin_direct_visualizer_gesture() and layout.is_direct and not layout.is_editing
        assert layout.finish_direct_visualizer_gesture() and not layout.is_active
        assert settings.save_calls == 0

        assert layout.begin_direct_visualizer_gesture()
        assert unit.runtime.window._custom_layout_input_blocked is False      # input stays with the gesture
        assert scene.custom_layout_overlay._model is None                     # no Edit chrome
        origin = layout.session.items()[0].current_global_rect
        cursor = QPoint(origin.center())
        assert layout.move_direct_visualizer(QPoint(40, 25), cursor + QPoint(40, 25))
        moved = scene.visualizer_item.presentation.outer_rect
        assert moved[0] == pytest.approx(before[0] + 40, abs=0.51) and moved[1] == pytest.approx(before[1] + 25,
                                                                                                 abs=0.51)
        assert layout.scale_direct_visualizer(120)                              # wheel up: larger
        assert scene.visualizer_item.presentation.outer_rect[2] > moved[2]
        working = scene.visualizer_item.presentation
        assert layout.finish_direct_visualizer_gesture()
        assert settings.save_calls == 1 and len(config_commits) == 1 and not layout.is_active
        assert reloads == [] and visualizer.render_identity is identity         # promoted live, not rebuilt
        assert suppressions == []                                               # no Edit-close input guard
        saved = resolve_quick_committed_geometry(settings.widgets, screen, "spotify_visualizer")
        assert saved is not None
        assert (saved.x, saved.y, saved.width, saved.height) == pytest.approx(tuple(working.outer_rect), abs=1.0)
        assert tick_pipeline.logical_tick(state) is not None and visualizer.sync_present()
        assert scene.visualizer_item.presentation.outer_rect == pytest.approx(working.outer_rect)

        # Edit never inherits a gesture: starting Edit commits it first.
        assert layout.begin_direct_visualizer_gesture()
        assert layout.move_direct_visualizer(QPoint(-10, 0), cursor)
        assert layout.start() and layout.is_editing and settings.save_calls == 2
        assert layout.cancel()
    finally:
        layout.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()
