"""The glyphs, Now Playing and the neighbour display under each display style (Current_Plan 1D.2, box 5).

On the production ``DisplayScene.qml`` through the hidden ``QQuickRenderControl`` host (no window is ever shown):

* The glyph row's inset is relative to the card: ``max(12, border + 6)`` of the frame each style draws (Hide
  Borders: its floor). The overlays' safe area is the card inset by its frame's border plus ``max(24, 2.5 %)``.
* One stored placement, three renderings: a placed overlay sits at the same fractions of the safe area in every style
  (placements are never rewritten by a style).
* The overlays' own optional cards keep the widget cards' chrome (border width, corner radius, shadow), whatever frame
  the expanded card is handed.
* The neighbour display (a second hidden host in the same share group, as every product display window) draws exactly
  the same pixels whatever style the expanded display takes.
"""
from __future__ import annotations

import pytest

from core.settings.fullscreen_overlays import DISPLAY_STYLES, canonical_fullscreen_overlays

pytestmark = pytest.mark.qt

DISPLAY = (960, 600)
CARD = {"border_width": 5.0, "corner_radius": 8.0, "content_inset": 0.0, "background_color": (20, 22, 26, 200),
        "border_color": (230, 234, 240, 255), "shadow_enabled": True, "shadow_color": (0, 0, 0, 150),
        "shadow_blur": 12.0, "shadow_offset": (0.0, 4.0), "shadow_spread": 0.0,
        "shadow_extensions": (0.0, 0.0, 0.0, 2.0)}
OFFSET = (0.125, 0.0625)


@pytest.fixture
def host(qt_app):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    display = HiddenDisplayHost(*DISPLAY, dpr=1.25, share=True)
    try:
        yield display
    finally:
        display.close()


def _records(style: str, dpr: float = 1.25):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation,
        resolve_visualizer_presentation,
    )

    ordinary = resolve_visualizer_presentation(policy=get_visualizer_presentation_policy("devcurve"),
                                               display_size=DISPLAY, outer_origin=(24.0, 300.0), dpr=dpr, **CARD)
    return ordinary, resolve_expanded_visualizer_presentation(ordinary, display_size=DISPLAY, dpr=dpr,
                                                              display_style=style)


def _show(host, record) -> None:
    from widgets.spotify_visualizer.expanded_overlays import resolve_expanded_overlay_config

    value = canonical_fullscreen_overlays()
    value["preset"].update(offset_x=OFFSET[0], offset_y=OFFSET[1], corner="top_left", card=True, always_show=True)
    scene = host.scene
    scene.apply_visualizer_presentation(record, active=True)
    scene.set_visualizer_expanded_overlay_config(resolve_expanded_overlay_config({"fullscreen_overlays": value}))
    scene.announce_visualizer_preset("Test Preset", reveal=True)
    scene.set_visualizer_expanded_overlays_drawn(True)
    for _ in range(4):
        host.render()


def _facts(host) -> dict:
    from PySide6.QtQuick import QQuickItem

    scene = host.scene
    root = scene._visualizer_root
    stage = scene._expanded_overlay_stage()
    assert stage is not None, "the overlays did not load"
    slot = stage.findChild(QQuickItem, "expandedOverlayPreset")
    return {
        "glyph_inset": float(root.property("glyphRowInset")),
        "safe_inset": float(stage.property("safeInset")),
        "safe": (float(stage.property("safeWidth")), float(stage.property("safeHeight"))),
        "stage": (stage.width(), stage.height()),
        "slot": (slot.x(), slot.y()),
        "card_chrome": (float(stage.property("cardBorderWidth")), float(stage.property("cornerRadius")),
                        bool(stage.property("cardShadowEnabled"))),
        "slot_padding": float(slot.property("padding")),
        "font": float(slot.property("fontSize")),
    }


@pytest.mark.parametrize("style", DISPLAY_STYLES)
def test_glyphs_and_overlays_are_placed_by_the_note(host, style):
    ordinary, record = _records(style)
    _show(host, record)
    facts = _facts(host)
    frame_border = record.border_width
    # The glyph row: relative to the card, inset by the frame's border plus 6, never under 12.
    assert facts["glyph_inset"] == max(12.0, frame_border + 6.0)
    # The safe area: the card inset by its frame's border plus max(24, 2.5 % of the shorter side).
    width, height = facts["stage"]
    from widgets.spotify_visualizer.presentation_geometry import resolve_card_drawn_rect

    assert (width, height) == pytest.approx(resolve_card_drawn_rect(record)[2:], abs=1e-4)   # the card as drawn
    assert facts["safe_inset"] == round(max(24.0, min(width, height) * 0.025)) + frame_border
    # One stored placement: the same fractions of the safe area from its corner, in every style.
    safe_width, safe_height = facts["safe"]
    assert facts["slot"] == pytest.approx((facts["safe_inset"] + OFFSET[0] * safe_width,
                                           facts["safe_inset"] + OFFSET[1] * safe_height), abs=1e-6)
    # The overlay's own card: the widget cards' chrome, never the style's frame.
    assert facts["card_chrome"] == (ordinary.border_width, float(ordinary.shell_style["corner_radius"]),
                                    bool(ordinary.shell_style["shadow_enabled"]))
    assert facts["slot_padding"] == round(facts["font"] * 0.5) + ordinary.border_width


def test_negative_control_overlay_cards_following_the_frame_lose_the_widget_chrome(host, monkeypatch):
    """Without ``overlay_chrome`` (the record as the frame alone would give it), Hide Borders' overlay card would draw
    no border, square corners and no shadow: the bar above sees it."""
    from dataclasses import replace

    from widgets.spotify_visualizer.render_state import FrozenFields

    ordinary, record = _records("hide_borders")
    _show(host, replace(record, overlay_chrome=FrozenFields()))
    facts = _facts(host)
    assert facts["card_chrome"] == (0.0, 0.0, False)
    assert facts["card_chrome"] != (ordinary.border_width, float(ordinary.shell_style["corner_radius"]), True)


def test_the_neighbour_displays_pixels_never_change_with_the_style(host):
    """Two hidden hosts in one share group stand in for two display windows: the neighbour draws exactly the same
    pixels before and after the expanded display takes each style in turn (its window never reaches past a shared
    edge, and nothing is shared between the scenes)."""
    import numpy

    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    neighbour = HiddenDisplayHost(*DISPLAY, dpr=1.25, share=True)
    try:
        ordinary, _record = _records("default")
        neighbour.scene.apply_visualizer_presentation(ordinary, active=True)
        neighbour.render()
        before = neighbour.read()
        for style in DISPLAY_STYLES:
            _show(host, _records(style)[1])
            neighbour.render()
            assert numpy.array_equal(neighbour.read(), before), style
        # The check is not vacuous: the expanded display itself does change with the style.
        frames = []
        for style in DISPLAY_STYLES:
            _show(host, _records(style)[1])
            frames.append(host.read())
        assert not numpy.array_equal(frames[0], frames[1]) and not numpy.array_equal(frames[1], frames[2])
    finally:
        neighbour.close()
