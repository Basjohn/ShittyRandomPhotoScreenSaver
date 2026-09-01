import QtQuick
import QtQuick.Effects

OverlayWidget {
    id: mediaRoot
    objectName: "mediaPresentation"

    // H9: CUSTOM wheel/corner resize is one uniform retained-presentation scale.
    // Header, metadata, artwork, progress and controls scale together from the
    // outer-rect / baseline-preferred ratio, so a resize no longer recentres or
    // respaces individual bands. CUSTOM resize is purely geometric here; font and
    // artwork sizes stay Settings-owned (no per-value payload scaling).
    uniformScaleTransform: true

    required property var mediaModel
    semanticDoubleClickEnabled: true
    signal refreshRequested()
    signal playPauseRequested()
    signal previousRequested()
    signal nextRequested()
    signal appVolumeLevelRequested(real level)
    signal systemMuteToggleRequested()
    signal seekFractionRequested(real fraction)

    // Content-driven outer size (H option A). Width honours the historical
    // ordinary-card minimum footprint (600) and enlarges above it only when the
    // artwork + metadata genuinely require it. Height honours the historical
    // media floor of max(220, artwork_size + 60). Config-derived (no assigned
    // width/height dependency, no feedback). J refines exact dimensions.
    preferredContentWidth: Math.max(
        600.0,
        mediaModel.artworkSize + 18.0 + Math.max(220.0, mediaModel.fontSize * 16.0)
            + mediaRoot.shellInset
    )
    preferredContentHeight: Math.max(220.0, mediaModel.artworkSize + 60.0)

    function appVolumeLevelAt(y, height) {
        if (height <= 0.0)
            return 0.0
        return Math.max(0.0, Math.min(1.0, 1.0 - y / height))
    }

    function seekFractionAt(x, width) {
        if (width <= 0.0)
            return 0.0
        return Math.max(0.0, Math.min(1.0, x / width))
    }

    readonly property int visibleSectionCount: 1
        + (mediaModel.showHeaderFrame ? 1 : 0)
        + (mediaModel.progressAvailable ? 1 : 0)
        + (mediaModel.controlsBandAvailable ? 1 : 0)

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: mediaRoot.refreshRequested()
    }

    Column {
        id: mediaColumn
        objectName: "mediaContent"
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.rightMargin: appVolumeSlider.visible ? 48.0 : 0.0
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
                visible: mediaRoot.mediaModel.hasArtwork || mediaArtwork.transitionVisible
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

                ArtworkFadeImage {
                    id: mediaArtwork
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

                RectangularShadow {
                    objectName: "mediaProgressGlow"
                    visible: mediaRoot.mediaModel.progressGlowEnabled
                        && progressFill.width > 0.0
                    anchors.fill: progressFill
                    blur: Math.max(9.0, mediaRoot.mediaModel.progressHeight * 2.0)
                    spread: Math.max(1.0, mediaRoot.mediaModel.progressHeight * 0.35)
                    radius: progressFill.radius
                    color: mediaRoot.mediaModel.progressGlowColor
                    offset: Qt.vector2d(0.0, 0.0)
                    cached: true
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

                MouseArea {
                    id: progressSeekArea
                    objectName: "mediaProgressSeekArea"
                    anchors.fill: parent
                    enabled: mediaRoot.mediaModel.interactionEnabled
                        && mediaRoot.mediaModel.canSeek
                    acceptedButtons: Qt.LeftButton
                    onReleased: function(mouse) {
                        mediaRoot.seekFractionRequested(
                            mediaRoot.seekFractionAt(mouse.x, width)
                        )
                    }
                }
            }
        }

        Rectangle {
            id: controlsRow
            objectName: "mediaControlsRow"
            visible: mediaRoot.mediaModel.controlsBandAvailable
            width: parent.width
            height: visible ? Math.max(38.0, mediaRoot.mediaModel.fontSize * 2.15) : 0.0
            radius: 12.0
            color: mediaRoot.mediaModel.controlsSurfaceColor
            border.width: 1.5
            border.color: "#55ffffff"

            Row {
                visible: mediaRoot.mediaModel.controlsAvailable
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.right: parent.right
                anchors.rightMargin: systemMuteButton.visible
                    ? systemMuteButton.width + 1.0
                    : 0.0

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

            Rectangle {
                id: systemMuteButton
                objectName: "mediaSystemMuteButton"
                visible: mediaRoot.mediaModel.systemMuteAvailable
                height: parent.width < 210.0
                    ? Math.min(30.0, parent.height * 0.92)
                    : Math.min(36.0, parent.height * 0.92)
                width: parent.width < 210.0
                    ? Math.min(32.0, height * 1.08)
                    : Math.min(40.0, height * 1.08)
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                radius: Math.max(8.0, Math.min(12.0, height * 0.32))
                border.width: 1.25
                border.color: "#41ffffff"
                scale: systemMuteTap.pressed ? 1.06 : 1.0
                property real feedbackOpacity: 0.0
                gradient: Gradient {
                    GradientStop {
                        position: 0.0
                        color: Qt.rgba(
                            mediaRoot.mediaModel.systemMuteBackgroundColor.r,
                            mediaRoot.mediaModel.systemMuteBackgroundColor.g,
                            mediaRoot.mediaModel.systemMuteBackgroundColor.b,
                            Math.min(
                                1.0,
                                mediaRoot.mediaModel.systemMuteBackgroundColor.a * 0.95
                                    + 30.0 / 255.0
                            )
                        )
                    }
                    GradientStop {
                        position: 1.0
                        color: Qt.rgba(
                            mediaRoot.mediaModel.systemMuteBackgroundColor.r,
                            mediaRoot.mediaModel.systemMuteBackgroundColor.g,
                            mediaRoot.mediaModel.systemMuteBackgroundColor.b,
                            mediaRoot.mediaModel.systemMuteBackgroundColor.a * 0.85
                        )
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 3.0
                    radius: Math.max(1.0, parent.radius - 1.0)
                    color: "transparent"
                    border.width: 1.0
                    border.color: "#3c000000"
                }

                Canvas {
                    id: systemMuteIcon
                    objectName: "mediaSystemMuteIcon"
                    anchors.centerIn: parent
                    width: Math.min(parent.width, parent.height) * 0.64
                    height: width
                    property bool muted: mediaRoot.mediaModel.systemMuted
                    property color iconColor: mediaRoot.mediaModel.systemMuteIconColor
                    onMutedChanged: requestPaint()
                    onIconColorChanged: requestPaint()
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    onPaint: {
                        var context = getContext("2d")
                        context.reset()
                        context.fillStyle = iconColor
                        context.strokeStyle = iconColor
                        context.lineCap = "round"
                        context.lineWidth = Math.max(1.2, width * 0.045)
                        context.beginPath()
                        context.moveTo(width * 0.18, height * 0.42)
                        context.lineTo(width * 0.32, height * 0.42)
                        context.lineTo(width * 0.48, height * 0.27)
                        context.lineTo(width * 0.48, height * 0.73)
                        context.lineTo(width * 0.32, height * 0.58)
                        context.lineTo(width * 0.18, height * 0.58)
                        context.closePath()
                        context.fill()
                        if (muted) {
                            context.beginPath()
                            context.moveTo(width * 0.48, height * 0.28)
                            context.lineTo(width * 0.78, height * 0.72)
                            context.stroke()
                        } else {
                            context.beginPath()
                            context.arc(
                                width * 0.44, height * 0.5, width * 0.22,
                                -0.68, 0.68
                            )
                            context.stroke()
                            context.beginPath()
                            context.arc(
                                width * 0.44, height * 0.5, width * 0.36,
                                -0.68, 0.68
                            )
                            context.stroke()
                        }
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    color: "white"
                    opacity: parent.feedbackOpacity
                }

                SequentialAnimation {
                    id: systemMuteFeedback
                    NumberAnimation {
                        target: systemMuteButton
                        property: "feedbackOpacity"
                        from: 0.47
                        to: 0.0
                        duration: 350
                        easing.type: Easing.OutCubic
                    }
                }

                TapHandler {
                    id: systemMuteTap
                    enabled: mediaRoot.mediaModel.interactionEnabled
                    acceptedButtons: Qt.LeftButton
                    onTapped: {
                        systemMuteFeedback.restart()
                        mediaRoot.systemMuteToggleRequested()
                    }
                }
            }
        }
    }

    Item {
        id: appVolumeSlider
        objectName: "mediaAppVolumeSlider"
        visible: mediaRoot.mediaModel.appVolumeAvailable
        width: 32.0
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right

        Rectangle {
            id: appVolumeTrack
            objectName: "mediaAppVolumeTrack"
            width: 18.0
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.topMargin: 6.0
            anchors.bottomMargin: 6.0
            anchors.horizontalCenter: parent.horizontalCenter
            radius: width / 2.0
            color: mediaRoot.mediaModel.appVolumeTrackColor
            border.width: 1.5
            border.color: mediaRoot.mediaModel.appVolumeBorderColor

            Rectangle {
                objectName: "mediaAppVolumeFill"
                width: parent.width
                readonly property real normalizedLevel: Math.max(
                    0.0, Math.min(1.0, mediaRoot.mediaModel.appVolumeLevel)
                )
                height: normalizedLevel <= 0.0
                    ? 0.0
                    : Math.min(parent.height, Math.max(2.0, parent.height * normalizedLevel))
                y: (parent.height - height) / 2.0
                radius: width / 2.0
                color: mediaRoot.mediaModel.appVolumeFillColor
                border.width: height > 0.0 ? 1.5 : 0.0
                border.color: mediaRoot.mediaModel.appVolumeBorderColor
            }

            MouseArea {
                anchors.fill: parent
                enabled: mediaRoot.mediaModel.interactionEnabled
                acceptedButtons: Qt.LeftButton
                onPressed: function(mouse) {
                    mediaRoot.appVolumeLevelRequested(
                        mediaRoot.appVolumeLevelAt(mouse.y, height)
                    )
                }
                onPositionChanged: function(mouse) {
                    if (pressed) {
                        mediaRoot.appVolumeLevelRequested(
                            mediaRoot.appVolumeLevelAt(mouse.y, height)
                        )
                    }
                }
                onWheel: function(wheel) {
                    if (wheel.angleDelta.y === 0)
                        return
                    var direction = wheel.angleDelta.y > 0 ? 1.0 : -1.0
                    mediaRoot.appVolumeLevelRequested(
                        mediaRoot.mediaModel.appVolumeLevel + direction * 0.05
                    )
                    wheel.accepted = true
                }
            }
        }
    }
}
