import QtQuick
import QtQuick.Effects

OverlayWidget {
    id: friendRoot
    objectName: "friendPulsePresentation"


    required property var friendPulseModel
    semanticDoubleClickEnabled: friendPulseModel.interactionEnabled

    // Friend Pulse's family-local chrome was visually too faint at authored size.
    // Add 1 authored px before the shared scale-aware envelope; the shared
    // BrandedHeader deliberately does not use this helper.
    function friendStrokeWidth(baseWidth) {
        return friendRoot.scaleAwareStrokeWidth(baseWidth + 1.0)
    }
    uniformScaleTransform: true
    preferredContentWidth: friendPulseModel.authoredWidth
    preferredContentHeight: friendPulseModel.authoredHeight

    // Abandonment-style CUSTOM child geometry uses stable authored baselines.
    // Repeated friend primitives consume one grouped record each; no delegate
    // ever owns persistence or its own editable-child state.
    readonly property real baseAuthoredWidth: friendPulseModel.baseAuthoredWidth
    readonly property real baseAuthoredHeight: friendPulseModel.baseAuthoredHeight
    readonly property real customAvatarScale: friendPulseModel.customAvatarScale
    readonly property real headerSafeInsetX: 18.0
    readonly property bool headerFlipped:
        friendPulseModel.customHeaderAlignment === "right"
    readonly property real headerSafeInsetY: 14.0
    readonly property real canonicalOnlineCountX: 296.0
    readonly property real canonicalOnlineCountY: 13.0
    readonly property real canonicalOnlineCountWidth: Math.max(48.0, baseAuthoredWidth - 314.0)
    readonly property real canonicalOnlineCountHeight: 56.0
    readonly property real canonicalSeparatorX: 18.0
    readonly property real canonicalSeparatorY: 81.0
    // Follow the SAME live content-extent width as the card. The base authored
    // width is only the edit-offset normalization authority, not a live rail.
    // A user's separator width_scale continues to apply to this natural span.
    readonly property real canonicalSeparatorWidth: Math.max(1.0,
        friendPulseModel.authoredWidth - 2.0 * canonicalSeparatorX)
    readonly property real canonicalSeparatorHeight: friendStrokeWidth(1.0)
    readonly property real canonicalRowFrameWidth: Math.max(72.0, baseAuthoredWidth - 48.0)
    readonly property real canonicalRowFrameHeight: 50.0
    readonly property real canonicalRowAvatarSize: 36.0
    readonly property real canonicalGridViewportHeight: Math.max(1.0, baseAuthoredHeight - 110.0)
    readonly property int canonicalGridRows: Math.max(
        1, Math.ceil(friendPulseModel.visibleCapacity / Math.max(1, friendPulseModel.baseGridColumns))
    )
    readonly property real canonicalGridCellWidth: Math.max(1.0,
        (baseAuthoredWidth - 36.0) / Math.max(1, friendPulseModel.baseGridColumns)
    )
    readonly property real canonicalGridCellHeight: Math.max(120.0, Math.min(
        154.0, canonicalGridViewportHeight / canonicalGridRows
    ))
    readonly property real canonicalGridTileWidth: Math.max(72.0, canonicalGridCellWidth - 12.0)
    readonly property real canonicalGridTileHeight: canonicalGridCellHeight - 12.0
    readonly property real canonicalGridAvatarSize: Math.min(
        58.0, Math.max(38.0, canonicalGridTileWidth * 0.42)
    )
    readonly property real rowFrameHeight: Math.max(
        canonicalRowFrameHeight * friendPulseModel.customFriendFrameHeightScale,
        canonicalRowAvatarSize * customAvatarScale + 14.0
    )
    readonly property real gridTileHeight: Math.max(
        canonicalGridTileHeight * friendPulseModel.customFriendFrameHeightScale,
        canonicalGridAvatarSize * customAvatarScale + 60.0
    )

    // Stable retained semantic roles. Visibility is evaluated by the selected
    // Edit mapper, not by rebuilding this role list during content transitions.
    customEditableChildRoles: {
        const roles = []
        roles.push({
            "roleId": "header",
            "normalizationTarget": friendRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": headerFrame,
            // Keep model identity stable during parent X/Y reflow. The shared
            // edit frame projects these authored insets into live letterboxing.
            "semanticCornerInsetX": friendRoot.headerSafeInsetX,
            "semanticCornerInsetY": friendRoot.headerSafeInsetY,
            "semanticInsetUsesUniformCard": true
        })
        roles.push({
            "roleId": "online_count",
            "normalizationTarget": friendRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": activitySummary
        })
        roles.push({
            // The separator follows the parent width; its role cannot also
            // demand a larger parent or create a width feedback loop.
            "roleId": "separator",
            "normalizationTarget": friendRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": headerSeparator
        })
        roles.push({
            "roleId": "friend_frames",
            "normalizationTarget": friendRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": customFriendFrameRoleTarget,
            "collisionIgnoreRoleIds": ["avatars", "usernames"],
            "geometryDependencies": [activityRowsView, activityGridView]
        })
        roles.push({
            "roleId": "avatars",
            "normalizationTarget": friendRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": customAvatarRoleTarget,
            "collisionIgnoreRoleIds": ["friend_frames"],
            "geometryDependencies": [customFriendFrameRoleTarget, activityRowsView, activityGridView]
        })
        roles.push({
            "roleId": "usernames",
            "normalizationTarget": friendRoot,
            "normalizationWidthProperty": "baseAuthoredWidth",
            "normalizationHeightProperty": "baseAuthoredHeight",
            "target": customUsernameRoleTarget,
            "collisionIgnoreRoleIds": ["friend_frames"],
            "geometryDependencies": [customFriendFrameRoleTarget, customAvatarRoleTarget]
        })
        return roles
    }

    signal refreshRequested()
    signal friendActionRequested(int rowIndex)
    signal gameActionRequested(int rowIndex)
    signal friendPinToggleRequested(int rowIndex)
    signal friendMenuActionRequested(string action, int rowIndex)
    signal actionMenuPointerGesture()
    signal visibleRangeChanged(int firstIndex, int lastIndex)

    // The host already knows this retained-card convention and clears it when
    // an admitted pointer press lands outside the card.
    property string activeActionIdentity: ""
    property int menuRowIndex: -1
    property bool menuFriendActionAvailable: false
    property bool menuGameActionAvailable: false
    property real actionPopupX: 0.0
    property real actionPopupY: 0.0
    property int _reportedFirstVisible: -2
    property int _reportedLastVisible: -2
    property var pendingChangeRows: ({})
    property bool viewportReportingReady: false

    function closeActionMenu(armPointerGuard) {
        if (menuRowIndex < 0)
            return
        menuRowIndex = -1
        activeActionIdentity = ""
        if (armPointerGuard)
            actionMenuPointerGesture()
    }

    function openActionMenu(rowIndex, friendAvailable, gameAvailable, anchor) {
        if (!friendPulseModel.interactionEnabled || !friendAvailable)
            return
        var mapped = anchor.mapToItem(friendRoot, 0, anchor.height)
        menuFriendActionAvailable = friendAvailable
        menuGameActionAvailable = gameAvailable
        menuRowIndex = rowIndex
        activeActionIdentity = "friend-row-" + rowIndex
        actionPopupX = Math.max(8.0, Math.min(
            mapped.x + anchor.width - actionPopup.width,
            friendRoot.width - actionPopup.width - 8.0
        ))
        actionPopupY = Math.max(8.0, Math.min(
            mapped.y + 4.0,
            friendRoot.height - actionPopup.height - 8.0
        ))
    }

    function reportVisibleRange(forceReport) {
        if (!viewportReportingReady)
            return
        var force = forceReport === true
        var view = friendPulseModel.viewMode === "rows" ? activityRowsView : activityGridView
        if (!view.visible || view.count === 0) {
            if (force || _reportedFirstVisible !== -1 || _reportedLastVisible !== -1) {
                _reportedFirstVisible = -1
                _reportedLastVisible = -1
                pendingChangeRows = ({})
                visibleRangeChanged(-1, -1)
            }
            return
        }
        var first
        var last
        if (friendPulseModel.viewMode === "rows") {
            var rowStride = friendRoot.rowFrameHeight + activityRowsView.spacing
            first = Math.max(0, Math.floor(view.contentY / rowStride))
            last = Math.min(
                view.count - 1,
                Math.ceil((view.contentY + view.height) / rowStride) - 1
            )
        } else {
            var firstGridRow = Math.max(0, Math.floor(view.contentY / view.cellHeight))
            var lastGridRow = Math.max(
                firstGridRow,
                Math.ceil((view.contentY + view.height) / view.cellHeight) - 1
            )
            first = firstGridRow * view.activeColumns
            last = Math.min(
                view.count - 1,
                (lastGridRow + 1) * view.activeColumns - 1
            )
        }
        if (force || first !== _reportedFirstVisible || last !== _reportedLastVisible) {
            _reportedFirstVisible = first
            _reportedLastVisible = last
            // A pulse belongs only to the viewport that admitted it.  Never
            // replay a queued row-index cue after scrolling or model clamping.
            pendingChangeRows = ({})
            visibleRangeChanged(first, last)
        }
    }

    function clampScrollToBounds(view) {
        // A shrinking roster (a periodic Steam refresh returning fewer friends)
        // can leave contentY beyond the new content end. With StopAtBounds the
        // flickable only self-corrects during a live flick, so a programmatic
        // shrink otherwise keeps the view scrolled past its content and keeps
        // reporting a stale, out-of-range visible window to the avatar-hydration
        // runtime. Clamp here; the resulting contentY change re-reports a valid
        // range through onContentYChanged.
        if (!view)
            return
        var maxY = Math.max(0.0, view.contentHeight - view.height)
        if (view.contentY > maxY)
            view.contentY = maxY
    }

    function triggerChangeGlow(rowIndex) {
        var view = friendPulseModel.viewMode === "rows" ? activityRowsView : activityGridView
        if (!view.visible || view.moving
                || rowIndex < _reportedFirstVisible
                || rowIndex > _reportedLastVisible)
            return
        var delegateItem = typeof view.itemAtIndex === "function" ? view.itemAtIndex(rowIndex) : null
        if (delegateItem && delegateItem.triggerEventGlow) {
            delegateItem.triggerEventGlow()
            return
        }
        var pending = Object.assign({}, pendingChangeRows)
        pending[rowIndex] = true
        pendingChangeRows = pending
    }

    function consumeChangeGlow(rowIndex, delegateItem) {
        if (!pendingChangeRows[rowIndex])
            return
        var pending = Object.assign({}, pendingChangeRows)
        delete pending[rowIndex]
        pendingChangeRows = pending
        var view = friendPulseModel.viewMode === "rows" ? activityRowsView : activityGridView
        if (!delegateItem || !delegateItem.triggerEventGlow || view.moving
                || rowIndex < _reportedFirstVisible
                || rowIndex > _reportedLastVisible)
            return
        delegateItem.triggerEventGlow()
    }

    Component.onCompleted: {
        viewportReportingReady = true
        reportVisibleRange()
    }

    onFriendPulseModelChanged: {
        closeActionMenu(false)
    }
    onActiveActionIdentityChanged: {
        if (activeActionIdentity.length === 0)
            menuRowIndex = -1
    }

    TapHandler {
        enabled: friendRoot.friendPulseModel.interactionEnabled
            && friendRoot.menuRowIndex < 0
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: friendRoot.refreshRequested()
    }

    Connections {
        target: friendRoot.friendPulseModel
        function onStateChanged() {
            friendRoot.closeActionMenu(false)
            friendRoot.pendingChangeRows = ({})
        }
        function onFriendChangePulseRequested(rowIndex) {
            friendRoot.triggerChangeGlow(rowIndex)
        }
    }

    BrandedHeader {
        id: headerFrame
        frameObjectName: "friendPulseHeaderFrame"
        logoObjectName: "friendPulseSteamLogo"
        textObjectName: "friendPulseHeaderText"
        property real customEditPlacementCompensationX:
            friendRoot.friendPulseModel.customHeaderAnchor.length > 0
                    || friendRoot.headerFlipped
                ? x - (friendRoot.headerSafeInsetX
                    + friendRoot.friendPulseModel.customHeaderXOffset
                        * friendRoot.baseAuthoredWidth)
                : 0.0
        property real customEditPlacementCompensationY:
            friendRoot.friendPulseModel.customHeaderAnchor.length > 0
                ? y - (friendRoot.headerSafeInsetY
                    + friendRoot.friendPulseModel.customHeaderYOffset
                        * friendRoot.baseAuthoredHeight)
                : 0.0
        transformOrigin: Item.TopLeft
        scale: friendRoot.friendPulseModel.customHeaderWidthScale
        x: friendRoot.friendPulseModel.customHeaderAnchor.endsWith("right")
            ? friendRoot.friendPulseModel.authoredWidth - friendRoot.headerSafeInsetX
                - width * scale
            : (friendRoot.friendPulseModel.customHeaderAnchor.endsWith("left")
                ? friendRoot.headerSafeInsetX
                : (friendRoot.headerFlipped
                    ? friendRoot.friendPulseModel.authoredWidth
                        - friendRoot.headerSafeInsetX - width * scale
                    : friendRoot.headerSafeInsetX)
                    + friendRoot.friendPulseModel.customHeaderXOffset
                        * friendRoot.baseAuthoredWidth)
        y: friendRoot.friendPulseModel.customHeaderAnchor.startsWith("bottom")
            ? friendRoot.friendPulseModel.authoredHeight - friendRoot.headerSafeInsetY
                - height * scale
            : (friendRoot.friendPulseModel.customHeaderAnchor.startsWith("top")
                ? friendRoot.headerSafeInsetY
                : friendRoot.headerSafeInsetY
                    + friendRoot.friendPulseModel.customHeaderYOffset
                        * friendRoot.baseAuthoredHeight)
        contentReversed: friendRoot.friendPulseModel.customHeaderAlignment === "right"
        label: friendRoot.friendPulseModel.headerText
        logoSource: friendRoot.friendPulseModel.logoSource
        fillColor: friendRoot.friendPulseModel.headerFillColor
        borderColor: friendRoot.friendPulseModel.headerBorderColor
        borderWidth: friendRoot.scaleAwareHeaderStrokeWidth(friendRoot.friendPulseModel.headerBorderWidth)
        textColor: friendRoot.friendPulseModel.headerTextColor
        fontFamily: friendRoot.friendPulseModel.fontFamily
        textShadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
        textShadowColor: friendRoot.friendPulseModel.textShadowColor
        textShadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
        textShadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
        shadowEnabled: friendRoot.cardShadowEnabled
        shadowColor: Qt.rgba(friendRoot.cardShadowColor.r, friendRoot.cardShadowColor.g,
                              friendRoot.cardShadowColor.b, friendRoot.cardShadowColor.a * 0.45)
        shadowBlur: Math.max(2.0, Math.min(6.0, friendRoot.cardShadowBlur * 0.25))
        shadowOffsetX: friendRoot.cardShadowOffsetX * 1.15
        shadowOffsetY: friendRoot.cardShadowOffsetY * 1.15
    }

    Item {
        id: activitySummary
        objectName: "friendPulseSummary"
        visible: friendRoot.friendPulseModel.showOnlineCount
            && friendRoot.friendPulseModel.onlineFriendsText.length > 0
        // On the unedited authored rail, the summary follows the actual
        // parent right edge on X reflow; the baseline 296px was only correct
        // at baseline width. An explicitly moved summary is independent of
        // parent growth. Global header flip swaps the structural rail; its
        // individual text alignment remains an independent child edit.
        readonly property bool onAuthoredRightRail:
            Math.abs(friendRoot.friendPulseModel.customOnlineCountXOffset) < 0.0001
        property real customEditPlacementCompensationX: x - (
            friendRoot.canonicalOnlineCountX
                + friendRoot.friendPulseModel.customOnlineCountXOffset
                    * friendRoot.baseAuthoredWidth)
        x: (friendRoot.headerFlipped
                ? friendRoot.headerSafeInsetX
                : (onAuthoredRightRail
                    ? friendRoot.friendPulseModel.authoredWidth
                        - friendRoot.headerSafeInsetX - width
                    : friendRoot.canonicalOnlineCountX))
            + friendRoot.friendPulseModel.customOnlineCountXOffset
                * friendRoot.baseAuthoredWidth
        y: friendRoot.canonicalOnlineCountY
            + friendRoot.friendPulseModel.customOnlineCountYOffset
                * friendRoot.baseAuthoredHeight
        width: friendRoot.canonicalOnlineCountWidth
            * friendRoot.friendPulseModel.customOnlineCountWidthScale
        height: friendRoot.canonicalOnlineCountHeight
            * friendRoot.friendPulseModel.customOnlineCountHeightScale

        ShadowedText {
            anchors.fill: parent
            visible: true
            text: friendRoot.friendPulseModel.onlineFriendsText
            color: friendRoot.friendPulseModel.mutedTextColor
            font.family: friendRoot.friendPulseModel.fontFamily
            font.pointSize: friendRoot.friendPulseModel.fontSize * 0.82
            font.bold: true
            fontSizeMode: Text.HorizontalFit
            minimumPointSize: 8.0
            horizontalAlignment: (friendRoot.friendPulseModel.customOnlineCountAlignment === "right")
                !== friendRoot.headerFlipped ? Text.AlignRight : Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
            shadowColor: friendRoot.friendPulseModel.textShadowColor
            shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
            shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
        }
    }

    Rectangle {
        id: headerSeparator
        objectName: "friendPulseHeaderSeparator"
        x: friendRoot.canonicalSeparatorX
            + friendRoot.friendPulseModel.customSeparatorXOffset
                * friendRoot.baseAuthoredWidth
        y: friendRoot.canonicalSeparatorY
            + friendRoot.friendPulseModel.customSeparatorYOffset
                * friendRoot.baseAuthoredHeight
        width: friendRoot.canonicalSeparatorWidth
            * friendRoot.friendPulseModel.customSeparatorWidthScale
        height: friendRoot.canonicalSeparatorHeight
            * friendRoot.friendPulseModel.customSeparatorHeightScale
        color: friendRoot.friendPulseModel.rowInnerBorderColor
    }

    ListView {
        id: activityRowsView
        objectName: "friendPulseRowsView"
        onContentHeightChanged: {
            friendRoot.clampScrollToBounds(activityRowsView)
            if (!moving)
                friendRoot.reportVisibleRange(true)
        }
        visible: friendRoot.friendPulseModel.viewMode === "rows" && friendRoot.friendPulseModel.hasRows
                 && (friendRoot.friendPulseModel.viewState === "ready" || friendRoot.friendPulseModel.viewState === "stale")
        x: 18.0; y: 91.0; width: friendRoot.friendPulseModel.authoredWidth - 36.0
        height: friendRoot.friendPulseModel.authoredHeight - y - 19.0
        clip: true; spacing: 8.0
        interactive: friendRoot.friendPulseModel.interactionEnabled
        boundsBehavior: Flickable.StopAtBounds
        model: friendRoot.friendPulseModel.viewMode === "rows"
            ? friendRoot.friendPulseModel.rowModel : null
        onMovementEnded: friendRoot.reportVisibleRange()
        onMovementStarted: friendRoot.pendingChangeRows = ({})
        onMovingChanged: {
            if (!moving)
                friendRoot.reportVisibleRange()
        }
        onCountChanged: {
            if (!moving)
                friendRoot.reportVisibleRange(true)
        }
        onContentYChanged: {
            if (!moving)
                friendRoot.reportVisibleRange()
        }
        onHeightChanged: {
            if (!moving)
                friendRoot.reportVisibleRange()
        }
        onVisibleChanged: {
            friendRoot.closeActionMenu(false)
            if (!moving)
                friendRoot.reportVisibleRange()
        }

        delegate: Rectangle {
            id: activityRow
            required property string primaryText
            required property string secondaryText
            required property string presenceText
            required property bool isOnline
            required property bool changed
            required property string avatarSource
            required property int friendCount
            required property bool friendActionAvailable
            required property bool gameActionAvailable
            required property bool pinned
            required property int index
            property real eventGlowLevel: 0.0
            objectName: "friendPulseRow_" + index
            // Authored rows fill the LIVE viewport, just as before child editing.
            // The one shared frame scale is applied over that changing rail;
            // widening the parent must not leave baseline-sized orphan rows.
            width: Math.max(72.0, activityRowsView.width - 12.0)
                * friendRoot.friendPulseModel.customFriendFrameWidthScale
            x: (activityRowsView.width - width) / 2.0
            height: friendRoot.rowFrameHeight
            radius: 9.0
            color: friendRoot.friendPulseModel.rowSurfaceColor
            border.color: friendRoot.friendPulseModel.rowBorderColor
            border.width: friendRoot.friendStrokeWidth(1.0)
            antialiasing: true
            // Negative z paints the contact shadow behind the existing row
            // surface without wrapping/replacing its stable edit role target.
            Rectangle {
                objectName: "friendPulseRowContactShadow_" + index
                z: -1
                visible: friendRoot.cardShadowEnabled && activityRow.visible
                x: Math.max(-3.0, Math.min(3.0,
                    friendRoot.cardShadowOffsetX * 0.45))
                y: Math.max(-3.0, Math.min(3.0,
                    friendRoot.cardShadowOffsetY * 0.45))
                width: parent.width
                height: parent.height
                radius: parent.radius
                color: Qt.rgba(friendRoot.cardShadowColor.r,
                    friendRoot.cardShadowColor.g, friendRoot.cardShadowColor.b,
                    friendRoot.cardShadowColor.a * 0.22)
            }
            HoverHandler { id: activityRowHover; enabled: friendRoot.friendPulseModel.interactionEnabled }

            function triggerEventGlow() {
                if (!visible)
                    return
                rowEventGlowAnimation.stop()
                eventGlowLevel = 0.0
                rowEventGlowAnimation.restart()
            }

            Component.onCompleted: friendRoot.consumeChangeGlow(index, activityRow)

            SequentialAnimation {
                id: rowEventGlowAnimation
                NumberAnimation {
                    target: activityRow
                    property: "eventGlowLevel"
                    to: 1.0
                    duration: 2000
                    easing.type: Easing.InOutQuad
                }
                NumberAnimation {
                    target: activityRow
                    property: "eventGlowLevel"
                    to: 0.0
                    duration: 3000
                    easing.type: Easing.OutCubic
                }
            }

            ShaderEffect {
                objectName: "friendPulseRowEventGlow_" + index
                readonly property real glowDistance: 5.0 + activityRow.eventGlowLevel
                readonly property real glowScale: Math.max(0.5, glowDistance / 12.0)
                x: -glowDistance
                y: -glowDistance
                width: activityRow.width + glowDistance * 2.0
                height: activityRow.height + glowDistance * 2.0
                property vector2d effectSize: Qt.vector2d(width / glowScale, height / glowScale)
                property vector2d cardSize: Qt.vector2d(
                    activityRow.width / glowScale,
                    activityRow.height / glowScale
                )
                property real cornerRadius: activityRow.radius / glowScale
                property color glowColor: friendRoot.friendPulseModel.accentColor
                opacity: activityRow.eventGlowLevel * 0.82
                visible: opacity > 0.001
                z: 5
                fragmentShader: "shaders/widget_glow.frag.qsb"
            }

            // Contact-only avatar shadow: no extra offscreen image layer or
            // render-loop work; direction follows the shared card shadow vector.
            Rectangle {
                objectName: "friendPulseRowAvatarContactShadow_" + index
                visible: friendRoot.cardShadowEnabled && rowAvatarFrame.visible
                x: rowAvatarFrame.x + Math.max(-3.0, Math.min(3.0,
                    friendRoot.cardShadowOffsetX * 0.45))
                y: rowAvatarFrame.y + Math.max(-3.0, Math.min(3.0,
                    friendRoot.cardShadowOffsetY * 0.45))
                width: rowAvatarFrame.width
                height: rowAvatarFrame.height
                radius: rowAvatarFrame.radius
                color: Qt.rgba(friendRoot.cardShadowColor.r,
                    friendRoot.cardShadowColor.g, friendRoot.cardShadowColor.b,
                    friendRoot.cardShadowColor.a * 0.22)
            }
            Rectangle {
                id: rowAvatarFrame
                objectName: "friendPulseRowAvatar_" + index
                x: 7.0 + friendRoot.friendPulseModel.customAvatarXOffset
                    * friendRoot.baseAuthoredWidth
                y: (parent.height - height) / 2.0
                    + friendRoot.friendPulseModel.customAvatarYOffset
                        * friendRoot.baseAuthoredHeight
                width: friendRoot.canonicalRowAvatarSize * friendRoot.customAvatarScale
                height: width
                radius: Math.min(width / 2.0, 8.0 * friendRoot.customAvatarScale)
                color: Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g,
                               friendRoot.friendPulseModel.accentColor.b, 0.22)
                border.color: rowAvatarHover.hovered && rowAvatarHover.enabled
                    ? "white" : friendRoot.friendPulseModel.rowInnerBorderColor
                border.width: friendRoot.friendStrokeWidth(
                    rowAvatarHover.hovered && rowAvatarHover.enabled ? 2.25 : 1.0
                )
                antialiasing: true
                Item {
                    id: rowAvatarClip
                    anchors.fill: parent
                    anchors.margins: Math.max(1.0, friendRoot.friendStrokeWidth(1.0) / 2.0)
                    clip: true
                    Image {
                        id: rowAvatarImage
                        anchors.fill: parent
                        source: avatarSource
                        visible: avatarSource.length > 0
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        layer.enabled: avatarSource.length > 0
                        layer.effect: MultiEffect {
                            saturation: isOnline ? 0.0 : -1.0
                            maskEnabled: true
                            maskSource: rowAvatarMask
                        }
                    }
                    Rectangle {
                        id: rowAvatarMask
                        anchors.fill: parent
                        radius: Math.max(0.0, rowAvatarFrame.radius - 1.0)
                        visible: false
                        layer.enabled: true
                    }
                }
                Text { anchors.fill: parent; visible: avatarSource.length === 0; text: primaryText.length > 0 ? primaryText.charAt(0).toUpperCase() : ""; color: friendRoot.friendPulseModel.accentColor; font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 1.1 * friendRoot.customAvatarScale; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                Rectangle { anchors.fill: parent; radius: parent.radius; color: "transparent"; antialiasing: true; z: 2 }
                HoverHandler { id: rowAvatarHover; cursorShape: Qt.PointingHandCursor; enabled: friendRoot.friendPulseModel.interactionEnabled && friendActionAvailable }
                TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled && friendActionAvailable; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.friendActionRequested(index) }
            }
            Item {
                id: rowTextBlock
                x: rowAvatarFrame.x + rowAvatarFrame.width + 11.0
                y: Math.max(5.0, (parent.height - 40.0) / 2.0)
                width: Math.max(24.0, parent.width - x - 65.0)
                height: 40.0
                ShadowedText {
                    id: rowNameText
                    objectName: "friendPulseRowName_" + index
                    x: friendRoot.friendPulseModel.customUsernameXOffset
                        * friendRoot.baseAuthoredWidth
                    y: friendRoot.friendPulseModel.customUsernameYOffset
                        * friendRoot.baseAuthoredHeight
                    width: rowTextBlock.width
                        * friendRoot.friendPulseModel.customUsernameWidthScale
                    height: 23.0 * friendRoot.friendPulseModel.customUsernameHeightScale
                    text: primaryText
                    color: rowAvatarHover.hovered && rowAvatarHover.enabled
                        ? "white" : friendRoot.friendPulseModel.textColor
                    font.family: friendRoot.friendPulseModel.fontFamily
                    font.pointSize: friendRoot.friendPulseModel.fontSize
                        * friendRoot.friendPulseModel.customUsernameHeightScale
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                    wrap: true
                    maximumLineCount: 2
                    fontSizeMode: Text.Fit
                    minimumPointSize: 7.0
                    elide: Text.ElideNone
                    shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
                    shadowColor: friendRoot.friendPulseModel.textShadowColor
                    shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
                    shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
                }
                ShadowedText {
                    anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 18.0
                    text: (secondaryText.length > 0
                        ? secondaryText + "  " + presenceText
                        : presenceText).toUpperCase()
                    color: rowGameHover.hovered ? "white" : friendRoot.friendPulseModel.mutedTextColor
                    font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 0.72; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                    shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled; shadowColor: friendRoot.friendPulseModel.textShadowColor; shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX; shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
                    HoverHandler { id: rowGameHover; cursorShape: Qt.PointingHandCursor; enabled: friendRoot.friendPulseModel.interactionEnabled && gameActionAvailable }
                    TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled && gameActionAvailable; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.gameActionRequested(index) }
                }
            }
            Rectangle {
                id: rowPinButton
                objectName: "friendPulsePinButton_" + index
                visible: friendActionAvailable && activityRowHover.hovered
                width: 22.0; height: 22.0; radius: 6.0
                anchors.right: rowMenuButton.left; anchors.rightMargin: 2.0; anchors.verticalCenter: parent.verticalCenter
                color: pinned
                    ? Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g, friendRoot.friendPulseModel.accentColor.b, 0.34)
                    : rowPinHover.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.16) : "transparent"
                Item {
                    anchors.centerIn: parent; width: 11.0; height: 14.0
                    Rectangle { x: 2.0; y: 1.0; width: 7.0; height: 7.0; radius: 1.0; rotation: 45; color: pinned ? friendRoot.friendPulseModel.accentColor
                            : rowPinHover.hovered ? "white" : friendRoot.friendPulseModel.mutedTextColor; antialiasing: true }
                    Rectangle { x: 4.5; y: 6.0; width: 2.0; height: 7.0; radius: 1.0; color: pinned ? friendRoot.friendPulseModel.accentColor
                            : rowPinHover.hovered ? "white" : friendRoot.friendPulseModel.mutedTextColor; antialiasing: true }
                }
                HoverHandler { id: rowPinHover; cursorShape: Qt.PointingHandCursor; enabled: friendRoot.friendPulseModel.interactionEnabled }
                TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.friendPinToggleRequested(index) }
            }
            Rectangle {
                id: rowMenuButton
                objectName: "friendPulseMenuButton_" + index
                visible: friendActionAvailable
                width: 24.0; height: 30.0; radius: 7.0
                anchors.right: parent.right; anchors.rightMargin: 7.0; anchors.verticalCenter: parent.verticalCenter
                color: rowMenuHover.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.14) : "transparent"
                Text { anchors.fill: parent; text: "⋮"; color: rowMenuHover.hovered ? "white" : friendRoot.friendPulseModel.mutedTextColor; font.pixelSize: 20.0; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                HoverHandler { id: rowMenuHover; cursorShape: Qt.PointingHandCursor; enabled: friendRoot.friendPulseModel.interactionEnabled }
                TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.openActionMenu(index, friendActionAvailable, gameActionAvailable, rowMenuButton) }
            }
        }
    }

    GridView {
        id: activityGridView
        objectName: "friendPulseGridView"
        onContentHeightChanged: {
            friendRoot.clampScrollToBounds(activityGridView)
            if (!moving)
                friendRoot.reportVisibleRange(true)
        }
        visible: friendRoot.friendPulseModel.viewMode === "grid" && friendRoot.friendPulseModel.hasRows
                 && (friendRoot.friendPulseModel.viewState === "ready" || friendRoot.friendPulseModel.viewState === "stale")
        x: 18.0; y: 91.0; width: friendRoot.friendPulseModel.authoredWidth - 36.0
        height: friendRoot.friendPulseModel.authoredHeight - y - 19.0
        clip: true
        model: friendRoot.friendPulseModel.viewMode === "grid"
            ? friendRoot.friendPulseModel.rowModel : null
        interactive: friendRoot.friendPulseModel.interactionEnabled
        boundsBehavior: Flickable.StopAtBounds
        property int activeColumns: Math.max(1, friendRoot.friendPulseModel.gridColumns)
        property int rosterCapacity: Math.max(1, friendRoot.friendPulseModel.visibleCapacity)
        property real tileGap: 10.0
        cellWidth: width / activeColumns
        cellHeight: friendRoot.gridTileHeight + 12.0
        onCellHeightChanged: {
            if (!moving)
                friendRoot.reportVisibleRange(true)
        }
        onMovementEnded: friendRoot.reportVisibleRange()
        onMovementStarted: friendRoot.pendingChangeRows = ({})
        onMovingChanged: {
            if (!moving)
                friendRoot.reportVisibleRange()
        }
        onCountChanged: {
            if (!moving)
                friendRoot.reportVisibleRange(true)
        }
        onContentYChanged: {
            if (!moving)
                friendRoot.reportVisibleRange()
        }
        onWidthChanged: {
            if (!moving)
                friendRoot.reportVisibleRange()
        }
        onHeightChanged: {
            if (!moving)
                friendRoot.reportVisibleRange()
        }
        onActiveColumnsChanged: {
            if (!moving)
                friendRoot.reportVisibleRange()
        }
        onVisibleChanged: {
            friendRoot.closeActionMenu(false)
            if (!moving)
                friendRoot.reportVisibleRange()
        }

        delegate: Item {
            id: gridCell
            required property string primaryText
            required property string secondaryText
            required property string presenceText
            required property bool isOnline
            required property bool changed
            required property string avatarSource
            required property int friendCount
            required property bool friendActionAvailable
            required property bool gameActionAvailable
            required property bool pinned
            required property int index
            width: activityGridView.cellWidth; height: activityGridView.cellHeight
            property int gridRow: Math.floor(index / activityGridView.activeColumns)
            property int finalRowStart: Math.floor(Math.max(0, activityGridView.count - 1) / activityGridView.activeColumns) * activityGridView.activeColumns
            property int finalRowCount: activityGridView.count - finalRowStart
            property real incompleteRowShift: gridRow * activityGridView.activeColumns === finalRowStart && finalRowCount < activityGridView.activeColumns ? (activityGridView.activeColumns - finalRowCount) * activityGridView.cellWidth / 2.0 : 0.0
            function triggerEventGlow() {
                gridTile.triggerEventGlow()
            }
            Rectangle {
                id: gridTile
                objectName: "friendPulseGridTile_" + index
                x: (parent.width - width) / 2.0 + gridCell.incompleteRowShift
                y: 2.0
                // Authored grid tiles use their live cell, not a frozen
                // base-width column count (the latter broke parent X reflow).
                width: Math.max(72.0, gridCell.width - 12.0)
                    * friendRoot.friendPulseModel.customFriendFrameWidthScale
                height: friendRoot.gridTileHeight
                property real eventGlowLevel: 0.0
                radius: 11.0; color: friendRoot.friendPulseModel.rowSurfaceColor
                border.color: friendRoot.friendPulseModel.rowBorderColor
                border.width: friendRoot.friendStrokeWidth(1.0)
                antialiasing: true
                Rectangle {
                    objectName: "friendPulseGridContactShadow_" + index
                    z: -1
                    visible: friendRoot.cardShadowEnabled && gridTile.visible
                    x: Math.max(-3.0, Math.min(3.0,
                        friendRoot.cardShadowOffsetX * 0.45))
                    y: Math.max(-3.0, Math.min(3.0,
                        friendRoot.cardShadowOffsetY * 0.45))
                    width: parent.width
                    height: parent.height
                    radius: parent.radius
                    color: Qt.rgba(friendRoot.cardShadowColor.r,
                        friendRoot.cardShadowColor.g, friendRoot.cardShadowColor.b,
                        friendRoot.cardShadowColor.a * 0.22)
                }
                HoverHandler { id: gridTileHover; enabled: friendRoot.friendPulseModel.interactionEnabled }

                function triggerEventGlow() {
                    if (!visible)
                        return
                    gridEventGlowAnimation.stop()
                    eventGlowLevel = 0.0
                    gridEventGlowAnimation.restart()
                }

                Component.onCompleted: friendRoot.consumeChangeGlow(index, gridCell)

                SequentialAnimation {
                    id: gridEventGlowAnimation
                    NumberAnimation {
                        target: gridTile
                        property: "eventGlowLevel"
                        to: 1.0
                        duration: 2000
                        easing.type: Easing.InOutQuad
                    }
                    NumberAnimation {
                        target: gridTile
                        property: "eventGlowLevel"
                        to: 0.0
                        duration: 3000
                        easing.type: Easing.OutCubic
                    }
                }

                ShaderEffect {
                    objectName: "friendPulseGridEventGlow_" + index
                    readonly property real glowDistance: 5.0 + gridTile.eventGlowLevel
                    readonly property real glowScale: Math.max(0.5, glowDistance / 12.0)
                    x: -glowDistance
                    y: -glowDistance
                    width: gridTile.width + glowDistance * 2.0
                    height: gridTile.height + glowDistance * 2.0
                    property vector2d effectSize: Qt.vector2d(width / glowScale, height / glowScale)
                    property vector2d cardSize: Qt.vector2d(
                        gridTile.width / glowScale,
                        gridTile.height / glowScale
                    )
                    property real cornerRadius: gridTile.radius / glowScale
                    property color glowColor: friendRoot.friendPulseModel.accentColor
                    opacity: gridTile.eventGlowLevel * 0.82
                    visible: opacity > 0.001
                    z: 5
                    fragmentShader: "shaders/widget_glow.frag.qsb"
                }
                // Contact-only avatar shadow: no extra offscreen image layer or
                // render-loop work; direction follows the shared card shadow vector.
                Rectangle {
                    objectName: "friendPulseGridAvatarContactShadow_" + index
                    visible: friendRoot.cardShadowEnabled && gridAvatarFrame.visible
                    x: gridAvatarFrame.x + Math.max(-3.0, Math.min(3.0,
                        friendRoot.cardShadowOffsetX * 0.45))
                    y: gridAvatarFrame.y + Math.max(-3.0, Math.min(3.0,
                        friendRoot.cardShadowOffsetY * 0.45))
                    width: gridAvatarFrame.width
                    height: gridAvatarFrame.height
                    radius: gridAvatarFrame.radius
                    color: Qt.rgba(friendRoot.cardShadowColor.r,
                        friendRoot.cardShadowColor.g, friendRoot.cardShadowColor.b,
                        friendRoot.cardShadowColor.a * 0.22)
                }
                Rectangle {
                    id: gridAvatarFrame
                    objectName: "friendPulseGridAvatar_" + index
                    x: (parent.width - width) / 2.0
                        + friendRoot.friendPulseModel.customAvatarXOffset
                            * friendRoot.baseAuthoredWidth
                    y: 12.0 + friendRoot.friendPulseModel.customAvatarYOffset
                        * friendRoot.baseAuthoredHeight
                    width: Math.min(58.0, Math.max(38.0, gridTile.width * 0.42))
                        * friendRoot.customAvatarScale
                    height: width
                    radius: Math.min(width / 2.0, 12.0 * friendRoot.customAvatarScale)
                    color: Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g, friendRoot.friendPulseModel.accentColor.b, 0.22)
                    border.color: gridAvatarHover.hovered && gridAvatarHover.enabled
                        ? "white" : friendRoot.friendPulseModel.rowInnerBorderColor
                    border.width: friendRoot.friendStrokeWidth(
                        gridAvatarHover.hovered && gridAvatarHover.enabled ? 2.25 : 1.0
                    )
                    antialiasing: true
                    Item {
                        id: gridAvatarClip
                        anchors.fill: parent
                        anchors.margins: Math.max(1.0, friendRoot.friendStrokeWidth(1.0) / 2.0)
                        clip: true
                        Image {
                            id: gridAvatarImage
                            anchors.fill: parent
                            source: avatarSource
                            visible: avatarSource.length > 0
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            layer.enabled: avatarSource.length > 0
                            layer.effect: MultiEffect {
                                saturation: isOnline ? 0.0 : -1.0
                                maskEnabled: true
                                maskSource: gridAvatarMask
                            }
                        }
                        Rectangle {
                            id: gridAvatarMask
                            anchors.fill: parent
                            radius: Math.max(0.0, gridAvatarFrame.radius - 1.0)
                            visible: false
                            layer.enabled: true
                        }
                    }
                    Text { anchors.fill: parent; visible: avatarSource.length === 0; text: primaryText.length > 0 ? primaryText.charAt(0).toUpperCase() : ""; color: friendRoot.friendPulseModel.accentColor; font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 1.28 * friendRoot.customAvatarScale; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    Rectangle { anchors.fill: parent; radius: parent.radius; color: "transparent"; antialiasing: true; z: 2 }
                    HoverHandler { id: gridAvatarHover; cursorShape: Qt.PointingHandCursor; enabled: friendRoot.friendPulseModel.interactionEnabled && friendActionAvailable }
                    TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled && friendActionAvailable; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.friendActionRequested(index) }
                }
                ShadowedText {
                    id: gridNameText
                    objectName: "friendPulseGridName_" + index
                    readonly property real canonicalWidth: Math.max(20.0,
                        parent.width - 14.0
                    )
                    readonly property real canonicalHeight: Math.max(
                        19.0, friendRoot.friendPulseModel.nameFontSize * 1.3
                    )
                    x: (parent.width - width) / 2.0
                        + friendRoot.friendPulseModel.customUsernameXOffset
                            * friendRoot.baseAuthoredWidth
                    // Resize-driven authored reflow follows the shared avatar
                    // size; avatar CUSTOM movement remains a separate role.
                    y: 12.0 + Math.min(58.0, Math.max(38.0,
                        gridTile.width * 0.42)) * friendRoot.customAvatarScale + 5.0
                        + friendRoot.friendPulseModel.customUsernameYOffset
                            * friendRoot.baseAuthoredHeight
                    width: canonicalWidth
                        * friendRoot.friendPulseModel.customUsernameWidthScale
                    height: friendRoot.friendPulseModel.showNames
                        ? canonicalHeight
                            * friendRoot.friendPulseModel.customUsernameHeightScale
                        : 0.0
                    visible: friendRoot.friendPulseModel.showNames; text: primaryText; color: gridAvatarHover.hovered && gridAvatarHover.enabled
                        ? "white" : friendRoot.friendPulseModel.textColor
                    font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.nameFontSize * friendRoot.friendPulseModel.customUsernameHeightScale; font.bold: true
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    wrap: true; maximumLineCount: 2; fontSizeMode: Text.Fit; minimumPointSize: 7.0; elide: Text.ElideNone
                    shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled; shadowColor: friendRoot.friendPulseModel.textShadowColor; shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX; shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
                }
                ShadowedText {
                    anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 7.0; anchors.rightMargin: 7.0
                    y: friendRoot.friendPulseModel.showNames
                        ? gridNameText.y + gridNameText.height + 2.0
                        : 12.0 + Math.min(58.0, Math.max(38.0,
                            gridTile.width * 0.42)) * friendRoot.customAvatarScale + 5.0
                    height: 30.0
                    text: (secondaryText.length > 0
                        ? presenceText + "  " + secondaryText
                        : presenceText).toUpperCase()
                    color: gridGameHover.hovered ? "white" : friendRoot.friendPulseModel.mutedTextColor
                    font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 0.68
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; maximumLineCount: 2; wrap: true; elide: Text.ElideRight
                    shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled; shadowColor: friendRoot.friendPulseModel.textShadowColor; shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX; shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
                    HoverHandler { id: gridGameHover; cursorShape: Qt.PointingHandCursor; enabled: friendRoot.friendPulseModel.interactionEnabled && gameActionAvailable }
                    TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled && gameActionAvailable; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.gameActionRequested(index) }
                }
                Rectangle {
                    id: gridPinButton
                    objectName: "friendPulsePinButton_" + index
                    visible: friendActionAvailable && gridTileHover.hovered
                    anchors.left: parent.left; anchors.leftMargin: 6.0; anchors.top: parent.top; anchors.topMargin: 6.0
                    width: 22.0; height: 22.0; radius: 6.0
                    color: pinned
                        ? Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g, friendRoot.friendPulseModel.accentColor.b, 0.34)
                        : gridPinHover.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.16) : "transparent"
                    Item {
                        anchors.centerIn: parent; width: 11.0; height: 14.0
                        Rectangle { x: 2.0; y: 1.0; width: 7.0; height: 7.0; radius: 1.0; rotation: 45; color: pinned ? friendRoot.friendPulseModel.accentColor
                                : gridPinHover.hovered ? "white" : friendRoot.friendPulseModel.mutedTextColor; antialiasing: true }
                        Rectangle { x: 4.5; y: 6.0; width: 2.0; height: 7.0; radius: 1.0; color: pinned ? friendRoot.friendPulseModel.accentColor
                                : gridPinHover.hovered ? "white" : friendRoot.friendPulseModel.mutedTextColor; antialiasing: true }
                    }
                    HoverHandler { id: gridPinHover; cursorShape: Qt.PointingHandCursor; enabled: friendRoot.friendPulseModel.interactionEnabled }
                    TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.friendPinToggleRequested(index) }
                }
                Rectangle {
                    id: gridMenuButton
                    objectName: "friendPulseMenuButton_" + index
                    visible: friendActionAvailable
                    anchors.right: parent.right; anchors.rightMargin: 6.0; anchors.top: parent.top; anchors.topMargin: 4.0
                    width: 24.0; height: 28.0; radius: 7.0
                    color: gridMenuHover.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.14) : "transparent"
                    Text { anchors.fill: parent; text: "⋮"; color: gridMenuHover.hovered ? "white" : friendRoot.friendPulseModel.mutedTextColor; font.pixelSize: 20.0; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    HoverHandler { id: gridMenuHover; cursorShape: Qt.PointingHandCursor; enabled: friendRoot.friendPulseModel.interactionEnabled }
                    TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.openActionMenu(index, friendActionAvailable, gameActionAvailable, gridMenuButton) }
                }
            }
        }
    }

    // Retained proxies expose one representative geometry surface for each
    // repeated role. The actual delegates all consume the same model factors,
    // so edit cost/state is constant regardless of roster size.
    Item {
        id: customFriendFrameRoleTarget
        objectName: "friendPulseCustomFriendFrameRoleTarget"
        visible: friendRoot.friendPulseModel.hasRows
            && (friendRoot.friendPulseModel.viewState === "ready"
                || friendRoot.friendPulseModel.viewState === "stale")
        enabled: false
        readonly property bool rowsMode: friendRoot.friendPulseModel.viewMode === "rows"
        readonly property real gridIncompleteShift: activityGridView.count > 0
            && activityGridView.count < activityGridView.activeColumns
            ? (activityGridView.activeColumns - activityGridView.count)
                * activityGridView.cellWidth / 2.0
            : 0.0
        width: rowsMode
            ? Math.max(72.0, activityRowsView.width - 12.0)
                * friendRoot.friendPulseModel.customFriendFrameWidthScale
            : Math.max(72.0, activityGridView.cellWidth - 12.0)
                * friendRoot.friendPulseModel.customFriendFrameWidthScale
        height: rowsMode ? friendRoot.rowFrameHeight : friendRoot.gridTileHeight
        x: rowsMode
            ? activityRowsView.x + (activityRowsView.width - width) / 2.0
            : activityGridView.x + gridIncompleteShift
                + activityGridView.cellWidth / 2.0 - width / 2.0
        y: rowsMode ? activityRowsView.y : activityGridView.y + 2.0
    }

    Item {
        id: customAvatarRoleTarget
        objectName: "friendPulseCustomAvatarRoleTarget"
        visible: customFriendFrameRoleTarget.visible
        enabled: false
        readonly property bool rowsMode: customFriendFrameRoleTarget.rowsMode
        width: (rowsMode ? friendRoot.canonicalRowAvatarSize
            : Math.min(58.0, Math.max(38.0,
                customFriendFrameRoleTarget.width * 0.42)))
            * friendRoot.customAvatarScale
        height: width
        x: rowsMode
            ? customFriendFrameRoleTarget.x + 7.0
                + friendRoot.friendPulseModel.customAvatarXOffset
                    * friendRoot.baseAuthoredWidth
            : customFriendFrameRoleTarget.x
                + (customFriendFrameRoleTarget.width - width) / 2.0
                + friendRoot.friendPulseModel.customAvatarXOffset
                    * friendRoot.baseAuthoredWidth
        y: rowsMode
            ? customFriendFrameRoleTarget.y
                + (customFriendFrameRoleTarget.height - height) / 2.0
                + friendRoot.friendPulseModel.customAvatarYOffset
                    * friendRoot.baseAuthoredHeight
            : customFriendFrameRoleTarget.y + 12.0
                + friendRoot.friendPulseModel.customAvatarYOffset
                    * friendRoot.baseAuthoredHeight
    }

    Item {
        id: customUsernameRoleTarget
        objectName: "friendPulseCustomUsernameRoleTarget"
        visible: customFriendFrameRoleTarget.visible
            && (friendRoot.friendPulseModel.viewMode === "rows"
                || friendRoot.friendPulseModel.showNames)
        enabled: false
        readonly property bool rowsMode: customFriendFrameRoleTarget.rowsMode
        readonly property real rowTextBaseX:
            customAvatarRoleTarget.x + customAvatarRoleTarget.width + 11.0
        readonly property real rowTextBaseWidth: Math.max(24.0,
            customFriendFrameRoleTarget.x + customFriendFrameRoleTarget.width
                - rowTextBaseX - 65.0
        )
        readonly property real gridBaseWidth: Math.max(20.0,
            customFriendFrameRoleTarget.width - 14.0
        )
        readonly property real gridBaseHeight: Math.max(
            19.0, friendRoot.friendPulseModel.nameFontSize * 1.3
        )
        width: (rowsMode ? rowTextBaseWidth : gridBaseWidth)
            * friendRoot.friendPulseModel.customUsernameWidthScale
        height: (rowsMode ? 23.0 : gridBaseHeight)
            * friendRoot.friendPulseModel.customUsernameHeightScale
        x: rowsMode
            ? rowTextBaseX
                + friendRoot.friendPulseModel.customUsernameXOffset
                    * friendRoot.baseAuthoredWidth
            : customFriendFrameRoleTarget.x
                + (customFriendFrameRoleTarget.width - width) / 2.0
                + friendRoot.friendPulseModel.customUsernameXOffset
                    * friendRoot.baseAuthoredWidth
        y: rowsMode
            ? customFriendFrameRoleTarget.y
                + Math.max(5.0, (customFriendFrameRoleTarget.height - 40.0) / 2.0)
                + friendRoot.friendPulseModel.customUsernameYOffset
                    * friendRoot.baseAuthoredHeight
            : customFriendFrameRoleTarget.y + 12.0
                + Math.min(58.0, Math.max(38.0,
                    customFriendFrameRoleTarget.width * 0.42))
                    * friendRoot.customAvatarScale + 5.0
                + friendRoot.friendPulseModel.customUsernameYOffset
                    * friendRoot.baseAuthoredHeight
    }

    Rectangle {
        id: rosterScrollTrack
        objectName: "friendPulseScrollTrack"
        property var activeView: friendRoot.friendPulseModel.viewMode === "rows"
            ? activityRowsView : activityGridView
        visible: activeView.visible && activeView.contentHeight > activeView.height + 1.0
        x: friendRoot.friendPulseModel.authoredWidth - 14.0
        y: 94.0
        width: 3.5
        height: friendRoot.friendPulseModel.authoredHeight - y - 22.0
        radius: 1.75
        color: Qt.rgba(
            friendRoot.friendPulseModel.mutedTextColor.r,
            friendRoot.friendPulseModel.mutedTextColor.g,
            friendRoot.friendPulseModel.mutedTextColor.b,
            0.20
        )
        z: 8

        Rectangle {
            width: parent.width
            height: Math.max(
                20.0,
                parent.height * Math.min(1.0, rosterScrollTrack.activeView.height
                    / rosterScrollTrack.activeView.contentHeight)
            )
            y: (parent.height - height) * Math.min(
                1.0,
                Math.max(0.0, rosterScrollTrack.activeView.visibleArea.yPosition
                    / Math.max(0.0001, 1.0 - rosterScrollTrack.activeView.visibleArea.heightRatio))
            )
            radius: parent.radius
            color: friendRoot.friendPulseModel.accentColor
        }
    }

    Item {
        id: quietState
        objectName: "friendPulseQuietState"
        visible: !activityRowsView.visible && !activityGridView.visible
        x: 36.0; y: 104.0; width: friendRoot.friendPulseModel.authoredWidth - 72.0; height: friendRoot.friendPulseModel.authoredHeight - y - 32.0
        Rectangle { anchors.horizontalCenter: parent.horizontalCenter; y: 8.0; width: 54.0; height: 54.0; radius: 27.0; color: Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g, friendRoot.friendPulseModel.accentColor.b, 0.16); border.color: friendRoot.friendPulseModel.rowBorderColor; border.width: friendRoot.friendStrokeWidth(1.0); Text { anchors.fill: parent; text: friendRoot.friendPulseModel.viewState === "private" ? "◌" : "●"; color: friendRoot.friendPulseModel.accentColor; font.pixelSize: 25.0; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter } }
        ShadowedText { anchors.left: parent.left; anchors.right: parent.right; y: 73.0; height: 34.0; text: friendRoot.friendPulseModel.primaryMetric; color: friendRoot.friendPulseModel.textColor; font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 1.18; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled; shadowColor: friendRoot.friendPulseModel.textShadowColor; shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX; shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY }
        ShadowedText { anchors.left: parent.left; anchors.right: parent.right; y: 108.0; height: 42.0; text: friendRoot.friendPulseModel.viewState === "connect_required" ? "Connect Steam in Settings to see the friend roster." : (friendRoot.friendPulseModel.viewState === "private" ? "Steam is not exposing this friend roster." : (friendRoot.friendPulseModel.viewState === "stale" ? "This friend roster uses the last accepted Steam observation." : (friendRoot.friendPulseModel.viewState === "loading" ? "Loading the account-private friend roster first…" : "The next accepted friend-roster observation will appear here."))); color: friendRoot.friendPulseModel.mutedTextColor; font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 0.76; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; wrap: true; maximumLineCount: 2; elide: Text.ElideRight; shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled; shadowColor: friendRoot.friendPulseModel.textShadowColor; shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX; shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY }
    }


    Item {
        id: actionMenuLayer
        objectName: "friendPulseActionMenuLayer"
        anchors.fill: parent; z: 100
        visible: friendRoot.activeActionIdentity.length > 0
        MouseArea {
            anchors.fill: parent
            enabled: parent.visible && friendRoot.friendPulseModel.interactionEnabled
            onClicked: friendRoot.closeActionMenu(true)
        }
        Rectangle {
            id: actionPopup
            objectName: "friendPulseActionPopup"
            width: 176.0; height: actionColumn.height + 16.0; radius: 10.0
            x: friendRoot.actionPopupX
            y: friendRoot.actionPopupY
            color: friendRoot.friendPulseModel.headerFillColor
            border.color: friendRoot.friendPulseModel.headerBorderColor
            border.width: friendRoot.friendStrokeWidth(2.0)
            Column {
                id: actionColumn
                x: 8.0; y: 8.0; width: parent.width - 16.0; spacing: 3.0
                Repeater {
                    model: ["profile", "chat", "store", "copy_id"]
                    delegate: Rectangle {
                        required property string modelData
                        property bool enabledAction: (modelData === "profile" || modelData === "chat") ? friendRoot.menuFriendActionAvailable : (modelData === "store" ? friendRoot.menuGameActionAvailable : friendRoot.menuFriendActionAvailable)
                        visible: enabledAction; width: parent.width; height: visible ? 29.0 : 0.0; radius: 6.0
                        color: actionHover.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.12) : "transparent"
                        objectName: "friendPulseAction_" + modelData
                        Text { anchors.fill: parent; leftPadding: 8.0; text: modelData === "profile" ? "View Profile" : (modelData === "chat" ? "Start Chat" : (modelData === "store" ? "View Game in Store" : "Copy Steam ID")); color: actionHover.hovered ? "white" : friendRoot.friendPulseModel.textColor; font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 0.78; verticalAlignment: Text.AlignVCenter }
                        HoverHandler { id: actionHover; cursorShape: Qt.PointingHandCursor; enabled: parent.enabledAction && friendRoot.friendPulseModel.interactionEnabled }
                        TapHandler {
                            enabled: parent.enabledAction && friendRoot.friendPulseModel.interactionEnabled
                            acceptedButtons: Qt.LeftButton
                            onTapped: {
                                friendRoot.friendMenuActionRequested(parent.modelData, friendRoot.menuRowIndex)
                                friendRoot.closeActionMenu(true)
                            }
                        }
                    }
                }
            }
        }
    }
}
