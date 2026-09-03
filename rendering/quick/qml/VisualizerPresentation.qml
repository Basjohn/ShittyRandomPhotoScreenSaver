import QtQuick
import QtQuick.Effects

Item {
    id: visualizerPresentationRoot
    objectName: "visualizerPresentationRoot"

    property bool presentationActive: false
    property bool customLayoutWorkingVisible: true
    property bool volumeWheelEnabled: true
    signal appVolumeStepRequested(int direction)
    property real authoredSceneOpacity: 1.0
    property real startupRevealOpacity: 1.0
    property bool cardShellEnabled: true
    property color cardBackgroundColor: "#4c232323"
    property color cardBorderColor: "#ffffffff"
    property real cardBorderWidth: 4.0
    property real cardCornerRadius: 8.0
    property bool cardShadowEnabled: true
    property color cardShadowColor: "#96000000"
    property real cardShadowBlur: 18.0
    property real cardShadowOffsetX: 0.0
    property real cardShadowOffsetY: 4.0
    property real cardShadowSpread: 0.0
    property real cardShadowExtendLeft: 0.0
    property real cardShadowExtendTop: 0.0
    property real cardShadowExtendRight: 0.0
    property real cardShadowExtendBottom: 0.0
    readonly property real cardShadowBaseLeft: Math.max(0.0, -cardShadowOffsetX)
    readonly property real cardShadowBaseTop: Math.max(0.0, -cardShadowOffsetY)
    readonly property real cardShadowBaseRight: Math.max(0.0, cardShadowOffsetX)
    readonly property real cardShadowBaseBottom: Math.max(0.0, cardShadowOffsetY)
    property bool perfHudEnabled: false
    property string perfHudText: ""

    opacity: authoredSceneOpacity * startupRevealOpacity
    visible: presentationActive && customLayoutWorkingVisible && opacity > 0.0

    WheelHandler {
        target: null
        enabled: visualizerPresentationRoot.presentationActive
            && visualizerPresentationRoot.customLayoutWorkingVisible
            && visualizerPresentationRoot.volumeWheelEnabled
        onWheel: function(wheel) {
            if (wheel.angleDelta.y === 0)
                return
            visualizerPresentationRoot.appVolumeStepRequested(
                wheel.angleDelta.y > 0 ? 1 : -1
            )
            wheel.accepted = true
        }
    }

    RectangularShadow {
        id: cardShadow
        x: cardBackground.x
            - visualizerPresentationRoot.cardShadowBaseLeft
            - visualizerPresentationRoot.cardShadowExtendLeft
        y: cardBackground.y
            - visualizerPresentationRoot.cardShadowBaseTop
            - visualizerPresentationRoot.cardShadowExtendTop
        width: cardBackground.width
            + visualizerPresentationRoot.cardShadowBaseLeft
            + visualizerPresentationRoot.cardShadowBaseRight
            + visualizerPresentationRoot.cardShadowExtendLeft
            + visualizerPresentationRoot.cardShadowExtendRight
        height: cardBackground.height
            + visualizerPresentationRoot.cardShadowBaseTop
            + visualizerPresentationRoot.cardShadowBaseBottom
            + visualizerPresentationRoot.cardShadowExtendTop
            + visualizerPresentationRoot.cardShadowExtendBottom
        visible: visualizerPresentationRoot.cardShellEnabled
            && visualizerPresentationRoot.cardShadowEnabled
        color: visualizerPresentationRoot.cardShadowColor
        blur: visualizerPresentationRoot.cardShadowBlur
        radius: visualizerPresentationRoot.cardCornerRadius
        spread: visualizerPresentationRoot.cardShadowSpread
        // Card direction is one-sided surface extrusion, never effect
        // translation. This preserves opposite-edge coverage at large Extra
        // Offset values just like the shared ordinary-widget OverlayCard.
        offset: Qt.vector2d(0.0, 0.0)
        cached: true
        z: 0
    }

    Rectangle {
        id: cardBackground
        objectName: "visualizerCardBackground"
        anchors.fill: parent
        visible: visualizerPresentationRoot.cardShellEnabled
        color: visualizerPresentationRoot.cardBackgroundColor
        radius: visualizerPresentationRoot.cardCornerRadius
        z: 1
    }

    Item {
        id: visualizerContentHost
        objectName: "visualizerContentHost"
        anchors.fill: parent
        z: 2
    }

    Rectangle {
        id: cardFrame
        objectName: "visualizerCardFrame"
        anchors.fill: parent
        visible: visualizerPresentationRoot.cardShellEnabled
        color: "transparent"
        radius: visualizerPresentationRoot.cardCornerRadius
        border.color: visualizerPresentationRoot.cardBorderColor
        border.width: visualizerPresentationRoot.cardBorderWidth
        z: 3
    }

    Rectangle {
        id: visualizerPerfHud
        objectName: "visualizerPerfHud"
        visible: visualizerPresentationRoot.perfHudEnabled
            && visualizerPresentationRoot.perfHudText.length > 0
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 6
        width: visualizerPerfHudLabel.implicitWidth + 10
        height: visualizerPerfHudLabel.implicitHeight + 6
        radius: 3
        color: "#b8000000"
        border.color: "#80ffffff"
        border.width: 1
        z: 20
        enabled: false

        Text {
            id: visualizerPerfHudLabel
            anchors.centerIn: parent
            text: visualizerPresentationRoot.perfHudText
            color: "white"
            font.family: "Consolas"
            font.pixelSize: 10
            renderType: Text.NativeRendering
        }
    }
}
