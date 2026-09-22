import QtQuick

OverlayWidget {
    id: feedRoot
    objectName: "feedPresentation"
    uniformScaleTransform: true

    required property var feedModel
    signal openItemRequested(string url)
    signal refreshRequested()

    preferredContentWidth: feedModel.preferredWidth
    preferredContentHeight: feedModel.preferredHeight

    readonly property real pad: 10.0
    readonly property real headerHeight: Math.max(34.0, feedModel.fontSize * 2.2)
    readonly property real bodyTop: headerHeight + 8.0
    // A tiny fixed footer is always budgeted so status/overflow text can never
    // paint over the final feed row. Keeping the reserve unconditional also
    // avoids a capacity <-> footer-visibility binding cycle.
    readonly property real footerHeight: Math.max(16.0, feedModel.fontSize * 1.15)
    readonly property real bodyHeight: Math.max(0.0, height - bodyTop - footerHeight)
    readonly property real listSpacing: 3.0
    readonly property real listRowHeight: feedModel.viewMode === "compact"
        ? Math.max(30.0, feedModel.fontSize * 2.15)
        : Math.max(50.0, feedModel.fontSize * 3.55)
    readonly property int listCapacity: Math.max(1, Math.floor(
        (bodyHeight + listSpacing) / Math.max(1.0, listRowHeight + listSpacing)))
    readonly property real gridSpacing: 6.0
    readonly property real gridCellHeight: Math.max(84.0, feedModel.fontSize * 5.5)
    readonly property int gridColumns: Math.max(1, Math.min(4, Math.floor(
        (Math.max(1.0, width) + gridSpacing) / (240.0 + gridSpacing))))
    readonly property int gridRowCapacity: Math.max(1, Math.floor(
        (bodyHeight + gridSpacing) / Math.max(1.0, gridCellHeight + gridSpacing)))
    readonly property int visibleCapacity: feedModel.viewMode === "grid"
        ? gridColumns * gridRowCapacity : listCapacity
    readonly property int overflowCount: Math.max(0, feedModel.rowCount - visibleCapacity)

    Item {
        id: header
        objectName: "feedHeader"
        x: 0
        y: 0
        width: parent.width
        height: feedRoot.headerHeight

        Rectangle {
            id: monogramFrame
            objectName: "feedMonogramFrame"
            width: header.height - 4.0
            height: width
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            radius: 5.0
            color: "transparent"
            border.color: feedRoot.feedModel.textColor
            border.width: feedRoot.scaleAwareHeaderStrokeWidth(1.4)

            ShadowedText {
                anchors.centerIn: parent
                text: feedRoot.feedModel.monogram
                color: feedRoot.feedModel.textColor
                font.family: feedRoot.feedModel.fontFamily
                font.pixelSize: Math.max(13.0, feedRoot.feedModel.fontSize * 1.05)
                font.bold: true
                shadowEnabled: feedRoot.feedModel.textShadowEnabled
                shadowColor: feedRoot.feedModel.textShadowColor
                shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
            }
        }

        Column {
            anchors.left: monogramFrame.right
            anchors.leftMargin: 9.0
            anchors.right: refreshTarget.left
            anchors.rightMargin: 8.0
            anchors.verticalCenter: parent.verticalCenter
            spacing: 1.0

            ShadowedText {
                width: parent.width
                text: feedRoot.feedModel.displayName.toUpperCase()
                color: feedRoot.feedModel.textColor
                font.family: feedRoot.feedModel.fontFamily
                font.pixelSize: Math.max(11.0, feedRoot.feedModel.fontSize)
                font.bold: true
                elide: Text.ElideRight
                shadowEnabled: feedRoot.feedModel.textShadowEnabled
                shadowColor: feedRoot.feedModel.textShadowColor
                shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
            }

            ShadowedText {
                width: parent.width
                visible: text.length > 0
                text: feedRoot.feedModel.feedTitle
                color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                               feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.72)
                font.family: feedRoot.feedModel.fontFamily
                font.pixelSize: Math.max(9.0, feedRoot.feedModel.fontSize - 2.0)
                elide: Text.ElideRight
                shadowEnabled: feedRoot.feedModel.textShadowEnabled
                shadowColor: feedRoot.feedModel.textShadowColor
                shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
            }
        }

        Item {
            id: refreshTarget
            objectName: "feedRefreshTarget"
            width: 30.0
            height: 30.0
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            opacity: feedRoot.feedModel.interactionEnabled ? 0.9 : 0.45

            Canvas {
                id: refreshCanvas
                anchors.fill: parent
                onPaint: {
                    const ctx = getContext("2d")
                    ctx.reset()
                    ctx.strokeStyle = feedRoot.feedModel.textColor
                    ctx.lineWidth = 1.7
                    ctx.lineCap = "round"
                    ctx.beginPath()
                    ctx.arc(width / 2, height / 2, 7.0, -0.4, 4.8)
                    ctx.stroke()
                    ctx.beginPath()
                    ctx.moveTo(width / 2 + 6.5, height / 2 - 4.0)
                    ctx.lineTo(width / 2 + 8.0, height / 2 + 0.4)
                    ctx.lineTo(width / 2 + 3.5, height / 2 - 0.3)
                    ctx.stroke()
                }
                Connections {
                    target: feedRoot.feedModel
                    function onStateChanged() { refreshCanvas.requestPaint() }
                }
            }

            TapHandler {
                enabled: feedRoot.feedModel.interactionEnabled && !feedRoot.feedModel.refreshing
                onTapped: feedRoot.refreshRequested()
            }
        }
    }

    Rectangle {
        id: divider
        x: 0
        y: feedRoot.headerHeight
        width: parent.width
        height: Math.max(1.0, feedRoot.scaleAwareHeaderStrokeWidth(1.0))
        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.20)
    }

    Item {
        id: body
        objectName: "feedBody"
        x: 0
        y: feedRoot.bodyTop
        width: parent.width
        height: feedRoot.bodyHeight
        clip: true

        Column {
            id: listColumn
            width: parent.width
            spacing: feedRoot.listSpacing
            visible: feedRoot.feedModel.viewMode !== "grid"

            Repeater {
                model: feedRoot.feedModel.rowModel

                delegate: Item {
                    required property int index
                    required property string feedItemId
                    required property string feedTitle
                    required property string feedSummary
                    required property string feedAuthor
                    required property string feedAge
                    required property string feedUrl
                    visible: index < feedRoot.listCapacity
                    width: listColumn.width
                    height: visible ? feedRoot.listRowHeight : 0.0

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 1.0
                        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.12)
                    }

                    ShadowedText {
                        id: listTitle
                        anchors.left: parent.left
                        anchors.right: ageText.left
                        anchors.rightMargin: 8.0
                        anchors.top: parent.top
                        anchors.topMargin: 4.0
                        text: feedTitle
                        color: feedRoot.feedModel.textColor
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: feedRoot.feedModel.fontSize
                        font.bold: true
                        elide: Text.ElideRight
                        maximumLineCount: feedRoot.feedModel.viewMode === "compact" ? 1 : 2
                        wrap: true
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    ShadowedText {
                        id: ageText
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.topMargin: 5.0
                        text: feedAge
                        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.58)
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: Math.max(8.0, feedRoot.feedModel.fontSize - 3.0)
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    ShadowedText {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: listTitle.bottom
                        anchors.topMargin: 2.0
                        visible: feedRoot.feedModel.viewMode !== "compact" && text.length > 0
                        text: feedSummary
                        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.70)
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: Math.max(9.0, feedRoot.feedModel.fontSize - 2.0)
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    TapHandler {
                        enabled: feedRoot.feedModel.interactionEnabled && feedUrl.length > 0
                        onTapped: feedRoot.openItemRequested(feedUrl)
                    }
                }
            }
        }

        Grid {
            id: grid
            visible: feedRoot.feedModel.viewMode === "grid"
            width: parent.width
            columns: feedRoot.gridColumns
            spacing: feedRoot.gridSpacing

            Repeater {
                model: feedRoot.feedModel.rowModel
                delegate: Rectangle {
                    required property int index
                    required property string feedItemId
                    required property string feedTitle
                    required property string feedSummary
                    required property string feedAge
                    required property string feedUrl
                    visible: index < feedRoot.visibleCapacity
                    width: (grid.width - grid.spacing * Math.max(0, grid.columns - 1))
                        / Math.max(1, grid.columns)
                    height: visible ? feedRoot.gridCellHeight : 0.0
                    radius: 5.0
                    color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                   feedRoot.feedModel.textColor.b, 0.055)
                    border.color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                          feedRoot.feedModel.textColor.b, 0.16)
                    border.width: 1.0

                    ShadowedText {
                        id: gridTitle
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 8.0
                        text: feedTitle
                        color: feedRoot.feedModel.textColor
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: feedRoot.feedModel.fontSize
                        font.bold: true
                        wrap: true
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    ShadowedText {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: gridTitle.bottom
                        anchors.bottom: gridAge.top
                        anchors.margins: 8.0
                        text: feedSummary
                        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.68)
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: Math.max(9.0, feedRoot.feedModel.fontSize - 2.0)
                        wrap: true
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    ShadowedText {
                        id: gridAge
                        anchors.left: parent.left
                        anchors.bottom: parent.bottom
                        anchors.margins: 8.0
                        text: feedAge
                        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.55)
                        font.family: feedRoot.feedModel.fontFamily
                        font.pixelSize: Math.max(8.0, feedRoot.feedModel.fontSize - 3.0)
                        shadowEnabled: feedRoot.feedModel.textShadowEnabled
                        shadowColor: feedRoot.feedModel.textShadowColor
                        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
                        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
                    }

                    TapHandler {
                        enabled: feedRoot.feedModel.interactionEnabled && feedUrl.length > 0
                        onTapped: feedRoot.openItemRequested(feedUrl)
                    }
                }
            }
        }

        ShadowedText {
            anchors.centerIn: parent
            visible: feedRoot.feedModel.viewState === "loading" ||
                     feedRoot.feedModel.viewState === "empty" ||
                     feedRoot.feedModel.viewState === "error" ||
                     feedRoot.feedModel.viewState === "missing"
            text: feedRoot.feedModel.viewState === "loading" ? "LOADING FEED…"
                : feedRoot.feedModel.viewState === "empty" ? "NO FEED ITEMS"
                : feedRoot.feedModel.viewState === "missing" ? "CONFIGURE FEED IN SETTINGS"
                : "FEED UNAVAILABLE"
            color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                           feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.72)
            font.family: feedRoot.feedModel.fontFamily
            font.pixelSize: Math.max(10.0, feedRoot.feedModel.fontSize - 1.0)
            shadowEnabled: feedRoot.feedModel.textShadowEnabled
            shadowColor: feedRoot.feedModel.textShadowColor
            shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
            shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
        }
    }

    ShadowedText {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: feedRoot.footerHeight
        verticalAlignment: Text.AlignVCenter
        visible: feedRoot.feedModel.viewState === "ready"
            && (feedRoot.feedModel.statusText.length > 0 || feedRoot.overflowCount > 0)
        text: {
            const overflow = feedRoot.overflowCount > 0 ? "+" + feedRoot.overflowCount + " MORE" : ""
            if (feedRoot.feedModel.statusText.length > 0 && overflow.length > 0)
                return feedRoot.feedModel.statusText + "  ·  " + overflow
            return feedRoot.feedModel.statusText.length > 0 ? feedRoot.feedModel.statusText : overflow
        }
        color: Qt.rgba(feedRoot.feedModel.textColor.r, feedRoot.feedModel.textColor.g,
                       feedRoot.feedModel.textColor.b, feedRoot.feedModel.textColor.a * 0.58)
        font.family: feedRoot.feedModel.fontFamily
        font.pixelSize: Math.max(8.0, feedRoot.feedModel.fontSize - 4.0)
        horizontalAlignment: Text.AlignRight
        shadowEnabled: feedRoot.feedModel.textShadowEnabled
        shadowColor: feedRoot.feedModel.textShadowColor
        shadowOffsetX: feedRoot.feedModel.textShadowOffsetX
        shadowOffsetY: feedRoot.feedModel.textShadowOffsetY
    }
}
