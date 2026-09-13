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

    # Names remain readable while status/game chrome is explicitly all-caps.
    assert "maximumLineCount: 2" in qml
    assert "fontSizeMode: Text.Fit" in qml
    assert qml.count(".toUpperCase()") >= 3

    # Favourite/pin affordance is a separate hover-only control in both views.
    assert qml.count('objectName: "friendPulsePinButton_" + index') == 2
    assert "visible: friendActionAvailable && activityRowHover.hovered" in qml
    assert "visible: friendActionAvailable && gridTileHover.hovered" in qml
    assert qml.count("friendPinToggleRequested(index)") == 2



def test_online_count_summary_replaces_dropped_unread_message_feature() -> None:
    qml = _text("rendering/quick/qml/FriendPulsePresentation.qml")
    model = _text("rendering/quick/widgets/friend_pulse.py")
    runtime = _text("widgets/friend_pulse_runtime.py")

    assert "unreadMessage" not in qml
    assert "messageMenu" not in qml
    assert "FriendMessage" not in model
    assert "friend_message_sessions" not in runtime
    assert "onlineFriendsText" in qml
    assert "showOnlineCount" in qml
    assert 'return f"{count} {noun} ONLINE"' in model


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


def test_friend_pulse_wide_grid_and_online_count_contract() -> None:
    model = _text("rendering/quick/widgets/friend_pulse.py")
    qml = _text("rendering/quick/qml/FriendPulsePresentation.qml")
    settings = _text("ui/tabs/widgets_tab_steam.py")
    defaults = _text("core/settings/defaults_snapshot.json")

    assert 'min(normalized_capacity, 6, fitted)' not in model
    assert 'return min(normalized_capacity, fitted)' in model
    assert 'resolved_width = max(420, min(4000, resolved_width))' in model
    assert '"show_online_count": true' in defaults.lower()
    assert 'Show Friends Online Count' in settings
    assert 'payload["show_online_count"]' in settings
    assert "onlineFriendsText" in qml
    assert "showOnlineCount" in qml
