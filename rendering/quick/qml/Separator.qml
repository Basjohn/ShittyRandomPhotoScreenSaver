import QtQuick

// Presentation-only separator/rule primitive for simple shell layout. It has its
// own line alpha, carries no shadow, and performs no per-frame work.
Rectangle {
    id: separator
    objectName: "overlaySeparator"

    property color lineColor: "#66ffffff"
    property real thickness: 1.0
    property bool horizontal: true

    color: lineColor
    implicitWidth: horizontal ? 0.0 : thickness
    implicitHeight: horizontal ? thickness : 0.0
}
