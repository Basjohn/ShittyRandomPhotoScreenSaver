"""Contract tests: bounded, card-owned branded-header material reuse.

Static QML assertions run without installing Qt; real pixels remain a Windows
validation requirement. No new capture, render pass or per-family setting.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
QML=ROOT / "rendering" / "quick" / "qml"


def test_global_header_mode_is_normalized_and_never_needs_its_own_backdrop():
    # Execute only the pure resolver, without importing PySide6 in this CI runner.
    import ast
    src=(ROOT / "rendering/quick/widgets/surface_material.py").read_text("utf-8")
    tree=ast.parse(src)
    fn=next(node for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name == "resolve_header_surface_mode")
    from collections.abc import Mapping
    import typing
    scope={"Mapping":Mapping, "object":object}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(ROOT/"rendering/quick/widgets/surface_material.py"),"exec"),scope)
    resolve_header_surface_mode=scope["resolve_header_surface_mode"]

    assert resolve_header_surface_mode({}) == "inherit"
    assert resolve_header_surface_mode({"global": {"header_surface_mode": "normal"}}) == "normal"
    assert resolve_header_surface_mode({"global": {"header_surface_mode": "bogus"}}) == "inherit"
    assert resolve_header_surface_mode({"global": {"header_surface_mode": "INHERIT"}}) == "inherit"


def test_branded_header_reuses_the_card_without_capture_or_rewriting_card_guard():
    header=(QML/"BrandedHeader.qml").read_text(encoding="utf-8")
    assert "ChildMaterialSurface {" in header
    assert "card: header.materialCard" in header
    assert 'forceFlat: header.materialMode === "normal"' in header
    assert "legibilityPanel: true" in header
    assert 'forceFlat: header.materialMode === "normal"' in header
    assert 'headerMaterial.active ? "transparent" : header.adjustedFlatFillColor' in header
    assert 'additionalOpacityAdjust: header.materialOpacityAdjust' in header
    assert "ShaderEffectSource" not in header


def test_all_branded_header_families_bind_to_own_card_and_global_mode():
    pairs={
        "RedditPresentation.qml": "redditRoot", "FeedPresentation.qml": "feedRoot",
        "FriendPulsePresentation.qml": "friendRoot", "SystemStatsPresentation.qml": "statsRoot",
        "AbandonmentIssuesPresentation.qml": "abandonmentRoot", "GmailPresentation.qml": "gmailRoot",
        "AchievementPulsePresentation.qml": "achievementRoot", "MediaPresentation.qml": "mediaRoot",
        "GamesYouFollowPresentation.qml": "followsRoot",
    }
    for name,owner in pairs.items():
        qml=(QML/name).read_text(encoding="utf-8")
        assert f"materialCard: {owner}" in qml
        assert f"materialMode: {owner}.cardHeaderSurfaceMode" in qml


def test_global_style_persistence_and_projection_share_one_owner():
    host=(ROOT/"rendering/quick/widgets/host.py").read_text(encoding="utf-8")
    defaults=(ROOT/"core/settings/default_settings.py").read_text(encoding="utf-8")
    ui=(ROOT/"ui/tabs/widgets_tab_defaults.py").read_text(encoding="utf-8")
    assert '("cardHeaderSurfaceMode", "header_surface_mode")' in host
    assert "'header_surface_mode': 'inherit'" in defaults
    assert "Header Surface:" in ui
    assert '"header_surface_mode": (' in ui
    assert 'header_combo.setCurrentIndex(max(0, header_combo.findData(mode)))' in ui
