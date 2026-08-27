import QtQuick
import QtQuick.Effects

Item {
    id: visualizerPresentationRoot
    objectName: "visualizerPresentationRoot"

    property bool presentationActive: false
    property bool customLayoutWorkingVisible: true
    property bool cardShellEnabled: true
    property color cardBackgroundColor: "#b3101010"
    property color cardBorderColor: "#e6ffffff"
    property real cardBorderWidth: 4.0
    property real cardCornerRadius: 8.0
    property bool cardShadowEnabled: true
    property color cardShadowColor: "#96000000"
    property real cardShadowBlur: 18.0
    property real cardShadowOffsetX: 0.0
    property real cardShadowOffsetY: 4.0
    property real cardShadowSpread: 0.0

    visible: presentationActive && customLayoutWorkingVisible

    RectangularShadow {
        id: cardShadow
        anchors.fill: cardBackground
        visible: visualizerPresentationRoot.cardShellEnabled
            && visualizerPresentationRoot.cardShadowEnabled
        color: visualizerPresentationRoot.cardShadowColor
        blur: visualizerPresentationRoot.cardShadowBlur
        radius: visualizerPresentationRoot.cardCornerRadius
        spread: visualizerPresentationRoot.cardShadowSpread
        offset: Qt.vector2d(
            visualizerPresentationRoot.cardShadowOffsetX,
            visualizerPresentationRoot.cardShadowOffsetY
        )
        cached: false
        z: -1
    }

    Rectangle {
        id: cardBackground
        objectName: "visualizerCardBackground"
        anchors.fill: parent
        visible: visualizerPresentationRoot.cardShellEnabled
        color: visualizerPresentationRoot.cardBackgroundColor
        radius: visualizerPresentationRoot.cardCornerRadius
        z: 0
    }

    Item {
        id: visualizerContentHost
        objectName: "visualizerContentHost"
        anchors.fill: parent
        z: 1
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
        z: 2
    }
}
