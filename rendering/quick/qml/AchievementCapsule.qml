import QtQuick
import QtQuick.Effects

// Achievement Pulse supporting-data capsule. The bottom/right shell shadow is
// family-authored visual geometry from the existing card, independent of the
// canonical ordinary text-shadow direction supplied by Python.
Item {
    id: capsule

    required property string fieldId
    required property string fieldLabel
    required property string fieldValue
    property bool doubled: true
    property real capsuleHeight: 26.0
    property real capsuleGap: 6.0
    property real capsuleFontSize: 12.0
    property string fontFamily: "Inter"
    property color fillColor: "#26c7d5e0"
    property color borderColor: "#91c7d5e0"
    property color textColor: "#ffffffff"
    property bool textShadowEnabled: true
    property color textShadowColor: "#54000000"
    property real textShadowOffsetX: 1.0
    property real textShadowOffsetY: 1.0

    height: doubled ? capsuleHeight * 2.0 + capsuleGap : capsuleHeight

    Item {
        id: primaryShell
        objectName: "achievementCapsulePrimary_" + capsule.fieldId
        width: parent.width
        height: capsule.capsuleHeight

        RectangularShadow {
            anchors.fill: primaryBackground
            color: "#72000000"
            blur: 3.0
            radius: primaryBackground.radius
            offset: Qt.vector2d(1.5, 1.5)
            cached: true
        }

        Rectangle {
            id: primaryBackground
            anchors.fill: parent
            radius: height / 2.0
            color: capsule.fillColor
            border.color: capsule.borderColor
            border.width: 1.0
        }

        ShadowedText {
            anchors.fill: parent
            anchors.leftMargin: 7.0
            anchors.rightMargin: 7.0
            text: capsule.doubled
                ? (capsule.fieldId === "previous"
                    ? "PREVIOUSLY" : capsule.fieldLabel.toUpperCase())
                : capsule.fieldLabel.toUpperCase() + "   " + capsule.fieldValue
            color: capsule.textColor
            font.family: capsule.fontFamily
            font.pointSize: capsule.capsuleFontSize
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            shadowEnabled: capsule.textShadowEnabled
            shadowColor: capsule.textShadowColor
            shadowOffsetX: capsule.textShadowOffsetX
            shadowOffsetY: capsule.textShadowOffsetY
        }
    }

    Item {
        id: detailShell
        objectName: "achievementCapsuleDetail_" + capsule.fieldId
        visible: capsule.doubled
        y: capsule.capsuleHeight + capsule.capsuleGap
        width: parent.width
        height: capsule.capsuleHeight

        RectangularShadow {
            anchors.fill: detailBackground
            color: "#72000000"
            blur: 3.0
            radius: detailBackground.radius
            offset: Qt.vector2d(1.5, 1.5)
            cached: true
        }

        Rectangle {
            id: detailBackground
            anchors.fill: parent
            radius: height / 2.0
            color: capsule.fillColor
            border.color: capsule.borderColor
            border.width: 1.0
        }

        ShadowedText {
            anchors.fill: parent
            anchors.leftMargin: 7.0
            anchors.rightMargin: 7.0
            text: capsule.fieldValue.toUpperCase()
            color: capsule.textColor
            font.family: capsule.fontFamily
            font.pointSize: capsule.capsuleFontSize
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            shadowEnabled: capsule.textShadowEnabled
            shadowColor: capsule.textShadowColor
            shadowOffsetX: capsule.textShadowOffsetX
            shadowOffsetY: capsule.textShadowOffsetY
        }
    }
}
