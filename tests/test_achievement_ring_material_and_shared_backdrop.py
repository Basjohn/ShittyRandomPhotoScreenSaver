"""Import-free contracts for Achievement Pulse's opt-in circular material.

These guard ownership and preservation; Windows Qt rendering remains a separate
visual acceptance check.  No production code needs a test-only import path.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def default_widgets() -> dict:
    tree = ast.parse(read("core/settings/default_settings.py"))
    default = next(
        node.value for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "DEFAULT_SETTINGS" for t in node.targets)
    )
    return ast.literal_eval(default)["widgets"]


def test_opt_in_material_setting_has_canonical_boolean_authority() -> None:
    # The operator may enable or disable this default at any time. Only its
    # admission type and consumption contract belong in this test.
    assert type(default_widgets()["achievement_pulse"]["progress_circle_material"]) is bool
    model = read("rendering/quick/widgets/achievement_pulse.py")
    assert "progress_circle_material: bool" in model
    assert 'merged_card.get("progress_circle_material")' in model
    assert 'bool(default_card["progress_circle_material"])' in model
    assert 'def progressCircleMaterialEnabled(self) -> bool:' in model
    assert "return self.config.progress_circle_material" in model


def test_circle_checkbox_is_a_standard_steam_setting_with_round_trip() -> None:
    ui = read("ui/tabs/widgets_tab_steam.py")
    assert 'QCheckBox("Material Progress Circle")' in ui
    assert 'ring_material.setProperty("circleIndicator", True)' in ui
    assert 'ring_material.stateChanged.connect(tab._save_settings)' in ui
    assert 'tab.achievement_pulse_progress_circle_material = ring_material' in ui
    assert 'ring_material.setEnabled(pulse_enabled)' in ui
    assert 'config.get("progress_circle_material", tab._default_bool(key, "progress_circle_material"))' in ui
    assert 'payload["progress_circle_material"] = bool(' in ui


def test_circle_uses_only_the_card_backdrop_with_original_ring_and_pulse() -> None:
    source = read("rendering/quick/qml/AchievementPulsePresentation.qml")
    circle = source.split('id: progressCircleFace', 1)[1].split('ThemedText {', 1)[0]
    assert 'id: progressCircleMaterial' in circle
    assert 'card: achievementRoot' in circle
    assert 'forceFlat: !achievementRoot.achievementModel.progressCircleMaterialEnabled' in circle
    assert '(progressCircleMaterial.active ? "transparent" : originalFill)' in circle
    assert 'cornerRadius: progressCircleFace.width * 0.5' in circle
    # The material takes its tint from a semantic role rather than a frozen
    # opacity/tint/legibility recipe. Explicit opt-in and Normal fallback are
    # exercised by the live Qt presentation tests.
    assert 'fillColor: achievementRoot.achievementModel.progressDiscMaterialColor' in circle
    assert 'achievementRoot.scaleAwareStrokeWidthForScale(' in circle
    # The ring is a special object, not a border: it reads its own colour field so
    # Borderless (which hides border-named fields) cannot erase it.
    assert 'border.color: achievementRoot.achievementModel.progressRingColor' in circle
    assert 'capsuleBorderColor' not in circle
    assert 'ShaderEffectSource' not in circle
    assert 'Timer {' not in circle
    assert 'id: pulseAnimation' in source


def test_material_disc_has_its_own_resolved_accent_role_not_the_faint_flat_capsule() -> None:
    model = read("rendering/quick/widgets/achievement_pulse.py")
    theme = read("ui/widget_visual_roles.py")
    qml = read("rendering/quick/qml/AchievementPulsePresentation.qml")
    assert '"steam.progress.disc": "widget.accent"' in theme
    assert '"steam.progress.disc",' in model
    assert 'local_roles={"local.accent": capsule_border}' in model
    assert 'progress_disc_material_color=progress_disc_material' in model
    assert 'def progressDiscMaterialColor(self) -> QColor:' in model
    assert 'fillColor: achievementRoot.achievementModel.progressDiscMaterialColor' in qml
    # Normal/unchecked still paints its original flat capsule, and the ring's
    # material still follows the ONE display-scoped backdrop.
    assert '(progressCircleMaterial.active ? "transparent" : originalFill)' in qml
    assert 'card: achievementRoot' in qml


def test_every_ordinary_widget_shares_one_card_and_one_backdrop_owner() -> None:
    registry = read("rendering/quick/widgets/registry.py")
    names = (
        "ClockPresentation", "WeatherPresentation", "MediaPresentation",
        "RedditPresentation", "FeedPresentation", "GmailPresentation",
        "AchievementPulsePresentation", "AbandonmentIssuesPresentation",
        "FriendPulsePresentation", "GamesYouFollowPresentation",
        "SystemAudioOSDPresentation", "SystemStatsPresentation",
    )
    for name in names:
        assert f'qml_filename="{name}.qml"' in registry
        assert (QML / f"{name}.qml").read_text(encoding="utf-8").lstrip().find("OverlayWidget {") >= 0
    widget = read("rendering/quick/qml/OverlayWidget.qml")
    card = read("rendering/quick/qml/OverlayCard.qml")
    host = read("rendering/quick/widgets/host.py")
    scene = read("rendering/quick/scene_controller.py")
    assert 'property alias cardSurfaceBackdrop: card.surfaceBackdrop' in widget
    assert 'surfaceComponent' not in widget  # no competing family shader owner
    assert 'sourceComponent: MaterialSurface {' in card
    assert 'backdrop: card.surfaceBackdrop' in card
    assert 'widget.item.setProperty("cardSurfaceBackdrop", backdrop)' in host
    assert 'self._bind_surface_backdrop(owner.item)' in scene
    assert 'self._ordinary_widget_host' in scene


def test_gmail_and_achievement_use_valid_authored_colours_and_distinct_ink_routes() -> None:
    widgets = default_widgets()
    for key in ("gmail", "achievement_pulse", "reddit", "media"):
        colour = widgets[key]["bg_color"]
        assert len(colour) == 4 and all(isinstance(channel, int) and 0 <= channel <= 255 for channel in colour)
        assert 0.0 <= float(widgets[key]["bg_opacity"]) <= 1.0
    # Gmail's own ink route was retired: its panel density is the shared owner's
    # (test_qtquick_gmail_presentation.py::test_gmail_card_surface_comes_only_from_the_shared_owner).
    assert 'cardSurfaceLegibilityInk:' not in read(
        "rendering/quick/qml/GmailPresentation.qml")
    assert 'cardSurfaceLegibilityInk:' not in read(
        "rendering/quick/qml/AchievementPulsePresentation.qml")
    assert '"card.background"' in read("rendering/quick/widgets/theme_projection.py")
