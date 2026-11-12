"""The expanded card's display styles (Current_Plan 1D.2; plan 01 M3c "Display styles of the expanded card").

A style changes only two inputs of the display-wide resolver (``resolve_expanded_visualizer_presentation``): the
margin (the card's inset from the display's visible rect) and the frame (border width, corner radius, and the card
shadow, which nothing of can reach the display once the card meets its edges). Everything else is the existing path.

* Default reproduces, field for field and bit for bit, the record the resolver returned before display styles existed
  (``tests/fixtures/expanded_default_style_geometry.json``, recorded from the pre-1D.2 resolver; 420 cases: a carded
  2D mode, a framed 3D mode and a frameless mode, five ordinary cards, four chromes, seven displays). Negative
  control: a margin one logical pixel larger misses it.
* Borders To Edge: margin 0, the ordinary border width and colour, square outer corners (lead, 12 Nov), no shadow.
* Fullscreen (Hide Borders): margin 0, no border, square corners, no shadow; the content rect is the display.
* Every style keeps the world rule (contained, never cropped or stretched; the long axis grows) and the drawn card on
  whole device pixels inside the display at 100 %, 125 % and 150 %, on both axes.

All inputs are test-owned (``tests/_expanded_display_style_cases.py``); nothing reads Settings or authored presets.
"""
from __future__ import annotations

import math

import pytest

