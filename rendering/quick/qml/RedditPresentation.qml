import QtQuick

OverlayWidget {
    id: redditRoot
    objectName: "redditPresentation"

    // H9: CUSTOM wheel/corner resize is one uniform retained-presentation scale.
    // The whole authored card (header, rows, spacing, chrome) scales together
    // from the outer-rect / baseline-preferred ratio, so rows can no longer
    // escape a shrunk card. CUSTOM resize is purely geometric here; font size
    // stays Settings-owned (no per-value payload scaling).
    uniformScaleTransform: true

    required property var redditModel
    signal openPostRequested(string url)
    signal refreshRequested()

    // Content-driven outer size (H option A). Width honours the historical
    // ordinary-card minimum footprint (BaseOverlayWidget.DEFAULT_CARD_MIN_WIDTH =
    // 600) and only enlarges above it when the intrinsic header content genuinely
    // requires it - never shrinking below the authored floor. Height is content
    // driven. Intrinsic sources only (no width<->preferredWidth feedback). J
    // refines parity.
    preferredContentWidth: Math.max(
        600.0, headerRow.implicitWidth + 20.0 + redditRoot.shellInset
    )
    preferredContentHeight: Math.max(
        60.0, contentColumn.childrenRect.height
    ) + redditRoot.shellInset

    Column {
        id: contentColumn
        objectName: "redditContent"
        anchors.fill: parent
        spacing: 4.0

        Rectangle {
            id: headerFrame
            objectName: "redditHeaderFrame"
            width: Math.min(parent.width, headerRow.implicitWidth + 20.0)
            height: Math.max(36.0, headerRow.implicitHeight + 10.0)
            radius: 9.0
            color: redditRoot.redditModel.showBackground ? "#18000000" : "transparent"
            border.width: redditRoot.redditModel.showBackground ? 1.0 : 0.0
            border.color: redditRoot.redditModel.separatorColor

            Row {
                id: headerRow
                anchors.centerIn: parent
                spacing: 8.0

                Image {
                    id: redditLogo
                    objectName: "redditHeaderLogo"
                    source: redditRoot.redditModel.logoSource
                    width: redditRoot.redditModel.headerLogoSize
                    height: width
                    sourceSize.width: width * 2.0
                    sourceSize.height: height * 2.0
                    fillMode: Image.PreserveAspectFit
                    asynchronous: false
                    cache: true

                    TapHandler {
                        enabled: redditRoot.redditModel.interactionEnabled
                        acceptedButtons: Qt.LeftButton
                        onTapped: redditRoot.openPostRequested(
                            redditRoot.redditModel.subredditUrl
                        )
                    }
                }

                ShadowedText {
                    id: subredditLabel
                    objectName: "redditSubredditLabel"
                    text: redditRoot.redditModel.subredditText
                    color: "white"
                    font.family: redditRoot.redditModel.fontFamily
                    font.pointSize: redditRoot.redditModel.fontSize
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                    shadowEnabled: redditRoot.redditModel.textShadowEnabled
                    shadowColor: redditRoot.redditModel.textShadowColor
                    shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                    shadowOffsetY: redditRoot.redditModel.textShadowOffsetY

                    TapHandler {
                        enabled: redditRoot.redditModel.interactionEnabled
                        acceptedButtons: Qt.LeftButton
                        onTapped: redditRoot.openPostRequested(
                            redditRoot.redditModel.subredditUrl
                        )
                    }
                }

                ShadowedText {
                    id: refreshGlyph
                    objectName: "redditRefreshGlyph"
                    visible: redditRoot.redditModel.showRefreshSpiral
                    text: redditRoot.redditModel.refreshing ? "◌" : "↻"
                    color: redditRoot.redditModel.textColor
                    font.family: redditRoot.redditModel.fontFamily
                    font.pointSize: redditRoot.redditModel.fontSize
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                    shadowEnabled: redditRoot.redditModel.textShadowEnabled
                    shadowColor: redditRoot.redditModel.textShadowColor
                    shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                    shadowOffsetY: redditRoot.redditModel.textShadowOffsetY

                    TapHandler {
                        enabled: redditRoot.redditModel.interactionEnabled
                        acceptedButtons: Qt.LeftButton
                        onTapped: redditRoot.refreshRequested()
                    }
                }
            }

        }

        Item {
            id: statusArea
            objectName: "redditStatusArea"
            width: parent.width
            height: visible ? Math.max(36.0, statusText.implicitHeight + 8.0) : 0.0
            visible: redditRoot.redditModel.viewState !== "ready"

            ShadowedText {
                id: statusText
                anchors.fill: parent
                text: {
                    if (redditRoot.redditModel.viewState === "missing")
                        return "Subreddit required"
                    if (redditRoot.redditModel.viewState === "error")
                        return redditRoot.redditModel.errorText
                    if (redditRoot.redditModel.viewState === "empty")
                        return "No posts available"
                    return "Loading Reddit…"
                }
                color: redditRoot.redditModel.textColor
                font.family: redditRoot.redditModel.fontFamily
                font.pointSize: redditRoot.redditModel.fontSize * 0.78
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                wrap: true
                shadowEnabled: redditRoot.redditModel.textShadowEnabled
                shadowColor: redditRoot.redditModel.textShadowColor
                shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                shadowOffsetY: redditRoot.redditModel.textShadowOffsetY
            }
        }

        Repeater {
            id: postRepeater
            objectName: "redditPostRepeater"
            model: redditRoot.redditModel.rowModel

            delegate: Item {
                id: postRow
                required property string postIdentity
                required property string postTitle
                required property string postAge
                required property string postUrl
                required property int index

                objectName: "redditPostRow_" + index
                width: contentColumn.width
                height: Math.max(28.0, redditRoot.redditModel.fontSize * 1.55)

                ShadowedText {
                    id: ageText
                    objectName: "redditPostAge_" + postRow.index
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.max(96.0, redditRoot.redditModel.fontSize * 6.0)
                    height: parent.height
                    text: postRow.postAge
                    color: redditRoot.redditModel.ageColor
                    font.family: redditRoot.redditModel.fontFamily
                    font.pointSize: redditRoot.redditModel.ageFontSize
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    shadowEnabled: redditRoot.redditModel.textShadowEnabled
                    shadowColor: redditRoot.redditModel.textShadowColor
                    shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                    shadowOffsetY: redditRoot.redditModel.textShadowOffsetY
                }

                ShadowedText {
                    id: titleText
                    objectName: "redditPostTitle_" + postRow.index
                    anchors.left: ageText.right
                    anchors.leftMargin: 8.0
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    height: parent.height
                    text: postRow.postTitle
                    color: redditRoot.redditModel.textColor
                    font.family: redditRoot.redditModel.fontFamily
                    font.pointSize: redditRoot.redditModel.fontSize
                    font.weight: Font.DemiBold
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    shadowEnabled: redditRoot.redditModel.textShadowEnabled
                    shadowColor: redditRoot.redditModel.textShadowColor
                    shadowOffsetX: redditRoot.redditModel.textShadowOffsetX
                    shadowOffsetY: redditRoot.redditModel.textShadowOffsetY
                }

                Rectangle {
                    objectName: "redditPostSeparator_" + postRow.index
                    visible: redditRoot.redditModel.showSeparators
                        && postRow.index < postRepeater.count - 1
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1.0
                    color: redditRoot.redditModel.separatorColor
                }

                TapHandler {
                    enabled: redditRoot.redditModel.interactionEnabled
                    acceptedButtons: Qt.LeftButton
                    onTapped: redditRoot.openPostRequested(postRow.postUrl)
                }
            }
        }
    }
}
