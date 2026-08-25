import QtQuick
import QtQuick.Effects

OverlayWidget {
    id: mediaRoot
    objectName: "mediaPresentation"

    required property var mediaModel
    signal refreshRequested()

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
            height: Math.max(1.0, parent.height - headerFrame.height - mediaColumn.spacing)

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
    }
}
