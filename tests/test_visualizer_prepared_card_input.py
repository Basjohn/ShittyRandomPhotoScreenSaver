"""A display move's target card while its renderer prepares takes no input (Current_Plan 1C.2).

The target is drawn at a sub-visible opacity so its render thread prepares; it must not be a hit target meanwhile: a
press, double-click, orbit or wheel there belongs to whatever lies below. The scene is the real
``QuickSceneController`` on a real ``QuickDisplayWindow`` that is never shown.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QWheelEvent
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow
from tests._visualizer_presentation import resolve_presentation
from widgets.spotify_visualizer.quick_display_visualizer_owner import _PREWARM_SCENE_FADE
from widgets.spotify_visualizer.render_bridge import VisualizerRenderIdentity

_BELOW = b"""
import QtQuick
MouseArea {
    property int wheels: 0
    acceptedButtons: Qt.AllButtons
    onWheel: function(wheel) { wheels += 1; wheel.accepted = true }
}
"""


@pytest.mark.qt
def test_a_preparing_card_takes_no_input_and_a_wheel_there_reaches_what_is_below(qt_app):
    """The scene's own hit test (double-click mode cycling, plain orbit, the glow press) refuses the point, the
    shell's QML handlers are disabled, and a wheel there reaches the item below. Negative control (checked 12 Nov on
    the pre-change scene): the hit test claimed the point and the shell was enabled. (The wheel's delivery to the
    item below is not itself a control: on a never-shown window the shell's own WheelHandler did not take a synthetic
    wheel even before the change, so that line only proves the card does not swallow it.)"""
    window = QuickDisplayWindow(screen_index=0, runtime_generation=211, screen=qt_app.primaryScreen(),
                                policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    factory = QuickSceneFactory()
    scene = QuickSceneController(window=window, factory=factory)
    below = None
    try:
        record = resolve_presentation(policy=get_visualizer_presentation_policy("spectrum"),
                                      display_size=(1280.0, 720.0), outer_origin=(200.0, 150.0))
        record = replace(record, scene_fade=_PREWARM_SCENE_FADE, content_fade=0.0)
        identity = VisualizerRenderIdentity(runtime_generation=1, engine_generation=2, activation_id=3,
                                            mode_id="spectrum")
        # What lies below the card: a plain item under it in the cards' own layer.
        layer = scene.scene_root.findChild(QQuickItem, "pixelShiftLayer")
        engine = QQmlEngine.contextForObject(scene.scene_root).engine()
        component = QQmlComponent(engine)
        component.setData(_BELOW, QUrl())
        below = component.create()
        assert below is not None, component.errors()
        below.setParentItem(layer)
        below.setZ(15.0)                                  # above the ordinary widgets, below the Visualizer card
        below.setWidth(1280.0)
        below.setHeight(720.0)

        assert scene.begin_visualizer_prewarm(identity, record) is True
        root = scene._visualizer_root
        steps: list[int] = []
        root.appVolumeStepRequested.connect(steps.append)
        x, y, width, height = record.outer_rect
        centre = QPointF(x + width / 2.0, y + height / 2.0)
        assert root.isVisible()                            # drawn, so its render thread prepares
        assert root.property("prepareOnly") is True and not root.isEnabled()
        assert scene.visualizer_contains_scene_position(centre) is False

        event = QWheelEvent(centre, centre, QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QCoreApplication.sendEvent(window, event)
        assert steps == [] and below.property("wheels") == 1

        # The preparation ends (the move went elsewhere): the shell is no longer drawn and input returns to it.
        scene.end_visualizer_prewarm()
        assert root.property("prepareOnly") is False and root.isEnabled()
        assert root.property("presentationActive") is False
    finally:
        if below is not None:
            below.setParentItem(None)
            below.deleteLater()
        scene.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()
