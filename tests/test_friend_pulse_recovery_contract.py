from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_friend_pulse_recovery_visual_contract_is_explicit() -> None:
    qml = _text("rendering/quick/qml/FriendPulsePresentation.qml")

    # Offline image treatment + hard containment live on both roster delegates.
    assert qml.count("saturation: isOnline ? 0.0 : -1.0") == 2
    assert "id: rowAvatarClip" in qml and "id: gridAvatarClip" in qml
    assert qml.count("clip: true") >= 4

    # The old lower-right presence/status circles stay deleted.
    assert "friendPulseRowStatus" not in qml
    assert "friendPulseGridStatus" not in qml

    # Names remain readable while status/game/message chrome is explicitly all-caps.
    assert "maximumLineCount: 2" in qml
    assert "fontSizeMode: Text.Fit" in qml
    assert qml.count(".toUpperCase()") >= 3

    # Favourite/pin affordance is a separate hover-only control in both views.
    assert qml.count('objectName: "friendPulsePinButton_" + index') == 2
    assert "visible: friendActionAvailable && activityRowHover.hovered" in qml
    assert "visible: friendActionAvailable && gridTileHover.hovered" in qml
    assert qml.count("friendPinToggleRequested(index)") == 2


def test_unread_summary_fully_replaces_old_activity_metrics() -> None:
    qml = _text("rendering/quick/qml/FriendPulsePresentation.qml")
    model = _text("rendering/quick/widgets/friend_pulse.py")

    start = qml.index("    Item {\n        id: activitySummary")
    depth = 0
    end = None
    for index in range(start, len(qml)):
        if qml[index] == "{":
            depth += 1
        elif qml[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    assert end is not None
    summary = qml[start:end]
    assert "primaryMetric" not in summary
    assert "secondaryMetric" not in summary
    assert "unreadMessageText" in summary
    assert "onUnreadMessagePulseRequested" in qml
    assert "messageActionRequested(0)" in qml
    assert 'return f"{count:02d} UNREAD {noun}"' in model
    assert 'return "MESSAGES UNAVAILABLE"' not in model
    assert 'if count <= 0:' in model
    assert 'visible: friendRoot.friendPulseModel.unreadMessageCount > 0' in qml


def test_restore_size_uses_real_distinct_glyph_and_no_baseline_reset() -> None:
    qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    owner = _text("rendering/quick/custom_layout_owner.py")

    assert 'objectName: "customLayoutRestoreSize-" + editFrame.widgetId' in qml
    assert 'text: "↶"' in qml
    assert 'text: "↺"' not in qml[qml.index("id: restoreSizeControl"):qml.index("id: moveArea")]

    start = owner.index("    def restore_item_size(")
    end = owner.index("\n    def ", start + 10)
    method = owner[start:end]
    assert ".restore_baseline(" not in method
    assert "current.x(), current.y()" in method
    assert "fit_scale = min(" in method
    assert "1.0," in method
    assert "stack_items(" not in method and "apply_stacking(" not in method


def test_restore_size_authored_geometry_is_not_the_committed_custom_rect() -> None:
    resolver = _text("rendering/quick/widgets/geometry_resolver.py")
    presenter = _text("rendering/quick/display_presenter.py")

    assert "def _publish_authored_geometry(" in resolver
    assert "committed_rect=None" in resolver
    assert "authored_geometry_sink=" in presenter
    assert "def _record_authored_geometry(" in presenter
    assert "identity in self._base_geometries and not self._authored_layout_enabled" in presenter

    start = presenter.index("    def _apply_binding_geometry(")
    end = presenter.index("\n    def ", start + 10)
    block = presenter[start:end]
    assert "_base_geometries[widget_id] = geometry" not in block
