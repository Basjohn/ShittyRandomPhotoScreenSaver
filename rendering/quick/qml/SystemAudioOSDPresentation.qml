import QtQuick

// One retained ordinary item, visible only on effective master-audio events or
// while its existing CUSTOM editor owns input. No QML audio source or poll.
OverlayWidget {
    id: osdRoot
    objectName: "systemAudioOSDPresentation"
    required property var osdModel
    uniformScaleTransform: true
    preferredContentWidth: osdModel.authoredWidth
    preferredContentHeight: osdModel.authoredHeight
    // The host initializes fadeOpacity to zero before scene admission. The
    // retained model/host updates it only on event/deadline/Edit edges.
    Behavior on fadeOpacity {
        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
    }
    onCustomLayoutInputBlockedChanged: {
        fadeOpacity = customLayoutInputBlocked || osdModel.revealed ? 1.0 : 0.0
    }

    Item {
        id: osdBody
        objectName: "systemAudioOSDBody"
        anchors.fill: parent
        clip: true
        readonly property bool numericOnly: osdModel.textPosition === "numbers_only"
        readonly property bool showNumeric: osdModel.textPosition !== "none"
        readonly property bool leftNumeric: osdModel.textPosition === "left_of_bar"
        readonly property bool insideNumeric: osdModel.textPosition === "inside_bar"
        readonly property bool rightNumeric: osdModel.textPosition === "right_of_bar"
        readonly property real glyphSize: Math.max(15, Math.min(30, height * 0.53))
        readonly property real numericWidth: Math.min(70, Math.max(43, width * 0.18))
        readonly property real edgeInset: Math.min(12, width * 0.04)
        readonly property real laneStart: edgeInset + (numericOnly ? 0 : glyphSize + 8)
            + (leftNumeric ? numericWidth : 0)
        readonly property real laneEnd: width - edgeInset
            - ((rightNumeric || numericOnly) ? numericWidth : 0)
        readonly property real laneWidth: Math.max(0, laneEnd - laneStart)

        Canvas {
            id: speakerGlyph
            objectName: "systemAudioOSDSpeakerGlyph"
            visible: !osdBody.numericOnly
            x: osdBody.edgeInset
            width: osdBody.glyphSize
            height: width
            y: (parent.height - height) / 2
            onPaint: {
                const context = getContext("2d")
                context.clearRect(0, 0, width, height)
                context.strokeStyle = osdModel.accentColor.toString()
                context.lineWidth = 1.7
                context.lineCap = "round"
                context.lineJoin = "round"
                context.beginPath()
                context.moveTo(width * .12, height * .39)
                context.lineTo(width * .3, height * .39)
                context.lineTo(width * .53, height * .20)
                context.lineTo(width * .53, height * .80)
                context.lineTo(width * .3, height * .61)
                context.lineTo(width * .12, height * .61)
                context.closePath()
                context.stroke()
                context.beginPath()
                if (osdModel.muted) {
                    context.moveTo(width * .65, height * .34)
                    context.lineTo(width * .91, height * .66)
                    context.moveTo(width * .91, height * .34)
                    context.lineTo(width * .65, height * .66)
                } else {
                    context.moveTo(width * .65, height * .35)
                    context.quadraticCurveTo(width * .85, height * .5, width * .65, height * .65)
                }
                context.stroke()
            }
            Connections {
                target: osdRoot.osdModel
                function onStateChanged() { speakerGlyph.requestPaint() }
            }
        }

        Rectangle {
            id: audioTrack
            objectName: "systemAudioOSDVolumeTrack"
            visible: !osdBody.numericOnly && width > 0
            x: osdBody.laneStart
            width: osdBody.laneWidth
            height: Math.min(osdModel.barThickness, osdBody.height * .48)
            y: (osdBody.height - height) / 2
            radius: height / 2
            color: osdModel.trackColor
            clip: true
            Rectangle {
                id: audioFill
                objectName: "systemAudioOSDVolumeFill"
                x: 0
                width: parent.width * (osdModel.available ? osdModel.volumeFraction : 0)
                height: parent.height
                radius: parent.radius
                color: osdModel.accentColor
                opacity: osdModel.muted ? 0.37 : 1.0
            }
        }

        Text {
            id: percentage
            objectName: "systemAudioOSDPercentage"
            visible: osdBody.showNumeric
            text: osdModel.percentageText
            color: osdModel.textColor
            font.family: osdModel.fontFamily
            font.pixelSize: osdModel.fontSize
            font.bold: true
            width: osdBody.insideNumeric ? audioTrack.width : osdBody.numericWidth
            x: osdBody.insideNumeric ? audioTrack.x
                : (osdBody.leftNumeric ? osdBody.laneStart - width
                   : osdBody.numericOnly ? (osdBody.width - width) / 2
                   : osdBody.width - osdBody.edgeInset - width)
            height: parent.height
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            clip: true
        }
    }
}
