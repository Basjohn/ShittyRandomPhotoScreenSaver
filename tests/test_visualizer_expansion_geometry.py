"""Expanded Visualizer M2: the display-wide viewport (plan 01 §B2, §0.6, §H Milestone 2 / Gate 2).

The pure variant (``resolve_expanded_visualizer_presentation``) is checked on 16:9, 16:10, 21:9, portrait and three
DPRs for canonical, edge-resized (wide and tall) and chromed cards: the outer rect is the display inset by only the
card's own chrome (amended 7 Nov: much closer to the borders than the ordinary edge margin), the ordinary world stays
whole (contained, never cropped, never stretched), and the shell, clip, chrome and orientation
are the ordinary record's. The production owner (``QuickDisplayVisualizerOwner`` on an unshown
``QuickDisplayRuntime``, driven through its real ``sync_present`` publication edge by
``tools/expanded_visualizer_evidence.owner_replay``) shows that record display-wide, restores the ordinary record
byte for byte, publishes identical logical frames, and leaves the ordinary path's resolve/commit pair in place.
All inputs are test-owned; nothing reads Settings or authored presets.
"""
from __future__ import annotations

import math

import pytest

from core.settings.framed_camera import FRAMED_MAX_HORIZONTAL_FOV_DEG, tan_half_fov, viewport_tangents
from core.settings.visualizer_mode_registry import (
    VisualizerClipPolicy,
    VisualizerShellPolicy,
    get_visualizer_presentation_policy,
    iter_all_visualizer_mode_descriptors,
)
from tests._visualizer_presentation import resolve_presentation
from widgets.spotify_visualizer.presentation_geometry import (
    EXPANDED_CARD_EDGE_GAP,
    framed_aperture_scale,
    resolve_expanded_visualizer_presentation,
)

# (logical display size, DPR): 16:9 at 100 %, 3840 x 2160 at 150 %, 16:10, 21:9, portrait, 1920 x 1080 at 125 %.
DISPLAYS = {
    "16x9": ((1920.0, 1080.0), 1.0),
    "16x9_tv_150": ((2560.0, 1440.0), 1.5),
    "16x10": ((1920.0, 1200.0), 1.0),
    "21x9": ((3440.0, 1440.0), 1.0),
    "portrait": ((1080.0, 1920.0), 1.0),
    "16x9_125": ((1536.0, 864.0), 1.25),
}
CHROME = {"border_width": 3.0, "corner_radius": 8.0, "background_color": (20, 22, 26, 200),
          "border_color": (230, 234, 240, 255), "shadow_enabled": True, "shadow_color": (0, 0, 0, 150),
          "shadow_blur": 18.0, "shadow_offset": (0.0, 4.0), "shadow_extensions": (2.0, 2.0, 2.0, 6.0)}
# Ordinary records: canonical card, edge-resized wide and tall CUSTOM worlds, and a uniformly scaled card.
CARDS = {
    "canonical": {"outer_origin": (32.0, 400.0)},
    "custom_wide": {"outer_origin": (96.0, 180.0), "viewport_extent": (840.0, 280.0)},
    "custom_tall": {"outer_origin": (40.0, 40.0), "viewport_extent": (300.0, 520.0)},
    "scaled": {"outer_origin": (10.0, 10.0), "uniform_visual_scale": 1.6},
}


#: Chrome variants (test-owned): the shadow falling south-east with Extra Offset, north-west, none, and no border.
CHROMES = {
    "shadow_se": CHROME,
    "shadow_nw": {**CHROME, "shadow_offset": (-5.0, -3.0), "shadow_extensions": (4.0, 4.0, 0.0, 0.0)},
    "no_shadow": {**CHROME, "shadow_enabled": False},
    "bare": {**CHROME, "border_width": 0.0, "shadow_enabled": False},
}


def _ordinary(card: str, display: str, *, mode: str = "extruded_bubble", chrome: str = "shadow_se"):
    size, dpr = DISPLAYS[display]
    return resolve_presentation(policy=get_visualizer_presentation_policy(mode), display_size=size, dpr=dpr,
                                **CHROMES[chrome], **CARDS[card])


