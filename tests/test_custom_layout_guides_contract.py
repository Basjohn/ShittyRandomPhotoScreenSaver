from __future__ import annotations

import ast
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
    # The line is the actual bridge between the two 20 px-inset side-strip
    # endpoints, not a decorative slash. Corner orientation is deliberately
    # mirrored from the ordinary square-corner cursor mapping.
    assert "width: Math.SQRT2 * parent.width" in qml
    assert "rotation: parent.leftSide === parent.topSide ? -45 : 45" in qml
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
    size = _text("rendering/quick/custom_layout_size.py")
    overlay_model = _text("rendering/quick/custom_layout_overlay.py")
    scene = _text("rendering/quick/scene_controller.py")
    qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    root_qml = _text("rendering/quick/qml/OverlayWidget.qml")
    achievement_qml = _text("rendering/quick/qml/AchievementPulsePresentation.qml")
    media_qml = _text("rendering/quick/qml/MediaPresentation.qml")
    abandonment_qml = _text("rendering/quick/qml/AbandonmentIssuesPresentation.qml")
    friend_qml = _text("rendering/quick/qml/FriendPulsePresentation.qml")
    weather_qml = _text("rendering/quick/qml/WeatherPresentation.qml")
    reddit_qml = _text("rendering/quick/qml/RedditPresentation.qml")
    gmail_qml = _text("rendering/quick/qml/GmailPresentation.qml")
    reddit_model = _text("rendering/quick/widgets/reddit.py")
    gmail_model = _text("rendering/quick/widgets/gmail.py")
    clock_qml = _text("rendering/quick/qml/ClockPresentation.qml")
    clock_analogue_qml = _text("rendering/quick/qml/ClockAnalogueFace.qml")
    clock_digital_qml = _text("rendering/quick/qml/ClockDigitalFace.qml")
    descriptors = _text("rendering/widget_descriptors.py")
    general_settings = _text("ui/tabs/widgets_tab_defaults.py")
    media_settings = _text("ui/tabs/widgets_tab_media.py")
    steam_settings = _text("ui/tabs/widgets_tab_steam.py")
    canonical_defaults = _text("core/settings/default_settings.py")

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
    assert "child_content_requirement" in session
    assert "def begin_child_resize(" in owner
    assert "def preview_child_resize(" in owner
    assert "def update_child_resize(" in owner
    assert "def begin_child_move(" in owner
    assert "def update_child_move(" in owner
    assert "def cancel_child_gesture(" in owner
    assert "resolve_child_resize_geometry(" in owner
    assert "resolve_child_move_geometry(" in owner
    assert "class ResolvedChildResize" in child
    assert "def resolve_child_resize_geometry(" in child
    assert "def resolve_child_move_geometry(" in child
    assert "role.uniform_scale" in child
    assert "width - next_visible_width" in child
    assert "height - next_visible_height" in child
    assert 'QByteArray(b"presentationItem")' in overlay_model
    assert 'QByteArray(b"childCollisionEnabled")' in overlay_model
    assert "child_collision_enabled: bool = False" in session
    assert '"widgets.global.child_collision_enabled"' in owner
    assert 'f"widgets.{widget_id}.child_collision_enabled"' not in owner
    assert 'QCheckBox("Enable Child Widget Collisions")' in general_settings
    assert 'tab._default_bool("global", "child_collision_enabled")' in general_settings
    assert "media_child_collision_enabled" not in media_settings
    assert 'f"{key}_child_collision_enabled"' not in steam_settings
    assert canonical_defaults.count("'child_collision_enabled': False") == 1
    assert "if (editFrame.childCollisionEnabled)" in qml
    # Disabling peer collision must not disable sibling alignment discovery or
    # fixed family obstacles.  The peer-collision gate belongs only to
    # obstacleRects' editable-role admission.
    collision_gate = qml.index("if (editFrame.childCollisionEnabled)")
    fixed_obstacles = qml.index("presentation.customEditableChildObstacles", collision_gate)
    sibling_guides = qml.index('"kind": "sibling-edge"')
    assert collision_gate < fixed_obstacles
    assert sibling_guides > fixed_obstacles
    assert "def beginChildResize(" in overlay_model
    assert "def previewChildResize(" in overlay_model
    # Resize and move have deliberately separate handler contracts. Placement
    # compensation belongs only to free movement; leaking those names into the
    # resize slot used to leave a runtime NameError that py_compile cannot catch.
    overlay_tree = ast.parse(overlay_model)
    begin_resize_node = next(
        node for node in ast.walk(overlay_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "beginChildResize"
    )
    begin_resize_names = {
        node.id for node in ast.walk(begin_resize_node) if isinstance(node, ast.Name)
    }
    assert "placement_compensation_x" not in begin_resize_names
    assert "placement_compensation_y" not in begin_resize_names
    assert "def resizeChild(" in overlay_model
    assert "def childResizeHandles(" in overlay_model
    assert "def ensureChildContentExtent(" in overlay_model
    assert "def clearChildContentExtent(" in overlay_model
    assert "def ensure_child_content_extent(" in owner
    assert "def clear_child_content_extent(" in owner
    assert "item.child_content_requirement = (requested_width, requested_height)" in owner
    assert "def restore_authored_child_geometry(" in session
    assert "payload = item.restore_authored_child_geometry(payload)" in owner
    assert "child = item.child_content_requirement" in size
    assert "Qt.callLater(function()" not in qml
    # The old synchronous reentrancy guard still mutated Python extent INSIDE
    # a QML geometry-change callback. Queue the exact reconciliation on the
    # stable root and resolve the current selection at flush instead.
    assert "childRequirementSyncQueued = true" in qml
    assert "Qt.callLater(customLayoutOverlay.flushSelectedChildRequirementSync)" in qml
    assert "requirementSyncInProgress" not in qml
    assert "childRoleLoader.item !== childRoleLayer" in qml
    assert "function syncRequirementNow()" in qml
    assert "function aggregateRequiredContentSize()" in qml
    assert "frame.occupiedX + frame.occupiedWidth" in qml
    assert "childRoleLoader.item.syncRequirementNow()" in qml
    # Parent-driven mapped positions are NEVER new child-content requirements.
    assert "onOccupiedXChanged: childRoleLayer.scheduleRequirementSync()" not in qml
    assert "onOccupiedHeightChanged: childRoleLayer.scheduleRequirementSync()" not in qml
    assert "onChildStateRevisionChanged:" in qml
    assert "function ensureImmediateChildOverflow(" in qml
    assert 'const shiftX = axes.indexOf("horizontal") >= 0' in qml
    assert 'const shiftY = axes.indexOf("vertical") >= 0' in qml
    assert "peer.occupiedX + shiftX + peer.occupiedWidth" in qml
    assert "peer.occupiedY + shiftY + peer.occupiedHeight" in qml
    assert "function scheduleRequirementSync()" in qml
    # Wheel, white corners, blue sides and blue diagonals all synchronize the
    # exact selected-child floor before a parent gesture can capture its origin.
    assert qml.count("editFrame.syncChildRequirementNow()") >= 4
    assert "onRequiredContentWidthChanged: scheduleRequirementSync()" in qml
    assert "onRequiredContentHeightChanged: scheduleRequirementSync()" in qml
    assert "clearChildContentExtent(" in qml
    assert "const horizontalCandidate = occupiedRectAt(" in qml
    assert "horizontalCandidate.y + horizontalCandidate.height" in qml
    assert "def _custom_layout_presentation_item(" in scene
    assert "property var customEditableChildRoles: []" in root_qml
    assert "property var customEditableChildRequirementTarget: null" in root_qml
    assert "customEditableChildRequirementTarget: customChildRequirement" in achievement_qml
    # Media accessory extends the outer root, not the card-child legal surface.
    # No child-driven growth requirement may turn internal CUSTOM into an
    # alternative parent sizing authority.
    assert "customEditableChildRequirementTarget: null" in media_qml
    assert "id: customChildRequirement" not in media_qml
    assert "customEditableChildRequirementTarget: customChildRequirement" in abandonment_qml
    # Parent reflow belongs only to roles that remain on their authored rail.
    # A freely placed BACKLOG must keep its authored-relative X while the parent
    # right edge reclaims empty space; the live parent displacement is folded
    # once into the move gesture through the existing compensation hook.
    assert "readonly property bool backlogFollowsParentRightRail:" in abandonment_qml
    assert "readonly property real backlogParentReflowX: backlogFollowsParentRightRail" in abandonment_qml
    # Unflipped BACKLOG follows the parent's right rail. A flipped on-rail
    # BACKLOG occupies the left accessory rail instead; both feed the SAME
    # editor gesture via one placement-compensation expression.
    assert "abandonmentRoot.headerFlipped && abandonmentRoot.backlogOnAuthoredRail" in abandonment_qml
    assert "? 18.0 - (abandonmentRoot.baseAuthoredWidth" in abandonment_qml
    assert ": abandonmentRoot.backlogParentReflowX" in abandonment_qml
    assert ": abandonmentRoot.baseAuthoredWidth" in abandonment_qml
    assert "+ abandonmentRoot.backlogParentReflowX" in abandonment_qml
    assert "readonly property real backlogRight:" in abandonment_qml
    assert "readonly property real backlogParentReflowX: backlogFollowsParentRightRail" in abandonment_qml
    assert '"roleId": "flavour_text"' in abandonment_qml
    assert "childOnAuthoredResizeRail(" in abandonment_qml
    assert "childAxisOnAuthoredResizeRail(" in abandonment_qml
    assert "resizeCompensation" in abandonment_qml
    assert '"resizeReflowRoleIds"' in abandonment_qml
    assert '"resizeReflowGate"' in abandonment_qml
    assert "customEditReflowEnabled" in abandonment_qml
    # Moving a role off its authored rail must toggle an edit-only gate, not
    # rebuild the Repeater model from an offset-dependent ternary mid-gesture.
    assert '"resizeReflowRoleIds": abandonmentRoot.' not in abandonment_qml
    assert '"target": controlsRow' in media_qml
    # Friend Pulse has one constant-size edit schema: singleton chrome plus three
    # grouped repeated roles. Repeated friend delegates never acquire per-row
    # geometry state. The containing friend frame intentionally ignores only its
    # own nested avatar/username peers for collision; snapping remains shared.
    for role_id in (
        "header", "online_count", "separator",
        "friend_frames", "avatars", "usernames",
    ):
        assert f'"roleId": "{role_id}"' in friend_qml
    assert 'id: customFriendFrameRoleTarget' in friend_qml
    assert 'id: customAvatarRoleTarget' in friend_qml
    assert 'id: customUsernameRoleTarget' in friend_qml
    assert '"collisionIgnoreRoleIds": ["avatars", "usernames"]' in friend_qml
    assert '"collisionIgnoreRoleIds": ["friend_frames"]' in friend_qml
    assert "readonly property var collisionIgnoreRoleIds:" in qml
    assert "frameIgnoresPeer || peerIgnoresFrame" in qml
    assert "Timer {" not in friend_qml
    # Weather rollout is complete at semantic-element granularity: every ready
    # presentation block is descriptor-backed, including optional forecast bands.
    for role_id in (
        "location_text", "condition_text", "condition_icon",
        "details_separator", "details_metrics",
        "forecast_separator", "forecast_text",
        "extended_separator", "extended_label", "extended_text",
    ):
        assert f'"{role_id}"' in descriptors
        assert f'"roleId": "{role_id}"' in weather_qml
    assert 'id: statusTitle' in weather_qml
    assert 'id: statusAction' in weather_qml
    assert 'weatherModel.customChildGeometry' in weather_qml
    assert "Timer {" not in weather_qml

    # Feed rollback: only singleton Header/Refresh are admitted. Authored
    # sibling anchors and pure outer-Y row population are never child geometry.
    for source in (reddit_qml, gmail_qml):
        for role_id in ("header", "refresh"):
            assert f'"roleId": "{role_id}"' in source
        assert 'LayoutMirroring.childrenInherit:' not in source
        assert 'readonly property bool headerFlipped:' in source
        assert 'contentReversed:' in source
        assert '"roleId": "post_rows"' not in source
        assert '"roleId": "message_rows"' not in source
    for retired in ("post_rows", "post_time", "post_titles", "post_separators",
                    "message_rows", "envelopes", "timestamps", "senders",
                    "subjects", "message_actions", "message_separators",
                    "boundary_separators"):
        assert f'"roleId": "{retired}"' not in reddit_qml + gmail_qml
    # Retained explicit rails avoid flipped anchor-strength loops that once
    # widened ageText across the row and blanked the post title.
    assert 'x: redditRoot.headerFlipped ? 0.0 : ageText.width + 4.0' in reddit_qml
    assert 'parent.width - ageText.width - redditRoot.flippedTitleAgeGap' in reddit_qml
    assert 'ageValueText.width + redditRoot.ageValueAgoGap' in reddit_qml
    assert 'postRailBudget' in reddit_qml
    assert 'emailRailBudget' in gmail_qml
    assert 'Math.floor(postRailBudget / (naturalRowHeight + baseRowSpacing))' in reddit_qml
    assert 'Math.floor(emailRailBudget / (naturalRowHeight + baseRowSpacing))' in gmail_qml
    assert 'Timer {' not in reddit_qml + gmail_qml

    # Analogue Clock has exactly one center-owned face edit target. Numerals,
    # markers and hands share its scale and cannot obscure its edit hit area.
    for role_id in (
        "clock_face", "separator", "calendar_text", "timezone_text", "time_text",
    ):
        assert f'"{role_id}"' in descriptors
    assert '"roleId": "clock_face"' in clock_qml
    assert '"centeredResize": true' in clock_qml
    assert '"allowParentGrowth": false' in clock_qml
    assert '"roleId": "numerals"' not in clock_qml
    assert '"numerals", axes=' not in descriptors
    assert 'customNumeralsTarget' not in clock_analogue_qml
    assert 'childWidthScale("numerals")' not in clock_analogue_qml
    assert 'id: faceCoreUnderlay' in clock_analogue_qml
    assert 'id: faceCoreHands' in clock_analogue_qml
    assert 'id: numeralGroup' in clock_analogue_qml
    assert clock_analogue_qml.count(
        'Scale { origin.x: staticFace.centerX; origin.y: staticFace.centerY; '
        'xScale: analogueFace.childWidthScale("clock_face")'
    ) == 3
    assert 'faceCoreEditTarget.width / 2.0' in clock_analogue_qml
    assert 'faceCoreEditTarget.height / 2.0' in clock_analogue_qml
    assert 'faceInkRadius' in clock_analogue_qml
    assert '"roleId": "time_text"' in clock_qml
    assert 'clockModel.customChildGeometry' in clock_digital_qml
    assert "Timer {" not in clock_qml + clock_analogue_qml + clock_digital_qml
    assert "id: childRoleLoader" in qml
    assert "active: editFrame.selectedForChildEdit" in qml
    # Visualizer deliberately resolves no ordinary child-presentation QObject. Qt
    # may surface that Python None as QML undefined, so every child-edit dereference
    # must go through one null+undefined lifecycle gate. Parent handles call
    # syncChildRequirementNow() before beginResize; regressing this check aborts the
    # Visualizer resize press with a TypeError.
    assert "readonly property bool hasPresentationItem:" in qml
    assert "presentationItem !== null && presentationItem !== undefined" in qml
    assert "|| !editFrame.hasPresentationItem" in qml
    assert "&& editFrame.hasPresentationItem" in qml
    assert "customEditableChildRequirementTarget !== null" in qml
    assert 'objectName: "customLayoutChildRole-"' in qml
    assert 'readonly property string controlsWedgeSide:' in qml
    assert 'readonly property bool controlsWedgeVertical:' in qml
    assert 'width: editFrame.controlsWedgeVertical ? 22 : 104' in qml
    assert 'height: editFrame.controlsWedgeVertical ? 104 : 22' in qml
    assert 'editFrame.controlsWedgeSide === "right"\n                        ? 90' in qml
    assert "function admitChildMove(" in qml
    # Editable peers are hard at first contact but can be crossed with a small,
    # deliberate pressure threshold. Fixed family obstacles remain absolute and
    # the peer is never mutated as part of the selected role's transaction.
    assert "function tryChildPeerPassX(" in qml
    assert "function tryChildPeerPassY(" in qml
    assert "const resistance = 14.0" in qml
    assert '"passThrough": true' in qml
    assert "obstacleRect.passThrough = false" in qml
    assert "childMoveCandidateDeepensOverlap(" in qml
    # Crossing rebases the active pointer gesture onto the admitted far side,
    # otherwise the next sample would immediately request the pre-pass side.
    assert "property real movePassBiasX: 0.0" in qml
    assert "property real movePassBiasY: 0.0" in qml
    assert "frame.movePassBiasX += pass.coordinate - x" in qml
    assert "frame.movePassBiasY += pass.coordinate - y" in qml
    assert "+ childRoleFrame.movePassBiasX" in qml
    assert "+ childRoleFrame.movePassBiasY" in qml
    assert "function admitChildResize(" in qml
    assert "sessionModel.previewChildResize(" in qml
    assert "if (!bounded.valid)" in qml
    assert "resizeReflowRoleIds" in qml
    assert "frame.resizeReflowRoleIds || []" in qml
    assert "resizeReflowAxes" in qml
    assert "frame.resizeReflowAxes || []" in qml
    assert "function clampIndirectReflowShift(" in qml
    assert 'obstacleRects(frame, false, "")' in qml
    assert 'obstacleRects(\n                                frame, true, "horizontal"' in qml
    assert 'obstacleRects(\n                                frame, true, "vertical"' in qml
    assert 'reflowAxes.indexOf(String(resizeAxis || "")) >= 0' in qml
    assert "const admittedWidthDelta = clampIndirectReflowShift(" in qml
    assert "const admittedHeightDelta = clampIndirectReflowShift(" in qml
    assert '"resizeReflowAxes": ["horizontal"]' in abandonment_qml
    assert abandonment_qml.count('"resizeReflowAxes": ["vertical"]') >= 4
    assert '"resizeReflowAxes": ["vertical"]' in media_qml
    assert "resizeReflowGate" in qml
    assert "frame.resizeReflowEnabled" in qml
    assert "peer.resizeReflowEnabled" in qml
    assert "placementCompensationX" in qml
    assert "placementCompensationY" in qml
    assert "customEditPlacementCompensationX" in qml
    assert "customEditPlacementCompensationY" in qml
    assert "placement_compensation_x" in owner
    assert "placement_compensation_y" in owner
    assert "shelfGroupOnAuthoredRail" in abandonment_qml
    assert "property real customEditPlacementCompensationX" in abandonment_qml
    assert "property real customEditPlacementCompensationY" in abandonment_qml
    assert "onCountChanged: childRoleLayer.scheduleRequirementSync()" in qml
    assert "onModelChanged: childRoleLayer.scheduleRequirementSync()" in qml
    assert "Component.onDestruction" in qml
    assert "width: 8" in qml and "height: 8" in qml
    assert "childResizeHandles(" in qml
    # Pre-rollout editor polish is shared, not family-local: child movement can
    # align against parent/sibling edges and centres with finite hysteresis, and
    # current child roles default to four resize corners.
    assert "CHILD_RESIZE_HANDLES" in child
    assert 'CHILD_RESIZE_HANDLES = ("top_left", "top_right", "bottom_left", "bottom_right")' in child
    assert "function childGuideTargets(" in qml
    assert "function snapChildAxis(" in qml
    assert '"kind": "sibling-edge"' in qml
    assert '"kind": "sibling-center"' in qml
    assert 'objectName: "customLayoutChildVerticalGuide"' in qml
    assert 'objectName: "customLayoutChildHorizontalGuide"' in qml
    child_layer_start = qml.index("id: childRoleLayer")
    child_layer_end = qml.index("// One family-wide retained requirement", child_layer_start)
    child_layer = qml[child_layer_start:child_layer_end]
    assert "opacity: 0.0" in child_layer
    assert "NumberAnimation on opacity" in child_layer
    assert "to: 1.0" in child_layer
    assert "duration: 110" in child_layer
    assert "semanticSnapKind(activeKind) ? 28.0 : 11.0" in qml
    assert "distance <= 18.0" in qml
    assert "distance <= 6.0" in qml
    # Alignment is an admitted role capability inside child_geometry, not a
    # family-owned side store. Only eligible roles render the tiny centre flip.
    assert "alignment_flip: bool = False" in child
    assert "def flip_child_alignment(" in child
    assert "def flip_child_alignment(" in owner
    assert "def childAlignmentFlippable(" in overlay_model
    assert "def flipChildAlignment(" in overlay_model
    assert 'objectName: "customLayoutChildAlignmentFlip-"' in qml
    assert 'text: "↔"' in qml
    assert "customGameNameAlignment" in abandonment_qml
    assert "customFlavourAlignment" in abandonment_qml
    assert "customBacklogAlignment" in abandonment_qml
    assert "customLastVisitAlignment" in abandonment_qml
    assert "customShelfGroupAlignment" in abandonment_qml
    assert '"roleId": "header"' in abandonment_qml
    assert "semanticCornerInsetX" in abandonment_qml
    assert "semanticCornerInsetY" in abandonment_qml
    assert "customHeaderAnchor" in abandonment_qml
    assert "contentReversed" in abandonment_qml
    assert "semantic_corner_anchor: bool = False" in child
    assert "def set_child_semantic_anchor(" in child
    assert "def childSemanticCornerAnchorCapable(" in overlay_model
    assert "def setChildSemanticAnchor(" in overlay_model
    assert "function semanticCornerFromSnaps(" in qml
    # Obstruction chrome is explicitly session-local now. No delayed/guessed
    # gesture return remains: the attached wedge toggles glyph buttons only.
    assert "property bool parentGlyphControlsHidden: false" in qml
    assert 'objectName: "customLayoutParentGlyphToggle-"' in qml
    assert '"SHOW CONTROLS" : "HIDE CONTROLS"' in qml
    assert "parentGlyphControlsOpacity" in qml
    assert "duration: 180" in qml
    assert "childGestureActive" not in qml
    assert "? 1000 : 3000" not in qml
    assert "function overlapsEditRect(candidate)" in qml
    assert "childLayer.overlapsEditRect(candidate)" in qml

    # Child editing is selection/pointer driven only. No recurring scheduler is
    # permitted for observing retained child geometry or keeping handles alive.
    combined = (
        child + session + owner + size + overlay_model + scene + qml + root_qml
        + achievement_qml + media_qml + abandonment_qml
    )
    assert "Timer {" not in qml
    assert "QTimer" not in child
    assert "QTimer" not in session






def test_live_child_edit_path_is_in_memory_gui_work_until_explicit_save() -> None:
    owner_text = _text("rendering/quick/custom_layout_owner.py")
    overlay_text = _text("rendering/quick/custom_layout_overlay.py")
    scene_text = _text("rendering/quick/scene_controller.py")

    owner_tree = ast.parse(owner_text)
    owner_cls = next(
        node for node in owner_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "QuickCustomLayoutOwner"
    )
    live_names = {
        "begin_child_resize", "preview_child_resize", "update_child_resize",
        "begin_child_move", "update_child_move", "cancel_child_gesture",
        "ensure_child_content_extent", "clear_child_content_extent",
    }
    live_nodes = [
        node for node in owner_cls.body
        if isinstance(node, ast.FunctionDef) and node.name in live_names
    ]
    assert {node.name for node in live_nodes} == live_names
    forbidden_attrs = {
        "save", "set_widgets_map", "submit", "start", "write_text",
        "write_bytes", "open",
    }
    for node in live_nodes:
        attrs = {
            child.attr for child in ast.walk(node)
            if isinstance(child, ast.Attribute)
        }
        names = {
            child.id for child in ast.walk(node)
            if isinstance(child, ast.Name)
        }
        assert not (attrs & forbidden_attrs), (node.name, attrs & forbidden_attrs)
        assert "open" not in names, node.name

    # Disk persistence stays at the explicit Save/reset boundaries, not pointer
    # cadence. The scene projection is retained model/QQuickItem mutation only.
    assert "self._settings_manager.save()" in owner_text
    apply_method = scene_text.split("def _apply_custom_layout_item", 1)[1].split(
        "def _active_custom_layout_item", 1
    )[0]
    assert "apply_custom_layout_size_payload" in apply_method
    assert "presentation.set_geometry" in apply_method
    assert ".save(" not in apply_method
    assert "submit(" not in apply_method

    combined = owner_text + overlay_text
    assert "import threading" not in combined
    assert "QThread" not in combined
    assert "QTimer" not in combined


def test_live_child_pointer_samples_do_not_duplicate_exact_requirement_scans() -> None:
    qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")

    # Pointer motion performs provisional grow-only overflow admission, commits
    # the child, then lets retained occupied-rect notifications coalesce one exact
    # reconciliation. A second synchronous aggregate scan per motion sample was
    # redundant and could amplify dense-role drag cost. Release keeps an explicit
    # final sync as a deterministic gesture boundary.
    move_area = qml.split("id: childMoveArea", 1)[1]
    move_motion = move_area.split("onPositionChanged: function(mouse)", 1)[1].split(
        "onReleased: function(mouse)", 1
    )[0]
    assert "sessionModel.moveChild(" in move_motion
    assert "childRoleLayer.syncRequirementNow()" not in move_motion

    resize_area = qml.split("id: childResizeHandle", 1)[1]
    resize_motion = resize_area.split("onPositionChanged: function(mouse)", 1)[1].split(
        "onReleased: function(mouse)", 1
    )[0]
    # Corner and invisible-edge delegates intentionally share one resize pipeline.
    # Live motion delegates into it instead of cloning the preview/admission/commit
    # sequence in every MouseArea.  Exact containment remains release-only here;
    # retained occupied-rect changes coalesce the live exact reconciliation.
    assert "childRoleLayer.updateChildResizeGesture(" in resize_motion
    assert "childRoleLayer.syncRequirementNow()" not in resize_motion
    shared_resize = qml.split("function updateChildResizeGesture(", 1)[1].split(
        "function cancelChildResizeGesture(", 1
    )[0]
    assert "sessionModel.resizeChild(" in shared_resize
    assert "if (finalize)" in shared_resize
    assert "syncRequirementNow()" in shared_resize
    assert shared_resize.index("if (finalize)") < shared_resize.index("syncRequirementNow()")
    assert "Qt.callLater(customLayoutOverlay.flushSelectedChildRequirementSync)" in qml
    assert "requirementSyncInProgress" not in qml
    assert "Qt.callLater(function()" not in qml


def test_child_containment_growth_is_one_way_rounded_and_noop_republish_bounded() -> None:
    owner = _text("rendering/quick/custom_layout_owner.py")
    method = owner.split("def ensure_child_content_extent", 1)[1].split(
        "def resize_wheel", 1
    )[0]

    # A containment floor must never round below the requested logical edge.
    assert "int(math.ceil(next_width * scale))" in method
    assert "int(math.ceil(next_height * scale))" in method
    # When display clamping means the outer rect/extent is already the admitted
    # result, keep the transient floor but do not notify/project the same geometry
    # again for each live pointer sample.
    assert "local.width() == current.width()" in method
    assert "local.height() == current.height()" in method
    assert "return False" in method


def test_display_local_overlay_does_not_republish_stable_remote_pointer_chatter() -> None:
    overlay_model = _text("rendering/quick/custom_layout_overlay.py")

    handler = overlay_model.split("def _on_session_item_changed", 1)[1].split(
        "def _on_session_selection_changed", 1
    )[0]
    assert "if (prior_row is None) != (not belongs_here):" in handler
    assert "self.refresh()" in handler
    assert "if prior_row is None:\n            return" in handler
    assert "self._publish_item_change(item)" in handler
    assert "self._item_revisions[item_key]" in handler
    # Stable remote changes must not fall through to the scene publisher. The
    # refresh branch remains responsible for actual display membership changes.
    assert handler.index("if prior_row is None:") < handler.index(
        "self._publish_item_change(item)"
    )


def test_friend_pulse_grouped_roles_reuse_shared_owner_without_per_friend_state() -> None:
    descriptors = _text("rendering/widget_descriptors.py")
    model = _text("rendering/quick/widgets/friend_pulse.py")
    qml = _text("rendering/quick/qml/FriendPulsePresentation.qml")

    for role_id in (
        "header", "online_count", "separator",
        "friend_frames", "avatars", "usernames",
    ):
        assert f'"{role_id}"' in descriptors
        assert f'"roleId": "{role_id}"' in qml
    assert 'uniform_scale=True' in descriptors
    assert 'customGeometryChanged = Signal()' in model
    assert 'def set_custom_child_geometry(self, child_geometry: object)' in model
    assert 'frame_width_scale=float(self._custom_friend_frame_geometry[0])' in model
    assert 'objectName: "friendPulseCustomFriendFrameRoleTarget"' in qml
    assert 'objectName: "friendPulseCustomAvatarRoleTarget"' in qml
    assert 'objectName: "friendPulseCustomUsernameRoleTarget"' in qml
    assert 'friendRoot.customAvatarScale' in qml
    assert 'customFriendFrameWidthScale' in qml
    assert 'customUsernameWidthScale' in qml
    # The repeated delegate identity is never used as a child_geometry key.
    assert '"friend_frames_" + index' not in qml
    assert '"avatars_" + index' not in qml
    assert '"usernames_" + index' not in qml
    assert 'Timer {' not in qml


def test_friend_repeated_children_keep_live_authored_xy_reflow_and_proxy_parity() -> None:
    qml = _text("rendering/quick/qml/FriendPulsePresentation.qml")
    # The accepted pre-child-editor list filled the real viewport.  Replacing
    # this with a frozen baseAuthoredWidth leaked empty space as parent X grew.
    assert qml.count("Math.max(72.0, activityRowsView.width - 12.0)") == 2
    # Grid delegates and their edit proxy must derive their base from the same
    # live cell geometry. Shared CUSTOM scales remain uniform across delegates.
    assert "Math.max(72.0, gridCell.width - 12.0)" in qml
    assert "Math.max(72.0, activityGridView.cellWidth - 12.0)" in qml
    assert "customFriendFrameRoleTarget.width - 14.0" in qml
    assert "Math.min(58.0, Math.max(38.0, gridTile.width * 0.42))" in qml
    assert "Math.min(58.0, Math.max(38.0,\n                customFriendFrameRoleTarget.width * 0.42))" in qml
    assert '"friend_frames_" + index' not in qml
    assert "Timer {" not in qml


def test_custom_settings_lock_scopes_steam_cards_independently() -> None:
    descriptors = _text("rendering/widget_descriptors.py")
    settings = _text("ui/tabs/widgets_tab.py")

    assert 'section_id="steam_achievement_pulse"' in descriptors
    assert 'section_id="steam_abandonment_issues"' in descriptors
    assert 'section_id="steam_friend_pulse"' in descriptors
    assert 'widget_ids=("achievement_pulse",)' in descriptors
    assert 'widget_ids=("abandonment_issues",)' in descriptors
    assert 'widget_ids=("friend_pulse",)' in descriptors
    assert '"abandonment_issues_artwork_shape"' in descriptors
    assert '"abandonment_issues_artwork_size"' in descriptors
    assert 'restore_widget_family_to_authored_layout(widgets_cfg, widget_id)' in settings
    assert 'restore_all_custom_layouts_to_authored_layout(widgets_cfg)' not in settings
    assert 'Disable Custom</a> To Adjust!' in settings


def test_child_edit_selection_owns_transient_retirement_without_stale_row_cleanup() -> None:
    owner = _text("rendering/quick/custom_layout_owner.py")
    qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")

    assert "session.subscribe_selection(self._on_child_edit_selection_changed)" in owner
    assert "def _on_child_edit_selection_changed(" in owner
    assert "self.cancel_child_gesture(previous)" in owner
    assert "self.clear_child_content_extent(previous)" in owner
    assert "session.unsubscribe_selection(self._on_child_edit_selection_changed)" in owner

    # QML destruction hooks are defensive selected-parent fallbacks only. Stable
    # object identity in Python owns selection teardown, so a stale delegate row
    # cannot clear/cancel a newly reindexed session item.
    assert qml.count("&& editFrame.selectedForChildEdit") >= 2


def test_abandonment_dense_child_editor_reuses_shared_roles_without_new_cadence() -> None:
    child = _text("rendering/custom_child_geometry.py")
    descriptors = _text("rendering/widget_descriptors.py")
    model = _text("rendering/quick/widgets/abandonment_issues.py")
    qml = _text("rendering/quick/qml/AbandonmentIssuesPresentation.qml")

    assert "def freeform_layout_block_child_role(" in child
    for role_id in ("backlog_block", "game_name", "flavour_text", "last_visit", "shelf_group"):
        assert f'"{role_id}"' in descriptors
    assert "freeform_artwork_child_role(" in descriptors
    assert "self.customGeometryChanged.emit()" in model
    assert "size_payload.child_geometry" in model

    # One grouped ledger target/factor pair, never one persisted record per shelf.
    assert '"roleId": "shelf_group"' in qml
    assert '"target": ledgerGroupFrame' in qml
    assert "customShelfGroupWidthScale" in qml
    assert "customShelfGroupHeightScale" in qml
    assert "PreserveAspectCrop" in qml

    # Reflow is rail-aware: once a role is explicitly placed it stops dragging
    # downstream siblings. Automatic parent growth is not allowed to become a
    # new child anchor, which prevents resize -> outer-grow -> child-jump loops.
    assert "readonly property bool artworkOnAuthoredRail" in qml
    assert "readonly property bool backlogOnAuthoredRail" in qml
    assert "readonly property real backlogLayoutHeightDelta" in qml
    assert "readonly property real gameNameLayoutHeightDelta" in qml
    assert "readonly property bool backlogFollowsParentRightRail:" in qml
    assert "x: (abandonmentRoot.headerFlipped && abandonmentRoot.backlogOnAuthoredRail" in qml
    assert ": abandonmentRoot.baseAuthoredWidth" in qml
    assert "+ abandonmentRoot.backlogParentReflowX" in qml
    assert "readonly property real backlogRight:" in qml
    assert "backlogParentReflowX" not in qml.split(
        "readonly property real backlogRight:", 1
    )[1].split("readonly property real backlogBottom:", 1)[0]
    assert "y: 160.0\n                        + (abandonmentRoot.lastVisitOnAuthoredRail" in qml
    assert "y: 226.0\n                        + (abandonmentRoot.shelfGroupOnAuthoredRail" in qml
    assert "readonly property bool shelfGroupOnAuthoredRail" in qml
    assert "customEditPlacementCompensationX" in qml
    assert "customEditPlacementCompensationY" in qml
    assert "extraContentHeight * 0.20" not in qml
    assert "extraContentHeight * 0.65" not in qml
    assert "id: customChildRequirement" in qml
    assert "customEditableChildRequirementTarget: customChildRequirement" in qml

    # Resizing a title must preserve its text. It may shrink and/or wrap, but
    # CUSTOM width changes must not fall back to right-side truncation.
    assert "id: gameTitle" in qml
    assert "maximumLineCount: 2" in qml
    assert "fontSizeMode: Text.Fit" in qml
    assert "elide: Text.ElideNone" in qml

    # Freeform artwork must not churn decorative delegates at pointer cadence.
    assert "readonly property int stripeCount" in qml
    assert "model: artworkFrame.stripeCount" in qml
    assert "index * artworkFrame.stripeStep" in qml
    assert "model: Math.ceil((artworkFrame.width + artworkFrame.height)" not in qml

    combined = child + descriptors + model + qml
    assert "Timer {" not in qml
    assert "QTimer" not in model


def test_custom_edit_pointer_ownership_blocks_product_actions_without_a_timer() -> None:
    """CUSTOM owns pointer semantics above both retained QML and window routing."""

    scene = _text("rendering/quick/scene_controller.py")
    window = _text("rendering/quick/window.py")
    input_controller = _text("rendering/quick/input_controller.py")
    overlay_model = _text("rendering/quick/custom_layout_overlay.py")
    edit_qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    host = _text("rendering/quick/widgets/host.py")
    root_qml = _text("rendering/quick/qml/OverlayWidget.qml")

    # The window-level gate suppresses product pointer semantics while preserving
    # the editor's own context menu. Other events still flow to QQuickWindow/QML.
    assert "self._custom_layout_input_blocked = False" in window
    assert "def set_custom_layout_input_blocked(self, blocked: bool)" in window
    assert window.count("if self._custom_layout_input_blocked:") >= 4
    assert "handle_custom_layout_context_press" in window
    assert "handle_custom_layout_context_release" not in window
    assert "event.button() == Qt.MouseButton.RightButton" in window
    assert "super().mousePressEvent(event)" in window
    assert "super().mouseReleaseEvent(event)" in window
    assert "super().mouseDoubleClickEvent(event)" in window

    # Scene lifecycle must bracket both native/runtime and retained-family input.
    bind_start = scene.index("def bind_custom_layout_session(")
    bind_end = scene.index("def _custom_layout_presentation_item(", bind_start)
    bind = scene[bind_start:bind_end]
    assert "self._window.set_custom_layout_input_blocked(True)" in bind
    assert "self.ordinary_widget_host.set_custom_layout_input_blocked(True)" in bind

    clear_start = scene.index("def clear_custom_layout_session(")
    clear_end = scene.index("def _apply_custom_layout_item(", clear_start)
    clear = scene[clear_start:clear_end]
    assert "host.set_custom_layout_input_blocked(False)" in clear
    assert "self._window.set_custom_layout_input_blocked(False)" in clear
    assert clear.index("overlay.clear_session()") < clear.index(
        "host.set_custom_layout_input_blocked(False)"
    )

    # Ordinary families also receive a full-root retained blocker so handlers
    # that do not consume QuickInputState still cannot activate underneath Edit.
    assert "def set_custom_layout_input_blocked(self, blocked: bool)" in host
    assert 'property bool customLayoutInputBlocked: false' in root_qml
    assert 'id: customLayoutInputBlockerLoader' in root_qml
    assert "active: overlayWidget.customLayoutInputBlocked && overlayWidget.visible" in root_qml
    assert "acceptedButtons: Qt.AllButtons" in root_qml
    assert "onDoubleClicked:" in root_qml
    assert "onWheel:" in root_qml

    # Empty-background double-click is an editor Save/Apply command, while the
    # native runtime's slideshow double-click remains suppressed.
    assert 'objectName: "customLayoutBackgroundSaveArea"' in edit_qml
    assert "sessionModel.requestSave()" in edit_qml
    assert "save_requested = Signal()" in overlay_model
    assert "def requestSave(self)" in overlay_model
    assert "handle_custom_layout_context_press" in input_controller
    assert "context_menu_requested.emit" in input_controller

    # Input suppression is state/event driven, not another edit cadence.
    combined = scene + window + input_controller + overlay_model + edit_qml + host + root_qml
    assert "Timer {" not in root_qml
    assert "QTimer" not in host


def test_custom_edit_input_owns_pointer_before_runtime_replacement_guard() -> None:
    window = _text("rendering/quick/window.py")
    press = window.split("def mousePressEvent", 1)[1].split("def mouseMoveEvent", 1)[0]
    release = window.split("def mouseReleaseEvent", 1)[1].split("def mouseDoubleClickEvent", 1)[0]
    double = window.split("def mouseDoubleClickEvent", 1)[1].split(
        "def _runtime_discrete_pointer_event_is_suppressed", 1
    )[0]
    for body in (press, release, double):
        assert body.index("if self._custom_layout_input_blocked:") < body.index(
            "_runtime_discrete_pointer_event_is_suppressed"
        )
    assert "super().mousePressEvent(event)" in press
    assert "super().mouseReleaseEvent(event)" in release
    assert "super().mouseDoubleClickEvent(event)" in double


def test_child_editor_has_invisible_axis_edges_and_timid_step_growth() -> None:
    qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    overlay = _text("rendering/quick/custom_layout_overlay.py")
    child = _text("rendering/custom_child_geometry.py")

    assert "def resize_edges(self)" in child
    assert "def admits_resize_handle(self, handle: str)" in child
    assert "def childResizeEdges(" in overlay
    assert 'objectName: "customLayoutChildResizeEdge-"' in qml
    assert "Qt.SizeHorCursor" in qml
    assert "Qt.SizeVerCursor" in qml
    assert "function throttleChildAutoGrowth(" in qml
    assert "const pointerThreshold = 12.0" in qml
    assert "const growthStep = 6.0" in qml
    assert "Timer {" not in qml


def test_child_resize_corner_and_edge_share_one_gesture_pipeline() -> None:
    qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    assert "function beginChildResizeGesture(" in qml
    assert "function updateChildResizeGesture(" in qml
    assert "function cancelChildResizeGesture(" in qml
    assert qml.count("beginChildResizeGesture(") >= 3  # definition + corner + edge
    assert qml.count("updateChildResizeGesture(") >= 5  # definition + update/release for both
    # Canonical model calls live in the shared function rather than duplicated
    # once per visible/invisible resize affordance.
    # Ordinary pointer samples make one canonical preview. A snapped edge
    # may make one additional preview, still from this single shared gesture.
    assert qml.count("sessionModel.previewChildResize(") == 2
    assert "Math.abs(snapped.x - canonical.x) > 0.01" in qml
    assert qml.count("sessionModel.resizeChild(") == 1


def test_selected_edit_role_containment_and_mapped_transform_contract() -> None:
    editor = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    weather = _text("rendering/quick/qml/WeatherPresentation.qml")
    media = _text("rendering/quick/qml/MediaPresentation.qml")

    # Current role geometry must always depend on normalized CUSTOM revision
    # AND reflowing/scaled ancestors. mapToItem alone registers neither.
    dependency = editor.split("readonly property real mappingDependency:", 1)[1].split(
        "readonly property point mappedTopLeft:", 1
    )[0]
    assert "editFrame.childStateRevision" in dependency
    assert "dependency.scale + dependency.rotation" in dependency
    assert "containmentTarget.scale + containmentTarget.rotation" in dependency

    # A physical role's true surface, not the whole root, owns clipping.
    assert "function childContainmentRect(frame)" in editor
    assert "const bounds = childContainmentRect(frame)" in editor
    assert "modelData.containmentTarget || null" in editor
    assert "modelData.allowParentGrowth !== false" in editor
    assert "if (!frame.allowParentGrowth)" in editor
    assert "admitted = containChildResize(frame, handle, gesture, admitted)" in editor
    assert "if (frame.allowParentGrowth)" in editor
    assert "if (!within(start))" in editor  # corrupt inherited layouts must not grow
    assert "for (let i = 0; i < 12; ++i)" in editor  # bounded gesture admission

    # Weather's fitted, centered column must remap the true child edit boxes
    # without waking the service or giving children a parent-growth pathway.
    assert "roles[i].geometryDependencies = [weatherContent, readyColumn," in weather
    assert "roles[i].containmentTarget = weatherContent" in weather
    assert "roles[i].allowParentGrowth = false" in weather

    # Media card vs optional external volume have separate legal surfaces;
    # card saved offsets must never change when accessory availability toggles.
    assert "readonly property real childNormalizationWidth: canonicalPreferredCardWidth" in media
    assert "roles[i].containmentTarget = mediaColumn" in media
    assert "roles[i].allowParentGrowth = false" in media
    assert '"containmentTarget": appVolumeSlider' in media
    assert '"normalizationWidth": canonicalPreferredCardWidth\n                    + canonicalVolumeAccessoryExtent' in media
    assert "customEditableChildRequirementTarget: null" in media


def test_centered_clock_face_is_canonical_and_old_numerals_retire_on_admission() -> None:
    geometry = _text("rendering/custom_child_geometry.py")
    descriptors = _text("rendering/widget_descriptors.py")
    owner = _text("rendering/quick/custom_layout_owner.py")
    editor = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    analogue = _text("rendering/quick/qml/ClockAnalogueFace.qml")
    assert "centered_resize: bool = False" in geometry
    assert "dx *= 2.0" in geometry and "dy *= 2.0" in geometry
    assert "uniform scaling and fixed center" in geometry
    assert "uniform_scale=True, centered_resize=True, movable=False" in descriptors
    assert "if role.centered_resize:" in owner
    assert '"clock3": frozenset(("numerals",))' in owner
    assert 'centered_face.pop("x_offset", None)' in owner
    assert 'centered_face.pop("y_offset", None)' in owner
    assert "modelData.centeredResize === true" in editor
    assert "gesture.startX - (width - gesture.startWidth) / 2.0" in editor
    assert "gesture.startY - (height - gesture.startHeight) / 2.0" in editor
    assert "if (!inside || !frame.centeredResize)" in editor
    assert "frame.centeredResize" in editor
    assert "? canonical" in editor
    assert 'childOffsetX("clock_face")' not in analogue
    assert 'childOffsetY("clock_face")' not in analogue


def test_resize_uses_shared_guides_without_override_of_descriptor_or_collision() -> None:
    qml = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    assert "function snapChildResizeAxis(frame, edge, horizontal)" in qml
    assert "function snapChildResizePointer(frame, handle, gesture, point)" in qml
    assert "function validateChildResizeGuides(frame, handle, rect)" in qml
    assert "const targets = childGuideTargets(frame, horizontal)" in qml
    assert "const surface = childContainmentRect(frame)" in qml
    assert "parentStart + parentSize / 2.0" in qml
    assert "frame.hasResizeSnapX = false" in qml
    assert "frame.hasResizeSnapY = false" in qml
    assert "const snapped = snapChildResizePointer(" in qml
    # The second Python bridge is conditional, and every snapped pointer is
    # canonicalized before the live collision + containment admission.
    update = qml.split("function updateChildResizeGesture(", 1)[1].split(
        "function cancelChildResizeGesture(", 1
    )[0]
    assert "const bounded = customLayoutOverlay.sessionModel.previewChildResize(" in update
    assert "Math.abs(snapped.x - canonical.x) > 0.01" in update
    assert "const resnapped = customLayoutOverlay.sessionModel.previewChildResize(" in update
    assert update.index("const resnapped") < update.index("let admitted")
    assert update.index("let admitted") < update.index("validateChildResizeGuides(")
    assert update.index("validateChildResizeGuides(") < update.index("ensureImmediateChildOverflow(")
    assert "childVerticalGuides = []" in qml
    assert "childHorizontalGuides = []" in qml
