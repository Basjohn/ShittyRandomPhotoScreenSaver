"""Static contracts for the 2026-09-11 Achievement Pulse polish slice."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRESENTATION = ROOT / "rendering/quick/qml/AchievementPulsePresentation.qml"
CAPSULE = ROOT / "rendering/quick/qml/AchievementCapsule.qml"


def test_progress_pulse_keeps_authored_geometry_but_uses_smaller_text_and_higher_bottom_padding():
    source = PRESENTATION.read_text(encoding="utf-8")

    assert "width: 108.0\n                height: 108.0" in source
    assert "y: authoredCanvas.height - visualSize - 20.0" in source
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


def test_achievement_declares_and_projects_all_three_custom_child_roles():
    presentation = PRESENTATION.read_text(encoding="utf-8")
    descriptor = (ROOT / "rendering/widget_descriptors.py").read_text(encoding="utf-8")
    model = (ROOT / "rendering/quick/widgets/achievement_pulse.py").read_text(encoding="utf-8")

    # Hydration normalizes persisted child scales with math.isfinite(); keep the
    # dependency explicit so a saved CUSTOM payload cannot abort display creation.
    assert "import math" in model

    assert '"roleId": "artwork"' in presentation
    assert '"target": artworkFrame' in presentation
    assert '"roleId": "badge"' in presentation
    assert '"target": latestArtworkFrame' in presentation
    assert '"roleId": "progress_circle"' in presentation
    assert '"target": progressPulse' in presentation
    assert "customArtworkWidthScale" in presentation
    assert "customArtworkHeightScale" in presentation
    assert "customBadgeWidthScale" in presentation
    assert "customProgressCircleScale" in presentation
    assert "requiredContentWidth" in presentation
    assert "requiredContentHeight" in presentation
    assert 'freeform_artwork_child_role(' in descriptor
    assert 'CustomChildRoleDescriptor(\n                "badge"' in descriptor
    assert 'CustomChildRoleDescriptor(\n                "progress_circle"' in descriptor
    assert 'freeform_artwork_child_role(\n                resize_handles=("bottom_left",),' in descriptor
    helper = (ROOT / "rendering/custom_child_geometry.py").read_text(encoding="utf-8")
    assert "uniform_scale=False" in helper
    assert descriptor.count("uniform_scale=True") >= 2
    assert 'resize_handles=("bottom_left",)' in descriptor
    assert 'resize_handles=("bottom_right",)' in descriptor
    assert 'resize_handles=("top_right",)' in descriptor
    assert 'artwork = _role("artwork")' in model
    assert 'badge = _role("badge")' in model
    assert 'progress = _role("progress_circle")' in model
    assert "def set_custom_child_geometry(" in model
    assert "customGeometryChanged = Signal()" in model


def test_achievement_artwork_is_freeform_but_intrinsic_roles_scale_as_shapes():
    presentation = PRESENTATION.read_text(encoding="utf-8")

    assert (
        "readonly property real artworkWidth: authoredArtworkWidth\n"
        "                * achievementRoot.achievementModel.customArtworkWidthScale"
    ) in presentation
    assert (
        "readonly property real artworkHeight: authoredArtworkHeight\n"
        "                * achievementRoot.achievementModel.customArtworkHeightScale"
    ) in presentation
    assert "fillMode: Image.PreserveAspectCrop" in presentation
    assert "scale: achievementRoot.achievementModel.customBadgeWidthScale" in presentation
    assert "scale: achievementRoot.achievementModel.customProgressCircleScale" in presentation
    assert "transformOrigin: Item.TopLeft" in presentation


def test_achievement_custom_child_growth_reports_one_family_wide_content_requirement():
    presentation = PRESENTATION.read_text(encoding="utf-8")

    assert "readonly property real artworkExtraWidth" in presentation
    assert "readonly property real badgeExtraWidth" in presentation
    assert "readonly property real progressExtraSize" in presentation
    assert "achievementRoot.baseAuthoredWidth + Math.max(" in presentation
    assert "achievementRoot.baseAuthoredHeight + Math.max(" in presentation
    assert "progressPulse.x + progressPulse.visualSize + 49.0" in presentation