def _expanded(card: str, display: str, *, mode: str = "extruded_bubble", chrome: str = "shadow_se"):
    size, dpr = DISPLAYS[display]
    ordinary = _ordinary(card, display, mode=mode, chrome=chrome)
    return ordinary, resolve_expanded_visualizer_presentation(ordinary, display_size=size, dpr=dpr)


def _chrome_inset(chrome: str, card_scale: float) -> float:
    """Derived from the test-owned chrome alone: the card's border, the shadow's displaced body beyond the card (base
    offset + Extra Offset on its furthest side, drawn at the card's scale), and the code-owned gap."""
    values = CHROMES[chrome]
    reach = 0.0
    if values["shadow_enabled"]:
        (dx, dy), (left, top, right, bottom) = values["shadow_offset"], values["shadow_extensions"]
        reach = max(max(0.0, -dx) + left, max(0.0, -dy) + top, max(0.0, dx) + right, max(0.0, dy) + bottom)
    return values["border_width"] + reach * card_scale + EXPANDED_CARD_EDGE_GAP


@pytest.mark.parametrize("chrome", list(CHROMES))
@pytest.mark.parametrize("display", list(DISPLAYS))
@pytest.mark.parametrize("card", list(CARDS))
def test_the_expanded_card_sits_only_its_chrome_inside_the_display(card, display, chrome):
    """Full display is not edge to edge, and it reaches close to the borders (operator, 7 Nov: "Don't reach nearly
    close enough to the screen borders"): the inset is the card's own chrome (its border, its shadow's displaced
    body) plus a small gap, never the ordinary slot's edge margin. The card keeps that chrome exactly."""
    (width, height), dpr = DISPLAYS[display]
    ordinary, expanded = _expanded(card, display, chrome=chrome)
    inset = _chrome_inset(chrome, ordinary.uniform_visual_scale)
    assert expanded.outer_rect == pytest.approx((inset, inset, width - 2 * inset, height - 2 * inset), abs=1e-9)
    border = ordinary.border_width
    assert expanded.border_width == border == CHROMES[chrome]["border_width"]
    assert expanded.shell_style["corner_radius"] == ordinary.shell_style["corner_radius"]
    assert expanded.content_rect == pytest.approx((inset + border, inset + border, width - 2 * (inset + border),
                                                   height - 2 * (inset + border)), abs=1e-9)
    assert expanded.dpr == dpr
    # The shadow is chrome, drawn as the card draws it: never magnified with the display-wide world (which would
    # push the card back from the borders and darken a wide band around it).
    for key in ("shadow_blur", "shadow_spread"):
        assert expanded.shell_style[key] == pytest.approx(ordinary.shell_style[key], abs=1e-9), key
    for key in ("shadow_offset", "shadow_extensions"):
        assert expanded.shell_style[key] == pytest.approx(ordinary.shell_style[key], abs=1e-9), key
    assert expanded.shell_style["shadow_enabled"] is ordinary.shell_style["shadow_enabled"]


def test_the_inset_is_capped_so_a_card_always_remains():
    ordinary = _ordinary("canonical", "16x9")
    expanded = resolve_expanded_visualizer_presentation(ordinary, display_size=(20.0, 24.0))
    assert expanded.outer_rect == (5.0, 5.0, 10.0, 14.0)


@pytest.mark.parametrize("display", list(DISPLAYS))
@pytest.mark.parametrize("card", list(CARDS))
def test_the_ordinary_world_stays_whole_and_unstretched(card, display):
    (width, height), _dpr = DISPLAYS[display]
    ordinary, expanded = _expanded(card, display)
    inset = expanded.outer_rect[0]
    width, height = width - 2 * inset, height - 2 * inset
    (ew, eh), (xw, xh) = ordinary.viewport_extent, expanded.viewport_extent
    # Contained: the expanded world holds the whole ordinary world and grows on the display's long axis only.
    assert xw >= ew - 1e-9 and xh >= eh - 1e-9
    assert math.isclose(xw, ew, rel_tol=1e-12) or math.isclose(xh, eh, rel_tol=1e-12)
    assert math.isclose(xw / xh, width / height, rel_tol=1e-12)
    # Uniform: one scale maps that world onto the display on both axes (no anisotropic stretch).
    scale = expanded.uniform_visual_scale
    assert math.isclose(xw * scale, width, rel_tol=1e-12) and math.isclose(xh * scale, height, rel_tol=1e-12)


