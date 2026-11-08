"""The Visualizer card's one bottom-right glyph row (operator, 8 Nov).

"The rotate glyph should be on the same line as the bottom right glyphs, heck let's put expansion there too to be
neater and do the same thing for the normal visualizer."

The card's controls of that corner are one row (``VisualizerPresentation.qml`` ``glyphRow``), on the ordinary and the
display-wide card alike; in Edit, Edit's own controls of that corner (the preset steps, Rotate Widget Content) continue
it from the card's row geometry (``CustomLayoutOverlay.qml`` ``editGlyphRow``). Left to right: the preset steps, Rotate
Widget Content (Edit), Reset Camera, expand / collapse at the far corner. A member is in the row while it is offered,
and the row skips the rest (no gaps).

The bars run the production ``DisplayScene.qml`` / ``VisualizerPresentation.qml`` / ``CustomLayoutOverlay.qml`` and
``QuickSceneController`` in the hidden ``QQuickRenderControl`` host (no window is shown). They assert structure only:
the members visible at once share one bottom edge and one size, sit left to right in the expected order at one even
spacing without overlap, inside the card, with the row's last member as far from the card's right edge as from its
bottom edge (the row's corner); Edit chrome and the expanded overlays keep clear of it. Every value a test writes is
test-owned; nothing pins a size, a default or UI wording.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QRect, QRectF
from PySide6.QtQuick import QQuickItem

from tests.test_visualizer_expansion_overlays import (
    CHROME,
    HEIGHT,
    SLOTS,
    WIDTH,
    _draw,
    _expanded_card,
    _Media,
    _open,
    _run,
    _settle,
    _slot,
    _visual,
)

CARD_ROW = ("visualizerPreviousPresetGlyph", "visualizerNextPresetGlyph", "visualizerCameraResetGlyph",
            "visualizerExpandGlyph")


@pytest.fixture
def display(qt_app):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    host = HiddenDisplayHost(WIDTH, HEIGHT, dpr=1.0)
    try:
        yield host
    finally:
        host.close()


def _ordinary(display, *, mode: str = "spectrum", extent: tuple[float, float] | None = None):
    """Draw the ordinary card (a test-owned origin and, for a narrow card, a test-owned extent)."""
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation

    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode), display_size=(WIDTH, HEIGHT), outer_origin=(120.0, 260.0),
        viewport_extent=extent, **CHROME)
    display.scene.apply_visualizer_presentation(presentation, active=True)
    return presentation


def _offer(display, *, reset: bool, expand: bool, admitted: bool = True) -> None:
    root = display.scene._visualizer_root
    for name, value in (("alwaysShowGlyphs", True), ("widgetGlowAdmitted", admitted),
                        ("cameraResetAvailable", reset), ("expandGlyphAvailable", expand)):
        root.setProperty(name, value)
    _run(display, 60)                               # a frame or two: the rows lay out at the frame's polish


def _scene(display):
    return display.window.contentItem()


def _rect(item, display) -> QRectF:
    return item.mapRectToItem(_scene(display), QRectF(0.0, 0.0, item.width(), item.height()))


def _named(display, name):
    found = [item for item in _visual(_scene(display)) if item.objectName() == name]
    assert len(found) == 1, (name, len(found))
    return found[0]


def _card_rect(display) -> QRectF:
    root = display.scene._visualizer_root
    return _rect(root, display)


def _row(display, names) -> list[tuple[str, QRectF]]:
    """The named members shown now (visible), left to right as they sit."""
    members = [(name, _rect(item, display)) for name in names if (item := _named(display, name)).isVisible()]
    return sorted(members, key=lambda member: member[1].left())


def _assert_one_row(members, card: QRectF, expected: tuple[str, ...]) -> None:
    names = tuple(name for name, _rect_ in members)
    assert names == expected, names                                     # the order, nothing missing or extra
    rects = [rect for _name, rect in members]
    first = rects[0]
    for rect in rects:
        assert abs(rect.bottom() - first.bottom()) < 0.5, names        # one baseline
        assert abs(rect.width() - first.width()) < 0.5 and abs(rect.height() - first.height()) < 0.5, names
        assert card.contains(rect), (names, rect, card)                 # inside the card: no overflow
    gaps = [right.left() - left.right() for left, right in zip(rects, rects[1:])]
    assert all(gap > 0.0 for gap in gaps), gaps                         # no overlap
    assert all(abs(gap - gaps[0]) < 0.5 for gap in gaps), gaps          # one spacing, no hole for a skipped member
    last = rects[-1]
    # The row's corner: its last member as far in from the card's right edge as from its bottom edge.
    assert abs((card.right() - last.right()) - (card.bottom() - last.bottom())) < 0.5, (last, card)


# -------------------------------------------------------------------------------------------- the card's row


@pytest.mark.qt
@pytest.mark.parametrize("card", ["ordinary", "narrow", "expanded"])
@pytest.mark.parametrize("reset,expand", [(False, False), (True, False), (False, True), (True, True)])
def test_the_cards_bottom_right_glyphs_are_one_row(display, card, reset, expand):
    if card == "expanded":
        _expanded_card(display)
    else:
        _ordinary(display, extent=(150.0, 70.0) if card == "narrow" else None)
    _offer(display, reset=reset, expand=expand)
    expected = ("visualizerPreviousPresetGlyph", "visualizerNextPresetGlyph") + (
        ("visualizerCameraResetGlyph",) if reset else ()) + (("visualizerExpandGlyph",) if expand else ())
    members = _row(display, CARD_ROW)
    _assert_one_row(members, _card_rect(display), expected)
    # Admission hides the row's members and never moves one: the same places when it returns.
    _offer(display, reset=reset, expand=expand, admitted=False)
    assert _row(display, CARD_ROW) == []
    _offer(display, reset=reset, expand=expand)
    assert _row(display, CARD_ROW) == members


@pytest.mark.qt
def test_the_tips_sit_above_the_row_at_their_glyphs(display):
    _ordinary(display)
    _offer(display, reset=True, expand=True)
    root = display.scene._visualizer_root
    row = [rect for _name, rect in _row(display, CARD_ROW)]
    top = min(rect.top() for rect in row)
    expand = _rect(_named(display, "visualizerExpandGlyph"), display)
    root.setProperty("expandTipProgress", 1.0)
    root.setProperty("cameraResetTipProgress", 1.0)
    steps = _named(display, "visualizerPresetControls")         # its completed hover (its own fade is covered)
    steps.setProperty("opacity", .92)
    steps.setEnabled(True)
    for name, glyph in (("visualizerExpandTooltip", expand), ("visualizerPresetTooltip", row[0])):
        if name == "visualizerPresetTooltip":
            # The tip's right edge follows the hovered glyph (the hover sets it from the glyph's place in the row).
            root.setProperty("cameraActionTipX", glyph.right() - _card_rect(display).left())
        _run(display, 20)
        tip = _named(display, name)
        assert tip.isVisible(), name
        rect = _rect(tip, display)
        assert rect.bottom() <= top, name                               # above the row, never on it
        assert _card_rect(display).contains(rect), name
        if name == "visualizerExpandTooltip":
            assert abs(rect.right() - glyph.right()) < 0.5               # right-aligned on its glyph


@pytest.mark.qt
def test_the_upper_right_corner_keeps_only_the_3d_hint(display):
    _ordinary(display, mode="extruded_bubble")
    root = display.scene._visualizer_root
    root.setProperty("controlHintsAvailable", True)
    root.setProperty("show3DControlHints", True)
    _offer(display, reset=True, expand=True)
    hint = _rect(_named(display, "visualizerControlHint"), display)
    card = _card_rect(display)
    assert hint.height() > 0.0
    for _name, rect in _row(display, CARD_ROW):
        assert not rect.intersects(hint)
    # The hint keeps its corner whether or not the expand glyph is offered.
    _offer(display, reset=True, expand=False)
    assert _rect(_named(display, "visualizerControlHint"), display) == hint
    assert abs((card.right() - hint.right()) - (hint.top() - card.top())) < 0.5


# ------------------------------------------------------------------------------------------ Edit continues it


def _edit(display, presentation, *, rotate: bool):
    from rendering.custom_layout_session import CustomLayoutSession
    from tests.test_qtquick_custom_layout_overlay import _item

    x, y, width, height = presentation.outer_rect
    session = CustomLayoutSession()
    session.add_item(_item("spotify_visualizer", "hidden", QRect(round(x), round(y), round(width), round(height)),
                           resizable=True, viewport_capable=True,
                           baseline_viewport_extent=tuple(presentation.viewport_extent),
                           content_rotation_capable=rotate, size_reset_capable=True))
    display.scene.bind_custom_layout_session(session, display_identity="hidden")
    _run(display, 80)
    return session


EDIT_ROW = ("customLayoutPreviousPreset-spotify_visualizer", "customLayoutNextPreset-spotify_visualizer",
            "customLayoutRotateContent-spotify_visualizer")


@pytest.mark.qt
@pytest.mark.parametrize("rotate,reset", [(True, False), (False, True), (True, True)])
def test_ordinary_edit_continues_the_cards_row(display, rotate, reset):
    """Ordinary Edit: Edit's preset steps and Rotate Widget Content on the card's own line, then the card's Reset
    Camera (the expand glyph is withdrawn under Edit); the both-offered case is test-owned, to pin the order."""
    presentation = _ordinary(display)
    _offer(display, reset=reset, expand=False)
    _edit(display, presentation, rotate=rotate)
    try:
        expected = ("customLayoutPreviousPreset-spotify_visualizer", "customLayoutNextPreset-spotify_visualizer") + (
            ("customLayoutRotateContent-spotify_visualizer",) if rotate else ()) + (
            ("visualizerCameraResetGlyph",) if reset else ())
        members = _row(display, EDIT_ROW + CARD_ROW)
        _assert_one_row(members, _card_rect(display), expected)
        # Edit's own chrome keeps clear of the row: corner handles, side strips, close, display hops, the wedge.
        chrome = [item for item in _visual(display.scene.custom_layout_overlay.item)
                  if item.isVisible() and item.objectName().startswith((
                      "customLayoutResize-", "customLayoutViewportEdge-", "customLayoutClose-",
                      "customLayoutTransfer", "customLayoutParentGlyphToggle-", "customLayoutRestoreSize-",
                      "customLayoutChildEditLock-"))]
        assert chrome
        for item in chrome:
            for name, rect in members:
                assert not _rect(item, display).intersects(rect), (item.objectName(), name)
        # The card's admission hides its members but never moves Edit's; what the card offers still places them,
        # admitted or not (a withdrawn Reset Camera gives its place up even while the card's glyphs are hidden).
        _offer(display, reset=reset, expand=False, admitted=False)
        assert _row(display, EDIT_ROW + CARD_ROW) == [member for member in members if member[0] in EDIT_ROW]
        _offer(display, reset=False, expand=False, admitted=False)
        _assert_one_row(_row(display, EDIT_ROW + CARD_ROW), _card_rect(display),
                        tuple(name for name in expected if name in EDIT_ROW))
    finally:
        display.scene.clear_custom_layout_session()


# ----------------------------------------------------------------------------------- Fullscreen Edit's card


@pytest.mark.qt
@pytest.mark.parametrize("reset", [False, True])
def test_fullscreen_edit_puts_rotate_on_the_expanded_cards_row_clear_of_the_overlays(display, tmp_path, reset):
    from tests.test_visualizer_expansion_fullscreen_edit import (
        _Fullscreen,
        _manager,
        _ordinary_card,
        _projection,
        _seed,
        _shown_and_settled,
        _Visualizer,
    )

    settings = _manager(tmp_path)
    seeded = _seed(settings, now_playing={"media_controls": True})
    _draw(display, media=_Media(), config=_projection(seeded))
    _open(display)
    edit = _Fullscreen(display, settings, _Visualizer("spectrum", _ordinary_card()))
    assert edit.start()
    try:
        _shown_and_settled(display)
        _offer(display, reset=reset, expand=False)               # Reset Camera beside it is test-owned (the order)
        rotate = "customLayoutRotateContent-fullscreen_overlay.visualizer"
        expected = (rotate,) + (("visualizerCameraResetGlyph",) if reset else ())
        members = _row(display, (rotate,) + CARD_ROW)
        _assert_one_row(members, _card_rect(display), expected)
        # Overlays moved into the right-hand column keep clear of the whole row, Edit's rotate included.
        for part in ("preset", "now_playing"):
            edit.drag(part, WIDTH, HEIGHT, steps=10)
        _run(display, 200)
        for name in SLOTS:
            overlay = _rect(_slot(display, name), display)
            assert overlay.right() > WIDTH * 0.75, name          # it really went into the column
            for member, rect in members:
                assert not overlay.intersects(rect), (name, member)
    finally:
        edit.owner.cancel()
