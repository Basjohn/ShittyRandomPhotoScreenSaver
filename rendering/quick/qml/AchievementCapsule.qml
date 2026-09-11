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
    property bool shelfStyle: false
    property real capsuleHeight: 26.0
    property real capsuleGap: 6.0
    property real capsuleFontSize: 12.0
    property string fontFamily: "Inter"
    property color fillColor: "#26c7d5e0"
    property color borderColor: "#91c7d5e0"
    property color shelfSeparatorColor: "#6ec7d5e0"
    property color shelfAccentColor: borderColor
    property color textColor: "#ffffffff"
    property bool textShadowEnabled: true
    property color textShadowColor: "#54000000"
    property real textShadowOffsetX: 1.0
    property real textShadowOffsetY: 1.0

    function shelfValueText(value) {
        const upper = String(value || "").trim().toUpperCase()
        return (upper === "UNKNOWN" || upper === "UNAVAILABLE")
            ? "UNAVAILABLE"
            : upper
    }

    height: shelfStyle
        ? capsuleHeight
        : (doubled ? capsuleHeight * 2.0 + capsuleGap : capsuleHeight)

    Item {
        id: primaryShell
        objectName: "achievementCapsulePrimary_" + capsule.fieldId
        visible: !capsule.shelfStyle
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
        visible: capsule.doubled && !capsule.shelfStyle
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
    Item {
        id: shelfShell
        objectName: "achievementShelf_" + capsule.fieldId
        visible: capsule.shelfStyle
        anchors.fill: parent

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1.0
            color: capsule.shelfSeparatorColor
        }

        Rectangle {
            x: 0.0
            anchors.verticalCenter: parent.verticalCenter
            width: 4.0
            height: 4.0
            radius: 2.0
            color: Qt.rgba(
                capsule.shelfAccentColor.r,
                capsule.shelfAccentColor.g,
                capsule.shelfAccentColor.b,
                0.76
            )
        }

        ShadowedText {
            x: 9.0
            width: (parent.width - 13.0) * 0.53
            height: parent.height
            text: capsule.fieldId === "previous"
                ? "PREVIOUSLY" : capsule.fieldLabel.toUpperCase()
            color: Qt.rgba(
                capsule.textColor.r,
                capsule.textColor.g,
                capsule.textColor.b,
                Math.max(0.47, capsule.textColor.a * 0.72)
            )
            font.family: capsule.fontFamily
            font.pointSize: capsule.capsuleFontSize * 0.82
            font.bold: true
            verticalAlignment: Text.AlignVCenter
            fontSizeMode: Text.HorizontalFit
            minimumPointSize: 6.0
            elide: Text.ElideRight
            shadowEnabled: capsule.textShadowEnabled
            shadowColor: capsule.textShadowColor
            shadowOffsetX: capsule.textShadowOffsetX
            shadowOffsetY: capsule.textShadowOffsetY
        }

        ShadowedText {
            x: 9.0 + (parent.width - 13.0) * 0.55
            width: (parent.width - 13.0) * 0.45
            height: parent.height
            text: capsule.shelfValueText(capsule.fieldValue)
            color: capsule.textColor
            font.family: capsule.fontFamily
            font.pointSize: capsule.capsuleFontSize * 0.82
            font.bold: true
            horizontalAlignment: Text.AlignRight
            verticalAlignment: Text.AlignVCenter
            fontSizeMode: Text.HorizontalFit
            minimumPointSize: 6.0
            elide: Text.ElideRight
            shadowEnabled: capsule.textShadowEnabled
            shadowColor: capsule.textShadowColor
            shadowOffsetX: capsule.textShadowOffsetX
            shadowOffsetY: capsule.textShadowOffsetY
        }
    }

}
