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


# ------------------------------------- plan 1B.12, relative form: Up here, up-left / up-right to the neighbours


def _presences(card):
    root = card.scene._visualizer_root
    return float(root.property("expandLeftPresence")), float(root.property("expandRightPresence"))


def _settle_presence(card, left: float, right: float, sample=None) -> list:
    """Each side glyph's place fades (an animation): process events until both settle, gradually."""
    from PySide6.QtCore import QCoreApplication, QElapsedTimer

    clock = QElapsedTimer()
    clock.start()
    samples = []
    while max(abs(_presences(card)[0] - left), abs(_presences(card)[1] - right)) > 1e-6:
        QCoreApplication.processEvents()
        polish_glyph_row(card)
        samples.append(_presences(card) if sample is None else sample())
        assert clock.elapsed() < 4000, "a side glyph's place did not settle"
    polish_glyph_row(card)
    return samples


def _side(card, side: int):
    glyph = _find(card.scene._visualizer_root, "visualizerExpandLeftGlyph" if side < 0 else "visualizerExpandRightGlyph")
    assert glyph is not None
    return glyph


def _arrow(glyph):
    return next(child for child in glyph.childItems() if child.objectName().endswith("Arrow"))


def _card_rect(card, item):
    return item.mapRectToItem(card.scene._visualizer_root, QRectF(0.0, 0.0, item.width(), item.height()))


@pytest.mark.qt
def test_one_display_shows_the_up_arrow_alone(glyph_card):
    card = glyph_card
    root = card.scene._visualizer_root
    card.scene.set_visualizer_expand_glyph(True, False)
    here = _glyph(card)
    assert not _side(card, -1).isVisible() and not _side(card, 1).isVisible()
    assert _presences(card) == (0.0, 0.0)
    slot = _find(root, "visualizerExpandSlot")
    assert abs(slot.width() - here.width()) < 0.5                     # one member's place
    # The operator's Up arrow (one named choice); the collapse is the same arrow turned to point down.
    assert float(root.property("expandHereArrowDegrees")) == 0.0
    assert float(_arrow(here).property("degrees")) == float(root.property("expandHereArrowDegrees"))
    card.scene.set_visualizer_expand_glyph(True, True)
    assert float(_arrow(here).property("degrees")) == float(root.property("expandHereArrowDegrees")) + 180.0


@pytest.mark.qt
@pytest.mark.parametrize("left,right", [(True, False), (False, True), (True, True)])
def test_only_the_offered_side_glyphs_show_around_this_displays_glyph(glyph_card, left, right):
    """Up-left before this display's glyph, up-right after it at the far corner: one size, one baseline, one
    spacing; each fades in (never pops) and its slot grows with it."""
    card = glyph_card
    root = card.scene._visualizer_root
    card.scene.set_visualizer_expand_glyph(True, False, sides=(left, right))
    samples = _settle_presence(card, float(left), float(right))
    assert any(0.0 < value < 1.0 for sample in samples for value in sample)   # faded in
    here = _glyph(card)
    shown = [glyph for side, offered in ((-1, left), (1, right)) if offered for glyph in [_side(card, side)]]
    hidden = [_side(card, side) for side, offered in ((-1, left), (1, right)) if not offered]
    assert all(glyph.isVisible() for glyph in shown) and not any(glyph.isVisible() for glyph in hidden)
    row = sorted([here, *shown], key=lambda glyph: _card_rect(card, glyph).left())
    expected = ([_side(card, -1)] if left else []) + [here] + ([_side(card, 1)] if right else [])
    assert row == expected
    rects = [_card_rect(card, glyph) for glyph in row]
    spacing = float(root.property("glyphSpacing")) * float(root.property("glyphRowScale"))
    for a, b in zip(rects, rects[1:]):
        assert abs(a.bottom() - b.bottom()) < 0.5 and abs(a.width() - b.width()) < 0.5
        assert abs((b.left() - a.right()) - spacing) < 0.5
    slot = _card_rect(card, _find(root, "visualizerExpandSlot"))
    assert abs(rects[-1].right() - slot.right()) < 0.5 and abs(rects[0].left() - slot.left()) < 0.5


