import QtQuick
import QtQuick.Effects

OverlayWidget {
    id: mediaRoot
    objectName: "mediaPresentation"

    required property var mediaModel
    signal refreshRequested()
    signal playPauseRequested()
    signal previousRequested()
    signal nextRequested()

    readonly property int visibleSectionCount: 1
        + (mediaModel.showHeaderFrame ? 1 : 0)
        + (mediaModel.progressAvailable ? 1 : 0)
        + (mediaModel.controlsAvailable ? 1 : 0)

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: mediaRoot.refreshRequested()
    }

    Column {
        id: mediaColumn
        objectName: "mediaContent"
        anchors.fill: parent
        spacing: 12.0

        Rectangle {
            id: headerFrame
            objectName: "mediaHeaderFrame"
            width: Math.min(parent.width, headerRow.implicitWidth + 28.0)
            height: visible ? Math.max(42.0, headerRow.implicitHeight + 12.0) : 0.0
            visible: mediaRoot.mediaModel.showHeaderFrame
            radius: 11.0
            color: "#26000000"
            border.width: 1.0
            border.color: "#55ffffff"

            Row {
                id: headerRow
                anchors.centerIn: parent
                spacing: 8.0

                Image {
                    visible: source.toString().length > 0
                    source: mediaRoot.mediaModel.providerLogoSource
                    width: 25.0
                    height: 25.0
                    sourceSize.width: 50
                    sourceSize.height: 50
                    fillMode: Image.PreserveAspectFit
                    asynchronous: false
                    cache: true
                }

                ShadowedText {
                    text: mediaRoot.mediaModel.providerName
                    color: mediaRoot.mediaModel.textColor
                    font.family: mediaRoot.mediaModel.fontFamily
                    font.pointSize: mediaRoot.mediaModel.fontSize * 0.82
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                    shadowEnabled: mediaRoot.mediaModel.textShadowEnabled
                    shadowColor: mediaRoot.mediaModel.textShadowColor
                    shadowOffsetX: mediaRoot.mediaModel.textShadowOffsetX
                    shadowOffsetY: mediaRoot.mediaModel.textShadowOffsetY
                }
            }
        }

        Item {
            id: mainBand
            objectName: "mediaMainBand"
            width: parent.width
            height: Math.max(
                1.0,
                parent.height
                    - headerFrame.height
                    - progressBand.height
                    - controlsRow.height
                    - mediaColumn.spacing * (mediaRoot.visibleSectionCount - 1)
            )

            Column {
                id: metadata
                objectName: "mediaMetadata"
                anchors.left: parent.left
                anchors.right: artworkFrame.visible ? artworkFrame.left : parent.right
                anchors.rightMargin: artworkFrame.visible ? 18.0 : 0.0
                anchors.verticalCenter: parent.verticalCenter
                spacing: 7.0
                transformOrigin: Item.Center
                scale: implicitHeight > mainBand.height && implicitHeight > 0.0
                    ? Math.max(0.1, (mainBand.height - 2.0) / implicitHeight)
                    : 1.0

                ShadowedText {
                    objectName: "mediaTitle"
                    width: metadata.width
                    height: implicitHeight
                    text: mediaRoot.mediaModel.title
                    color: mediaRoot.mediaModel.textColor
                    font.family: mediaRoot.mediaModel.fontFamily
                    font.pointSize: mediaRoot.mediaModel.fontSize * 1.12
                    font.bold: true
                    wrap: true
                    shadowEnabled: mediaRoot.mediaModel.textShadowEnabled
                    shadowColor: mediaRoot.mediaModel.textShadowColor
                    shadowOffsetX: mediaRoot.mediaModel.textShadowOffsetX
                    shadowOffsetY: mediaRoot.mediaModel.textShadowOffsetY
                }

                ShadowedText {
                    objectName: "mediaArtist"
                    visible: text.length > 0
                    width: metadata.width
                    height: visible ? implicitHeight : 0.0
                    text: mediaRoot.mediaModel.artist
                    color: mediaRoot.mediaModel.textColor
                    opacity: 0.92
                    font.family: mediaRoot.mediaModel.fontFamily
                    font.pointSize: mediaRoot.mediaModel.fontSize
                    font.bold: true
                    wrap: true
                    shadowEnabled: mediaRoot.mediaModel.textShadowEnabled
                    shadowColor: mediaRoot.mediaModel.textShadowColor
                    shadowOffsetX: mediaRoot.mediaModel.textShadowOffsetX
                    shadowOffsetY: mediaRoot.mediaModel.textShadowOffsetY
                }

                ShadowedText {
                    objectName: "mediaAlbum"
                    visible: text.length > 0
                    width: metadata.width
                    height: visible ? implicitHeight : 0.0
                    text: mediaRoot.mediaModel.album
                    color: mediaRoot.mediaModel.textColor
                    opacity: 0.75
                    font.family: mediaRoot.mediaModel.fontFamily
                    font.pointSize: mediaRoot.mediaModel.fontSize * 0.82
                    font.italic: true
                    wrap: true
                    shadowEnabled: mediaRoot.mediaModel.textShadowEnabled
                    shadowColor: mediaRoot.mediaModel.textShadowColor
                    shadowOffsetX: mediaRoot.mediaModel.textShadowOffsetX
                    shadowOffsetY: mediaRoot.mediaModel.textShadowOffsetY
                }

                ShadowedText {
                    objectName: "mediaPlaybackState"
                    visible: mediaRoot.mediaModel.hasTrack
                    width: metadata.width
                    height: visible ? implicitHeight : 0.0
                    text: mediaRoot.mediaModel.playbackState.toUpperCase()
                    color: mediaRoot.mediaModel.textColor
                    opacity: 0.62
                    font.family: mediaRoot.mediaModel.fontFamily
                    font.pointSize: mediaRoot.mediaModel.fontSize * 0.65
                    font.bold: true
                    shadowEnabled: mediaRoot.mediaModel.textShadowEnabled
                    shadowColor: mediaRoot.mediaModel.textShadowColor
                    shadowOffsetX: mediaRoot.mediaModel.textShadowOffsetX
                    shadowOffsetY: mediaRoot.mediaModel.textShadowOffsetY
                }
            }

            Rectangle {
                id: artworkFrame
                objectName: "mediaArtworkFrame"
                visible: mediaRoot.mediaModel.hasArtwork
                width: visible ? Math.min(mediaRoot.mediaModel.artworkSize, mainBand.height) : 0.0
                height: width
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                radius: mediaRoot.mediaModel.roundedArtwork ? width / 8.0 : 0.0
                color: "transparent"
                clip: false

                RectangularShadow {
                    anchors.fill: parent
                    color: "#55000000"
                    blur: 12.0
                    radius: artworkFrame.radius
                    offset: Qt.vector2d(4.0, 4.0)
                    cached: true
                    z: -1
                }

                Image {
                    objectName: "mediaArtwork"
                    anchors.fill: parent
                    source: mediaRoot.mediaModel.artworkSource.length > 0
                        ? mediaRoot.mediaModel.artworkSource
                            + (mediaRoot.mediaModel.roundedArtwork ? "/rounded" : "")
                        : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                }

                Rectangle {
                    anchors.fill: parent
                    radius: artworkFrame.radius
                    color: "transparent"
                    border.width: mediaRoot.mediaModel.artworkBorderWidth
                    border.color: mediaRoot.mediaModel.artworkBorderColor
                }
            }
        }

        Item {
            id: progressBand
            objectName: "mediaProgressBand"
            visible: mediaRoot.mediaModel.progressAvailable
            width: parent.width
            height: visible ? mediaRoot.mediaModel.progressHeight + 8.0 : 0.0

            Rectangle {
                id: progressTrack
                objectName: "mediaProgressTrack"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: Math.max(12.0, parent.width * 0.08)
                anchors.rightMargin: anchors.leftMargin
                height: mediaRoot.mediaModel.progressHeight
                radius: height / 2.0
                color: Qt.rgba(
                    mediaRoot.mediaModel.progressFillColor.r,
                    mediaRoot.mediaModel.progressFillColor.g,
                    mediaRoot.mediaModel.progressFillColor.b,
                    Math.min(0.35, mediaRoot.mediaModel.progressFillColor.a * 0.32)
                )

                Rectangle {
                    visible: mediaRoot.mediaModel.progressShadowEnabled
                    x: 0.0
                    y: 2.0
                    width: parent.width
                    height: parent.height
                    radius: parent.radius
                    color: "#66000000"
                    z: -2
                }

                Rectangle {
                    visible: mediaRoot.mediaModel.progressGlowEnabled
                        && progressFill.width > 0.0
                    anchors.fill: progressFill
                    anchors.margins: -3.0
                    radius: height / 2.0
                    color: mediaRoot.mediaModel.progressGlowColor
                    opacity: 0.38
                    z: -1
                }

                Rectangle {
                    id: progressFill
                    objectName: "mediaProgressFill"
                    width: parent.width * Math.max(
                        0.0, Math.min(1.0, mediaRoot.mediaModel.progressFraction)
                    )
                    height: parent.height
                    radius: Math.min(width, height) / 2.0
                    color: mediaRoot.mediaModel.progressFillColor
                }
            }
        }

        Rectangle {
            id: controlsRow
            objectName: "mediaControlsRow"
            visible: mediaRoot.mediaModel.controlsAvailable
            width: parent.width
            height: visible ? Math.max(38.0, mediaRoot.mediaModel.fontSize * 2.15) : 0.0
            radius: 12.0
            color: mediaRoot.mediaModel.controlsSurfaceColor
            border.width: 1.5
            border.color: "#55ffffff"

            Row {
                anchors.fill: parent

                Item {
                    id: previousButton
                    objectName: "mediaPreviousButton"
                    width: (parent.width - 2.0) / 3.0
                    height: parent.height
                    opacity: mediaRoot.mediaModel.canPrevious
                        ? (mediaRoot.mediaModel.interactionEnabled ? 1.0 : 0.68)
                        : 0.25
                    scale: previousTap.pressed ? 1.08 : 1.0

                    Text {
                        anchors.centerIn: parent
                        text: "←"
                        color: mediaRoot.mediaModel.textColor
                        font.family: mediaRoot.mediaModel.fontFamily
                        font.pointSize: mediaRoot.mediaModel.fontSize
                        font.bold: true
                    }

                    TapHandler {
                        id: previousTap
                        enabled: mediaRoot.mediaModel.interactionEnabled
                            && mediaRoot.mediaModel.canPrevious
                        acceptedButtons: Qt.LeftButton
                        onTapped: mediaRoot.previousRequested()
                    }
                }

                Rectangle {
                    width: 1.0
                    height: parent.height * 0.7
                    y: (parent.height - height) / 2.0
                    color: "#38ffffff"
                }

                Item {
                    id: playPauseButton
                    objectName: "mediaPlayPauseButton"
                    width: (parent.width - 2.0) / 3.0
                    height: parent.height
                    opacity: mediaRoot.mediaModel.canPlayPause
                        ? (mediaRoot.mediaModel.interactionEnabled ? 1.0 : 0.68)
                        : 0.25
                    scale: playPauseTap.pressed ? 1.08 : 1.0

                    Text {
                        anchors.centerIn: parent
                        text: mediaRoot.mediaModel.playbackState === "playing" ? "||" : "▶"
                        color: mediaRoot.mediaModel.textColor
                        font.family: mediaRoot.mediaModel.fontFamily
                        font.pointSize: mediaRoot.mediaModel.fontSize * 0.9
                        font.bold: true
                    }

                    TapHandler {
                        id: playPauseTap
                        enabled: mediaRoot.mediaModel.interactionEnabled
                            && mediaRoot.mediaModel.canPlayPause
                        acceptedButtons: Qt.LeftButton
                        onTapped: mediaRoot.playPauseRequested()
                    }
                }

                Rectangle {
                    width: 1.0
                    height: parent.height * 0.7
                    y: (parent.height - height) / 2.0
                    color: "#38ffffff"
                }

                Item {
                    id: nextButton
                    objectName: "mediaNextButton"
                    width: (parent.width - 2.0) / 3.0
                    height: parent.height
                    opacity: mediaRoot.mediaModel.canNext
                        ? (mediaRoot.mediaModel.interactionEnabled ? 1.0 : 0.68)
                        : 0.25
                    scale: nextTap.pressed ? 1.08 : 1.0

                    Text {
                        anchors.centerIn: parent
                        text: "→"
                        color: mediaRoot.mediaModel.textColor
                        font.family: mediaRoot.mediaModel.fontFamily
                        font.pointSize: mediaRoot.mediaModel.fontSize
                        font.bold: true
                    }

                    TapHandler {
                        id: nextTap
                        enabled: mediaRoot.mediaModel.interactionEnabled
                            && mediaRoot.mediaModel.canNext
                        acceptedButtons: Qt.LeftButton
                        onTapped: mediaRoot.nextRequested()
                    }
                }
            }
        }
    }
}
