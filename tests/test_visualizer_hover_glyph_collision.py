"""The Visualizer card's common hover glyphs (Restore, the display-transfer arrows) never collide with the card's own
bottom-right glyph row, at any card size (plan 1E side defect).

Both groups are laid out by different owners (``WidgetHoverEditGlyphs.qml`` for the common set, ``glyphRow`` in
``VisualizerPresentation.qml`` for the card's own controls); the card hands the common set the row's occupied space.
The bars run the production scene in the hidden ``QQuickRenderControl`` host (no window is shown) and assert structure
only: every visible glyph of either group stays inside the card and no two of them overlap. Sizes are test-owned.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF

from tests.test_visualizer_glyph_row import (
    CARD_ROW,
    _card_rect,
    _named,
    _offer,
    _ordinary,
    _rect,
    _row,
    _scene,
    display,  # noqa: F401  (the fixture)
)
from tests.test_visualizer_expansion_overlays import _run, _settle, _visual

COMMON = ("hoverEditGlyph-restore", "hoverEditGlyph-close", "hoverEditGlyph-transfer_left",
          "hoverEditGlyph-transfer_right")


def _hover_all(display) -> None:
    root = display.scene._visualizer_root
    root.setProperty("displayTransferLeftAvailable", True)
    root.setProperty("displayTransferRightAvailable", True)
    display.scene.set_visualizer_expand_glyph(True, False, sides=(True, True))
    _offer(display, reset=True, expand=True, studio=True, rotate=True)
    _settle(display, lambda: (float(root.property("expandLeftPresence")), float(root.property("expandRightPresence")))
            == (1.0, 1.0) and _find(display, "visualizerHoverEditGlyphs") is not None)
    _run(display, 60)
    _find(display, "visualizerHoverEditGlyphs").setProperty("hovered", True)
    _run(display, 80)


def _find(display, name):
    found = [item for item in _visual(_scene(display)) if item.objectName() == name]
    return found[0] if found else None


def _common(display) -> list[tuple[str, QRectF]]:
    shown = []
    for name in COMMON:
        item = _find(display, name)
        if item is not None and item.isVisible():
            shown.append((name, _rect(item, display)))
    return shown


@pytest.mark.qt
@pytest.mark.parametrize("extent", [(150.0, 70.0), (260.0, 110.0), (420.0, 200.0), None], ids=[
    "narrow", "mid", "wide", "ordinary"])
def test_common_hover_glyphs_never_collide_with_the_cards_glyph_row(display, extent):
    _ordinary(display, extent=extent)
    _hover_all(display)
    common = _common(display)
    assert {name for name, _r in common} == set(COMMON), common      # all three are offered and shown
    members = _row(display, CARD_ROW)
    assert members
    card = _card_rect(display)
    everything = common + members
    for name, rect in everything:
        assert card.contains(rect), (name, rect, card)
    for index, (name, rect) in enumerate(everything):
        for other, other_rect in everything[index + 1:]:
            same_group = (name in COMMON) == (other in COMMON)
            if same_group and name not in COMMON:
                continue                                              # the row's own spacing is pinned elsewhere
            assert not rect.intersects(other_rect), (name, other, rect, other_rect)
