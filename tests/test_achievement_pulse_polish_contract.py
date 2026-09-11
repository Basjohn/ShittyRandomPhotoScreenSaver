"""Static contracts for the 2026-09-11 Achievement Pulse polish slice."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRESENTATION = ROOT / "rendering/quick/qml/AchievementPulsePresentation.qml"
CAPSULE = ROOT / "rendering/quick/qml/AchievementCapsule.qml"


def test_progress_pulse_keeps_authored_geometry_but_uses_smaller_text_and_higher_bottom_padding():
    source = PRESENTATION.read_text(encoding="utf-8")

    assert "width: 108.0\n                height: 108.0" in source
    assert "y: authoredCanvas.height - height - 20.0" in source
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
