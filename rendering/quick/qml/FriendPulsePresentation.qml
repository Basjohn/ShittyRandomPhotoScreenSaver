import QtQuick

OverlayWidget {
    id: friendRoot
    objectName: "friendPulsePresentation"

    required property var friendPulseModel
    semanticDoubleClickEnabled: friendPulseModel.interactionEnabled
    uniformScaleTransform: true
    preferredContentWidth: friendPulseModel.authoredWidth
    preferredContentHeight: friendPulseModel.authoredHeight

    signal refreshRequested()
    signal friendActionRequested(int rowIndex)
    signal gameActionRequested(int rowIndex)

    TapHandler {
        enabled: friendRoot.friendPulseModel.interactionEnabled
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: friendRoot.refreshRequested()
    }

    BrandedHeader {
        id: headerFrame
        frameObjectName: "friendPulseHeaderFrame"
        logoObjectName: "friendPulseSteamLogo"
        textObjectName: "friendPulseHeaderText"
        x: 18.0
        y: 14.0
        label: friendRoot.friendPulseModel.headerText
        logoSource: friendRoot.friendPulseModel.logoSource
        fillColor: friendRoot.friendPulseModel.headerFillColor
        borderColor: friendRoot.friendPulseModel.headerBorderColor
        borderWidth: friendRoot.scaleAwareStrokeWidth(
            friendRoot.friendPulseModel.headerBorderWidth
        )
        textColor: friendRoot.friendPulseModel.headerTextColor
        fontFamily: friendRoot.friendPulseModel.fontFamily
        textShadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
        textShadowColor: friendRoot.friendPulseModel.textShadowColor
        textShadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
        textShadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
        shadowEnabled: friendRoot.cardShadowEnabled
        shadowColor: Qt.rgba(
            friendRoot.cardShadowColor.r,
            friendRoot.cardShadowColor.g,
            friendRoot.cardShadowColor.b,
            friendRoot.cardShadowColor.a * 0.45
        )
        shadowBlur: Math.max(2.0, Math.min(6.0, friendRoot.cardShadowBlur * 0.25))
        shadowOffsetX: friendRoot.cardShadowOffsetX * 1.15
        shadowOffsetY: friendRoot.cardShadowOffsetY * 1.15
    }

    Item {
        id: activitySummary
        objectName: "friendPulseSummary"
        x: 296.0
        y: 13.0
        width: friendRoot.friendPulseModel.authoredWidth - x - 18.0
        height: 56.0

        ShadowedText {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 34.0
            text: friendRoot.friendPulseModel.primaryMetric
            color: friendRoot.friendPulseModel.textColor
            font.family: friendRoot.friendPulseModel.fontFamily
            font.pointSize: friendRoot.friendPulseModel.fontSize * 1.32
            font.bold: true
            horizontalAlignment: Text.AlignRight
            verticalAlignment: Text.AlignVCenter
            fontSizeMode: Text.HorizontalFit
            minimumPointSize: 8.0
            elide: Text.ElideRight
            shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
            shadowColor: friendRoot.friendPulseModel.textShadowColor
            shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
            shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
        }

        ShadowedText {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 20.0
            text: friendRoot.friendPulseModel.secondaryMetric
            color: friendRoot.friendPulseModel.mutedTextColor
            font.family: friendRoot.friendPulseModel.fontFamily
            font.pointSize: friendRoot.friendPulseModel.fontSize * 0.72
            font.bold: true
            horizontalAlignment: Text.AlignRight
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
            shadowColor: friendRoot.friendPulseModel.textShadowColor
            shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
            shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
        }
    }

    Rectangle {
        x: 18.0
        y: 81.0
        width: friendRoot.friendPulseModel.authoredWidth - 36.0
        height: friendRoot.scaleAwareStrokeWidth(1.0)
        color: friendRoot.friendPulseModel.rowInnerBorderColor
    }

    Item {
        id: activityRows
        objectName: "friendPulseRows"
        visible: friendRoot.friendPulseModel.viewMode === "rows"
            && friendRoot.friendPulseModel.hasRows
            && (friendRoot.friendPulseModel.viewState === "ready"
                || friendRoot.friendPulseModel.viewState === "stale")
        x: 18.0
        y: 91.0
        width: friendRoot.friendPulseModel.authoredWidth - 36.0
        height: friendRoot.friendPulseModel.authoredHeight - y - 19.0

        Repeater {
            objectName: "friendPulseRepeater"
            model: activityRows.visible ? friendRoot.friendPulseModel.rowModel : null

            delegate: Rectangle {
                required property string primaryText
                required property string secondaryText
                required property string presenceText
                required property bool isOnline
                required property bool changed
                required property string avatarSource
                required property int friendCount
                required property bool friendActionAvailable
                required property bool gameActionAvailable
                required property int index

                objectName: "friendPulseRow_" + index
                x: 0.0
                y: index * 58.0
                width: activityRows.width
                height: 50.0
                radius: 9.0
                color: friendRoot.friendPulseModel.rowSurfaceColor
                border.color: changed
                    ? friendRoot.friendPulseModel.accentColor
                    : friendRoot.friendPulseModel.rowBorderColor
                border.width: friendRoot.scaleAwareStrokeWidth(changed ? 2.0 : 1.0)

                Rectangle {
                    id: rowAvatarFrame
                    x: 7.0
                    y: 7.0
                    width: 36.0
                    height: 36.0
                    radius: 8.0
                    color: Qt.rgba(
                        friendRoot.friendPulseModel.accentColor.r,
                        friendRoot.friendPulseModel.accentColor.g,
                        friendRoot.friendPulseModel.accentColor.b,
                        rowAvatarHover.hovered ? 0.38 : 0.22
                    )
                    border.color: friendRoot.friendPulseModel.rowInnerBorderColor
                    border.width: friendRoot.scaleAwareStrokeWidth(1.0)

                    Image {
                        anchors.fill: parent
                        anchors.margins: 2.0
                        source: avatarSource
                        visible: avatarSource.length > 0
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }

                    Text {
                        anchors.fill: parent
                        visible: avatarSource.length === 0
                        text: primaryText.length > 0 ? primaryText.charAt(0).toUpperCase() : "•"
                        color: friendRoot.friendPulseModel.accentColor
                        font.family: friendRoot.friendPulseModel.fontFamily
                        font.pointSize: friendRoot.friendPulseModel.fontSize * 1.1
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    HoverHandler {
                        id: rowAvatarHover
                        enabled: friendRoot.friendPulseModel.interactionEnabled
                            && friendActionAvailable
                    }

                    TapHandler {
                        enabled: friendRoot.friendPulseModel.interactionEnabled
                            && friendActionAvailable
                        acceptedButtons: Qt.LeftButton
                        onTapped: friendRoot.friendActionRequested(index)
                    }
                }

                Item {
                    x: 54.0
                    y: 5.0
                    width: parent.width - 66.0 - (changed ? 50.0 : 0.0)
                    height: 40.0

                    ShadowedText {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 23.0
                        text: primaryText
                        color: friendRoot.friendPulseModel.textColor
                        font.family: friendRoot.friendPulseModel.fontFamily
                        font.pointSize: friendRoot.friendPulseModel.fontSize
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
                        shadowColor: friendRoot.friendPulseModel.textShadowColor
                        shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
                        shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
                    }

                    ShadowedText {
                        id: rowGameText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 18.0
                        text: presenceText.length > 0
                            ? secondaryText + "  •  " + presenceText
                            : secondaryText
                        color: rowGameHover.hovered
                            ? friendRoot.friendPulseModel.accentColor
                            : friendRoot.friendPulseModel.mutedTextColor
                        font.family: friendRoot.friendPulseModel.fontFamily
                        font.pointSize: friendRoot.friendPulseModel.fontSize * 0.72
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
                        shadowColor: friendRoot.friendPulseModel.textShadowColor
                        shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
                        shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY

                        HoverHandler {
                            id: rowGameHover
                            enabled: friendRoot.friendPulseModel.interactionEnabled
                                && gameActionAvailable
                        }

                        TapHandler {
                            enabled: friendRoot.friendPulseModel.interactionEnabled
                                && gameActionAvailable
                            acceptedButtons: Qt.LeftButton
                            onTapped: friendRoot.gameActionRequested(index)
                        }
                    }
                }

                Rectangle {
                    id: rowNewBadge
                    visible: changed
                    anchors.right: parent.right
                    anchors.rightMargin: 8.0
                    anchors.verticalCenter: parent.verticalCenter
                    width: 42.0
                    height: 22.0
                    radius: 7.0
                    color: Qt.rgba(
                        friendRoot.friendPulseModel.accentColor.r,
                        friendRoot.friendPulseModel.accentColor.g,
                        friendRoot.friendPulseModel.accentColor.b,
                        0.22
                    )
                    border.color: friendRoot.friendPulseModel.accentColor
                    border.width: friendRoot.scaleAwareStrokeWidth(1.0)
                    scale: 1.0

                    Text {
                        anchors.fill: parent
                        text: "NEW"
                        color: friendRoot.friendPulseModel.accentColor
                        font.family: friendRoot.friendPulseModel.fontFamily
                        font.pixelSize: 10.0
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    SequentialAnimation on scale {
                        running: changed
                        loops: 1
                        NumberAnimation { from: 0.88; to: 1.06; duration: 140 }
                        NumberAnimation { to: 1.0; duration: 120 }
                    }

                    HoverHandler {
                        id: rowNewHover
                        enabled: friendRoot.friendPulseModel.interactionEnabled
                            && friendActionAvailable
                    }

                    TapHandler {
                        enabled: friendRoot.friendPulseModel.interactionEnabled
                            && friendActionAvailable
                        acceptedButtons: Qt.LeftButton
                        onTapped: friendRoot.friendActionRequested(index)
                    }
                }
            }
        }
    }

    Item {
        id: activityGrid
        objectName: "friendPulseGrid"
        visible: friendRoot.friendPulseModel.viewMode === "grid"
            && friendRoot.friendPulseModel.hasRows
            && (friendRoot.friendPulseModel.viewState === "ready"
                || friendRoot.friendPulseModel.viewState === "stale")
        x: 18.0
        y: 91.0
        width: friendRoot.friendPulseModel.authoredWidth - 36.0
        height: friendRoot.friendPulseModel.authoredHeight - y - 19.0
        property real horizontalGap: 10.0
        property real verticalGap: 10.0
        property real tileHeight: 102.0
        property int activeColumns: Math.min(
            friendRoot.friendPulseModel.gridColumns,
            Math.max(1, gridRepeater.count)
        )
        property real tileWidth: Math.min(
            257.0,
            (width - horizontalGap * (activeColumns - 1)) / activeColumns
        )

        Repeater {
            id: gridRepeater
            objectName: "friendPulseGridRepeater"
            model: activityGrid.visible ? friendRoot.friendPulseModel.rowModel : null

            delegate: Rectangle {
                required property string primaryText
                required property string secondaryText
                required property string presenceText
                required property bool isOnline
                required property bool changed
                required property string avatarSource
                required property int friendCount
                required property bool friendActionAvailable
                required property bool gameActionAvailable
                required property int index

                property int gridRow: Math.floor(index / activityGrid.activeColumns)
                property int rowStart: gridRow * activityGrid.activeColumns
                property int rowItemCount: Math.min(
                    activityGrid.activeColumns,
                    gridRepeater.count - rowStart
                )
                property real usedRowWidth: rowItemCount * activityGrid.tileWidth
                    + (rowItemCount - 1) * activityGrid.horizontalGap

                objectName: "friendPulseGridTile_" + index
                x: (activityGrid.width - usedRowWidth) / 2.0
                    + (index - rowStart)
                        * (activityGrid.tileWidth + activityGrid.horizontalGap)
                y: gridRow * (activityGrid.tileHeight + activityGrid.verticalGap)
                width: activityGrid.tileWidth
                height: activityGrid.tileHeight
                radius: 11.0
                color: friendRoot.friendPulseModel.rowSurfaceColor
                border.color: changed
                    ? friendRoot.friendPulseModel.accentColor
                    : friendRoot.friendPulseModel.rowBorderColor
                border.width: friendRoot.scaleAwareStrokeWidth(changed ? 2.0 : 1.0)

                Rectangle {
                    id: avatarFrame
                    x: activityGrid.activeColumns > 2 ? 9.0 : 12.0
                    y: 20.0
                    width: activityGrid.activeColumns > 2 ? 44.0 : 56.0
                    height: width
                    radius: 12.0
                    color: Qt.rgba(
                        friendRoot.friendPulseModel.accentColor.r,
                        friendRoot.friendPulseModel.accentColor.g,
                        friendRoot.friendPulseModel.accentColor.b,
                        gridAvatarHover.hovered ? 0.38 : 0.22
                    )
                    border.color: friendRoot.friendPulseModel.rowInnerBorderColor
                    border.width: friendRoot.scaleAwareStrokeWidth(1.0)

                    Image {
                        anchors.fill: parent
                        anchors.margins: 2.0
                        source: avatarSource
                        visible: avatarSource.length > 0
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }

                    Text {
                        anchors.fill: parent
                        visible: avatarSource.length === 0
                        text: primaryText.length > 0
                            ? primaryText.charAt(0).toUpperCase()
                            : "•"
                        color: friendRoot.friendPulseModel.accentColor
                        font.family: friendRoot.friendPulseModel.fontFamily
                        font.pointSize: friendRoot.friendPulseModel.fontSize * 1.28
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    Rectangle {
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.rightMargin: -2.0
                        anchors.bottomMargin: -2.0
                        width: 13.0
                        height: 13.0
                        radius: 6.5
                        color: isOnline
                            ? friendRoot.friendPulseModel.accentColor
                            : friendRoot.friendPulseModel.mutedTextColor
                        border.color: friendRoot.friendPulseModel.rowSurfaceColor
                        border.width: friendRoot.scaleAwareStrokeWidth(2.0)
                    }

                    HoverHandler {
                        id: gridAvatarHover
                        enabled: friendRoot.friendPulseModel.interactionEnabled
                            && friendActionAvailable
                    }

                    TapHandler {
                        enabled: friendRoot.friendPulseModel.interactionEnabled
                            && friendActionAvailable
                        acceptedButtons: Qt.LeftButton
                        onTapped: friendRoot.friendActionRequested(index)
                    }
                }

                Item {
                    x: avatarFrame.x + avatarFrame.width
                        + (activityGrid.activeColumns > 2 ? 8.0 : 12.0)
                    y: 10.0
                    width: parent.width - x
                        - (activityGrid.activeColumns > 2 ? 9.0 : 12.0)
                    height: parent.height - 20.0

                    ShadowedText {
                        objectName: "friendPulseGridTitle"
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.rightMargin: changed ? 32.0 : 0.0
                        anchors.top: parent.top
                        height: 27.0
                        text: primaryText
                        color: friendRoot.friendPulseModel.textColor
                        font.family: friendRoot.friendPulseModel.fontFamily
                        font.pointSize: friendRoot.friendPulseModel.fontSize * 0.94
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
                        shadowColor: friendRoot.friendPulseModel.textShadowColor
                        shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
                        shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
                    }

                    Row {
                        y: 31.0
                        width: parent.width
                        height: 18.0
                        spacing: 5.0

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 6.0
                            height: 6.0
                            radius: 3.0
                            color: isOnline
                                ? friendRoot.friendPulseModel.accentColor
                                : friendRoot.friendPulseModel.mutedTextColor
                        }

                        Text {
                            width: parent.width - 11.0
                            height: parent.height
                            text: presenceText.toUpperCase()
                            color: friendRoot.friendPulseModel.mutedTextColor
                            font.family: friendRoot.friendPulseModel.fontFamily
                            font.pixelSize: 10.0
                            font.bold: true
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }
                    }

                    ShadowedText {
                        id: gridGameText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        y: 53.0
                        height: 24.0
                        text: secondaryText
                        color: gridGameHover.hovered
                            ? friendRoot.friendPulseModel.accentColor
                            : friendRoot.friendPulseModel.textColor
                        font.family: friendRoot.friendPulseModel.fontFamily
                        font.pointSize: friendRoot.friendPulseModel.fontSize * 0.72
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
                        shadowColor: friendRoot.friendPulseModel.textShadowColor
                        shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
                        shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY

                        HoverHandler {
                            id: gridGameHover
                            enabled: friendRoot.friendPulseModel.interactionEnabled
                                && gameActionAvailable
                        }

                        TapHandler {
                            enabled: friendRoot.friendPulseModel.interactionEnabled
                                && gameActionAvailable
                            acceptedButtons: Qt.LeftButton
                            onTapped: friendRoot.gameActionRequested(index)
                        }
                    }
                }

                Rectangle {
                    id: gridNewBadge
                    visible: changed
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.rightMargin: 7.0
                    anchors.topMargin: 6.0
                    width: 34.0
                    height: 18.0
                    radius: 6.0
                    color: friendRoot.friendPulseModel.accentColor

                    Text {
                        anchors.fill: parent
                        text: "NEW"
                        color: "#07131c"
                        font.family: friendRoot.friendPulseModel.fontFamily
                        font.pixelSize: 9.0
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    HoverHandler {
                        id: gridNewHover
                        enabled: friendRoot.friendPulseModel.interactionEnabled
                            && friendActionAvailable
                    }

                    TapHandler {
                        enabled: friendRoot.friendPulseModel.interactionEnabled
                            && friendActionAvailable
                        acceptedButtons: Qt.LeftButton
                        onTapped: friendRoot.friendActionRequested(index)
                    }
                }
            }
        }
    }

    Item {
        id: quietState
        objectName: "friendPulseQuietState"
        visible: !activityRows.visible && !activityGrid.visible
        x: 36.0
        y: 104.0
        width: friendRoot.friendPulseModel.authoredWidth - 72.0
        height: friendRoot.friendPulseModel.authoredHeight - y - 32.0

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 8.0
            width: 54.0
            height: 54.0
            radius: 27.0
            color: Qt.rgba(
                friendRoot.friendPulseModel.accentColor.r,
                friendRoot.friendPulseModel.accentColor.g,
                friendRoot.friendPulseModel.accentColor.b,
                0.16
            )
            border.color: friendRoot.friendPulseModel.rowBorderColor
            border.width: friendRoot.scaleAwareStrokeWidth(1.0)

            Text {
                anchors.fill: parent
                text: friendRoot.friendPulseModel.viewState === "private" ? "◌" : "●"
                color: friendRoot.friendPulseModel.accentColor
                font.pixelSize: 25.0
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        ShadowedText {
            anchors.left: parent.left
            anchors.right: parent.right
            y: 73.0
            height: 34.0
            text: friendRoot.friendPulseModel.primaryMetric
            color: friendRoot.friendPulseModel.textColor
            font.family: friendRoot.friendPulseModel.fontFamily
            font.pointSize: friendRoot.friendPulseModel.fontSize * 1.18
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
            shadowColor: friendRoot.friendPulseModel.textShadowColor
            shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
            shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
        }

        ShadowedText {
            anchors.left: parent.left
            anchors.right: parent.right
            y: 108.0
            height: 42.0
            text: friendRoot.friendPulseModel.viewState === "connect_required"
                ? "Connect Steam in Settings to see current friend activity."
                : (friendRoot.friendPulseModel.viewState === "private"
                    ? "Steam is not exposing this friend list."
                    : (friendRoot.friendPulseModel.viewState === "stale"
                        ? "This is the last accepted cached Steam observation."
                    : (friendRoot.friendPulseModel.viewState === "loading"
                        ? "Loading the account-private cache first…"
                        : "The next accepted Steam observation will appear here.")))
            color: friendRoot.friendPulseModel.mutedTextColor
            font.family: friendRoot.friendPulseModel.fontFamily
            font.pointSize: friendRoot.friendPulseModel.fontSize * 0.76
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            wrap: true
            maximumLineCount: 2
            elide: Text.ElideRight
            shadowEnabled: friendRoot.friendPulseModel.textShadowEnabled
            shadowColor: friendRoot.friendPulseModel.textShadowColor
            shadowOffsetX: friendRoot.friendPulseModel.textShadowOffsetX
            shadowOffsetY: friendRoot.friendPulseModel.textShadowOffsetY
        }
    }
}
