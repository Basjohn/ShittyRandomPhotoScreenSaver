"""Native retained glyph actions, placement and delayed tooltip admission."""
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect, Qt, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from rendering.custom_layout_session import CustomLayoutSession
from rendering.quick.custom_layout_overlay import CustomLayoutOverlayModel
from tests.test_qtquick_custom_layout_overlay import _item, _quick_items_named

ROOT = Path(__file__).resolve().parents[1]


def _load(engine, name):
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT / "rendering/quick/qml" / name)))
    assert component.isReady(), "\n".join(map(str, component.errors()))
    root = component.create()
    assert isinstance(root, QQuickItem)
    return component, root


@pytest.mark.parametrize("editing", [False, True])
@pytest.mark.parametrize("camera", [False, True])
def test_preset_glyphs_click_both_directions_and_delay_tooltips(qt_app, qtbot, editing, camera):
    engine = QQmlEngine()
    component, root = _load(engine, "VisualizerPresentation.qml")
    root.setWidth(600)
    root.setHeight(360)
    for key, value in dict(presentationActive=True, widgetGlowAdmitted=True,
                           cameraResetAvailable=camera, volumeWheelEnabled=not editing).items():
        root.setProperty(key, value)
    window = QQuickWindow()
    window.resize(700, 460)
    root.setParentItem(window.contentItem())
    directions = []
    root.presetStepRequested.connect(directions.append)
    overlay = None
    if editing:
        edit_component, overlay = _load(engine, "CustomLayoutOverlay.qml")
        overlay.setParentItem(window.contentItem())
        overlay.setWidth(700)
        overlay.setHeight(460)
        overlay.setZ(50)
        session = CustomLayoutSession()
        session.add_item(_item("spotify_visualizer", "display:test", QRect(0, 0, 600, 360),
                               resizable=True, size_reset_capable=True, content_rotation_capable=not camera))
        model = CustomLayoutOverlayModel(session=session, display_identity="display:test",
                                        content_envelope_item_resolver=lambda _: root)
        overlay.setProperty("sessionModel", model)
        overlay.setProperty("editActive", True)
    window.show()
    assert QTest.qWaitForWindowExposed(window)
    def button(direction):
        name = (("customLayoutPreviousPreset-" if direction < 0 else "customLayoutNextPreset-") + "spotify_visualizer"
                if editing else ("visualizerPreviousPresetGlyph" if direction < 0 else "visualizerNextPresetGlyph"))
        return _quick_items_named(overlay if editing else root, name)[0]
    try:
        QTest.mouseMove(window, QPoint(300, 200))
        previous, following = button(-1), button(1)
        qtbot.waitUntil(lambda: previous.isEnabled() and previous.isVisible(), timeout=2500)
        assert previous.width() == following.width() == (22 if editing else 26)
        assert previous.mapToScene(previous.boundingRect().center()).x() < following.mapToScene(following.boundingRect().center()).x()
        for direction in (-1, 1):
            control = button(direction)
            point = control.mapToScene(control.boundingRect().center()).toPoint()
            QTest.mouseMove(window, point)
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            assert directions[-1] == direction
        tip = (_quick_items_named(overlay, "customLayoutGlyphTooltip-spotify_visualizer")[0] if editing
               else root.findChild(QQuickItem, "visualizerPresetTooltip"))
        assert tip is not None
        assert tip.opacity() == 0
        qtbot.waitUntil(lambda: tip.opacity() > 0.5, timeout=3000)
        QTest.mouseMove(window, QPoint(680, 440))
        qtbot.waitUntil(lambda: not tip.isVisible(), timeout=2000)
        assert directions == [-1, 1]
    finally:
        if overlay:
            overlay.setProperty("sessionModel", None)
            overlay.setParentItem(None)
            overlay.deleteLater()
        root.setParentItem(None)
        root.deleteLater()
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_default_visualizer_model_resolves_default_mode_and_first_preset():
    from core.settings.default_contract import require_canonical_default
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_mode_registry import get_preset_key
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload

    section = require_canonical_default("widgets.spotify_visualizer")
    bare = SpotifyVisualizerSettings()
    model = SpotifyVisualizerSettings.from_mapping(section)
    assert bare.mode == model.mode == section["mode"]
    key = get_preset_key(model.mode)
    assert getattr(model, key) == section[key]
    activation = resolve_visualizer_activation_payload(section, mode=model.mode)
    assert activation.mode == model.mode
