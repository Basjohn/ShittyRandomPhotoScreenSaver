import QtQuick

// Presentation-only separator/rule primitive. Like ShadowedText, its optional
// shadow follows the same optional soft silhouette as ordinary text, preserving
// its signed global displacement and the original layer-free dark/hard route.
Item {
    id: separator
    objectName: "overlaySeparator"

    property color lineColor: "#66ffffff"
    property real thickness: 1.0
    property bool horizontal: true

    property bool shadowEnabled: false
    property bool shadowSoft: false
    property color shadowColor: "#96000000"
    property real shadowOffsetX: 0.0
    property real shadowOffsetY: 2.0

    implicitWidth: horizontal ? 0.0 : thickness
    implicitHeight: horizontal ? thickness : 0.0
    clip: false

    Component {
        id: softShadowEffect
        SoftShadowEffect {
            softOffsetX: separator.shadowOffsetX
            softOffsetY: separator.shadowOffsetY
        }
    }

    Rectangle {
        id: separatorShadow
        objectName: "overlaySeparatorShadow"
        x: separator.shadowOffsetX
        y: separator.shadowOffsetY
        width: separator.horizontal ? separator.width : separator.thickness
        height: separator.horizontal ? separator.thickness : separator.height
        visible: separator.shadowEnabled
        layer.enabled: separator.shadowEnabled && separator.shadowSoft
        layer.effect: separator.shadowSoft ? softShadowEffect : null
        color: separator.shadowColor
        enabled: false
        z: 0
    }

    Rectangle {
        id: separatorLine
        objectName: "overlaySeparatorLine"
        width: separator.horizontal ? separator.width : separator.thickness
        height: separator.horizontal ? separator.thickness : separator.height
        color: separator.lineColor
        enabled: false
        z: 1
    }
}