@pytest.mark.parametrize("display", list(DISPLAYS))
def test_shell_clip_chrome_and_orientation_are_the_ordinary_records(display):
    ordinary, expanded = _expanded("custom_wide", display)
    assert (expanded.shell_policy, expanded.clip_policy, expanded.viewport_resize_capable) == (
        ordinary.shell_policy, ordinary.clip_policy, ordinary.viewport_resize_capable)
    assert expanded.shell_policy is VisualizerShellPolicy.CARD
    assert expanded.clip_policy is VisualizerClipPolicy.CARD_INTERIOR
    for key in ("background_color", "border_color", "authored_border_width", "authored_corner_radius",
                "corner_radius", "shadow_enabled", "shadow_color"):
        assert expanded.shell_style[key] == ordinary.shell_style[key], key
    assert expanded.content_rotation_quarters == ordinary.content_rotation_quarters
    assert (expanded.scene_fade, expanded.content_fade) == (ordinary.scene_fade, ordinary.content_fade)


def test_a_frameless_viewport_mode_keeps_its_own_policy():
    ordinary, expanded = _expanded("canonical", "21x9", mode="sphere")
    assert expanded.clip_policy is ordinary.clip_policy is VisualizerClipPolicy.VIEWPORT_RECT
    assert expanded.shell_policy is ordinary.shell_policy
    gap = EXPANDED_CARD_EDGE_GAP                      # frameless: no border, no card shadow
    assert expanded.outer_rect == expanded.content_rect == (gap, gap, 3440.0 - 2 * gap, 1440.0 - 2 * gap)


@pytest.mark.parametrize("display", list(DISPLAYS))
def test_the_framed_camera_keeps_its_lens_and_sees_the_whole_card_world(display):
    """EB's aperture follows the extent height exactly as an edge-resized card's does: on a display wider than the
    card it is unchanged (same vertical world, more width); on a narrower one it opens (same width, more height).
    The frustum's aspect is the content's, so circles stay round."""
    ordinary, expanded = _expanded("canonical", display)
    before, after = framed_aperture_scale(ordinary), framed_aperture_scale(expanded)
    _x, _y, card_width, card_height = expanded.outer_rect
    if card_width / card_height >= 1.5:
        assert after == before
    else:
        assert after > before
    aspect = expanded.viewport_extent[0] / expanded.viewport_extent[1]
    tan_x, tan_y = viewport_tangents(45.0, aspect, after)
    card_x, card_y = viewport_tangents(45.0, ordinary.viewport_extent[0] / ordinary.viewport_extent[1], before)
    max_tan_x = math.tan(math.radians(FRAMED_MAX_HORIZONTAL_FOV_DEG) / 2.0)
    if tan_half_fov(45.0) * after * aspect > max_tan_x:
        # The framed horizontal cap binds on a display this wide: exactly the capped view, at the content's aspect.
        assert tan_x == pytest.approx(max_tan_x) and tan_y == pytest.approx(max_tan_x / aspect)
        assert tan_x >= card_x - 1e-12
    else:
        assert tan_x >= card_x - 1e-12 and tan_y >= card_y - 1e-12    # never crops the card's view


def test_the_ordinary_record_is_never_mutated():
    ordinary = _ordinary("custom_wide", "16x9")
    snapshot = repr(ordinary).encode()
    for display in DISPLAYS:
        resolve_expanded_visualizer_presentation(ordinary, display_size=DISPLAYS[display][0])
    assert repr(ordinary).encode() == snapshot


def test_invalid_inputs_are_refused():
    ordinary = _ordinary("canonical", "16x9")
    with pytest.raises(TypeError):
        resolve_expanded_visualizer_presentation(object(), display_size=(10.0, 10.0))  # type: ignore[arg-type]
    for size in ((0.0, 1080.0), (1920.0, -1.0), (float("nan"), 1080.0)):
        with pytest.raises(ValueError):
            resolve_expanded_visualizer_presentation(ordinary, display_size=size)


