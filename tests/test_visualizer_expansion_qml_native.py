"""Expanded Visualizer M2: the retained expand / collapse glyph (plan 01 §B1, §H Milestone 2).

The real hidden Quick display unit and Visualizer presentation (``tests/test_framed_scene_input.card``); nothing is
shown. The glyph is offered only when the takeover coordinator publishes it, draws the direction it will act in,
reports one semantic press through the scene controller, keeps clear of the control hint, and the Edit glyphs
(which edit the ordinary card) are withdrawn while the view is display-wide. Its double-click consumption is in
``test_visualizer_in_card_control_double_click.py``.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtQuick import QQuickItem

from tests.test_framed_scene_input import NONE, card as production_card, mouse  # noqa: F401

LEFT = Qt.MouseButton.LeftButton


def _find(item, name):
    if item.objectName() == name:
        return item
    return next((hit for child in item.childItems() if (hit := _find(child, name)) is not None), None)


@pytest.fixture
def glyph_card(production_card):
    card = production_card
    root = card.scene._visualizer_root
    for name, value in (("alwaysShowGlyphs", True), ("widgetGlowAdmitted", True)):
        root.setProperty(name, value)
    return card


def _glyph(card):
    glyph = _find(card.scene._visualizer_root, "visualizerExpandGlyph")
    assert glyph is not None
    return glyph


def _hovered(glyph):
    """The glyph at its completed hover presentation (its fade is the same as Reset Camera's)."""
    glyph.setProperty("opacity", .92)
    glyph.setEnabled(True)
    return glyph


def _click(card, glyph):
    p = glyph.mapToScene(QPointF(glyph.width() / 2, glyph.height() / 2))
    mouse(card, QEvent.Type.MouseButtonPress, p, LEFT, NONE)
    mouse(card, QEvent.Type.MouseButtonRelease, p, LEFT, NONE)


@pytest.mark.qt
def test_the_glyph_is_offered_only_when_the_coordinator_publishes_it(glyph_card):
    card = glyph_card
    glyph = _glyph(card)
    assert card.scene.visualizer_expand_glyph == (False, False) and not glyph.isVisible()
    card.scene.set_visualizer_expand_glyph(True, False)
    assert glyph.isVisible()
    card.scene._visualizer_root.setProperty("widgetGlowAdmitted", False)   # the shared input admission
    assert not glyph.isVisible()
    card.scene._visualizer_root.setProperty("widgetGlowAdmitted", True)
    card.scene.set_visualizer_expand_glyph(False, False)
    assert not glyph.isVisible()


@pytest.mark.qt
@pytest.mark.parametrize("expanded", [False, True])
def test_one_press_reports_the_direction_the_glyph_shows(glyph_card, expanded):
    card = glyph_card
    card.scene.set_visualizer_expand_glyph(True, expanded)
    glyph = _hovered(_glyph(card))
    arrow = _find(glyph, "visualizerExpandGlyphArrow")
    assert bool(arrow.property("collapse")) is expanded
    tooltip = _find(card.scene._visualizer_root, "visualizerExpandTooltip")
    label = next(child for child in tooltip.childItems() if child.property("text"))
    assert label.property("text") == ("EXIT FULL DISPLAY" if expanded else "FULL DISPLAY")
    reported, cycles = [], []
    card.scene.visualizer_expand_requested.connect(reported.append)
    card.scene._visualizer_root.presetStepRequested.connect(lambda *_a: cycles.append(1))
    _click(card, glyph)
    assert reported == [not expanded]
    assert cycles == []


@pytest.mark.qt
def test_the_glyph_sits_in_the_upper_right_safe_zone_clear_of_the_hint(glyph_card):
    card = glyph_card
    root = card.scene._visualizer_root
    card.scene.set_visualizer_expand_glyph(True, False)
    glyph = _glyph(card)
    assert glyph.x() + glyph.width() <= root.width() and glyph.y() < root.height() / 4
    assert glyph.x() > root.width() / 2
    hint = _find(root, "visualizerControlHint")
    root.setProperty("controlHintsAvailable", True)
    # The hint's right edge stays left of the glyph whenever both are present (safe zone, plan 01 §B1)...
    assert hint.x() + hint.width() <= glyph.x() + 1e-6
    # ...and returns to the corner when no glyph is offered.
    card.scene.set_visualizer_expand_glyph(False, False)
    assert hint.x() + hint.width() > glyph.x()


@pytest.mark.qt
def test_edit_glyphs_are_withdrawn_while_display_wide(glyph_card):
    card = glyph_card
    root = card.scene._visualizer_root
    root.setProperty("presentationActive", True)
    loader = _find(root, "visualizerHoverGlyphLoader")
    assert isinstance(loader, QQuickItem) and bool(loader.property("active"))
    card.scene.set_visualizer_expand_glyph(True, True)
    assert not bool(loader.property("active"))
    card.scene.set_visualizer_expand_glyph(True, False)
    assert bool(loader.property("active"))
