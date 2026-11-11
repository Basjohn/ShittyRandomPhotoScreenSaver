import QtQuick
import QtQuick.Effects

// Media's seek bar: the rounded track, its fill to the playback fraction, an optional drop shadow under the track
// and an optional glow around the fill, a hover wash while seeking is admitted, and the seek area. The one seek bar,
// drawn by the Media card (MediaPresentation.qml, in its progress band) and, optionally, by the Expanded Visualizer's
// Now Playing (ExpandedVisualizerOverlays.qml). The caller places and sizes it, feeds the model's state and look (the
// Media model's progress traits; MediaPresentationModel.seekBarLook carries them as plain values for a second drawing)
// and routes seekRequested(fraction) to the Media card's own seek owner. Position steps on the Media timeline's own
// events (no timer, no interpolation here).
Rectangle {
    id: seekBar
    objectName: "mediaProgressTrack"

    // ---- state (the Media model's)
    property real fraction: 0.0
    property bool seekEnabled: false

    // ---- look (the Media model's progress traits)
    property color trackColor: "#4dffffff"
    property color fillColor: "#ffffffff"
    property bool shadowEnabled: false
    property color shadowColor: "#00000000"
    property bool glowEnabled: false
    property color glowColor: "#00000000"
    // The Settings-authored seek height the glow's blur and spread follow (not the drawn, possibly edited height).
    property real glowBaseHeight: 6.0

    // ---- object names (the callers' test and capture hooks)
    property alias hoverWashObjectName: hoverWash.objectName
    property alias glowObjectName: glow.objectName
    property alias fillObjectName: fill.objectName
    property alias seekAreaObjectName: seekArea.objectName
    readonly property alias hovered: seekArea.containsMouse

    signal seekRequested(real fraction)

    function fractionAt(x, extent) {
        if (extent <= 0.0)
            return 0.0
        return Math.max(0.0, Math.min(1.0, x / extent))
    }

    radius: height / 2.0
    color: seekBar.trackColor

    Rectangle {
        id: hoverWash
        objectName: "mediaProgressHoverWash"
        anchors.fill: parent
        radius: parent.radius
        color: seekArea.containsMouse && seekArea.enabled
            ? Qt.rgba(seekBar.fillColor.r, seekBar.fillColor.g, seekBar.fillColor.b, 0.18)
            : "transparent"
        z: 2
    }

    Rectangle {
        visible: seekBar.shadowEnabled
        x: 0.0
        y: 2.0
        width: parent.width
        height: parent.height
        radius: parent.radius
        color: seekBar.shadowColor
        z: -2
    }

    RectangularShadow {
        id: glow
        objectName: "mediaProgressGlow"
        visible: seekBar.glowEnabled && fill.width > 0.0
        anchors.fill: fill
        blur: Math.max(9.0, seekBar.glowBaseHeight * 2.0)
        spread: Math.max(1.0, seekBar.glowBaseHeight * 0.35)
        radius: fill.radius
        color: seekBar.glowColor
        offset: Qt.vector2d(0.0, 0.0)
        cached: true
        z: -1
    }

    Rectangle {
        id: fill
        objectName: "mediaProgressFill"
        width: parent.width * Math.max(0.0, Math.min(1.0, seekBar.fraction))
        height: parent.height
        radius: Math.min(width, height) / 2.0
        color: seekBar.fillColor
    }

    MouseArea {
        id: seekArea
        objectName: "mediaProgressSeekArea"
        anchors.fill: parent
        enabled: seekBar.seekEnabled
        hoverEnabled: enabled
        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        acceptedButtons: Qt.LeftButton
        onReleased: function(mouse) {
            seekBar.seekRequested(seekBar.fractionAt(mouse.x, width))
        }
    }
}
