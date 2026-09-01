"""Phase B gates for shared runtime input policy and Quick event ownership."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QKeyEvent

from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
from rendering.quick.input_controller import QuickInputController
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.runtime_input import (
    RuntimeInputOwner,
    clear_runtime_pointer_input_suppression,
    suppress_runtime_pointer_input,
)


ROOT = Path(__file__).resolve().parents[1]


def _key_press(key: Qt.Key, text: str = "") -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyPress,
        key,
        Qt.KeyboardModifier.NoModifier,
        text,
    )


def _key_release(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyRelease,
        key,
        Qt.KeyboardModifier.NoModifier,
    )


def test_quick_input_uses_the_single_neutral_policy_owner():
    assert issubclass(QuickInputController, RuntimeInputOwner)

    neutral_source = (ROOT / "rendering" / "runtime_input.py").read_text(
        encoding="utf-8"
    )
    quick_source = (
        ROOT / "rendering" / "quick" / "input_controller.py"
    ).read_text(encoding="utf-8")
    window_source = (ROOT / "rendering" / "quick" / "window.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (ROOT / "rendering" / "quick" / "runtime.py").read_text(
        encoding="utf-8"
    )

    assert "def handle_key_press(" in neutral_source
    assert "def handle_mouse_move(" in neutral_source
    assert "RuntimeInputOwner" in quick_source
    assert "bind_input_controller" in window_source
    compact_runtime_source = "".join(runtime_source.split())
    assert (
        "self._input.input_state_changed.connect(self._scene.apply_input_state)"
        in compact_runtime_source
    )
    for event_method in (
        "keyPressEvent",
        "keyReleaseEvent",
        "mousePressEvent",
        "mouseMoveEvent",
        "mouseReleaseEvent",
        "mouseDoubleClickEvent",
    ):
        assert f"super().{event_method}(event)" in window_source
    for signal_name in (
        "exit_requested",
        "previous_requested",
        "next_requested",
        "cycle_transition_requested",
        "settings_requested",
        "play_pause_requested",
        "home_play_pause_requested",
        "previous_track_requested",
        "next_track_requested",
        "slider_volume_up_requested",
        "slider_volume_down_requested",
        "global_volume_up_requested",
        "global_volume_down_requested",
        "global_mute_toggle_requested",
        "context_menu_requested",
        "layout_slot_load_requested",
        "layout_slot_save_requested",
    ):
        assert f"{signal_name} = Signal(" in runtime_source
        input_signal_name = {
            "previous_requested": "previous_image_requested",
            "next_requested": "next_image_requested",
        }.get(signal_name, signal_name)
        assert (
            f"self._input.{input_signal_name}.connect(self.{signal_name}.emit)"
            in compact_runtime_source
        )
    for forbidden in (
        "QtWidgets",
        "QWidget",
        "DisplayWidget",
        "WidgetManager",
        "SettingsManager",
    ):
        assert forbidden not in quick_source
        assert forbidden not in window_source
    assert not (ROOT / "rendering" / "input_handler.py").exists()


def test_every_retained_double_click_owner_declares_fallback_admission() -> None:
    qml_root = ROOT / "rendering" / "quick" / "qml"
    expected = {
        "AbandonmentIssuesPresentation.qml": (
            "semanticDoubleClickEnabled: abandonmentModel.interactionEnabled",
            "enabled: abandonmentRoot.abandonmentModel.interactionEnabled",
        ),
        "AchievementPulsePresentation.qml": (
            "semanticDoubleClickEnabled: achievementModel.interactionEnabled",
            "enabled: achievementRoot.achievementModel.interactionEnabled",
        ),
        "ClockPresentation.qml": ("semanticDoubleClickEnabled: true",),
        "GmailPresentation.qml": (
            "semanticDoubleClickEnabled: gmailModel.interactionEnabled",
            "enabled: gmailRoot.gmailModel.interactionEnabled",
        ),
        "MediaPresentation.qml": ("semanticDoubleClickEnabled: true",),
        "WeatherPresentation.qml": (
            'semanticDoubleClickEnabled: weatherModel.viewState !== "missing"',
            'enabled: weatherRoot.weatherModel.viewState !== "missing"',
        ),
    }
    actual = {
        path.name
        for path in qml_root.glob("*.qml")
        if "onDoubleTapped" in path.read_text(encoding="utf-8")
    }
    assert actual == set(expected)
    for filename, markers in expected.items():
        source = (qml_root / filename).read_text(encoding="utf-8")
        assert all(marker in source for marker in markers)
    assert "property bool semanticDoubleClickEnabled: false" in (
        qml_root / "OverlayWidget.qml"
    ).read_text(encoding="utf-8")


def test_runtime_input_state_reaches_retained_presenters_without_recreation(
    qt_app,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=37,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    try:
        host = runtime.scene_controller.ordinary_widget_host
        widget = host.create_widget(
            geometry=OverlayWidgetGeometry(5.0, 6.0, 120.0, 70.0),
        )
        item = widget.item
        received = []
        host.set_widget_input_state_handler(widget, received.append)

        assert len(received) == 1
        assert received[-1].screen_index == 0
        assert received[-1].runtime_generation == 37
        assert received[-1].ctrl_held is False

        runtime.input_controller.set_ctrl_held(True)

        assert widget.item is item
        assert received[-1].screen_index == 0
        assert received[-1].runtime_generation == 37
        assert received[-1].ctrl_held is True
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


def test_quick_window_forwards_hotkeys_to_generation_zero_owner(qt_app):
    screen = qt_app.primaryScreen()
    assert screen is not None
    controller = QuickInputController(
        screen_index=0,
        runtime_generation=0,
    )
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=0,
        screen=screen,
        policy=QuickWindowPolicy(
            accepts_focus=False,
            blank_cursor=False,
        ),
    )
    window.bind_input_controller(controller)

    routed: list[str] = []
    controller.previous_image_requested.connect(lambda: routed.append("previous"))
    controller.next_image_requested.connect(lambda: routed.append("next"))
    controller.cycle_transition_requested.connect(lambda: routed.append("cycle"))
    controller.settings_requested.connect(lambda: routed.append("settings"))
    controller.exit_requested.connect(lambda: routed.append("exit"))

    for key, text in (
        (Qt.Key.Key_Z, "z"),
        (Qt.Key.Key_X, "x"),
        (Qt.Key.Key_C, "c"),
        (Qt.Key.Key_S, "s"),
    ):
        event = _key_press(key, text)
        QCoreApplication.sendEvent(window, event)
        assert event.isAccepted() is True

    assert routed == ["previous", "next", "cycle", "settings"]
    assert controller.input_state.runtime_generation == 0
    assert window.describe_window_state()["input_controller_bound"] is True

    control_press = _key_press(Qt.Key.Key_Control)
    QCoreApplication.sendEvent(window, control_press)
    assert controller.input_state.ctrl_held is True
    QCoreApplication.sendEvent(window, _key_press(Qt.Key.Key_A, "a"))
    assert routed == ["previous", "next", "cycle", "settings"]

    QCoreApplication.sendEvent(window, _key_release(Qt.Key.Key_Control))
    assert controller.input_state.ctrl_held is False
    QCoreApplication.sendEvent(window, _key_press(Qt.Key.Key_A, "a"))
    assert routed[-1] == "exit"
    assert controller.input_state.exiting is True

    window.deleteLater()
    controller.deleteLater()


def test_closed_quick_input_consumes_stale_events_without_emitting():
    controller = QuickInputController(
        screen_index=2,
        runtime_generation=0,
    )
    routed: list[str] = []
    controller.next_image_requested.connect(lambda: routed.append("next"))

    assert controller.close_input() is True
    assert controller.input_state.admission_open is False
    assert controller.handle_key_press(_key_press(Qt.Key.Key_X, "x")) is True
    assert routed == []
    assert controller.close_input() is False


def test_replacement_pointer_guard_suppresses_quick_double_click_route():
    controller = QuickInputController(
        screen_index=2,
        runtime_generation=1,
    )
    routed: list[str] = []
    controller.next_image_requested.connect(lambda: routed.append("next"))

    try:
        suppress_runtime_pointer_input(500, reason="test_replacement")
        assert controller.handle_mouse_double_click(object()) is True
        assert routed == []
    finally:
        clear_runtime_pointer_input_suppression()


def test_ctrl_state_is_not_stuck_when_global_clears_after_focus_moves():
    # G8 focus invariant: when focus has moved to another display and the shared
    # coordinator clears Ctrl (the physical release lands on the other display),
    # this display must follow the authoritative global clear, never staying
    # stuck on a stale local Ctrl-held that it never received a release for.
    coord = SharedCtrlCoordinator()
    key_a = (0, 0)
    display_a = QuickInputController(
        screen_index=0,
        runtime_generation=0,
        ctrl_state_publisher=coord.publisher_for(key_a),
    )
    coord.subscribe(key_a, display_a.set_shared_ctrl_held)

    assert display_a.handle_key_press(_key_press(Qt.Key.Key_Control)) is True
    assert coord.is_held() is True
    assert display_a.is_ctrl_mode_active() is True

    # Focus moved to display B; the physical release landed there and the shared
    # coordinator broadcasts the authoritative global clear to this display,
    # which never received its own key release.
    display_a.set_shared_ctrl_held(False)

    assert display_a.is_ctrl_mode_active() is False
    assert display_a.input_state.ctrl_held is False


def test_quick_input_uses_injected_cross_display_ctrl_state():
    # Event-driven cross-display Ctrl: each display publishes only its own
    # contribution and the coordinator broadcasts the authoritative global OR to
    # every subscribed display, so a peer that never saw the key press still
    # observes Ctrl-held and does not exit on an ordinary key.
    coord = SharedCtrlCoordinator()
    key_owner = (0, 0)
    key_peer = (0, 1)
    owner = QuickInputController(
        screen_index=0,
        runtime_generation=0,
        ctrl_state_publisher=coord.publisher_for(key_owner),
    )
    peer = QuickInputController(
        screen_index=1,
        runtime_generation=0,
        ctrl_state_publisher=coord.publisher_for(key_peer),
    )
    coord.subscribe(key_owner, owner.set_shared_ctrl_held)
    coord.subscribe(key_peer, peer.set_shared_ctrl_held)
    peer_exits: list[bool] = []
    peer.exit_requested.connect(lambda: peer_exits.append(True))

    assert owner.handle_key_press(_key_press(Qt.Key.Key_Control)) is True
    assert coord.is_held() is True
    assert peer.handle_key_press(_key_press(Qt.Key.Key_A, "a")) is False
    assert peer.input_state.ctrl_held is True
    assert peer_exits == []

    assert owner.handle_key_release(_key_release(Qt.Key.Key_Control)) is True
    assert coord.is_held() is False
    assert peer.handle_key_press(_key_press(Qt.Key.Key_A, "a")) is True
    assert peer_exits == [True]
