"""Fullscreen Now Playing Normal fill ownership, independent of Qt rendering.

Live-pixel acceptance remains a Windows Qt gate in the temporary material audit.
These checks deliberately target the canonical owner and QML activation/colour
contracts, including the previously broken source-vs-runtime distinction.
"""
from __future__ import annotations

from pathlib import Path

from core.settings.fullscreen_overlays import canonical_fullscreen_overlays, normalize_fullscreen_overlays

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_neutral_defaults_use_semantic_normal_card_alpha_not_fixed_alpha() -> None:
    defaults = canonical_fullscreen_overlays()["now_playing"]
    for key in ("bar_fill_opacity_adjust", "card_fill_opacity_adjust"):
        assert -1.0 <= float(defaults[key]) <= 1.0
    stage = source("rendering/quick/qml/ExpandedVisualizerOverlays.qml")
    slot = source("rendering/quick/qml/ExpandedOverlaySlot.qml")
    assert 'cardSurfaceMode: "normal"' in stage
    assert 'materialMode: "normal"' in stage
    assert 'surfaceColor: Qt.rgba(authoredBarColor.r, authoredBarColor.g,' in stage
    assert 'authoredBarColor.b, overlays.cardColor.a)' in stage
    assert 'SurfaceContrast.adjustedDensity(stage.cardColor.a, cardFillOpacityAdjust)' in slot
    assert 'surfaceMaterial: slot.cardSurfaceMode === "inherit" ? slot.stage.surfaceMaterial : slot.cardSurfaceMode' in slot
    assert 'materialBackdrop: null // The fullscreen Normal fill' in stage
    assert 'surfaceBackdrop: slot.cardSurfaceMode === "normal" ? null : slot.stage.surfaceBackdrop' in slot
    assert 'materialChildOpacityAdjust: Number(nowPlayingSlot.options.bar_fill_opacity_adjust || 0.0)' in stage
    assert 'cardFillOpacityAdjust: Number(options.card_fill_opacity_adjust || 0.0)' in stage


def test_opacity_roundtrip_clamps_and_preserves_legacy_fields() -> None:
    old = {'now_playing': {'card': True, 'media_controls_style': 'floating',
                           'child_geometry': {}, 'offset_x': 0.12}}
    baseline = normalize_fullscreen_overlays(old)
    canonical = canonical_fullscreen_overlays()["now_playing"]
    for key in ("bar_fill_opacity_adjust", "card_fill_opacity_adjust"):
        assert baseline["now_playing"][key] == canonical[key]
    request = {'now_playing': {**baseline['now_playing'], 'bar_fill_opacity_adjust': -0.35,
                                'card_fill_opacity_adjust': 0.65}}
    parsed = normalize_fullscreen_overlays(request)
    assert parsed['now_playing']['bar_fill_opacity_adjust'] == -0.35
    assert parsed['now_playing']['card_fill_opacity_adjust'] == 0.65
    assert parsed['now_playing']['media_controls_style'] == 'floating'
    assert parsed['now_playing']['card'] is True
    assert parsed['now_playing']['offset_x'] == 0.12
    assert normalize_fullscreen_overlays(parsed) == parsed
    for bad in (-float('inf'), float('nan'), float('inf'), 'bad', None, True):
        assert normalize_fullscreen_overlays({'now_playing': {'bar_fill_opacity_adjust':bad}})['now_playing']['bar_fill_opacity_adjust'] == canonical_fullscreen_overlays()["now_playing"]["bar_fill_opacity_adjust"]
    assert normalize_fullscreen_overlays({'now_playing': {'card_fill_opacity_adjust':3}})['now_playing']['card_fill_opacity_adjust'] == 1.0
    assert normalize_fullscreen_overlays({'now_playing': {'card_fill_opacity_adjust':-3}})['now_playing']['card_fill_opacity_adjust'] == -1.0


def test_controls_share_one_fullscreen_settings_owner_and_leave_ordinary_media_alone() -> None:
    settings = source("ui/tabs/visualizers_fullscreen_page.py")
    assert '"bar_fill_opacity_adjust"' in settings
    assert '"card_fill_opacity_adjust"' in settings
    assert 'self._set_value(("now_playing", field), n / 100)' in settings
    assert 'with QSignalBlocker(slider)' in settings
    stage = source("rendering/quick/qml/ExpandedVisualizerOverlays.qml")
    assert 'id: presetSlot' in stage and 'id: nowPlayingSlot' in stage
    assert stage.index('cardSurfaceMode: "normal"') > stage.index('id: nowPlayingSlot')
    assert 'materialBackdrop: null' in stage
    assert 'id: nowPlayingSlot' in stage
    assert 'overlays.mediaLook("materialMode", "inherit")' not in stage
    ordinary = source("rendering/quick/qml/MediaPresentation.qml")
    assert 'MediaTransportBar {' in ordinary
    assert 'materialBackdrop' in ordinary
