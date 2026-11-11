"""Expanded Visualizer M2: the retained expand / collapse glyph (plan 01 §B1, §H Milestone 2).

The real hidden Quick display unit and Visualizer presentation (``tests/test_framed_scene_input.card``); nothing is
shown. The glyph is offered only when the takeover coordinator publishes it, draws the direction it will act in,
reports one semantic press through the scene controller, sits at the far corner of the card's bottom-right glyph row
(the upper-right corner is the control hint's), and the Edit glyphs (which edit the ordinary card) are withdrawn while
the view is display-wide. Its double-click consumption is in
``test_visualizer_in_card_control_double_click.py``.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtQuick import QQuickItem

from tests.test_framed_scene_input import NONE, card as production_card, mouse, polish_glyph_row  # noqa: F401

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
    polish_glyph_row(card)
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
def test_the_glyph_closes_the_bottom_right_row_and_leaves_the_upper_right_to_the_hint(glyph_card):
    """Operator, 8 Nov: the expand glyph joins the bottom-right glyph row, at its far corner (after Reset Camera and
    the preset steps); the 3D control hint keeps the upper-right corner whether or not the glyph is offered."""
    card = glyph_card
    root = card.scene._visualizer_root
    root.setProperty("cameraResetAvailable", True)
    card.scene.set_visualizer_expand_glyph(True, False)
    glyph = _glyph(card)

    def rect(item):
        return item.mapRectToItem(root, QRectF(0.0, 0.0, item.width(), item.height()))

    reset, steps = _find(root, "visualizerCameraResetGlyph"), _find(root, "visualizerPresetControls")
    expand = rect(glyph)
    assert expand.right() <= root.width() and expand.bottom() <= root.height()
    assert expand.top() > root.height() / 2 and expand.left() > root.width() / 2      # the bottom-right corner
    for other in (rect(reset), rect(steps)):
        assert abs(other.bottom() - expand.bottom()) < 0.5                             # one baseline
        assert other.right() <= expand.left()                                          # left of it, no overlap
    assert rect(steps).right() <= rect(reset).left()
    hint = _find(root, "visualizerControlHint")
    root.setProperty("controlHintsAvailable", True)
    corner = rect(hint).right()
    card.scene.set_visualizer_expand_glyph(False, False)
    assert rect(hint).right() == corner and rect(hint).bottom() < expand.top()        # the hint never moves for it


@pytest.mark.qt
def test_the_camera_controls_stay_offered_and_working_while_display_wide(glyph_card):
    """Operator, 8 Nov ("the fullscreen visualizer is also missing its rotate glyph"): the framed camera's in-card
    controls are the card's on the display-wide view too: Reset Camera (the rotate arrow), the preset steps and the
    3D control hint show under the same admission, clear of the collapse glyph, and Reset Camera still acts."""
    card = glyph_card
    root = card.scene._visualizer_root
    root.setProperty("presentationActive", True)
    card.scene.set_visualizer_camera_reset_available(True)
    card.scene.set_visualizer_control_hints_available(True)
    resets = []
    card.scene.visualizer_camera_reset_requested.connect(lambda *_args: resets.append(1))
    for expanded in (False, True):
        card.scene.set_visualizer_expand_glyph(True, expanded)
        polish_glyph_row(card)
        reset = _find(root, "visualizerCameraResetGlyph")
        steps = _find(root, "visualizerPresetControls")
        assert reset.isVisible() and steps.isVisible(), expanded
        assert bool(root.property("controlHintEligible")), expanded
        glyph = _glyph(card)
        collapse = glyph.mapRectToItem(root, QRectF(0.0, 0.0, glyph.width(), glyph.height()))
        for control in (reset, steps):
            assert not control.mapRectToItem(root, QRectF(0.0, 0.0, control.width(), control.height())).intersects(
                collapse)
        _click(card, _hovered(reset))
        assert len(resets) == (2 if expanded else 1), expanded
        root.setProperty("widgetGlowAdmitted", False)       # the same input admission as on the card
        assert not reset.isVisible()
        root.setProperty("widgetGlowAdmitted", True)


# ------------------------------------------------- plan 1B.12: one full-display glyph per target display


def _settle_presence(card, target: float) -> None:
    """The second glyph's place fades (an animation): process events until it settles, gradually."""
    from PySide6.QtCore import QCoreApplication, QElapsedTimer

    root = card.scene._visualizer_root
    clock = QElapsedTimer()
    clock.start()
    samples = []
    while abs(float(root.property("expandLeftPresence")) - target) > 1e-6:
        QCoreApplication.processEvents()
        samples.append(float(root.property("expandLeftPresence")))
        assert clock.elapsed() < 4000, "the display glyph's place did not settle"
    polish_glyph_row(card)
    return samples


