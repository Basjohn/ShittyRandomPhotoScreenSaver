import QtQuick
import QtQuick.Effects
import QtQuick.Shapes

OverlayWidget {
    id: abandonmentRoot
    objectName: "abandonmentIssuesPresentation"

    required property var abandonmentModel
    semanticDoubleClickEnabled: abandonmentModel.interactionEnabled
    signal refreshRequested()
    signal settingsRequested(string target)

    readonly property real authoredWidth: abandonmentModel.authoredWidth
    readonly property real authoredHeight: abandonmentModel.authoredHeight
    readonly property real contentScale: Math.max(
        0.05,
        Math.min(width / authoredWidth, height / authoredHeight)
    )

    // Content-driven outer size (H option A): this card is a self-contained
    // authored canvas, so its preferred content size is the authored dimension
    // directly (no shell inset - it draws its own frame). Size only; Python owns
    // anchor/clamp/outer rect.
    preferredContentWidth: abandonmentRoot.authoredWidth
    preferredContentHeight: abandonmentRoot.authoredHeight

    TapHandler {
        enabled: abandonmentRoot.abandonmentModel.interactionEnabled
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: abandonmentRoot.refreshRequested()
    }

    Connections {
        target: abandonmentRoot.abandonmentModel

        function onContentTransitionRequested() {
            archiveTransition.restart()
        }
    }

    Item {
        id: authoredCanvas
        objectName: "abandonmentAuthoredCanvas"
        width: abandonmentRoot.authoredWidth
        height: abandonmentRoot.authoredHeight
        x: (abandonmentRoot.width - width * scale) / 2.0
        y: (abandonmentRoot.height - height * scale) / 2.0
        scale: abandonmentRoot.contentScale
        transformOrigin: Item.TopLeft

        Rectangle {
            id: headerFrame
            objectName: "abandonmentHeaderFrame"
            x: 18.0
            y: 14.0
            width: 322.0
            height: 42.0
            radius: 8.0
            color: "#e60b1016"
            border.color: "#d8e5edf4"
            border.width: 2.0

            Image {
                objectName: "abandonmentSteamLogo"
                x: 12.0
                y: 6.0
                width: 30.0
                height: 30.0
                source: abandonmentRoot.abandonmentModel.logoSource
                sourceSize.width: 60
                sourceSize.height: 60
                fillMode: Image.PreserveAspectFit
                cache: true
            }

            ShadowedText {
                objectName: "abandonmentHeaderText"
                x: 50.0
                y: 3.0
                width: 254.0
                height: 36.0
                text: abandonmentRoot.abandonmentModel.headerText
                color: abandonmentRoot.abandonmentModel.textColor
                font.family: abandonmentRoot.abandonmentModel.fontFamily
                font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 1.05
                font.bold: true
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
            }
        }

        Rectangle {
            id: connectionInfo
            objectName: "abandonmentConnectionInfo"
            visible: abandonmentRoot.abandonmentModel.showConnectionInfo
            x: 318.0
            y: 17.0
            width: 18.0
            height: 18.0
            radius: 9.0
            color: "#e6f0902d"
            border.color: "#dcffe6b4"
            border.width: 1.0
            z: 5

            Text {
                anchors.fill: parent
                text: "i"
                color: "#e61e140a"
                font.family: abandonmentRoot.abandonmentModel.fontFamily
                font.pixelSize: 12.0
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            HoverHandler {
                id: infoHover
                enabled: abandonmentRoot.abandonmentModel.interactionEnabled
            }

            TapHandler {
                enabled: abandonmentRoot.abandonmentModel.interactionEnabled
                acceptedButtons: Qt.LeftButton
                onTapped: abandonmentRoot.settingsRequested(
                    abandonmentRoot.abandonmentModel.connectionInfoTarget
                )
            }
        }

        Rectangle {
            id: infoTip
            objectName: "abandonmentConnectionInfoTip"
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
                text: abandonmentRoot.abandonmentModel.connectionInfoTooltip
                color: "white"
                font.family: abandonmentRoot.abandonmentModel.fontFamily
                font.pixelSize: 12.0
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignVCenter
            }
        }

        Item {
            id: archiveContent
            objectName: "abandonmentArchiveContent"
            anchors.fill: parent

            SequentialAnimation {
                id: archiveTransition

                NumberAnimation {
                    target: archiveContent
                    property: "opacity"
                    from: 1.0
                    to: 0.0
                    duration: 130
                    easing.type: Easing.InOutQuad
                }
                ScriptAction {
                    script: abandonmentRoot.abandonmentModel.commitPendingPresentation()
                }
                NumberAnimation {
                    target: archiveContent
                    property: "opacity"
                    from: 0.0
                    to: 1.0
                    duration: 170
                    easing.type: Easing.InOutQuad
                }
            }

            Shape {
                id: archiveTab
                objectName: "abandonmentArchiveTab"
                x: 447.0
                y: 19.0
                width: 135.0
                height: 30.0

                ShapePath {
                    strokeColor: Qt.rgba(
                        abandonmentRoot.abandonmentModel.accentColor.r,
                        abandonmentRoot.abandonmentModel.accentColor.g,
                        abandonmentRoot.abandonmentModel.accentColor.b,
                        0.80
                    )
                    strokeWidth: 1.0
                    fillColor: Qt.rgba(
                        abandonmentRoot.abandonmentModel.accentColor.r,
                        abandonmentRoot.abandonmentModel.accentColor.g,
                        abandonmentRoot.abandonmentModel.accentColor.b,
                        0.36
                    )
                    startX: 10.0
                    startY: 0.0
                    PathLine { x: archiveTab.width; y: 0.0 }
                    PathLine { x: archiveTab.width; y: archiveTab.height }
                    PathLine { x: 0.0; y: archiveTab.height }
                    PathLine { x: 10.0; y: 0.0 }
                }

                ShadowedText {
                    anchors.fill: parent
                    anchors.leftMargin: 10.0
                    anchors.rightMargin: 6.0
                    text: abandonmentRoot.abandonmentModel.statusText.length > 0
                        ? abandonmentRoot.abandonmentModel.statusText
                        : "CURATED SHELF"
                    color: abandonmentRoot.abandonmentModel.textColor
                    font.family: abandonmentRoot.abandonmentModel.fontFamily
                    font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.66
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.HorizontalFit
                    minimumPointSize: 6.0
                    shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                    shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                    shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                    shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                }
            }

            Item {
                id: normalContent
                objectName: "abandonmentNormalContent"
                visible: abandonmentRoot.abandonmentModel.viewState !== "connect_required"
                anchors.fill: parent

                readonly property bool portraitArtwork:
                    abandonmentRoot.abandonmentModel.artworkShape === "portrait"
                readonly property real artworkWidth: portraitArtwork
                    ? abandonmentRoot.abandonmentModel.artworkSize
                    : Math.min(238.0, abandonmentRoot.abandonmentModel.artworkSize * 1.45)
                readonly property real artworkHeight: portraitArtwork
                    ? abandonmentRoot.abandonmentModel.artworkSize * 1.4
                    : Math.max(78.0, abandonmentRoot.abandonmentModel.artworkSize * 0.66)
                readonly property real artworkY: portraitArtwork ? 76.0 : 82.0
                readonly property real textLeft:
                    abandonmentRoot.abandonmentModel.showArtwork
                    ? 22.0 + artworkWidth + 24.0 : 24.0
                readonly property real textWidth: Math.max(150.0, 578.0 - textLeft)

                Item {
                    id: artworkShelf
                    objectName: "abandonmentArtworkShelf"
                    visible: abandonmentRoot.abandonmentModel.showArtwork
                    x: 17.0
                    y: normalContent.artworkY - 4.0
                    width: normalContent.artworkWidth + 13.0
                    height: normalContent.artworkHeight + 13.0

                    RectangularShadow {
                        anchors.fill: shelfBackground
                        color: "#76000000"
                        blur: 8.0
                        radius: shelfBackground.radius
                        offset: Qt.vector2d(2.0, 3.0)
                        cached: true
                    }

                    Rectangle {
                        id: shelfBackground
                        objectName: "abandonmentArtworkShelfBackground"
                        anchors.fill: parent
                        radius: 8.0
                        gradient: Gradient {
                            GradientStop {
                                position: 0.0
                                color: Qt.rgba(
                                    abandonmentRoot.abandonmentModel.accentColor.r,
                                    abandonmentRoot.abandonmentModel.accentColor.g,
                                    abandonmentRoot.abandonmentModel.accentColor.b,
                                    0.31
                                )
                            }
                            GradientStop { position: 0.22; color: "#96483020" }
                            GradientStop { position: 1.0; color: "#cd121417" }
                        }
                    }

                    Item {
                        id: artworkFrame
                        objectName: "abandonmentArtworkFrame"
                        x: 5.0
                        y: 4.0
                        width: normalContent.artworkWidth
                        height: normalContent.artworkHeight
                        clip: true

                        Rectangle {
                            anchors.fill: parent
                            radius: 8.0
                            color: "#be141518"
                        }

                        Repeater {
                            model: Math.ceil((artworkFrame.width + artworkFrame.height) / 12.0)
                            delegate: Rectangle {
                                required property int index
                                x: index * 12.0 - artworkFrame.height
                                y: artworkFrame.height
                                width: artworkFrame.height * 1.45
                                height: 1.0
                                rotation: -45.0
                                transformOrigin: Item.Left
                                color: "#26ffffff"
                            }
                        }

                        ArtworkFadeImage {
                            id: abandonmentArtworkImage
                            objectName: "abandonmentArtworkImage"
                            anchors.fill: parent
                            source: abandonmentRoot.abandonmentModel.artworkSource
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            // The archive transition commits the new model at
                            // parent opacity zero; do not waste 140 ms fading an
                            // already-invisible old texture before loading new art.
                            fadeOutDuration: archiveContent.opacity <= 0.001 ? 0 : 140
                            layer.enabled: true
                            layer.effect: MultiEffect {
                                maskEnabled: true
                                maskSource: artworkMask
                            }
                        }

                        Rectangle {
                            id: artworkMask
                            anchors.fill: parent
                            radius: 8.0
                            visible: false
                            layer.enabled: true
                        }

                        Rectangle {
                            anchors.fill: parent
                            radius: 8.0
                            color: "transparent"
                            border.color: Qt.rgba(
                                abandonmentRoot.abandonmentModel.accentColor.r,
                                abandonmentRoot.abandonmentModel.accentColor.g,
                                abandonmentRoot.abandonmentModel.accentColor.b,
                                0.78
                            )
                            border.width: 2.0
                        }
                    }
                }

                ShadowedText {
                    objectName: "abandonmentGameTitle"
                    x: normalContent.textLeft
                    y: 74.0
                    width: normalContent.textWidth
                    height: 46.0
                    text: abandonmentRoot.abandonmentModel.title
                    color: abandonmentRoot.abandonmentModel.textColor
                    font.family: abandonmentRoot.abandonmentModel.fontFamily
                    font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 1.45
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.HorizontalFit
                    minimumPointSize: abandonmentRoot.abandonmentModel.fontSize * 0.75
                    elide: Text.ElideRight
                    shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                    shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                    shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                    shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                }

                ShadowedText {
                    objectName: "abandonmentRediscoveryText"
                    x: normalContent.textLeft
                    y: 119.0
                    width: normalContent.textWidth
                    height: 34.0
                    text: abandonmentRoot.abandonmentModel.subtitle
                    color: Qt.rgba(
                        abandonmentRoot.abandonmentModel.textColor.r,
                        abandonmentRoot.abandonmentModel.textColor.g,
                        abandonmentRoot.abandonmentModel.textColor.b,
                        Math.max(0.47, abandonmentRoot.abandonmentModel.textColor.a * 0.72)
                    )
                    font.family: abandonmentRoot.abandonmentModel.fontFamily
                    font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.88
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                    wrap: true
                    maximumLineCount: 2
                    fontSizeMode: Text.Fit
                    minimumPointSize: 6.0
                    shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                    shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                    shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                    shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                }

                Rectangle {
                    id: ageStamp
                    objectName: "abandonmentAgeStamp"
                    x: normalContent.textLeft
                    y: 160.0
                    width: Math.min(300.0, normalContent.textWidth)
                    height: 54.0
                    radius: 6.0
                    color: Qt.rgba(
                        abandonmentRoot.abandonmentModel.accentColor.r,
                        abandonmentRoot.abandonmentModel.accentColor.g,
                        abandonmentRoot.abandonmentModel.accentColor.b,
                        0.27
                    )
                    border.color: Qt.rgba(
                        abandonmentRoot.abandonmentModel.accentColor.r,
                        abandonmentRoot.abandonmentModel.accentColor.g,
                        abandonmentRoot.abandonmentModel.accentColor.b,
                        0.78
                    )
                    border.width: 2.0

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 4.0
                        radius: 4.0
                        color: "transparent"
                        border.color: Qt.rgba(
                            abandonmentRoot.abandonmentModel.accentColor.r,
                            abandonmentRoot.abandonmentModel.accentColor.g,
                            abandonmentRoot.abandonmentModel.accentColor.b,
                            0.39
                        )
                        border.width: 1.0
                    }

                    ShadowedText {
                        x: 11.0
                        width: parent.width * 0.36
                        height: parent.height
                        text: abandonmentRoot.abandonmentModel.metricLabel.toUpperCase()
                        color: Qt.rgba(
                            abandonmentRoot.abandonmentModel.textColor.r,
                            abandonmentRoot.abandonmentModel.textColor.g,
                            abandonmentRoot.abandonmentModel.textColor.b,
                            0.75
                        )
                        font.family: abandonmentRoot.abandonmentModel.fontFamily
                        font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.68
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                        shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                        shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                        shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                    }

                    ShadowedText {
                        x: parent.width * 0.40
                        width: parent.width * 0.56 - 7.0
                        height: parent.height
                        text: abandonmentRoot.abandonmentModel.metricValue
                        color: abandonmentRoot.abandonmentModel.textColor
                        font.family: abandonmentRoot.abandonmentModel.fontFamily
                        font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.95
                        font.bold: true
                        horizontalAlignment: Text.AlignRight
                        verticalAlignment: Text.AlignVCenter
                        fontSizeMode: Text.HorizontalFit
                        minimumPointSize: 7.0
                        shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                        shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                        shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                        shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                    }
                }

                Repeater {
                    id: ledgerRepeater
                    model: abandonmentRoot.abandonmentModel.fieldModel

                    delegate: Item {
                        required property string fieldId
                        required property string fieldLabel
                        required property string fieldValue
                        required property int index
                        objectName: "abandonmentLedgerShelf_" + fieldId
                        readonly property int row: Math.floor(index / 2)
                        readonly property int column: index % 2
                        readonly property real shelfWidth: Math.max(
                            110.0,
                            (normalContent.textWidth - 12.0) * 0.5
                        )
                        x: normalContent.textLeft + column * (shelfWidth + 12.0)
                        y: 226.0 + row * 31.0
                        width: shelfWidth
                        height: 25.0

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1.0
                            color: Qt.rgba(
                                abandonmentRoot.abandonmentModel.accentColor.r,
                                abandonmentRoot.abandonmentModel.accentColor.g,
                                abandonmentRoot.abandonmentModel.accentColor.b,
                                0.43
                            )
                        }

                        Rectangle {
                            x: 0.0
                            anchors.verticalCenter: parent.verticalCenter
                            width: 4.0
                            height: 4.0
                            radius: 2.0
                            color: Qt.rgba(
                                abandonmentRoot.abandonmentModel.accentColor.r,
                                abandonmentRoot.abandonmentModel.accentColor.g,
                                abandonmentRoot.abandonmentModel.accentColor.b,
                                0.76
                            )
                        }

                        ShadowedText {
                            x: 9.0
                            width: (parent.width - 13.0) * 0.53
                            height: parent.height
                            text: fieldLabel.toUpperCase()
                            color: Qt.rgba(
                                abandonmentRoot.abandonmentModel.textColor.r,
                                abandonmentRoot.abandonmentModel.textColor.g,
                                abandonmentRoot.abandonmentModel.textColor.b,
                                Math.max(0.47, abandonmentRoot.abandonmentModel.textColor.a * 0.72)
                            )
                            font.family: abandonmentRoot.abandonmentModel.fontFamily
                            font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.68
                            font.bold: true
                            verticalAlignment: Text.AlignVCenter
                            fontSizeMode: Text.HorizontalFit
                            minimumPointSize: 6.0
                            elide: Text.ElideRight
                            shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                            shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                            shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                            shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                        }

                        ShadowedText {
                            x: 9.0 + (parent.width - 13.0) * 0.55
                            width: (parent.width - 13.0) * 0.45
                            height: parent.height
                            text: fieldValue.toUpperCase()
                            color: abandonmentRoot.abandonmentModel.textColor
                            font.family: abandonmentRoot.abandonmentModel.fontFamily
                            font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.68
                            font.bold: true
                            horizontalAlignment: Text.AlignRight
                            verticalAlignment: Text.AlignVCenter
                            fontSizeMode: Text.HorizontalFit
                            minimumPointSize: 6.0
                            elide: Text.ElideRight
                            shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                            shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                            shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                            shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                        }
                    }
                }
            }

            Item {
                id: connectRequired
                objectName: "abandonmentConnectRequired"
                visible: abandonmentRoot.abandonmentModel.viewState === "connect_required"
                x: 74.0
                y: 122.0
                width: 412.0
                height: 66.0

                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    height: 38.0

                    ShadowedText {
                        width: 90.0
                        height: parent.height
                        text: abandonmentRoot.abandonmentModel.actionLabel
                        color: abandonmentRoot.abandonmentModel.accentColor
                        font.family: abandonmentRoot.abandonmentModel.fontFamily
                        font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 1.12
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                        shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                        shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                        shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY

                        TapHandler {
                            enabled: abandonmentRoot.abandonmentModel.interactionEnabled
                            acceptedButtons: Qt.LeftButton
                            onTapped: abandonmentRoot.settingsRequested(
                                abandonmentRoot.abandonmentModel.settingsTarget
                            )
                        }
                    }

                    ShadowedText {
                        width: implicitWidth
                        height: parent.height
                        text: abandonmentRoot.abandonmentModel.actionText.replace(
                            abandonmentRoot.abandonmentModel.actionLabel,
                            ""
                        )
                        color: abandonmentRoot.abandonmentModel.textColor
                        font.family: abandonmentRoot.abandonmentModel.fontFamily
                        font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 1.12
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                        shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                        shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                        shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                        shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                    }
                }

                ShadowedText {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 24.0
                    text: abandonmentRoot.abandonmentModel.statusText
                    color: abandonmentRoot.abandonmentModel.textColor
                    font.family: abandonmentRoot.abandonmentModel.fontFamily
                    font.pointSize: abandonmentRoot.abandonmentModel.fontSize * 0.82
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    shadowEnabled: abandonmentRoot.abandonmentModel.textShadowEnabled
                    shadowColor: abandonmentRoot.abandonmentModel.textShadowColor
                    shadowOffsetX: abandonmentRoot.abandonmentModel.textShadowOffsetX
                    shadowOffsetY: abandonmentRoot.abandonmentModel.textShadowOffsetY
                }
            }
        }
    }
}