@pytest.mark.qt
def test_a_side_glyph_that_goes_fades_out_and_the_row_glides_never_jumps(glyph_card):
    """A display on one side goes (or comes): its glyph fades with its place, and the glyphs beside it glide."""
    card = glyph_card
    card.scene.set_visualizer_expand_glyph(True, False, sides=(True, True))
    _settle_presence(card, 1.0, 1.0)
    here = _glyph(card)
    start = _card_rect(card, here).left()
    card.scene.set_visualizer_expand_glyph(True, False, sides=(True, False))
    lefts = _settle_presence(card, 1.0, 0.0, sample=lambda: _card_rect(card, here).left())
    end = _card_rect(card, here).left()
    assert end > start                                                  # it took the corner the up-right gave up
    steps = [abs(b - a) for a, b in zip([start, *lefts], [*lefts, end])]
    assert len([value for value in lefts if start < value < end]) >= 3  # through the places between
    assert max(steps) < (end - start) / 2.0                             # never one jump
    assert not _side(card, 1).isVisible() and _side(card, -1).isVisible()


@pytest.mark.qt
@pytest.mark.parametrize("expanded", [False, True])
def test_each_glyph_draws_its_own_direction(glyph_card, expanded):
    """Up-left and up-right are this display's arrow turned 45 degrees each way; expanded, this display's glyph is
    the collapse (turned to point down) and the diagonals keep their direction (they move the view)."""
    card = glyph_card
    root = card.scene._visualizer_root
    card.scene.set_visualizer_expand_glyph(True, expanded, sides=(True, True))
    _settle_presence(card, 1.0, 1.0)
    here = float(root.property("expandHereArrowDegrees"))
    assert bool(_arrow(_glyph(card)).property("collapse")) is expanded
    assert float(_arrow(_glyph(card)).property("degrees")) == here + (180.0 if expanded else 0.0)
    assert float(_arrow(_side(card, -1)).property("degrees")) == -45.0
    assert float(_arrow(_side(card, 1)).property("degrees")) == 45.0


@pytest.mark.qt
@pytest.mark.parametrize("expanded", [False, True])
def test_a_press_reports_the_side_or_this_displays_expand_and_collapse(glyph_card, expanded):
    card = glyph_card
    card.scene.set_visualizer_expand_glyph(True, expanded, sides=(True, True))
    _settle_presence(card, 1.0, 1.0)
    sides, presses = [], []
    card.scene.visualizer_expand_to_side_requested.connect(sides.append)
    card.scene.visualizer_expand_requested.connect(presses.append)
    root = card.scene._visualizer_root
    tooltip = _find(root, "visualizerExpandTooltip")
    label = next(child for child in tooltip.childItems() if child.property("text"))
    texts = {}
    for side, glyph in ((-1, _side(card, -1)), (0, _glyph(card)), (1, _side(card, 1))):
        root.setProperty("expandTipGlyph", side)
        texts[side] = label.property("text")
        _click(card, _hovered(glyph))
    assert sides == [-1, 1] and presses == [not expanded]
    # Each glyph says what it does relative to the Visualizer's display: three different tips, no display number
    # (the words are UI copy, so only that is asserted).
    assert len(set(texts.values())) == 3
    assert not any(character.isdigit() for text in texts.values() for character in text)


@pytest.mark.qt
def test_a_side_glyph_that_is_not_offered_takes_no_press(glyph_card):
    card = glyph_card
    card.scene.set_visualizer_expand_glyph(True, False, sides=(False, True))
    _settle_presence(card, 0.0, 1.0)
    sides = []
    card.scene.visualizer_expand_to_side_requested.connect(sides.append)
    left = _side(card, -1)
    assert not left.isEnabled()
    _click(card, _hovered(_side(card, 1)))
    assert sides == [1]


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
