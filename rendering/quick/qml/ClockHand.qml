import QtQuick

Item {
    id: hand
    objectName: "clockHand"

    property real centerX: 0.0
    property real centerY: 0.0
    property real handLength: 40.0
    property real handWidth: 3.0
    property real handAngle: 0.0
    property color handColor: "white"
    property bool shadowEnabled: true
    property color shadowColor: "#e6000000"
    property real shadowOffsetX: 4.0
    property real shadowOffsetY: 4.0

    Item {
        objectName: "clockHandShadow"
        x: hand.centerX + hand.shadowOffsetX
        y: hand.centerY + hand.shadowOffsetY
        width: 0.0
        height: 0.0
        rotation: hand.handAngle
        visible: hand.shadowEnabled

        Rectangle {
            width: Math.max(1.5, hand.handWidth * 1.5)
            height: hand.handLength
            x: -width / 2.0
            y: -height
            radius: width / 2.0
            color: hand.shadowColor
        }
    }

    Item {
        objectName: "clockHandVisible"
        x: hand.centerX
        y: hand.centerY
        width: 0.0
        height: 0.0
        rotation: hand.handAngle

        Rectangle {
            width: hand.handWidth
            height: hand.handLength
            x: -width / 2.0
            y: -height
            radius: width / 2.0
            color: hand.handColor
        }
    }
}
