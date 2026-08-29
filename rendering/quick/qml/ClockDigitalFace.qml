import QtQuick

Item {
    id: digitalFace
    required property var clockModel

    // Intrinsic preferred content size (H option A): the natural, unconstrained
    // text widths (implicitWidth) and the stacked column's natural height. These
    // derive only from content/font metrics, never from this face's assigned
    // width, so reporting them upward creates no width<->preferredWidth loop.
    readonly property real preferredContentWidth: Math.max(
        timeText.implicitWidth,
        calendarText.visible ? calendarText.implicitWidth : 0.0,
        timezoneText.visible ? timezoneText.implicitWidth : 0.0
    )
    // The stacked column's natural height. childrenRect.height is used rather
    // than the Column's implicitHeight because the column is centre-anchored,
    // which leaves implicitHeight unpopulated; the height dimension of
    // childrenRect stays intrinsic (it does not depend on the assigned width).
    readonly property real preferredContentHeight: contentColumn.childrenRect.height

    Column {
        id: contentColumn
        objectName: "clockDigitalContent"
        width: parent.width
        anchors.centerIn: parent
        spacing: 4.0

        ShadowedText {
            id: timeText
            objectName: "clockDigitalTime"
            width: contentColumn.width
            height: implicitHeight
            text: digitalFace.clockModel.timeText
            color: digitalFace.clockModel.textColor
            font.family: digitalFace.clockModel.fontFamily
            font.pointSize: digitalFace.clockModel.fontSize
            font.bold: true
            font.features: { "tnum": 1 }
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            shadowEnabled: digitalFace.clockModel.textShadowEnabled
            shadowColor: digitalFace.clockModel.textShadowColor
            shadowOffsetX: digitalFace.clockModel.textShadowOffsetX
            shadowOffsetY: digitalFace.clockModel.textShadowOffsetY
        }

        Item {
            id: separatorBand
            objectName: "clockDigitalSeparatorBand"
            width: contentColumn.width
            height: visible ? 14.0 : 0.0
            visible: digitalFace.clockModel.showSeparator

            Separator {
                objectName: "clockDigitalSeparator"
                width: separatorBand.width * 0.77
                height: 2.0
                anchors.centerIn: parent
                thickness: 2.0
                lineColor: digitalFace.clockModel.separatorColor
            }
        }

        ShadowedText {
            id: calendarText
            objectName: "clockDigitalCalendar"
            width: contentColumn.width
            height: visible ? implicitHeight : 0.0
            visible: text.length > 0
            text: digitalFace.clockModel.calendarText
            color: digitalFace.clockModel.textColor
            font.family: digitalFace.clockModel.fontFamily
            font.pointSize: digitalFace.clockModel.calendarFontSize
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            shadowEnabled: digitalFace.clockModel.textShadowEnabled
            shadowColor: digitalFace.clockModel.textShadowColor
            shadowOffsetX: digitalFace.clockModel.textShadowOffsetX
            shadowOffsetY: digitalFace.clockModel.textShadowOffsetY
        }

        ShadowedText {
            id: timezoneText
            objectName: "clockDigitalTimezone"
            width: contentColumn.width
            height: visible ? implicitHeight : 0.0
            visible: text.length > 0
            text: digitalFace.clockModel.timezoneText
            color: digitalFace.clockModel.textColor
            font.family: digitalFace.clockModel.fontFamily
            font.pointSize: digitalFace.clockModel.secondaryFontSize
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            shadowEnabled: digitalFace.clockModel.textShadowEnabled
            shadowColor: digitalFace.clockModel.textShadowColor
            shadowOffsetX: digitalFace.clockModel.textShadowOffsetX
            shadowOffsetY: digitalFace.clockModel.textShadowOffsetY
        }
    }
}