def _left(card):
    glyph = _find(card.scene._visualizer_root, "visualizerExpandLeftGlyph")
    assert glyph is not None
    return glyph


@pytest.mark.qt
def test_one_display_keeps_the_single_glyph_exactly(glyph_card):
    card = glyph_card
    card.scene.set_visualizer_expand_glyph(True, False)
    right = _glyph(card)
    assert not _left(card).isVisible()
    assert float(card.scene._visualizer_root.property("expandLeftPresence")) == 0.0
    slot = _find(card.scene._visualizer_root, "visualizerExpandSlot")
    assert abs(slot.width() - right.width()) < 0.5                    # one member's place, as before


@pytest.mark.qt
def test_two_displays_offer_up_left_beside_up_right_and_fade_it_in_and_out(glyph_card):
    card = glyph_card
    root = card.scene._visualizer_root
    card.scene.set_visualizer_expand_glyph(True, False, display_targets=True, display=0)
    samples = _settle_presence(card, 1.0)
    assert any(0.0 < sample < 1.0 for sample in samples)             # it fades in, never pops
    left, right = _left(card), _glyph(card)
    assert left.isVisible() and right.isVisible()

    def rect(item):
        return item.mapRectToItem(root, QRectF(0.0, 0.0, item.width(), item.height()))

    a, b = rect(left), rect(right)
    assert abs(a.bottom() - b.bottom()) < 0.5 and abs(a.width() - b.width()) < 0.5
    assert a.right() < b.left()                                         # up-left first, then up-right at the corner
    assert abs((b.left() - a.right()) - float(root.property("glyphSpacing")) * float(root.property("glyphRowScale"))) < 0.5
    card.scene.set_visualizer_expand_glyph(True, False)                 # back to one display
    samples = _settle_presence(card, 0.0)
    assert any(0.0 < sample < 1.0 for sample in samples)             # it fades out
    assert not left.isVisible()


@pytest.mark.qt
@pytest.mark.parametrize("display,expanded,left_collapses,right_collapses,two", [
    (0, False, False, False, True), (1, False, False, False, True),
    (0, True, True, False, True), (1, True, False, True, True),
    # A view expanded on a display neither glyph names keeps the single collapse glyph (V reaches that display).
    (2, True, False, True, False),
])
def test_each_glyph_draws_its_own_direction(glyph_card, display, expanded, left_collapses, right_collapses, two):
    card = glyph_card
    root = card.scene._visualizer_root
    card.scene.set_visualizer_expand_glyph(True, expanded, display_targets=True, display=display)
    _settle_presence(card, 1.0 if two else 0.0)
    assert bool(root.property("expandTwoGlyphs")) is two
    assert bool(_find(_left(card), "visualizerExpandLeftGlyphArrow").property("collapse")) is left_collapses
    assert bool(_find(_glyph(card), "visualizerExpandGlyphArrow").property("collapse")) is right_collapses


@pytest.mark.qt
@pytest.mark.parametrize("display,expanded", [(0, False), (1, False), (0, True), (1, True)])
def test_a_press_reports_the_target_display_or_the_collapse(glyph_card, display, expanded):
    card = glyph_card
    card.scene.set_visualizer_expand_glyph(True, expanded, display_targets=True, display=display)
    _settle_presence(card, 1.0)
    targets, collapses = [], []
    card.scene.visualizer_expand_on_display_requested.connect(targets.append)
    card.scene.visualizer_expand_requested.connect(collapses.append)
    root = card.scene._visualizer_root
    tooltip = _find(root, "visualizerExpandTooltip")
    label = next(child for child in tooltip.childItems() if child.property("text"))
    texts = {}
    for index, glyph in ((0, _left(card)), (1, _glyph(card))):
        root.setProperty("expandTipGlyph", index)
        texts[index] = label.property("text")
        _click(card, _hovered(glyph))
    # Each glyph names its own target (the words are UI copy, so only their difference is asserted).
    assert texts[0] != texts[1]
    if expanded:
        # The card's own display glyph collapses; the other moves the view to its display.
        assert collapses == [False] and targets == [1 - display]
    else:
        assert collapses == [] and targets == [0, 1]


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
