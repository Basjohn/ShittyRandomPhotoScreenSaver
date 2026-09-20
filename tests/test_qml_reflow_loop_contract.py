"""Source-level companion to Qt scene gates for the Sep 19 binding-loop report.

These prove structural invariants; the dynamic QML scene tests and a new
operator QML log are required to verify absence of runtime binding warnings.
"""
from pathlib import Path

QML = Path(__file__).resolve().parents[1] / "rendering" / "quick" / "qml"


def source(name: str) -> str:
    return (QML / name).read_text(encoding="utf-8")


def test_parent_size_authority_has_no_selected_child_requirement_observer() -> None:
    editor = source("CustomLayoutOverlay.qml")
    assert "queueSelectedChildRequirementSync" not in editor
    assert "flushSelectedChildRequirementSync" not in editor
    assert "ensureImmediateChildOverflow" not in editor
    assert "syncRequirementNow()" not in editor
    assert "Qt.callLater(function" not in editor


def test_dense_parent_reflow_cannot_publish_a_child_driven_outer_size() -> None:
    editor = source("CustomLayoutOverlay.qml")
    assert "ensureImmediateChildOverflow" not in editor
    assert "aggregateRequiredContentSize" not in editor
    assert "queueSelectedChildRequirementSync" not in editor
    abandonment = source("AbandonmentIssuesPresentation.qml")
    assert "id: customChildRequirement" not in abandonment
    assert "customEditableChildRequirementTarget: null" in abandonment
    assert '"requirementTarget": customChildRequirement' not in abandonment
    assert "backlogParentReflowX" in abandonment



def test_dense_header_snap_uses_static_roles_with_live_edit_frame_projection() -> None:
    editor = source("CustomLayoutOverlay.qml")
    assert "modelData.semanticInsetUsesUniformCard === true" in editor
    assert "card.authoredWidth * card.presentationScale" in editor
    for name, root in (("AbandonmentIssuesPresentation.qml", "abandonmentRoot"),
                       ("AchievementPulsePresentation.qml", "achievementRoot")):
        qml = source(name)
        header = qml.split('"roleId": "header",', 1)[1].split('"requirementTarget": null', 1)[0]
        assert f'"semanticCornerInsetX": {root}.headerSafeInsetX' in header
        assert f'"semanticCornerInsetY": {root}.headerSafeInsetY' in header
        assert '"semanticInsetUsesUniformCard": true' in header
        assert f"{root}.presentationScale" not in header
        assert f"{root}.authoredWidth" not in header


def test_gmail_refresh_has_single_painted_and_edit_rectangle_inside_header() -> None:
    gmail = source("GmailPresentation.qml")
    header = gmail.split('"roleId": "header",', 1)[1].split('"roleId": "refresh",', 1)[0]
    refresh = gmail.split('"roleId": "refresh",', 1)[1].split("return roles", 1)[0]
    assert '"allowParentGrowth": false' not in header
    assert '"allowParentGrowth": false' not in refresh
    bounds = gmail.split("id: refreshTarget", 1)[1].split("ShadowedText {", 1)[0]
    assert "clip: true" in bounds
    assert "Math.min(Math.max(1.0, headerArea.width)" in bounds
    assert "Math.min(Math.max(1.0, headerArea.height)" in bounds
    assert "Math.min(headerArea.width - width," in bounds
    assert "Math.min(headerArea.height - height," in bounds


def test_other_uniform_family_header_role_models_do_not_bind_live_parent_geometry() -> None:
    """Friend/System Stats inherited the same parent/scale-driven role-model cycle."""
    for name, root, inset_x, inset_y in (
        ("FriendPulsePresentation.qml", "friendRoot",
         "friendRoot.headerSafeInsetX", "friendRoot.headerSafeInsetY"),
        ("SystemStatsPresentation.qml", "statsRoot", "16.0", "14.0"),
    ):
        qml = source(name)
        header = qml.split('"roleId": "header",', 1)[1].split('roles.push({', 1)[0]
        assert f'"semanticCornerInsetX": {inset_x}' in header
        assert f'"semanticCornerInsetY": {inset_y}' in header
        assert '"semanticInsetUsesUniformCard": true' in header
        assert f'{root}.width' not in header
        assert f'{root}.height' not in header
        assert f'{root}.presentationScale' not in header


def test_parent_geometry_change_does_not_republish_child_requirement_or_child_revision() -> None:
    editor = source("CustomLayoutOverlay.qml")
    assert "onOccupiedXChanged: childRoleLayer.scheduleRequirementSync()" not in editor
    assert "onOccupiedYChanged: childRoleLayer.scheduleRequirementSync()" not in editor
    assert "onOccupiedWidthChanged: childRoleLayer.scheduleRequirementSync()" not in editor
    assert "onOccupiedHeightChanged: childRoleLayer.scheduleRequirementSync()" not in editor
    assert "onChildStateRevisionChanged:" not in editor
    model = (QML.parent / "custom_layout_overlay.py").read_text(encoding="utf-8")
    assert "child_snapshot = tuple(sorted(item.current_child_sizes.items()))" in model
    assert "if child_changed:" in model
    assert "roles.append(self._CHILD_STATE_REVISION_ROLE)" in model
    assert "self._child_state_snapshots.setdefault(" in model