from core.settings.fullscreen_overlays import (
    DISPLAY_STYLE_BORDERS_TO_EDGE,
    DISPLAY_STYLE_DEFAULT,
    DISPLAY_STYLE_HIDE_BORDERS,
    DISPLAY_STYLES,
)
from core.settings.visualizer_mode_registry import VisualizerShellPolicy
from tests._expanded_display_style_cases import (
    CARDS,
    CHROMES,
    DISPLAYS,
    MODES,
    cases,
    load_baseline,
    ordinary,
    record_fields,
)
from widgets.spotify_visualizer import presentation_geometry
from widgets.spotify_visualizer.presentation_geometry import (
    expanded_card_inset,
    framed_aperture_scale,
    resolve_card_clip_path,
    resolve_card_drawn_rect,
    resolve_expanded_visualizer_presentation,
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_state import ResolvedVisualizerPresentation

NEW_STYLES = (DISPLAY_STYLE_BORDERS_TO_EDGE, DISPLAY_STYLE_HIDE_BORDERS)


def _mismatches(baseline, *, display_style=None):
    """Labels whose Default record differs from the pre-1D.2 baseline (any baseline field, bit for bit)."""
    defaults = {field: getattr(ResolvedVisualizerPresentation.__dataclass_fields__[field], "default", None)
                for field in ResolvedVisualizerPresentation.__dataclass_fields__}
    wrong = []
    for label, record, size, dpr in cases():
        kwargs = {} if display_style is None else {"display_style": display_style}
        expanded = resolve_expanded_visualizer_presentation(record, display_size=size, dpr=dpr, **kwargs)
        fields = record_fields(expanded)
        expected = baseline[label]
        if any(fields[name] != value for name, value in expected.items()):
            wrong.append(label)
            continue
        # A field added since (the style's own record facts) holds its dataclass default: the record is the same.
        for name in set(fields) - set(expected):
            if getattr(expanded, name) != defaults[name]:
                wrong.append(label)
                break
    return wrong


def test_default_reproduces_todays_record_bit_for_bit():
    baseline = load_baseline()
    assert len(baseline) == sum(1 for _case in cases()) == 420
    assert _mismatches(baseline) == []                                   # the owner's call shape: no style passed
    assert _mismatches(baseline, display_style=DISPLAY_STYLE_DEFAULT) == []


def test_negative_control_a_one_pixel_margin_misses_todays_record(monkeypatch):
    baseline = load_baseline()
    monkeypatch.setattr(presentation_geometry, "EXPANDED_CARD_EDGE_GAP", presentation_geometry.EXPANDED_CARD_EDGE_GAP
                        + 1.0)
    wrong = _mismatches(baseline, display_style=DISPLAY_STYLE_DEFAULT)
    # Every case misses but some on the tiny display, whose quarter cap binds before the gap does.
    assert {label for label in baseline if not label.endswith("|tiny")} <= set(wrong)


def _expected_frame(style: str, ordinary_record):
    border = float(ordinary_record.shell_style["authored_border_width"])
    return {DISPLAY_STYLE_BORDERS_TO_EDGE: (border, 0.0), DISPLAY_STYLE_HIDE_BORDERS: (0.0, 0.0)}[style]


@pytest.mark.parametrize("style", NEW_STYLES)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("chrome", list(CHROMES))
@pytest.mark.parametrize("card", list(CARDS))
@pytest.mark.parametrize("display", [name for name in DISPLAYS if name != "tiny"])
def test_a_style_changes_only_the_margin_and_the_frame(style, mode, chrome, card, display):
    """The new styles are the canonical resolver with margin 0 and the style's frame; the world, extent and scale
    rule is the Default's, applied to the whole display."""
    size, dpr = DISPLAYS[display]
    base = ordinary(mode, card, chrome, display)
    expanded = resolve_expanded_visualizer_presentation(base, display_size=size, dpr=dpr, display_style=style)
    border, radius = _expected_frame(style, base)
    width, height = size
    carded = base.shell_policy is VisualizerShellPolicy.CARD
    assert expanded.outer_rect == (0.0, 0.0, width, height)
    assert expanded.border_width == (border if carded else 0.0)
    assert expanded.shell_style["corner_radius"] == 0.0 and expanded.shell_style["inner_corner_radius"] == 0.0
    assert expanded.shell_style["shadow_enabled"] is False
    # The rest of the chrome (colours, surface) is the card's.
    for key in ("background_color", "border_color", "shadow_color"):
        assert expanded.shell_style[key] == base.shell_style[key], key
    # Same world rule as Default: contained (the long axis grows), one uniform scale onto the whole display.
    (ew, eh), (xw, xh) = base.viewport_extent, expanded.viewport_extent
    assert xw >= ew - 1e-9 and xh >= eh - 1e-9
    assert math.isclose(xw, ew, rel_tol=1e-12) or math.isclose(xh, eh, rel_tol=1e-12)
    assert math.isclose(xw / xh, width / height, rel_tol=1e-12)
    assert math.isclose(xw * expanded.uniform_visual_scale, width, rel_tol=1e-12)
    # Shell, clip policy, orientation, fades and DPR are the ordinary record's (only the target DPR may differ).
    assert (expanded.shell_policy, expanded.clip_policy, expanded.content_rotation_quarters) == (
        base.shell_policy, base.clip_policy, base.content_rotation_quarters)
    assert expanded.expanded_display is True and expanded.dpr == dpr
    assert expanded.display_style == style
    # Exactly the canonical resolver handed margin 0 and the style's frame (no style-specific geometry).
    direct = resolve_visualizer_presentation(
        policy=presentation_geometry.VisualizerModePresentationPolicy(
            shell_policy=base.shell_policy, clip_policy=base.clip_policy,
            viewport_resize_capable=base.viewport_resize_capable),
        display_size=size, outer_origin=(0.0, 0.0), dpr=dpr, uniform_visual_scale=expanded.uniform_visual_scale,
        viewport_extent=expanded.viewport_extent, committed_outer_size=(width, height),
        content_rotation_quarters=base.content_rotation_quarters, expanded_display=True,
        scene_fade=base.scene_fade, content_fade=base.content_fade, border_width=border, corner_radius=radius,
        content_inset=float(base.shell_style["content_inset"]) / base.uniform_visual_scale,
        background_color=base.shell_style["background_color"], border_color=base.shell_style["border_color"],
        shadow_enabled=False, shadow_color=base.shell_style["shadow_color"], shadow_blur=0.0,
        shadow_offset=(0.0, 0.0), shadow_spread=0.0, shadow_extensions=(0.0, 0.0, 0.0, 0.0))
    for name in ("outer_rect", "content_rect", "viewport_extent", "uniform_visual_scale", "border_width",
                 "current_aspect_ratio"):
        assert getattr(expanded, name) == getattr(direct, name), name
    assert expanded.shell_style["corner_radius"] == direct.shell_style["corner_radius"]


@pytest.mark.parametrize("style", NEW_STYLES)
def test_hide_borders_content_is_the_whole_display_and_borders_to_edge_frames_it(style):
    size, dpr = DISPLAYS["3840x2160_150"]
    base = ordinary("devcurve", "canonical", "no_shadow", "3840x2160_150")
    expanded = resolve_expanded_visualizer_presentation(base, display_size=size, dpr=dpr, display_style=style)
    clip, clip_radius = resolve_card_clip_path(expanded)
    border = expanded.border_width
    edge = math.floor(border * dpr + 0.5) / dpr          # the frame's inner edge as Qt draws its pen (R-191)
    assert clip == (edge, edge, size[0] - 2 * edge, size[1] - 2 * edge) and clip_radius == 0.0
    if style == DISPLAY_STYLE_HIDE_BORDERS:
        assert border == 0.0 and expanded.content_rect == (0.0, 0.0, *size)
    else:
        assert border == float(base.shell_style["authored_border_width"]) > 0.0


def test_an_unknown_style_is_refused_by_the_resolver():
    base = ordinary("devcurve", "canonical", "no_shadow", "1920x1080_100")
    with pytest.raises(ValueError):
        resolve_expanded_visualizer_presentation(base, display_size=(1920.0, 1080.0), display_style="edge")


@pytest.mark.parametrize("style", DISPLAY_STYLES)
@pytest.mark.parametrize("display", [name for name in DISPLAYS if name != "tiny"])
def test_each_styles_drawn_card_is_on_whole_device_pixels_inside_the_display(style, display):
    """At 100 %, 125 % and 150 % on both axes: the drawn card's every edge is a whole device pixel and lies inside
    the display's visible rect (the margin-0 styles' outer edges are exactly the display's)."""
    size, dpr = DISPLAYS[display]
    for card in CARDS:
        base = ordinary("extruded_bubble", card, "shadow_se", display)
        expanded = resolve_expanded_visualizer_presentation(base, display_size=size, dpr=dpr, display_style=style)
        x, y, width, height = resolve_card_drawn_rect(expanded)
        device = [value * dpr for value in (x, y, x + width, y + height)]
        assert all(abs(value - round(value)) < 1e-6 for value in device), (card, device)
        assert device[0] >= -1e-6 and device[1] >= -1e-6
        assert device[2] <= round(size[0] * dpr) + 1e-6 and device[3] <= round(size[1] * dpr) + 1e-6
        if style != DISPLAY_STYLE_DEFAULT:
            assert [round(value) for value in device] == [0, 0, round(size[0] * dpr), round(size[1] * dpr)]


@pytest.mark.parametrize("style", DISPLAY_STYLES)
def test_the_framed_camera_aperture_follows_each_styles_extent(style):
    """The framed camera standard: the lens and pose stay; the aperture follows the extent's height (a margin-0
    card on a display wider than the world keeps its aperture; on a narrower one it opens)."""
    for display in ("1920x1080_100", "portrait_100"):
        size, dpr = DISPLAYS[display]
        base = ordinary("extruded_bubble", "canonical", "shadow_se", display)
        expanded = resolve_expanded_visualizer_presentation(base, display_size=size, dpr=dpr, display_style=style)
        assert framed_aperture_scale(expanded) == expanded.viewport_extent[1] / expanded.baseline_viewport_size[1]
        if size[0] / size[1] >= base.viewport_extent[0] / base.viewport_extent[1]:
            assert framed_aperture_scale(expanded) == framed_aperture_scale(base)
        else:
            assert framed_aperture_scale(expanded) > framed_aperture_scale(base)


def test_the_overlay_cards_keep_the_ordinary_chrome_in_every_style():
    """Now Playing's and the preset toast's optional Card draw the widget cards' own chrome (the ordinary record's
    border, radius and shadow), whatever frame the expanded card is handed; Default carries nothing extra."""
    size, dpr = DISPLAYS["1920x1080_125"]
    base = ordinary("devcurve", "canonical", "shadow_se", "1920x1080_125")
    default = resolve_expanded_visualizer_presentation(base, display_size=size, dpr=dpr)
    assert len(default.overlay_chrome) == 0
    for style in NEW_STYLES:
        expanded = resolve_expanded_visualizer_presentation(base, display_size=size, dpr=dpr, display_style=style)
        chrome = expanded.overlay_chrome
        assert chrome["border_width"] == default.border_width
        assert chrome["corner_radius"] == default.shell_style["corner_radius"]
        for key in ("shadow_enabled", "shadow_color"):
            assert chrome[key] == default.shell_style[key], key
        for key in ("shadow_blur", "shadow_offset"):
            assert chrome[key] == pytest.approx(default.shell_style[key], abs=1e-9), key
        assert chrome["shadow_enabled"] is True and chrome["border_width"] > 0.0      # the case is discriminating


def test_the_inset_helper_is_unchanged_and_default_only():
    base = ordinary("devcurve", "canonical", "shadow_se", "1920x1080_100")
    default = resolve_expanded_visualizer_presentation(base, display_size=(1920.0, 1080.0))
    assert default.outer_rect[0] == expanded_card_inset(base)
