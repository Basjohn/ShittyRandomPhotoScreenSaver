"""Source guards for the selected-only child-geometry observation path.

These are causal architecture guards, not a claim about measured performance or
about every possible external feed producer. Runtime interaction coverage lives
in the Qt child edit-lifecycle and mapped-geometry tests.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering/quick/qml"


def test_role_declarations_have_no_edit_off_observer_or_publisher() -> None:
    root = (QML / "OverlayWidget.qml").read_text(encoding="utf-8")
    edit = (QML / "CustomLayoutOverlay.qml").read_text(encoding="utf-8")
    assert "property var customEditableChildRoles: []" in root
    assert "property var customEditableChildRequirementTarget: null" in root
    assert "onCustomEditableChildRolesChanged" not in root
    assert "customEditableChildRolesChanged" not in edit
    assert "active: editFrame.selectedForChildEdit" in edit
    assert "model: editFrame.hasPresentationItem" in edit
    assert "? (editFrame.presentationItem.customEditableChildRoles || [])" in edit
    assert "&& ((editFrame.presentationItem.customEditableChildRoles || []).length > 0" in edit
    assert "if (childRequirementSyncQueued || !editActive || !sessionModel)" in edit
    assert "if (!editActive || !sessionModel)" in edit
    assert "Qt.callLater(customLayoutOverlay.flushSelectedChildRequirementSync)" in edit


def test_preferred_size_sink_remains_change_driven_and_geometry_idempotent() -> None:
    root = (QML / "OverlayWidget.qml").read_text(encoding="utf-8")
    binding = (ROOT / "rendering/quick/widgets/geometry_resolver.py").read_text(encoding="utf-8")
    assert "onPreferredContentWidthChanged: overlayWidget.preferredContentSizeChanged(" in root
    assert "onPreferredContentHeightChanged: overlayWidget.preferredContentSizeChanged(" in root
    assert "signal.preferredContentSizeChanged" not in binding
    assert "signal.connect(callback)" in binding
    assert "signal.disconnect(callback)" in binding
    assert "if geometry == self._current_geometry:\n            return None" in binding
    assert "if self._retired:\n            return None" in binding
