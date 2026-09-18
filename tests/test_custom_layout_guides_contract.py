from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_custom_alignment_guides_have_explicit_above_below_layering() -> None:
    scene = _text("rendering/quick/qml/DisplayScene.qml")
    overlay = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    underlay = _text("rendering/quick/qml/CustomLayoutGuideUnderlay.qml")
    qmldir = _text("rendering/quick/qml/qmldir")

    assert "CustomLayoutGuideUnderlay 1.0 CustomLayoutGuideUnderlay.qml" in qmldir
    assert "id: customLayoutGuideUnderlay" in scene
    assert "z: 4" in scene
    assert 'objectName: "pixelShiftLayer"' in scene
    assert "z: 5" in scene
    assert "id: customLayoutOverlay" in scene
    assert "z: 100" in scene

    # Peer-edge alignment is a gentle blue high-layer guide, one pixel thicker
    # than the former baseline.
    assert 'color: "#aa5ea8ff"' in overlay
    assert 'width: 3' in overlay
    assert 'height: 3' in overlay
    assert 'objectName: "customLayoutVerticalGuide"' in overlay
    assert 'objectName: "customLayoutHorizontalGuide"' in overlay

    # Centering guides and the stronger absolute centre cross stay under widgets.
    assert 'color: "#a8b46eff"' in underlay
    assert 'objectName: "customLayoutVerticalCenterGuide"' in underlay
    assert 'objectName: "customLayoutHorizontalCenterGuide"' in underlay
    assert 'color: "#70ffffff"' in underlay
    assert 'border.width: 2' in underlay
    assert underlay.count('width: 3') >= 2
    assert underlay.count('height: 3') >= 2
    # Generic grid lines deliberately remain at the original 1 px.
    assert 'width: 1' in underlay
    assert 'height: 1' in underlay
    assert 'color: index % 4 === 0 ? "#3affffff" : "#1cffffff"' in underlay


def test_custom_move_publishes_existing_snap_metadata_without_new_cadence() -> None:
    owner = _text("rendering/quick/custom_layout_owner.py")
    scene = _text("rendering/quick/scene_controller.py")
    overlay_qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")

    assert "resolution = resolve_snap_local_rect_for_edit(" in owner
    assert "self._publish_move_guides(target.identity, resolution)" in owner
    assert 'allowed_kinds = {"peer", "peer_center", "display_center"}' in owner
    assert 'getattr(resolution, "vertical_assists", ())' in owner
    assert 'getattr(resolution, "horizontal_assists", ())' in owner
    assert "move_finished_handler=self.clear_move_guides" in owner
    assert "self._publish_uniform_wheel_guides(item)" in owner
    assert "never feed the resolver's suggested scale back into geometry" in owner
    assert "def set_custom_layout_guides(" in scene
    assert 'center_kinds = {"display_center", "peer_center"}' in scene
    assert "onReleased: customLayoutOverlay.sessionModel.finishMove()" in overlay_qml
    assert "onCanceled: customLayoutOverlay.sessionModel.finishMove()" in overlay_qml

    # The restoration is event-driven: do not introduce a guide-owned cadence.
    combined = owner + scene + overlay_qml
    assert "QTimer" not in combined
    assert "Timer {" not in combined


def test_selected_parent_two_axis_reflow_affordance_is_event_driven_and_collision_bounded() -> None:
    session = _text("rendering/custom_layout_session.py")
    overlay_model = _text("rendering/quick/custom_layout_overlay.py")
    owner = _text("rendering/quick/custom_layout_owner.py")
    qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")

    assert "def select_item(" in session
    assert "subscribe_selection" in session
    assert 'QByteArray(b"selectedForChildEdit")' in overlay_model
    assert '"content_top_left"' in overlay_model
    assert "def _resize_content_corner(" in owner
    assert 'handle_id.startswith("content_")' in owner

    assert "active: editFrame.selectedForChildEdit" in qml
    assert "editFrame.twoAxisContentExtentCapable" in qml
    assert 'objectName: "customLayoutContentCorner-"' in qml
    assert 'color: "#dc6aa8e8"' in qml
    assert '"content_" + parent.corner' in qml
    assert "contentCornerAvailable" in qml
    assert "contentCornerLocalRect" in qml
    assert "peerMargin = 8.0" in qml
    assert "localChromeClear" in qml
    assert "frame.width - size" in qml
    assert "frame.height - size" in qml
    assert "outerGap" not in qml
    assert "NumberAnimation on opacity" in qml

    # Selection and the brief fade are event-driven. No timer/cadence or hover
    # scanner is allowed to appear for edit chrome or future child controls.
    combined = session + overlay_model + owner + qml
    assert "Timer {" not in qml
    assert "QTimer" not in overlay_model
    assert "QTimer" not in session


