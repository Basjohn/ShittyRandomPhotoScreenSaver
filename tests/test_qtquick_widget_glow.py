"""Widget feedback crosses real input -> host -> QML without owning actions."""
from dataclasses import replace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem

from rendering.quick.bootstrap import quick_qml_root
from rendering.quick.input_controller import QuickInputController
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickInputState, QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.window import QuickDisplayWindow


@pytest.fixture
def glow_scene(qt_app):
    factory = QuickSceneFactory()
    window = QuickDisplayWindow(
        screen_index=0, runtime_generation=0, screen=qt_app.primaryScreen(),
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    window.setGeometry(0, 0, 400, 300)
    scene = QuickSceneController(window=window, factory=factory)
    scene.scene_root.setWidth(400)
    scene.scene_root.setHeight(300)
    controller = QuickInputController(
        screen_index=0, runtime_generation=0, interaction_mode_enabled=True,
    )
    window.bind_input_controller(controller)
    controller.input_state_changed.connect(scene.apply_input_state)
    controller.widget_glow_pressed.connect(scene.apply_widget_glow_press)
    scene.apply_input_state(controller.input_state)
    yield scene, controller, window
    scene.quiesce_for_retirement()
    controller.close_input()
    window.deleteLater()
    controller.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


def _widget(scene):
    return scene.ordinary_widget_host.create_widget(
        geometry=OverlayWidgetGeometry(40, 40, 220, 150), fade_opacity=1.0,
    )


def _glow(item):
    return item.findChild(QQuickItem, "widgetInteractionGlowLoader").property("item")


def test_input_options_are_event_cached_idempotent_and_closed_at_retirement(qt_app):
    controller = QuickInputController(screen_index=0, runtime_generation=0)
    changes = []
    controller.input_state_changed.connect(changes.append)
    options = dict(
        on_hover=True, on_click=False, intensity=0.42, distance=31.0,
        color=(7, 33, 98, 128),
    )
    assert controller.configure_widget_glow(**options)
    assert not controller.configure_widget_glow(**options)
    assert len(changes) == 1
    assert controller.input_state.widget_glow_intensity == pytest.approx(0.42)
    assert controller.input_state.widget_glow_distance == pytest.approx(31.0)
    assert controller.input_state.widget_glow_color == (7, 33, 98, 128)
    controller.close_input()
    assert not controller.configure_widget_glow(**options)
    controller.deleteLater()


def test_late_adoption_gating_generation_and_retirement(glow_scene, qt_app):
    scene, controller, _ = glow_scene
    dormant = _widget(scene)
    assert _glow(dormant.item) is None
    controller.configure_widget_glow(on_hover=True, on_click=True, intensity=0.5, color=(1, 2, 3, 128))
    late = _widget(scene)
    for widget in (dormant, late):
        assert widget.item.property("widgetGlowAdmitted")
        assert widget.item.property("widgetGlowColor") == QColor(1, 2, 3, 128)
        assert widget.item.property("widgetGlowIntensity") == pytest.approx(0.5)
        assert _glow(widget.item) is not None
    wrong = replace(controller.input_state, runtime_generation=1, widget_glow_on_hover=False)
    assert not scene.apply_input_state(wrong)
    assert late.item.property("widgetGlowOnHover")

    controller.set_context_menu_active(True)
    assert _glow(late.item) is None
    controller.set_context_menu_active(False)
    assert _glow(late.item) is not None
    controller.set_interaction_mode_enabled(False)
    assert _glow(late.item) is None
    controller.set_shared_ctrl_held(True)
    assert _glow(late.item) is not None
    controller.configure_widget_glow(
        on_hover=True, on_click=True, intensity=0.0, color=(1, 2, 3, 128)
    )
    assert _glow(late.item) is None
    controller.configure_widget_glow(
        on_hover=True, on_click=True, intensity=0.5, color=(1, 2, 3, 128)
    )
    assert _glow(late.item) is not None
    late.set_working_visible(False)
    assert _glow(late.item) is None
    late.set_working_visible(True)
    assert _glow(late.item) is not None
    controller.close_input()
    assert _glow(late.item) is None
    late.retire()
    assert late.is_retired


def test_transfer_uses_target_input_policy(glow_scene, qt_app):
    scene, controller, _ = glow_scene
    controller.configure_widget_glow(on_hover=True, on_click=True, intensity=1.0, color=(1, 2, 3, 255))
    widget = _widget(scene)
    factory = QuickSceneFactory()
    window = QuickDisplayWindow(
        screen_index=1, runtime_generation=0, screen=qt_app.primaryScreen(),
        policy=QuickWindowPolicy(always_on_top=False),
    )
    target = QuickSceneController(window=window, factory=factory)
    try:
        target.apply_input_state(QuickInputState(screen_index=1, runtime_generation=0))
        scene.ordinary_widget_host.transfer_widget_to(widget, target.ordinary_widget_host)
        assert not widget.item.property("widgetGlowAdmitted")
        assert _glow(widget.item) is None
    finally:
        target.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


def _mouse(window, kind, x, y, button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.NoButton):
    local = QPointF(x, y)
    event = QMouseEvent(
        kind, local, QPointF(window.mapToGlobal(local.toPoint())), button, buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QCoreApplication.sendEvent(window, event)


def test_passive_click_reaches_existing_action_and_holds_until_target_changes(
    glow_scene, qt_app, qtbot
):
    scene, controller, window = glow_scene
    controller.configure_widget_glow(
        on_hover=True,
        on_click=True,
        intensity=0.6,
        color=(130, 205, 255, 255),
    )
    widget = _widget(scene)
    # Real family-style child MouseArea competes with the feedback observer.
    engine = scene.ordinary_widget_host._context.engine()
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
        MouseArea {
            property int actionCount: 0
            width: 220; height: 150
            onClicked: actionCount += 1
        }''', QUrl.fromLocalFile(str(quick_qml_root() / "GlowActionProbe.qml")))
    assert component.status() == QQmlComponent.Status.Ready, component.errors()
    action = component.create()
    action.setParentItem(widget.item.findChild(QQuickItem, "overlayWidgetCard"))
    action.setParent(widget.item)
    qt_app.processEvents()
    _mouse(window, QEvent.Type.MouseMove, 80, 80)
    _mouse(window, QEvent.Type.MouseButtonPress, 80, 80, Qt.LeftButton, Qt.LeftButton)
    _mouse(window, QEvent.Type.MouseButtonRelease, 80, 80, Qt.LeftButton)
    glow = _glow(widget.item)
    assert action.property("actionCount") == 1
    assert widget.item.property("widgetGlowClicked") is True
    assert glow.property("clickLevel") > 0.0
    qtbot.waitUntil(lambda: not glow.property("animating"), timeout=1200)
    # The glow settles at the selected state; release does not start a self-decay.
    assert glow.property("clickLevel") == pytest.approx(1.0)
    assert glow.property("intensity") == pytest.approx(0.6)
    # Edge-driven hover settles; moving inside does not restart its animation.
    assert glow.property("hoverLevel") == pytest.approx(0.80)
    _mouse(window, QEvent.Type.MouseMove, 90, 90)
    assert not glow.property("animating")
    # A later click on empty space is the next click-state edge and gently fades.
    _mouse(window, QEvent.Type.MouseMove, 330, 240)
    _mouse(window, QEvent.Type.MouseButtonPress, 330, 240, Qt.LeftButton, Qt.LeftButton)
    _mouse(window, QEvent.Type.MouseButtonRelease, 330, 240, Qt.LeftButton)
    assert widget.item.property("widgetGlowClicked") is False
    qtbot.waitUntil(lambda: not glow.property("animating"), timeout=1400)
    assert glow.property("intensity") == 0.0


def test_feedback_has_no_polling_or_texture_capture():
    code = (quick_qml_root() / "WidgetInteractionGlow.qml").read_text(encoding="utf-8")
    for forbidden in ("Timer {", "FrameAnimation", "Animation.Infinite", "layer.enabled", "MultiEffect", "ShaderEffectSource"):
        assert forbidden not in code


def test_glow_projects_visualizer_frame_and_shell_less_digital_clock_bounds():
    qml = quick_qml_root()
    visualizer = (qml / "VisualizerPresentation.qml").read_text(encoding="utf-8")
    clock = (qml / "ClockPresentation.qml").read_text(encoding="utf-8")
    overlay = (qml / "OverlayWidget.qml").read_text(encoding="utf-8")
    glow = (qml / "WidgetInteractionGlow.qml").read_text(encoding="utf-8")

    assert 'objectName: "visualizerInteractionGlowLoader"' in visualizer
    assert "widgetGlowAdmitted" in visualizer
    assert "HoverHandler" in visualizer and "blocking: false" in visualizer
    assert "_isDigital && !cardShellEnabled" in clock
    assert "interactionGlowWidth" in clock and "digitalFace.preferredContentWidth" in clock
    assert "property real interactionGlowWidth" in overlay
    assert "hovered ? 0.80 : 0.0" in glow
    assert "property real distancePx: 14.0" in glow
    assert "distancePx / 12.0" in glow
    assert "width / glow.distanceScale" in glow
    assert "widgetGlowDistance" in visualizer and "distancePx:" in visualizer
    assert "widgetGlowDistance" in overlay and "distancePx:" in overlay
    # Stronger 100% uses the same baked shader twice; no extra clock or capture.
    assert glow.count('fragmentShader: "shaders/widget_glow.frag.qsb"') == 2
