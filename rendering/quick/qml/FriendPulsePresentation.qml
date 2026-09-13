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

    signal refreshRequested()
    signal friendActionRequested(int rowIndex)
    signal gameActionRequested(int rowIndex)
    signal friendPinToggleRequested(int rowIndex)
    signal messageActionRequested(int rowIndex)
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
    property bool messageMenuOpen: false

    function closeActionMenu(armPointerGuard) {
        if (menuRowIndex < 0)
            return
        menuRowIndex = -1
        activeActionIdentity = ""
        if (armPointerGuard)
            actionMenuPointerGesture()
    }

    function closeMessageMenu(armPointerGuard) {
        if (!messageMenuOpen)
            return
        messageMenuOpen = false
        if (armPointerGuard)
            actionMenuPointerGesture()
    }

    function twoDigitCount(value) {
        var count = Math.max(0, Math.floor(Number(value) || 0))
        return count < 10 ? "0" + String(count) : String(count)
    }

    function openActionMenu(rowIndex, friendAvailable, gameAvailable, anchor) {
        if (!friendPulseModel.interactionEnabled || !friendAvailable)
            return
        closeMessageMenu(false)
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

    function activateUnreadMessages() {
        var count = friendPulseModel.unreadMessageCount
        if (!friendPulseModel.interactionEnabled || count <= 0)
            return
        closeActionMenu(false)
        if (count === 1) {
            messageActionRequested(0)
            actionMenuPointerGesture()
            return
        }
        messageMenuOpen = true
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
            var rowStride = 58.0
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
            && friendRoot.menuRowIndex < 0 && !friendRoot.messageMenuOpen
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: friendRoot.refreshRequested()
    }

    Connections {
        target: friendRoot.friendPulseModel
        function onStateChanged() {
            friendRoot.closeActionMenu(false)
            if (friendRoot.friendPulseModel.unreadMessageCount <= 1)
                friendRoot.closeMessageMenu(false)
            friendRoot.pendingChangeRows = ({})
        }
        function onFriendChangePulseRequested(rowIndex) {
            friendRoot.triggerChangeGlow(rowIndex)
        }
        function onUnreadMessagePulseRequested() {
            unreadMessageLine.triggerEventGlow()
        }
    }

    BrandedHeader {
        id: headerFrame
        frameObjectName: "friendPulseHeaderFrame"
        logoObjectName: "friendPulseSteamLogo"
        textObjectName: "friendPulseHeaderText"
        x: 18.0; y: 14.0
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
        x: 296.0; y: 13.0
        width: friendRoot.friendPulseModel.authoredWidth - x - 18.0; height: 56.0
        Rectangle {
            id: unreadMessageLine
            objectName: "friendPulseUnreadMessageLine"
            property real eventGlowLevel: 0.0
            anchors.fill: parent
            visible: friendRoot.friendPulseModel.unreadMessageCount > 0
            radius: 8.0
            color: "transparent"

            function triggerEventGlow() {
                messageGlowAnimation.stop()
                eventGlowLevel = 0.0
                messageGlowAnimation.restart()
            }

            SequentialAnimation {
                id: messageGlowAnimation
                onRunningChanged: {
                    if (typeof widgetFrameDemand !== 'undefined' && widgetFrameDemand)
                        widgetFrameDemand.setAnimationActive(messageGlowAnimation, running)
                }
                NumberAnimation { target: unreadMessageLine; property: "eventGlowLevel"; to: 1.0; duration: 2000; easing.type: Easing.InOutQuad }
                NumberAnimation { target: unreadMessageLine; property: "eventGlowLevel"; to: 0.0; duration: 3000; easing.type: Easing.OutCubic }
            }

            ShaderEffect {
                readonly property real glowDistance: 4.0 + unreadMessageLine.eventGlowLevel
                readonly property real glowScale: Math.max(0.5, glowDistance / 12.0)
                x: -glowDistance; y: -glowDistance
                width: unreadMessageLine.width + glowDistance * 2.0
                height: unreadMessageLine.height + glowDistance * 2.0
                property vector2d effectSize: Qt.vector2d(width / glowScale, height / glowScale)
                property vector2d cardSize: Qt.vector2d(unreadMessageLine.width / glowScale, unreadMessageLine.height / glowScale)
                property real cornerRadius: unreadMessageLine.radius / glowScale
                property color glowColor: friendRoot.friendPulseModel.accentColor
                opacity: unreadMessageLine.eventGlowLevel * 0.82
                visible: opacity > 0.001
                z: -1
                fragmentShader: "shaders/widget_glow.frag.qsb"
            }

            ShadowedText {
                anchors.fill: parent
                text: friendRoot.friendPulseModel.unreadMessageText
                color: unreadSummaryHover.hovered && friendRoot.friendPulseModel.unreadMessageCount > 0
                    ? friendRoot.friendPulseModel.accentColor
                    : friendRoot.friendPulseModel.mutedTextColor
                font.family: friendRoot.friendPulseModel.fontFamily
                font.pointSize: friendRoot.friendPulseModel.fontSize * 1.02
                font.bold: true
                fontSizeMode: Text.HorizontalFit
                minimumPointSize: 8.0
                horizontalAlignment: Text.AlignRight; verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
                shadowColor: friendRoot.friendPulseModel.textShadowColor
                shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
                shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
            }
            HoverHandler {
                id: unreadSummaryHover
                enabled: friendRoot.friendPulseModel.interactionEnabled
                    && friendRoot.friendPulseModel.unreadMessageCount > 0
            }
            TapHandler {
                enabled: friendRoot.friendPulseModel.interactionEnabled
                    && friendRoot.friendPulseModel.unreadMessageCount > 0
                acceptedButtons: Qt.LeftButton
                onTapped: friendRoot.activateUnreadMessages()
            }
        }
    }

    Rectangle {
        x: 18.0; y: 81.0; width: friendRoot.friendPulseModel.authoredWidth - 36.0
        height: friendRoot.friendStrokeWidth(1.0); color: friendRoot.friendPulseModel.rowInnerBorderColor
    }

    ListView {
        id: activityRowsView
        objectName: "friendPulseRowsView"
        onContentHeightChanged: friendRoot.clampScrollToBounds(activityRowsView)
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
            x: 6.0; width: activityRowsView.width - 12.0; height: 50.0; radius: 9.0
            color: friendRoot.friendPulseModel.rowSurfaceColor
            border.color: friendRoot.friendPulseModel.rowBorderColor
            border.width: friendRoot.friendStrokeWidth(1.0)
            antialiasing: true
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
                onRunningChanged: {
                    if (typeof widgetFrameDemand !== 'undefined' && widgetFrameDemand)
                        widgetFrameDemand.setAnimationActive(rowEventGlowAnimation, running)
                }
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

            Rectangle {
                id: rowAvatarFrame
                objectName: "friendPulseRowAvatar_" + index
                x: 7.0; anchors.verticalCenter: parent.verticalCenter
                width: 36.0; height: width; radius: 8.0
                color: Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g,
                               friendRoot.friendPulseModel.accentColor.b, rowAvatarHover.hovered ? 0.38 : 0.22)
                border.color: friendRoot.friendPulseModel.rowInnerBorderColor; border.width: friendRoot.friendStrokeWidth(1.0); antialiasing: true
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
                Text { anchors.fill: parent; visible: avatarSource.length === 0; text: primaryText.length > 0 ? primaryText.charAt(0).toUpperCase() : ""; color: friendRoot.friendPulseModel.accentColor; font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 1.1; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                Rectangle { anchors.fill: parent; radius: parent.radius; color: "transparent"; border.color: friendRoot.friendPulseModel.rowInnerBorderColor; border.width: friendRoot.friendStrokeWidth(1.0); antialiasing: true; z: 2 }
                HoverHandler { id: rowAvatarHover; enabled: friendRoot.friendPulseModel.interactionEnabled && friendActionAvailable }
                TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled && friendActionAvailable; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.friendActionRequested(index) }
            }
            Item {
                x: 54.0; y: 5.0; width: parent.width - x - 65.0; height: 40.0
                ShadowedText { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 23.0; text: primaryText; color: friendRoot.friendPulseModel.textColor; font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize; font.bold: true; verticalAlignment: Text.AlignVCenter; wrap: true; maximumLineCount: 2; fontSizeMode: Text.Fit; minimumPointSize: 7.0; elide: Text.ElideNone; shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled; shadowColor: friendRoot.friendPulseModel.textShadowColor; shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX; shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY }
                ShadowedText {
                    anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 18.0
                    text: (secondaryText.length > 0
                        ? secondaryText + "  " + presenceText
                        : presenceText).toUpperCase()
                    color: rowGameHover.hovered ? friendRoot.friendPulseModel.accentColor : friendRoot.friendPulseModel.mutedTextColor
                    font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 0.72; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                    shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled; shadowColor: friendRoot.friendPulseModel.textShadowColor; shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX; shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
                    HoverHandler { id: rowGameHover; enabled: friendRoot.friendPulseModel.interactionEnabled && gameActionAvailable }
                    TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled && gameActionAvailable; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.gameActionRequested(index) }
                }
            }
            Rectangle {
                id: rowPinButton
                objectName: "friendPulsePinButton_" + index
                visible: friendActionAvailable && activityRowHover.hovered
                width: 22.0; height: 22.0; radius: 6.0
                anchors.right: rowMenuButton.left; anchors.rightMargin: 2.0; anchors.verticalCenter: parent.verticalCenter
                color: rowPinHover.hovered || pinned
                    ? Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g, friendRoot.friendPulseModel.accentColor.b, pinned ? 0.34 : 0.22)
                    : "transparent"
                Item {
                    anchors.centerIn: parent; width: 11.0; height: 14.0
                    Rectangle { x: 2.0; y: 1.0; width: 7.0; height: 7.0; radius: 1.0; rotation: 45; color: pinned ? friendRoot.friendPulseModel.accentColor : friendRoot.friendPulseModel.mutedTextColor; antialiasing: true }
                    Rectangle { x: 4.5; y: 6.0; width: 2.0; height: 7.0; radius: 1.0; color: pinned ? friendRoot.friendPulseModel.accentColor : friendRoot.friendPulseModel.mutedTextColor; antialiasing: true }
                }
                HoverHandler { id: rowPinHover; enabled: friendRoot.friendPulseModel.interactionEnabled }
                TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.friendPinToggleRequested(index) }
            }
            Rectangle {
                id: rowMenuButton
                objectName: "friendPulseMenuButton_" + index
                visible: friendActionAvailable
                width: 24.0; height: 30.0; radius: 7.0
                anchors.right: parent.right; anchors.rightMargin: 7.0; anchors.verticalCenter: parent.verticalCenter
                color: rowMenuHover.hovered ? Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g, friendRoot.friendPulseModel.accentColor.b, 0.24) : "transparent"
                Text { anchors.fill: parent; text: "⋮"; color: friendRoot.friendPulseModel.mutedTextColor; font.pixelSize: 20.0; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                HoverHandler { id: rowMenuHover; enabled: friendRoot.friendPulseModel.interactionEnabled }
                TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.openActionMenu(index, friendActionAvailable, gameActionAvailable, rowMenuButton) }
            }
        }
    }

    GridView {
        id: activityGridView
        objectName: "friendPulseGridView"
        onContentHeightChanged: friendRoot.clampScrollToBounds(activityGridView)
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
        cellHeight: Math.max(120.0, Math.min(154.0,
                                              height / Math.max(1, Math.ceil(rosterCapacity / activeColumns))))
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
                y: 2.0; width: Math.max(72.0, parent.width - 12.0); height: parent.height - 12.0
                property real eventGlowLevel: 0.0
                radius: 11.0; color: friendRoot.friendPulseModel.rowSurfaceColor
                border.color: friendRoot.friendPulseModel.rowBorderColor
                border.width: friendRoot.friendStrokeWidth(1.0)
                antialiasing: true
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
                    onRunningChanged: {
                        if (typeof widgetFrameDemand !== 'undefined' && widgetFrameDemand)
                            widgetFrameDemand.setAnimationActive(gridEventGlowAnimation, running)
                    }
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
                Rectangle {
                    id: gridAvatarFrame
                    anchors.horizontalCenter: parent.horizontalCenter; y: 12.0
                    width: Math.min(58.0, Math.max(38.0, parent.width * 0.42)); height: width; radius: 12.0
                    color: Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g, friendRoot.friendPulseModel.accentColor.b, gridAvatarHover.hovered ? 0.38 : 0.22)
                    border.color: friendRoot.friendPulseModel.rowInnerBorderColor; border.width: friendRoot.friendStrokeWidth(1.0); antialiasing: true
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
                    Text { anchors.fill: parent; visible: avatarSource.length === 0; text: primaryText.length > 0 ? primaryText.charAt(0).toUpperCase() : ""; color: friendRoot.friendPulseModel.accentColor; font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 1.28; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    Rectangle { anchors.fill: parent; radius: parent.radius; color: "transparent"; border.color: friendRoot.friendPulseModel.rowInnerBorderColor; border.width: friendRoot.friendStrokeWidth(1.0); antialiasing: true; z: 2 }
                    HoverHandler { id: gridAvatarHover; enabled: friendRoot.friendPulseModel.interactionEnabled && friendActionAvailable }
                    TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled && friendActionAvailable; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.friendActionRequested(index) }
                }
                ShadowedText {
                    id: gridNameText
                    objectName: "friendPulseGridName_" + index
                    anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 7.0; anchors.rightMargin: 7.0
                    y: gridAvatarFrame.y + gridAvatarFrame.height + 5.0
                    height: friendRoot.friendPulseModel.showNames
                        ? Math.max(19.0, friendRoot.friendPulseModel.nameFontSize * 1.3)
                        : 0.0
                    visible: friendRoot.friendPulseModel.showNames; text: primaryText; color: friendRoot.friendPulseModel.textColor
                    font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.nameFontSize; font.bold: true
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    wrap: true; maximumLineCount: 2; fontSizeMode: Text.Fit; minimumPointSize: 7.0; elide: Text.ElideNone
                    shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled; shadowColor: friendRoot.friendPulseModel.textShadowColor; shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX; shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
                }
                ShadowedText {
                    anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 7.0; anchors.rightMargin: 7.0
                    y: friendRoot.friendPulseModel.showNames
                        ? gridNameText.y + gridNameText.height + 2.0
                        : gridAvatarFrame.y + gridAvatarFrame.height + 5.0
                    height: 30.0
                    text: (secondaryText.length > 0
                        ? presenceText + "  " + secondaryText
                        : presenceText).toUpperCase()
                    color: gridGameHover.hovered ? friendRoot.friendPulseModel.accentColor : friendRoot.friendPulseModel.mutedTextColor
                    font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 0.68
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; maximumLineCount: 2; wrap: true; elide: Text.ElideRight
                    shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled; shadowColor: friendRoot.friendPulseModel.textShadowColor; shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX; shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
                    HoverHandler { id: gridGameHover; enabled: friendRoot.friendPulseModel.interactionEnabled && gameActionAvailable }
                    TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled && gameActionAvailable; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.gameActionRequested(index) }
                }
                Rectangle {
                    id: gridPinButton
                    objectName: "friendPulsePinButton_" + index
                    visible: friendActionAvailable && gridTileHover.hovered
                    anchors.left: parent.left; anchors.leftMargin: 6.0; anchors.top: parent.top; anchors.topMargin: 6.0
                    width: 22.0; height: 22.0; radius: 6.0
                    color: gridPinHover.hovered || pinned
                        ? Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g, friendRoot.friendPulseModel.accentColor.b, pinned ? 0.34 : 0.22)
                        : "transparent"
                    Item {
                        anchors.centerIn: parent; width: 11.0; height: 14.0
                        Rectangle { x: 2.0; y: 1.0; width: 7.0; height: 7.0; radius: 1.0; rotation: 45; color: pinned ? friendRoot.friendPulseModel.accentColor : friendRoot.friendPulseModel.mutedTextColor; antialiasing: true }
                        Rectangle { x: 4.5; y: 6.0; width: 2.0; height: 7.0; radius: 1.0; color: pinned ? friendRoot.friendPulseModel.accentColor : friendRoot.friendPulseModel.mutedTextColor; antialiasing: true }
                    }
                    HoverHandler { id: gridPinHover; enabled: friendRoot.friendPulseModel.interactionEnabled }
                    TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.friendPinToggleRequested(index) }
                }
                Rectangle {
                    id: gridMenuButton
                    objectName: "friendPulseMenuButton_" + index
                    visible: friendActionAvailable
                    anchors.right: parent.right; anchors.rightMargin: 6.0; anchors.top: parent.top; anchors.topMargin: 4.0
                    width: 24.0; height: 28.0; radius: 7.0
                    color: gridMenuHover.hovered ? Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g, friendRoot.friendPulseModel.accentColor.b, 0.24) : "transparent"
                    Text { anchors.fill: parent; text: "⋮"; color: friendRoot.friendPulseModel.mutedTextColor; font.pixelSize: 20.0; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    HoverHandler { id: gridMenuHover; enabled: friendRoot.friendPulseModel.interactionEnabled }
                    TapHandler { enabled: friendRoot.friendPulseModel.interactionEnabled; acceptedButtons: Qt.LeftButton; onTapped: friendRoot.openActionMenu(index, friendActionAvailable, gameActionAvailable, gridMenuButton) }
                }
            }
        }
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
        id: messageMenuLayer
        objectName: "friendPulseMessageMenuLayer"
        anchors.fill: parent; z: 105
        visible: friendRoot.messageMenuOpen
        MouseArea {
            anchors.fill: parent
            enabled: parent.visible && friendRoot.friendPulseModel.interactionEnabled
            onClicked: friendRoot.closeMessageMenu(true)
        }
        Rectangle {
            id: messagePopup
            objectName: "friendPulseMessagePopup"
            width: Math.min(300.0, Math.max(220.0, friendRoot.friendPulseModel.authoredWidth * 0.48))
            height: Math.min(200.0, messageList.contentHeight) + 16.0
            radius: 10.0
            x: friendRoot.friendPulseModel.authoredWidth - width - 18.0
            y: 72.0
            color: friendRoot.friendPulseModel.headerFillColor
            border.color: friendRoot.friendPulseModel.headerBorderColor
            border.width: friendRoot.friendStrokeWidth(2.0)

            ListView {
                id: messageList
                x: 8.0; y: 8.0; width: parent.width - 16.0
                height: parent.height - 16.0
                spacing: 3.0; clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: friendRoot.friendPulseModel.messageModel
                delegate: Rectangle {
                    id: messageRow
                    required property string displayName
                    required property string avatarSource
                    required property int unreadCount
                    required property int lastMessageAt
                    required property int index
                    width: messageList.width; height: 42.0; radius: 7.0
                    color: messageRowHover.hovered
                        ? Qt.rgba(friendRoot.friendPulseModel.accentColor.r,
                                  friendRoot.friendPulseModel.accentColor.g,
                                  friendRoot.friendPulseModel.accentColor.b, 0.22)
                        : "transparent"
                    Rectangle {
                        id: messageAvatarFrame
                        x: 5.0; anchors.verticalCenter: parent.verticalCenter
                        width: 30.0; height: width; radius: 7.0
                        color: Qt.rgba(friendRoot.friendPulseModel.accentColor.r,
                                       friendRoot.friendPulseModel.accentColor.g,
                                       friendRoot.friendPulseModel.accentColor.b, 0.18)
                        border.color: friendRoot.friendPulseModel.rowInnerBorderColor
                        border.width: friendRoot.friendStrokeWidth(1.0)
                        Item {
                            anchors.fill: parent; anchors.margins: 1.0; clip: true
                            Image {
                                anchors.fill: parent; source: avatarSource
                                visible: avatarSource.length > 0
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true; cache: true
                                layer.enabled: visible
                                layer.effect: MultiEffect {
                                    maskEnabled: true
                                    maskSource: messageAvatarMask
                                }
                            }
                            Rectangle {
                                id: messageAvatarMask
                                anchors.fill: parent; radius: 6.0
                                visible: false; layer.enabled: true
                            }
                        }
                        Text {
                            anchors.fill: parent; visible: avatarSource.length === 0
                            text: displayName.length > 0 ? displayName.charAt(0).toUpperCase() : ""
                            color: friendRoot.friendPulseModel.accentColor
                            font.family: friendRoot.friendPulseModel.fontFamily
                            font.pointSize: friendRoot.friendPulseModel.fontSize * 0.85
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                    ShadowedText {
                        anchors.left: messageAvatarFrame.right; anchors.leftMargin: 9.0
                        anchors.right: parent.right; anchors.rightMargin: 8.0
                        anchors.verticalCenter: parent.verticalCenter; height: 28.0
                        text: friendRoot.twoDigitCount(unreadCount) + "  " + displayName.toUpperCase()
                        color: friendRoot.friendPulseModel.textColor
                        font.family: friendRoot.friendPulseModel.fontFamily
                        font.pointSize: friendRoot.friendPulseModel.fontSize * 0.76
                        font.bold: true; elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
                        shadowColor: friendRoot.friendPulseModel.textShadowColor
                        shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
                        shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
                    }
                    HoverHandler { id: messageRowHover; enabled: friendRoot.friendPulseModel.interactionEnabled }
                    TapHandler {
                        enabled: friendRoot.friendPulseModel.interactionEnabled
                        acceptedButtons: Qt.LeftButton
                        onTapped: {
                            friendRoot.messageActionRequested(index)
                            friendRoot.closeMessageMenu(true)
                        }
                    }
                }
            }
        }
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
                        color: actionHover.hovered ? Qt.rgba(friendRoot.friendPulseModel.accentColor.r, friendRoot.friendPulseModel.accentColor.g, friendRoot.friendPulseModel.accentColor.b, 0.22) : "transparent"
                        objectName: "friendPulseAction_" + modelData
                        Text { anchors.fill: parent; leftPadding: 8.0; text: modelData === "profile" ? "View Profile" : (modelData === "chat" ? "Start Chat" : (modelData === "store" ? "View Game in Store" : "Copy Steam ID")); color: friendRoot.friendPulseModel.textColor; font.family: friendRoot.friendPulseModel.fontFamily; font.pointSize: friendRoot.friendPulseModel.fontSize * 0.78; verticalAlignment: Text.AlignVCenter }
                        HoverHandler { id: actionHover; enabled: parent.enabledAction && friendRoot.friendPulseModel.interactionEnabled }
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
