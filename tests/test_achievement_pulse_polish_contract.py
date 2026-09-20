"""Static contracts for the 2026-09-11 Achievement Pulse polish slice."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRESENTATION = ROOT / "rendering/quick/qml/AchievementPulsePresentation.qml"
CAPSULE = ROOT / "rendering/quick/qml/AchievementCapsule.qml"


def test_progress_pulse_keeps_authored_geometry_but_uses_smaller_text_and_higher_bottom_padding():
    source = PRESENTATION.read_text(encoding="utf-8")

    assert "width: achievementRoot.canonicalProgressSize\n                height: achievementRoot.canonicalProgressSize" in source
    assert "- achievementRoot.canonicalProgressSize - 20.0" in source
    assert "scale: achievementRoot.achievementModel.customProgressCircleScale" in source
    assert source.count(
        "font.pointSize: achievementRoot.achievementModel.fontSize * 1.998"
    ) == 3
    assert "font.pointSize: achievementRoot.achievementModel.fontSize * 2.22" not in source

def test_shelf_missing_values_share_one_presentation_spelling_and_metrics_path():
    source = CAPSULE.read_text(encoding="utf-8")

    assert "function shelfValueText(value)" in source
    assert 'upper === "UNKNOWN" || upper === "UNAVAILABLE"' in source
    assert '? "UNAVAILABLE"' in source
    assert "text: capsule.shelfValueText(capsule.fieldValue)" in source
    assert "font.pointSize: capsule.capsuleFontSize * 0.82" in source
    assert "horizontalAlignment: Text.AlignRight" in source


def test_achievement_declares_and_projects_dense_custom_child_roles():
    presentation = PRESENTATION.read_text(encoding="utf-8")
    descriptor = (ROOT / "rendering/widget_descriptors.py").read_text(encoding="utf-8")
    model = (ROOT / "rendering/quick/widgets/achievement_pulse.py").read_text(encoding="utf-8")

    expected_targets = {
        "header": "headerFrame",
        "artwork": "artworkFrame",
        "game_name": "gameTitle",
        "achievement_list": "achievementListFrame",
        "badge": "latestArtworkFrame",
        "progress_circle": "progressPulse",
        "field_group": "fieldGroupFrame",
    }
    for role_id, target in expected_targets.items():
        assert f'"roleId": "{role_id}"' in presentation
        assert f'"target": {target}' in presentation
    for role_id in expected_targets.keys() - {"artwork"}:
        assert f'"{role_id}"' in descriptor
    assert "freeform_artwork_child_role(" in descriptor

    for property_name in (
        "customHeaderWidthScale", "customHeaderXOffset", "customHeaderAnchor",
        "customArtworkWidthScale", "customArtworkXOffset",
        "customBadgeWidthScale", "customBadgeXOffset",
        "customProgressCircleScale", "customProgressCircleXOffset",
        "customGameNameWidthScale", "customGameNameXOffset", "customGameNameAlignment",
        "customAchievementListWidthScale", "customAchievementListXOffset",
        "customAchievementListAlignment",
        "customFieldGroupWidthScale", "customFieldGroupXOffset",
    ):
        assert property_name in presentation
        assert f"def {property_name}(self)" in model

    # A child-driven outer-size authority is deliberately retired: authored
    # content_extent and the existing CUSTOM owner remain the only parent size.
    assert "id: customChildRequirement" not in presentation
    assert "customEditableChildRequirementTarget: null" in presentation
    assert '"requirementTarget": customChildRequirement' not in presentation
    assert "readonly property bool artworkOnAuthoredRail" in presentation
    assert "readonly property bool progressOnAuthoredRail" in presentation
    assert "readonly property bool fieldGroupOnAuthoredRail" in presentation
    assert "artworkFollowsParentRightRail" in presentation
    assert "progressFollowsParentBottomRail" in presentation
    assert "fieldGroupFollowsParentBottomRail" in presentation
    assert 'freeform_artwork_child_role(\n                movable=True' in descriptor
    assert 'freeform_layout_block_child_role(\n                "achievement_list"' in descriptor
    assert 'freeform_layout_block_child_role(\n                "field_group"' in descriptor
    assert 'CustomChildRoleDescriptor(\n                "header"' in descriptor
    assert 'CustomChildRoleDescriptor(\n                "badge"' in descriptor
    assert 'CustomChildRoleDescriptor(\n                "progress_circle"' in descriptor
    assert 'CustomChildRoleDescriptor(\n                "game_name"' in descriptor
    assert "def set_custom_child_geometry(" in model
    assert "clamp_child_geometry(" in model
    assert "self.customGeometryChanged.emit()" in model
    assert "Timer {" not in presentation
    assert "QTimer" not in model

def test_achievement_artwork_is_freeform_but_intrinsic_roles_scale_as_shapes():
    presentation = PRESENTATION.read_text(encoding="utf-8")

    assert (
        "readonly property real artworkWidth: achievementRoot.canonicalArtworkWidth\n"
        "                * achievementRoot.achievementModel.customArtworkWidthScale"
    ) in presentation
    assert (
        "readonly property real artworkHeight: achievementRoot.canonicalArtworkHeight\n"
        "                * achievementRoot.achievementModel.customArtworkHeightScale"
    ) in presentation
    assert "fillMode: Image.PreserveAspectCrop" in presentation
    assert "scale: achievementRoot.achievementModel.customBadgeWidthScale" in presentation
    assert "scale: achievementRoot.achievementModel.customProgressCircleScale" in presentation
    assert "transformOrigin: Item.TopLeft" in presentation

def test_achievement_outer_extent_is_not_observed_or_republished_by_children():
    presentation = PRESENTATION.read_text(encoding="utf-8")

    assert "id: customChildRequirement" not in presentation
    assert "customEditableChildRequirementTarget: null" in presentation
    assert '"requirementTarget": customChildRequirement' not in presentation
    assert "preferredContentWidth: achievementRoot.authoredWidth" in presentation
    assert "preferredContentHeight: achievementRoot.authoredHeight" in presentation
    assert "readonly property real baseAuthoredWidth: achievementModel.baseAuthoredWidth" in presentation
    assert "readonly property real baseAuthoredHeight: achievementModel.baseAuthoredHeight" in presentation
    assert "readonly property real artworkParentReflowX:" in presentation
    assert "readonly property real progressParentReflowY:" in presentation
    assert "readonly property real fieldGroupParentReflowY:" in presentation
    assert "extraContentHeight * 0.20" not in presentation
    assert "extraContentHeight * 0.65" not in presentation


def test_achievement_live_parent_x_reflow_retains_authored_title_rail_without_growth_feedback():
    qml = PRESENTATION.read_text(encoding="utf-8")
    # Child roles have stable canonical persistence baselines, but the displayed
    # text rail follows the old artwork-right/parent-right relation until moved.
    assert 'readonly property real titleParentReflowWidth:' in qml
    assert '|| achievementRoot.artworkFollowsParentRightRail' in qml
    assert '|| achievementRoot.headerFlipped)' in qml
    assert 'achievementRoot.canonicalTitleWidth + titleParentReflowWidth' in qml
    assert '(achievementRoot.gameNameOnAuthoredRail\n                    ? normalContent.titleWidth' in qml
    assert '(achievementRoot.achievementListOnAuthoredRail\n                    ? normalContent.titleWidth' in qml
    assert 'achievementRoot.firstAchievementOnAuthoredRail' in qml
    # Width reflow is projected once through normalContent.titleWidth.
    # Re-adding titleParentReflowWidth to either child's X would create a
    # second, competing placement path and parent-width feedback.
    assert 'achievementRoot.semanticRailX(' in qml
    assert 'achievementRoot.canonicalTitleWidth + titleParentReflowWidth' in qml
    assert 'Timer {' not in qml
