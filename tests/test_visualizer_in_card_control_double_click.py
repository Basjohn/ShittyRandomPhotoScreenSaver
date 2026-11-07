"""In-card controls own their presses: a double-click on Reset Camera (or a preset step) never cycles the mode.

Operator 6 Nov: two quick clicks on Reset Camera ran two resets *and* reached the card's double-click admission
(``QuickVisualizerDoubleClickAdmission``), which cycled Extruded Bubble to Waveform. The controls consume every
press, the double-click's second press included, and ``QuickDisplayWindow`` leaves a double-click a QML control
accepted alone. A double-click on the card's empty area still cycles (negative control).

The real hidden Quick display unit and Visualizer presentation (``tests/test_framed_scene_input.card``), with the
production admission wired as ``DisplayManager`` wires it; nothing is shown.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt

from rendering.quick.visualizer.double_click_admission import QuickVisualizerDoubleClickAdmission
from tests.test_framed_scene_input import NONE, card as production_card, mouse, point  # noqa: F401

LEFT = Qt.MouseButton.LeftButton


@pytest.fixture
def admitted_card(production_card):
    card = production_card
    cycles = []
    card.scene.set_visualizer_double_click_admission(QuickVisualizerDoubleClickAdmission(
        region_contains=card.scene.visualizer_contains_scene_position,
        is_active=lambda: True,
        cycle_mode=lambda: cycles.append(1)))
    card.cycles = cycles
    root = card.scene._visualizer_root
    for name, value in (("cameraResetAvailable", True), ("alwaysShowGlyphs", True), ("widgetGlowAdmitted", True),
                        ("volumeWheelEnabled", True)):
        root.setProperty(name, value)
    return card


def _control(card, object_name):
    """An in-card control at its completed hover presentation (its fade has its own coverage)."""
    def find(item):                                           # visual children: Repeater delegates included
        if item.objectName() == object_name:
            return item
        return next((hit for child in item.childItems() if (hit := find(child)) is not None), None)
    item = find(card.scene._visualizer_root)
    assert item is not None, object_name
    holder = item if object_name == "visualizerCameraResetGlyph" else item.parentItem()
    holder.setProperty("opacity", .92)
    holder.setEnabled(True)
    assert item.isVisible() and item.isEnabled()
    return item


def _double_click(card, p):
    """The native sequence of a double-click: press, release, press + double-click, release."""
    mouse(card, QEvent.Type.MouseButtonPress, p, LEFT, NONE)
    mouse(card, QEvent.Type.MouseButtonRelease, p, LEFT, NONE)
    mouse(card, QEvent.Type.MouseButtonPress, p, LEFT, NONE)
    mouse(card, QEvent.Type.MouseButtonDblClick, p, LEFT, NONE)
    mouse(card, QEvent.Type.MouseButtonRelease, p, LEFT, NONE)


@pytest.mark.qt
@pytest.mark.parametrize("object_name,signal", [
    ("visualizerCameraResetGlyph", "cameraResetRequested"),
    ("visualizerNextPresetGlyph", "presetStepRequested"),
])
def test_a_double_click_on_an_in_card_control_never_cycles_the_mode(admitted_card, object_name, signal):
    card = admitted_card
    control = _control(card, object_name)
    p = control.mapToScene(QPointF(control.width() / 2, control.height() / 2))
    assert card.scene.visualizer_contains_scene_position(p)      # the control sits inside the card's region
    requests = []
    getattr(card.scene._visualizer_root, signal).connect(lambda *_a: requests.append(1))
    _double_click(card, p)
    assert 1 <= len(requests) <= 2                               # the control ran once or twice
    assert card.cycles == [], f"a double-click on {object_name} cycled the Visualizer mode"


@pytest.mark.qt
def test_a_double_click_on_the_cards_empty_area_still_cycles_negative_control(admitted_card):
    card = admitted_card
    _control(card, "visualizerCameraResetGlyph")
    requests = []
    card.scene._visualizer_root.cameraResetRequested.connect(lambda: requests.append(1))
    _double_click(card, point(card))
    assert card.cycles == [1]
    assert requests == []
