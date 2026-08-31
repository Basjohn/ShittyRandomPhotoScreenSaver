"""H8 retained Visualizer middle-click semantic admission bars."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from rendering.quick.input_controller import QuickInputController
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.visualizer.middle_click_admission import (
    QuickVisualizerMiddleClickAdmission,
)
from rendering.quick.window import QuickDisplayWindow


def test_middle_click_admission_consumes_only_an_active_inside_hit() -> None:
    active = {"value": True}
    cycled: list[str] = []
    admission = QuickVisualizerMiddleClickAdmission(
        region_contains=lambda position: position == "inside",
        is_active=lambda: active["value"],
        cycle_preset=lambda: cycled.append("cycle"),
    )

    assert admission.handles_semantic_middle_click_at("outside") is False
    assert admission.handles_semantic_middle_click_at("inside") is True
    active["value"] = False
    assert admission.handles_semantic_middle_click_at("inside") is False
    assert cycled == ["cycle"]


def test_quick_window_middle_hit_preempts_neutral_input_without_side_effects(
    qt_app,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    controller = QuickInputController(screen_index=0, runtime_generation=91)
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=91,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    window.bind_input_controller(controller)
    hits: list[QPointF] = []
    routed: list[str] = []
    controller.next_image_requested.connect(lambda: routed.append("next"))
    controller.exit_requested.connect(lambda: routed.append("exit"))
    controller.context_menu_requested.connect(lambda _point: routed.append("menu"))
    window.bind_semantic_middle_click_hit_test(
        lambda position: hits.append(position) or position.x() < 50.0
    )

    def _middle_press(x: float) -> QMouseEvent:
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(x, 20.0),
            QPointF(x, 20.0),
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.MiddleButton,
            Qt.KeyboardModifier.NoModifier,
        )
        window.mousePressEvent(event)
        return event

    try:
        inside = _middle_press(25.0)
        _middle_press(75.0)
        assert inside.isAccepted() is True
        assert [point.x() for point in hits] == [25.0, 75.0]
        assert routed == []
    finally:
        window.bind_semantic_middle_click_hit_test(None)
        window.deleteLater()
        controller.deleteLater()
        qt_app.processEvents()
