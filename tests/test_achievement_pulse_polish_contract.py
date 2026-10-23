"""Lean source-level guards for Achievement Pulse semantic ownership.

Presentation polish (font multipliers, offsets and selected geometry sizes) is
not a functional oracle. Rendered geometry lives in
``test_qtquick_achievement_pulse_presentation.py``.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering/quick/qml/AchievementPulsePresentation.qml"
CAPSULE = ROOT / "rendering/quick/qml/AchievementCapsule.qml"
DESCRIPTORS = ROOT / "rendering/widget_descriptors.py"


def test_missing_shelf_values_share_one_normalization_path() -> None:
    source = CAPSULE.read_text(encoding="utf-8")
    # Actual text normalization is part of the UI's data semantics, not styling.
    assert "function shelfValueText(value)" in source
    assert 'upper === "UNKNOWN" || upper === "UNAVAILABLE"' in source
    assert 'text: capsule.shelfValueText(capsule.fieldValue)' in source


def test_custom_child_roles_are_declared_by_the_shared_descriptor() -> None:
    qml = QML.read_text(encoding="utf-8")
    descriptors = DESCRIPTORS.read_text(encoding="utf-8")
    # Stable role identifiers form the persisted child-geometry schema.
    for role in (
        "header", "artwork", "game_name", "achievement_list",
        "badge", "progress_circle", "field_group",
    ):
        assert f'"roleId": "{role}"' in qml
        if role != "artwork":
            assert f'"{role}"' in descriptors
    assert "freeform_artwork_child_role(" in descriptors


def test_child_content_does_not_acquire_an_independent_parent_size_authority() -> None:
    qml = QML.read_text(encoding="utf-8")
    assert "customEditableChildRequirementTarget: null" in qml
    assert '"requirementTarget": customChildRequirement' not in qml
    assert "preferredContentWidth: achievementRoot.authoredWidth" in qml
    assert "preferredContentHeight: achievementRoot.authoredHeight" in qml
    assert "Timer {" not in qml