# ------------------------------------------------------------------------------- the production owner's route


def card_inset():
    """The replay card's chrome (``tools/expanded_visualizer_evidence.CARD``: a border, no shadow) plus the gap."""
    from tools.expanded_visualizer_evidence import CARD

    assert CARD["shadow_enabled"] is False
    return CARD["border_width"] + EXPANDED_CARD_EDGE_GAP


@pytest.fixture(scope="module")
def looped_clip():
    from tools.expanded_visualizer_evidence import looped_fixture

    return looped_fixture(loops=6)


def _replay(qt_app, clip, mode="extruded_bubble", **kwargs):
    from tools.expanded_visualizer_evidence import owner_replay

    return owner_replay(clip, mode, settings=_frozen(mode), **kwargs)


def _frozen(mode):
    from tests._visualizer_frozen_settings import frozen_visualizer_settings

    return frozen_visualizer_settings(mode)


@pytest.mark.qt
@pytest.mark.parametrize("committed", [None, ((96.0, 180.0, 840.0, 280.0), (840.0, 280.0))],
                         ids=["authored", "custom"])
def test_the_owner_shows_the_display_and_restores_the_ordinary_record_byte_for_byte(qt_app, looped_clip, committed):
    result = _replay(qt_app, looped_clip, expand_at=30, collapse_at=250, animate=True, committed=committed)
    _x, _y, width, height = result["display"]
    records = result["ordinary"]
    margin = card_inset()
    # The production scene drew the card near the display's extents while expanded...
    assert result["drawn"][200] == (margin, margin, width - 2 * margin, height - 2 * margin)
    # ...and the ordinary geometry (record, committed extent, drawn record) came back exactly.
    assert records["before"] == records["after"]
    assert repr(records["before"]).encode() == repr(records["after"]).encode()
    assert records["before_extent"] == records["after_extent"]
    assert records["after_drawn"] == records["after"]
    assert result["drawn"][-1] == tuple(records["before"].outer_rect)
    # Every published frame committed the ordinary extent to the controller, expanded or not.
    assert set(result["extents"]) == {tuple(records["before_extent"])}
    # One fade-through each way, each completing once on the publication edge, after its start.
    (entered, kind_in), (collapsed, kind_out) = result["events"]
    assert (kind_in, kind_out) == ("entered", "collapsed") and 30 < entered < 250 < collapsed


@pytest.mark.qt
@pytest.mark.parametrize("mode", [d.mode_id for d in iter_all_visualizer_mode_descriptors()
                                  if d.supports_expanded_display])
def test_published_logical_frames_are_identical_ordinary_and_expanded(qt_app, looped_clip, mode):
    """Reactivity and payload are untouched for every capable mode (Spectrum's extra bars on the expanded
    horizontal card are drawn from these same frames: ``spectrum_display_bar_count``). Bubble and Waveform Ribbon are extent-sensitive sentinels: their logical worlds read the
    controller's committed extent (Bubble's world, Waveform's visible span), so a display-wide record reaching the
    controller would change their frames (``tools/expanded_visualizer_evidence.leak_control``).

    The one input the logical side legitimately takes from the drawn card is its framed view (R-196, N0.4: Waveform's
    pulse is born at the edge of the part of the scene the drawn card's camera shows), so an expanded owner's frames
    may differ from the ordinary owner's by exactly that. The contract is therefore: every view an owner sends
    (``VIS_SET_VIEW``) carries the ordinary committed metrics, expanded or not; and each owner's frames are exactly
    the logical side's (the engine session, which has no presentation record) fed that owner's own views before
    each tick, as ``test_visualizer_engine_worker`` replays them. Nothing else of the display-wide record reaches
    the frames. Where the framed view does not feed a mode, both reduce to identical frames."""
    clip = looped_clip
    if mode == "waveform_ribbon":
        from tools.expanded_visualizer_evidence import shipped_clip

        clip = shipped_clip(4.0)              # native PCM on every frame (its raw musical lanes need it)
    ordinary = _replay(qt_app, clip, mode)
    from_first = _replay(qt_app, clip, mode, expand_at=0)
    mid_clip = _replay(qt_app, clip, mode, expand_at=40, collapse_at=260, animate=True)
    margin = card_inset()
    assert from_first["drawn"][0] == (margin, margin, from_first["display"][2] - 2 * margin,
                                      from_first["display"][3] - 2 * margin)
    # The committed metrics in every view (extent, rotations, CUSTOM override) are the ordinary owner's.
    metrics = {repr(view[:4]) for view in ordinary["views"]}
    assert len(metrics) == 1
    for run in (from_first, mid_clip):
        assert {repr(view[:4]) for view in run["views"]} == metrics
    for run in (ordinary, from_first, mid_clip):
        assert run["digests"] == _session_digests(clip, mode, run["views"])
    assert len(ordinary["digests"]) == len(clip.frames)
    assert [kind for _frame, kind in mid_clip["events"]] == ["entered", "collapsed"]


