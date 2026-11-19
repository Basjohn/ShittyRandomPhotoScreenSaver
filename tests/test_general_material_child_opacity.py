"""Import-free checks of paired global child material overrides and persistence.

No PySide6 installation is required. Actual visual pixels and Settings widget
interaction still require acceptance against the Windows frozen build.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _pure_resolver():
    path = ROOT / "rendering/quick/widgets/surface_material.py"
    source = ast.parse(path.read_text(encoding="utf-8"))
    func = next(node for node in source.body if isinstance(node, ast.FunctionDef)
                and node.name == "resolve_media_controls_surface_mode")
    namespace = {"Mapping": Mapping}
    exec(compile(ast.Module(body=[func], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["resolve_media_controls_surface_mode"]


def test_media_choice_migrates_old_settings_without_changing_the_media_card():
    resolver = _pure_resolver()
    assert resolver({}) == "inherit"
    assert resolver({"media": {"controls_surface_material": "flat"}}) == "normal"
    assert resolver({"media": {"controls_surface_material": "normal"}}) == "normal"
    assert resolver({"media": {"controls_surface_material": "inherit"}}) == "inherit"
    assert resolver({"media": {"controls_surface_material": "normal"},
                     "global": {"media_controls_surface_mode": "inherit"}}) == "inherit"
    assert resolver({"media": {"controls_surface_material": "inherit"},
                     "global": {"media_controls_surface_mode": "normal"}}) == "normal"
    assert resolver({"global": {"media_controls_surface_mode": "invalid"}}) == "inherit"


def test_two_new_opacity_adjustments_use_exact_original_zero():
    from core.settings.surface_opacity import adjusted_surface_density, resolve_opacity_adjust
    for target in ("header_surface", "media_controls"):
        assert resolve_opacity_adjust({}, target) == 0.0
        assert resolve_opacity_adjust({"global": {f"{target}_opacity_adjust": -0.35}}, target) == -0.35
        assert resolve_opacity_adjust({"global": {f"{target}_opacity_adjust": 2}}, target) == 1.0
        assert resolve_opacity_adjust({"global": {f"{target}_opacity_adjust": -2}}, target) == -1.0
    for density in (0.0, 0.1, 0.4, 0.72, 1.0):
        assert adjusted_surface_density(density, 0.0) == density


def test_general_page_houses_both_controlled_surfaces_and_both_sliders():
    defaults = read("ui/tabs/widgets_tab_defaults.py")
    media_ui = read("ui/tabs/widgets_tab_media.py")
    conf = read("core/settings/default_settings.py")
    for name in ("header_surface", "media_controls"):
        assert f'add_material_opacity_slider("{name}",' in defaults
        assert f'("{name}", "settings", "widget")' not in defaults
        assert f'"{name}_opacity_adjust"' in conf.replace("'", '"')
    assert '"Header Surface:"' in defaults
    assert '"Media Bar Surface:"' in defaults
    assert '"media_controls_surface_mode"' in defaults
    assert 'resolve_media_controls_surface_mode(widgets_config)' in defaults
    assert '"Control Bar Surface:"' not in media_ui
    assert 'tab.media_controls_surface_material' not in media_ui
    assert 'for target in ("border_surface", "header_surface", "media_controls", "settings", "widget"):' in defaults
    assert '"media_controls_surface_mode" in global_values' in read("rendering/quick/widgets/surface_material.py")


def test_header_only_adjustment_projects_to_all_nine_branded_headers():
    host = read("rendering/quick/widgets/host.py")
    styler = read("rendering/quick/widgets/surface_material.py")
    header = read("rendering/quick/qml/BrandedHeader.qml")
    child = read("rendering/quick/qml/ChildMaterialSurface.qml")
    assert '("cardHeaderSurfaceOpacityAdjust", "header_surface_opacity_adjust")' in host
    assert 'header_surface_opacity_adjust=header_adjustment' in styler
    assert 'additionalOpacityAdjust: header.materialOpacityAdjust' in header
    assert 'SurfaceContrast.adjustedDensity(fillColor.a, materialOpacityAdjust)' in header
    assert 'child.resolvedOpacityAdjust + child.additionalOpacityAdjust' in child
    for fname, owner in {
        "RedditPresentation.qml": "redditRoot", "FeedPresentation.qml": "feedRoot",
        "FriendPulsePresentation.qml": "friendRoot", "SystemStatsPresentation.qml": "statsRoot",
        "AbandonmentIssuesPresentation.qml": "abandonmentRoot", "GmailPresentation.qml": "gmailRoot",
        "AchievementPulsePresentation.qml": "achievementRoot", "MediaPresentation.qml": "mediaRoot",
        "GamesYouFollowPresentation.qml": "followsRoot",
    }.items():
        assert f"materialOpacityAdjust: {owner}.cardHeaderSurfaceOpacityAdjust" in read(
            "rendering/quick/qml/" + fname)


def test_both_media_bars_receive_shared_adjustment_without_touching_the_outer_media_card():
    media = read("rendering/quick/widgets/media.py")
    ordinary = read("rendering/quick/qml/MediaPresentation.qml")
    fullscreen = read("rendering/quick/qml/ExpandedVisualizerOverlays.qml")
    bar = read("rendering/quick/qml/MediaTransportBar.qml")
    assert '"childOpacityAdjust": self.controlsSurfaceOpacityAdjust' in media
    assert 'return float(self.style.card_style.media_controls_opacity_adjust)' in media
    assert 'materialChildOpacityAdjust: mediaRoot.mediaModel.controlsSurfaceOpacityAdjust' in ordinary
    assert 'materialChildOpacityAdjust: overlays.mediaLook("childOpacityAdjust", 0.0)' in fullscreen
    assert 'additionalOpacityAdjust: bar.materialChildOpacityAdjust' in bar
    assert 'SurfaceContrast.adjustedDensity(effectiveSurfaceColor.a, materialChildOpacityAdjust)' in bar
    assert 'legibilityPanel: false' in bar
    assert 'legibilityPanel: true' in read("rendering/quick/qml/BrandedHeader.qml")
    assert 'property bool legibilityPanel: true' in read("rendering/quick/qml/ChildMaterialSurface.qml")
    # The existing card opacity adjustment and colour channels stay separate.
    assert 'materialOpacityAdjust: mediaRoot.cardSurfaceOpacityAdjust' in ordinary
    assert 'materialFillColor: mediaRoot.mediaModel.appVolumeTrackColor' in ordinary