def test_custom_child_geometry_stays_on_one_session_owner_and_is_event_driven() -> None:
    child = _text("rendering/custom_child_geometry.py")
    session = _text("rendering/custom_layout_session.py")
    owner = _text("rendering/quick/custom_layout_owner.py")
    overlay_model = _text("rendering/quick/custom_layout_overlay.py")
    scene = _text("rendering/quick/scene_controller.py")
    qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    root_qml = _text("rendering/quick/qml/OverlayWidget.qml")

    assert 'CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY = "child_geometry"' in child
    assert "class CustomChildRoleDescriptor" in child
    assert "class CustomChildSize" in child
    assert "def freeform_artwork_child_role(" in child
    assert "uniform_scale: bool = False" in child
    assert "resize_handles:" in child
    assert "artwork rectangles" in child
    assert "image content preserves native" in child
    assert "def normalize_child_geometry(" in child
    assert "def update_child_geometry_payload(" in child
    assert "custom_child_roles" in session
    assert "current_child_sizes" in session
    assert "def begin_child_resize(" in owner
    assert "def update_child_resize(" in owner
    assert "role.uniform_scale" in owner
    assert 'QByteArray(b"presentationItem")' in overlay_model
    assert "def beginChildResize(" in overlay_model
    assert "def resizeChild(" in overlay_model
    assert "def childResizeHandles(" in overlay_model
    assert "def ensureChildContentExtent(" in overlay_model
    assert "def ensure_child_content_extent(" in owner
    assert "Qt.callLater(function()" in qml
    assert "def _custom_layout_presentation_item(" in scene
    assert "property var customEditableChildRoles: []" in root_qml
    assert "id: childRoleLoader" in qml
    assert "active: editFrame.selectedForChildEdit" in qml
    assert 'objectName: "customLayoutChildRole-"' in qml
    assert "width: 8" in qml and "height: 8" in qml
    assert "childResizeHandles(" in qml
    assert "NumberAnimation on opacity" in qml
    assert "function overlapsEditRect(candidate)" in qml
    assert "childLayer.overlapsEditRect(candidate)" in qml

    # Child editing is selection/pointer driven only. No recurring scheduler is
    # permitted for observing retained child geometry or keeping handles alive.
    combined = child + session + owner + overlay_model + scene + qml + root_qml
    assert "Timer {" not in qml
    assert "QTimer" not in child
    assert "QTimer" not in session


def test_friend_pulse_grouped_avatar_child_role_reuses_shared_owner_without_per_avatar_state() -> None:
    descriptors = _text("rendering/widget_descriptors.py")
    model = _text("rendering/quick/widgets/friend_pulse.py")
    qml = _text("rendering/quick/qml/FriendPulsePresentation.qml")

    assert 'CustomChildRoleDescriptor(\n                "avatars"' in descriptors
    assert 'uniform_scale=True' in descriptors
    assert 'resize_handles=("bottom_right",)' in descriptors
    assert 'customGeometryChanged = Signal()' in model
    assert 'def set_custom_child_geometry(self, child_geometry: object)' in model
    assert 'avatar_scale=self._custom_avatar_scale' in model
    assert 'customEditableChildRoles: [' in qml
    assert '{ "roleId": "avatars", "target": customAvatarRoleTarget }' in qml
    assert 'objectName: "friendPulseCustomAvatarRoleTarget"' in qml
    assert '36.0 * friendRoot.customAvatarScale' in qml
    assert '* friendRoot.customAvatarScale' in qml
    assert 'Timer {' not in qml


def test_custom_settings_lock_scopes_steam_cards_independently() -> None:
    descriptors = _text("rendering/widget_descriptors.py")
    settings = _text("ui/tabs/widgets_tab.py")

    assert 'section_id="steam_achievement_pulse"' in descriptors
    assert 'section_id="steam_abandonment_issues"' in descriptors
    assert 'section_id="steam_friend_pulse"' in descriptors
    assert 'widget_ids=("achievement_pulse",)' in descriptors
    assert 'widget_ids=("abandonment_issues",)' in descriptors
    assert 'widget_ids=("friend_pulse",)' in descriptors
    assert 'restore_widget_family_to_authored_layout(widgets_cfg, widget_id)' in settings
    assert 'restore_all_custom_layouts_to_authored_layout(widgets_cfg)' not in settings
    assert 'Disable Custom</a> To Adjust!' in settings
