import QtQuick
import QtQuick.Effects

OverlayWidget {
    id: achievementRoot
    objectName: "achievementPulsePresentation"

    required property var achievementModel
    semanticDoubleClickEnabled: achievementModel.interactionEnabled
    signal refreshRequested()
    signal settingsRequested(string target)

    readonly property real authoredWidth: achievementModel.authoredWidth
    readonly property real authoredHeight: achievementModel.authoredHeight
    readonly property real contentScale: Math.max(
        0.05,
        Math.min(width / authoredWidth, height / authoredHeight)
    )

    // Content-driven outer size (H option A): this card is a self-contained
    // authored canvas, so its preferred content size is the authored dimension
    // directly (no shell inset - it draws its own frame). Size only; Python owns
    // anchor/clamp/outer rect.
    preferredContentWidth: achievementRoot.authoredWidth
    preferredContentHeight: achievementRoot.authoredHeight

    TapHandler {
        enabled: achievementRoot.achievementModel.interactionEnabled
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: achievementRoot.refreshRequested()
    }

    Item {
        id: authoredCanvas
        objectName: "achievementAuthoredCanvas"
        width: achievementRoot.authoredWidth
        height: achievementRoot.authoredHeight
        x: (achievementRoot.width - width * scale) / 2.0
        y: (achievementRoot.height - height * scale) / 2.0
        scale: achievementRoot.contentScale
        transformOrigin: Item.TopLeft

        Rectangle {
            id: headerFrame
            objectName: "achievementHeaderFrame"
            x: 18.0
            y: 14.0
            width: 302.0
            height: 38.0
            radius: 8.0
            color: "#e60b1016"
            border.color: "#d8e5edf4"
            border.width: 2.0

            Image {
                id: steamLogo
                objectName: "achievementSteamLogo"
                x: 11.0
                anchors.verticalCenter: parent.verticalCenter
                width: 28.0
                height: 28.0
                source: achievementRoot.achievementModel.logoSource
                sourceSize.width: 56
                sourceSize.height: 56
                fillMode: Image.PreserveAspectFit
                cache: true
            }

            ShadowedText {
                objectName: "achievementHeaderText"
                x: 48.0
                width: parent.width - 61.0
                height: parent.height
                text: achievementRoot.achievementModel.headerText
                color: achievementRoot.achievementModel.textColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pointSize: achievementRoot.achievementModel.fontSize
                font.bold: true
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                shadowColor: achievementRoot.achievementModel.textShadowColor
                shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
            }
        }

        Rectangle {
            id: connectionInfo
            objectName: "achievementConnectionInfo"
            visible: achievementRoot.achievementModel.showConnectionInfo
            x: 300.0
            y: 14.0
            width: 18.0
            height: 18.0
            radius: 9.0
            color: "#e6f0902d"
            border.color: "#dcffe6b4"
            border.width: 1.0
            z: 4

            Text {
                anchors.fill: parent
                text: "i"
                color: "white"
                font.family: achievementRoot.achievementModel.fontFamily
                font.pixelSize: 12.0
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            HoverHandler {
                id: infoHover
                enabled: achievementRoot.achievementModel.interactionEnabled
            }

            TapHandler {
                enabled: achievementRoot.achievementModel.interactionEnabled
                acceptedButtons: Qt.LeftButton
                onTapped: achievementRoot.settingsRequested(
                    achievementRoot.achievementModel.connectionInfoTarget
                )
            }
        }

        Rectangle {
            id: infoTip
            objectName: "achievementConnectionInfoTip"
            visible: connectionInfo.visible && infoHover.hovered
            x: connectionInfo.x
            y: connectionInfo.y + connectionInfo.height + 5.0
            width: 276.0
            height: infoTipText.implicitHeight + 14.0
            radius: 6.0
            color: "#ff2b2b2b"
            border.color: "#c89a9a9a"
            border.width: 1.0
            z: 10

            Text {
                id: infoTipText
                anchors.fill: parent
                anchors.margins: 7.0
                text: achievementRoot.achievementModel.connectionInfoTooltip
                color: "white"
                font.family: achievementRoot.achievementModel.fontFamily
                font.pixelSize: 12.0
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignVCenter
            }
        }

        Item {
            id: normalContent
            objectName: "achievementNormalContent"
            visible: achievementRoot.achievementModel.viewState !== "connect_required"
            anchors.fill: parent

            readonly property bool verticalArtwork:
                achievementRoot.achievementModel.showArtwork
                && (achievementRoot.achievementModel.artworkShape === "square"
                    || achievementRoot.achievementModel.artworkShape === "portrait")
            readonly property real artworkWidth: verticalArtwork
                ? achievementRoot.achievementModel.squareArtworkSize : 180.0
            readonly property real artworkHeight:
                achievementRoot.achievementModel.artworkShape === "portrait"
                    ? artworkWidth * 1.4
                    : (verticalArtwork ? artworkWidth : 86.0)
            readonly property real artworkX: verticalArtwork
                ? 582.0 - artworkWidth : 402.0
            readonly property real titleWidth: !achievementRoot.achievementModel.showArtwork
                ? 564.0 : (verticalArtwork ? artworkX - 32.0 : 370.0)

            Item {
                id: artworkFrame
                objectName: "achievementArtworkFrame"
                visible: achievementRoot.achievementModel.showArtwork
                x: normalContent.artworkX
                y: 14.0
                width: normalContent.artworkWidth
                height: normalContent.artworkHeight

                RectangularShadow {
                    anchors.fill: artworkBackground
                    color: "#76000000"
                    blur: 8.0
                    radius: artworkBackground.radius
                    offset: Qt.vector2d(2.0, 3.0)
                    cached: true
                }

                Rectangle {
                    id: artworkBackground
                    anchors.fill: parent
                    radius: 7.0
                    border.color: "#afffffff"
                    border.width: 2.0
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#ff69737c" }
                        GradientStop { position: 1.0; color: "#ff171b20" }
                    }
                }

                ArtworkFadeImage {
                    id: artworkImage
                    objectName: "achievementArtworkImage"
                    anchors.fill: parent
                    anchors.margins: 2.0
                    source: achievementRoot.achievementModel.artworkSource
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        maskEnabled: true
                        maskSource: artworkMask
                    }
                }

                Rectangle {
                    id: artworkMask
                    anchors.fill: artworkImage
                    radius: 5.0
                    visible: false
                    layer.enabled: true
                }
            }

            ShadowedText {
                id: gameTitle
                objectName: "achievementGameTitle"
                x: 18.0
                y: 62.0
                width: normalContent.titleWidth
                height: 34.0
                text: achievementRoot.achievementModel.title
                color: achievementRoot.achievementModel.textColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pointSize: achievementRoot.achievementModel.fontSize + 5.0
                font.bold: true
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                shadowColor: achievementRoot.achievementModel.textShadowColor
                shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
            }

            ShadowedText {
                objectName: "achievementSubtitle"
                // The legacy presenter treated the latest-unlock stack as the
                // subtitle area's content, rather than painting both layers.
                visible: text.length > 0 && unlockRepeater.count === 0
                x: 18.0
                y: 100.0
                width: normalContent.titleWidth
                height: 88.0
                text: achievementRoot.achievementModel.subtitle
                color: achievementRoot.achievementModel.textColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pointSize: achievementRoot.achievementModel.fontSize * 0.78
                wrap: true
                elide: Text.ElideRight
                shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                shadowColor: achievementRoot.achievementModel.textShadowColor
                shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
            }

            Repeater {
                id: unlockRepeater
                model: achievementRoot.achievementModel.unlockModel

                delegate: ShadowedText {
                    required property string unlockIdentity
                    required property string unlockText
                    required property int index
                    objectName: "achievementUnlock_" + index
                    x: 18.0
                    y: index === 0 ? 100.0 : 130.0 + (index - 1) * 14.0
                    width: normalContent.titleWidth
                    height: index === 0 ? 26.0 : 13.0
                    text: unlockText
                    color: achievementRoot.achievementModel.textColor
                    font.family: achievementRoot.achievementModel.fontFamily
                    font.pointSize: index === 0
                        ? achievementRoot.achievementModel.fontSize * 0.72
                        : achievementRoot.achievementModel.fontSize * 0.48
                    font.bold: index === 0
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                    shadowColor: achievementRoot.achievementModel.textShadowColor
                    shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                    shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
                }
            }

            Item {
                id: latestArtworkFrame
                objectName: "achievementLatestArtworkFrame"
                visible: achievementRoot.achievementModel.showLatestArtwork
                    && (achievementRoot.achievementModel.latestArtworkSource.length > 0
                        || latestArtworkImage.transitionVisible)
                    && unlockRepeater.count > 0
                x: Math.max(18.0, normalContent.artworkX - 48.0)
                y: 130.0
                width: 40.0
                height: 40.0

                RectangularShadow {
                    anchors.fill: latestArtworkBackground
                    color: "#76000000"
                    blur: 6.0
                    radius: 7.0
                    offset: Qt.vector2d(2.0, 2.0)
                    cached: true
                }

                Rectangle {
                    id: latestArtworkBackground
                    anchors.fill: parent
                    radius: 7.0
                    color: "#e60c0f14"
                    border.color: "#afffffff"
                    border.width: 1.0
                }

                ArtworkFadeImage {
                    id: latestArtworkImage
                    objectName: "achievementLatestArtworkImage"
                    anchors.fill: parent
                    anchors.margins: 1.0
                    source: achievementRoot.achievementModel.latestArtworkSource
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                }
            }

            ShadowedText {
                id: metricText
                objectName: "achievementMetric"
                visible: achievementRoot.achievementModel.metricValue.length > 0
                x: normalContent.verticalArtwork
                    ? normalContent.artworkX - 10.0 : 392.0
                y: normalContent.verticalArtwork
                    ? 14.0 + normalContent.artworkHeight + 6.0 : 108.0
                width: normalContent.verticalArtwork
                    ? normalContent.artworkWidth + 20.0 : 200.0
                height: 28.0
                text: achievementRoot.achievementModel.metricLabel
                    + " " + achievementRoot.achievementModel.metricValue
                color: achievementRoot.achievementModel.textColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pointSize: achievementRoot.achievementModel.fontSize * 0.95
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                shadowColor: achievementRoot.achievementModel.textShadowColor
                shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
            }

            Repeater {
                id: fieldRepeater
                model: achievementRoot.achievementModel.fieldModel

                delegate: Item {
                    required property string fieldId
                    required property string fieldLabel
                    required property string fieldValue
                    required property int index
                    objectName: "achievementField_" + fieldId
                    readonly property int compactRow: Math.floor(index / 3)
                    readonly property int column: index % 3
                    readonly property int railStride:
                        achievementRoot.achievementModel.doubleCapsules ? 2 : 1
                    readonly property int railCount: Math.max(
                        1,
                        Math.ceil(fieldRepeater.count / 3) * railStride
                    )
                    readonly property real railStep:
                        achievementRoot.achievementModel.capsuleHeight
                        + achievementRoot.achievementModel.capsuleGap
                    readonly property real firstRailY:
                        authoredCanvas.height - 16.0
                        - achievementRoot.achievementModel.capsuleHeight
                        - (railCount - 1) * railStep
                    x: 18.0 + column * 191.0
                    y: firstRailY + compactRow * railStride * railStep
                    width: 182.0
                    height: achievementRoot.achievementModel.doubleCapsules
                        ? achievementRoot.achievementModel.capsuleHeight * 2.0
                            + achievementRoot.achievementModel.capsuleGap
                        : achievementRoot.achievementModel.capsuleHeight

                    AchievementCapsule {
                        anchors.fill: parent
                        fieldId: parent.fieldId
                        fieldLabel: parent.fieldLabel
                        fieldValue: parent.fieldValue
                        doubled: achievementRoot.achievementModel.doubleCapsules
                        capsuleHeight: achievementRoot.achievementModel.capsuleHeight
                        capsuleGap: achievementRoot.achievementModel.capsuleGap
                        capsuleFontSize: achievementRoot.achievementModel.capsuleFontSize
                        fontFamily: achievementRoot.achievementModel.fontFamily
                        fillColor: achievementRoot.achievementModel.capsuleFillColor
                        borderColor: achievementRoot.achievementModel.capsuleBorderColor
                        textColor: achievementRoot.achievementModel.textColor
                        textShadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                        textShadowColor: achievementRoot.achievementModel.textShadowColor
                        textShadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                        textShadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
                    }
                }
            }
        }

        Item {
            id: connectRequired
            objectName: "achievementConnectRequired"
            visible: achievementRoot.achievementModel.viewState === "connect_required"
            x: 44.0
            y: 76.0
            width: 332.0
            height: 61.0

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                height: 34.0

                ShadowedText {
                    width: 82.0
                    height: parent.height
                    text: achievementRoot.achievementModel.actionLabel
                    color: achievementRoot.achievementModel.accentColor
                    font.family: achievementRoot.achievementModel.fontFamily
                    font.pointSize: achievementRoot.achievementModel.fontSize
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                    shadowColor: achievementRoot.achievementModel.textShadowColor
                    shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                    shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY

                    TapHandler {
                        enabled: achievementRoot.achievementModel.interactionEnabled
                        acceptedButtons: Qt.LeftButton
                        onTapped: achievementRoot.settingsRequested(
                            achievementRoot.achievementModel.settingsTarget
                        )
                    }
                }

                ShadowedText {
                    width: implicitWidth
                    height: parent.height
                    text: achievementRoot.achievementModel.actionText.replace(
                        achievementRoot.achievementModel.actionLabel, ""
                    )
                    color: achievementRoot.achievementModel.textColor
                    font.family: achievementRoot.achievementModel.fontFamily
                    font.pointSize: achievementRoot.achievementModel.fontSize
                    verticalAlignment: Text.AlignVCenter
                    shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                    shadowColor: achievementRoot.achievementModel.textShadowColor
                    shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                    shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
                }
            }

            ShadowedText {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 24.0
                text: achievementRoot.achievementModel.statusText
                color: achievementRoot.achievementModel.textColor
                font.family: achievementRoot.achievementModel.fontFamily
                font.pointSize: achievementRoot.achievementModel.fontSize * 0.78
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                shadowEnabled: achievementRoot.achievementModel.textShadowEnabled
                shadowColor: achievementRoot.achievementModel.textShadowColor
                shadowOffsetX: achievementRoot.achievementModel.textShadowOffsetX
                shadowOffsetY: achievementRoot.achievementModel.textShadowOffsetY
            }
        }
    }
}