def _session_digests(clip, mode, views):
    """The logical side's frames for ``clip`` with ``views`` applied before each tick (the link's shape)."""
    import tools.expanded_visualizer_evidence as evidence
    from core.visualizer_engine.engine_worker import EngineSession
    from core.visualizer_engine.packet_mailbox import PacketMailbox

    before_ticks, sent = [None], None
    for snapshot in views[:-1]:
        before_ticks.append(None if snapshot == sent else snapshot)
        sent = snapshot
    reader = PacketMailbox(role="reader")
    session = EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=9001, settings=_frozen(mode))
    try:
        seen = []
        for feature, view in zip(clip.frames, before_ticks):
            if view is not None:
                session.set_view(**evidence.view_message(view))
            session.tick(feature)
            seen.append(evidence.frame_digest(reader.take().state))
    finally:
        session.close()
        reader.close()
    return seen


@pytest.mark.qt
def test_negative_control_the_digests_see_a_display_wide_record_reaching_the_controller(qt_app, looped_clip):
    """The identity above is not vacuous: committing the display-wide record's metrics (the mistake the owner's
    expanded commit avoids) changes Bubble's published frames."""
    from unittest.mock import patch

    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    def leaky(self, presentation):
        self._presentation_runtime.scene_controller.apply_visualizer_presentation(presentation, active=True)
        self._controller.commit_presentation_metrics(presentation)

    ordinary = _replay(qt_app, looped_clip, "bubble")["digests"]
    with patch.object(QuickDisplayVisualizerOwner, "_apply_expanded_presentation", leaky):
        leaked = _replay(qt_app, looped_clip, "bubble", expand_at=0)["digests"]
    assert leaked != ordinary


@pytest.mark.qt
def test_the_ordinary_path_keeps_its_own_resolve_and_commit(qt_app, looped_clip):
    """Dormancy: after a collapse the sync's pair is the ordinary owner methods again (no wrapper, no per-frame
    branch left behind); while expanded it is the display-wide pair."""
    from PySide6.QtWidgets import QApplication

    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tests._visualizer_presentation import make_visualizer_owner

    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(screen_index=0, runtime_generation=777, screen=QApplication.primaryScreen(),
                                  scene_factory=factory,
                                  window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    owner = make_visualizer_owner(runtime, bar_count=32, initial_mode="extruded_bubble")
    try:
        owner.bind(engine_generation=1, activation_id=1)
        sync = owner._sync
        ordinary_pair = (owner._resolve_current_presentation, owner._apply_resolved_presentation)
        assert (sync._resolve_presentation, sync._commit_presentation) == ordinary_pair
        assert owner.set_expanded_display(True) is True and owner.expanded_display
        assert (sync._resolve_presentation, sync._commit_presentation) == (
            owner._resolve_expanded_presentation, owner._apply_expanded_presentation)
        assert owner.set_expanded_display(False) is True and not owner.expanded_display
        assert (sync._resolve_presentation, sync._commit_presentation) == ordinary_pair
        # Laying out the ordinary card still plans with the ordinary size while expanded.
        owner.set_expanded_display(True)
        assert owner.resolved_outer_size() == (420.0, 280.0)
    finally:
        owner.retire()
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
    assert owner.set_expanded_display(True) is False          # a retired owner changes nothing
