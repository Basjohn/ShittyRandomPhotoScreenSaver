"""Achievement Pulse progress-text visual sizing contract.

Qt-free source assertions protect the normalization boundary: the percentage
value and authored pulse geometry stay with their existing owners, while the
requested readability tweak is a final presentation-only transform after
HorizontalFit has resolved the text.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering/quick/qml/AchievementPulsePresentation.qml"
PY_MODEL = ROOT / "rendering/quick/widgets/achievement_pulse.py"
LAYOUT = ROOT / "rendering/quick/widgets/achievement_pulse_layout.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_percentage_reduction_is_post_fit_presentation_only() -> None:
    qml = _source(QML)

    assert "readonly property real progressTextVisualScale: 0.90" in qml
    assert "fontSizeMode: Text.HorizontalFit" in qml
    assert "scale: progressPulse.progressTextVisualScale" in qml
    assert "scale: progressPulse.progressTextVisualScale * 1.11" in qml
    assert "scale: progressPulse.progressTextVisualScale * 1.045" in qml


def test_progress_pulse_geometry_and_total_normalization_authority_are_unchanged() -> None:
    qml = _source(QML)
    model = _source(PY_MODEL)
    layout = _source(LAYOUT)

    # The earlier 4 px lift and canonical pulse diameter remain the geometry
    # authority; the text tweak must not resize or relocate the pulse/card.
    assert "y: authoredCanvas.height - height - 20.0" in qml
    assert "width: 108.0" in qml
    assert "height: 108.0" in qml

    # Progress Pulse still presents the existing authored Total field rather
    # than calculating or normalizing another percentage in QML.
    assert 'if field.field_id != "total":' in model
    assert "progress_text, progress_percent, progress_visible = self._progress_value(card)" in model
    assert "achievement_pulse_authored_size(" in model
    assert "def achievement_pulse_authored_size(" in layout
    assert "progressTextVisualScale" not in model
    assert "progressTextVisualScale" not in layout
