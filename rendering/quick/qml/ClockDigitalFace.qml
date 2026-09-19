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

    readonly property var childGeometry: clockModel.customChildGeometry
    function childWidthScale(roleId) {
        const value = childGeometry ? childGeometry[roleId] : null
        return value && value.width_scale !== undefined ? Number(value.width_scale) : 1.0
    }
    function childHeightScale(roleId) {
        const value = childGeometry ? childGeometry[roleId] : null
        return value && value.height_scale !== undefined ? Number(value.height_scale) : 1.0
    }
    function childOffsetX(roleId) {
        const value = childGeometry ? childGeometry[roleId] : null
        return (value && value.x_offset !== undefined ? Number(value.x_offset) : 0.0)
            * Math.max(160.0, preferredContentWidth)
    }
    function childOffsetY(roleId) {
        const value = childGeometry ? childGeometry[roleId] : null
        return (value && value.y_offset !== undefined ? Number(value.y_offset) : 0.0)
            * Math.max(72.0, preferredContentHeight)
    }
    property alias customTimeTarget: timeText
    property alias customSeparatorTarget: digitalSeparator
    property alias customCalendarTarget: calendarText
    property alias customTimezoneTarget: timezoneText

    Column {
        id: contentColumn
        objectName: "clockDigitalContent"
        width: parent.width
        anchors.centerIn: parent
        spacing: 4.0

        ShadowedText {
            id: timeText
            objectName: "clockDigitalTime"
            transform: [
                Scale { origin.x: 0.0; origin.y: 0.0; xScale: digitalFace.childWidthScale("time_text"); yScale: digitalFace.childHeightScale("time_text") },
                Translate { x: digitalFace.childOffsetX("time_text"); y: digitalFace.childOffsetY("time_text") }
            ]
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
                id: digitalSeparator
                objectName: "clockDigitalSeparator"
                transform: [
                    Scale { origin.x: 0.0; origin.y: 0.0; xScale: digitalFace.childWidthScale("separator"); yScale: digitalFace.childHeightScale("separator") },
                    Translate { x: digitalFace.childOffsetX("separator"); y: digitalFace.childOffsetY("separator") }
                ]
                width: separatorBand.width * 0.77
                height: digitalFace.clockModel.separatorThickness
                anchors.centerIn: parent
                thickness: digitalFace.clockModel.separatorThickness
                lineColor: digitalFace.clockModel.separatorColor
                shadowEnabled: digitalFace.clockModel.textShadowEnabled
                shadowColor: digitalFace.clockModel.textShadowColor
                shadowOffsetX: digitalFace.clockModel.textShadowOffsetX
                shadowOffsetY: digitalFace.clockModel.textShadowOffsetY
            }
        }

        ShadowedText {
            id: calendarText
            objectName: "clockDigitalCalendar"
            transform: [
                Scale { origin.x: 0.0; origin.y: 0.0; xScale: digitalFace.childWidthScale("calendar_text"); yScale: digitalFace.childHeightScale("calendar_text") },
                Translate { x: digitalFace.childOffsetX("calendar_text"); y: digitalFace.childOffsetY("calendar_text") }
            ]
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
            transform: [
                Scale { origin.x: 0.0; origin.y: 0.0; xScale: digitalFace.childWidthScale("timezone_text"); yScale: digitalFace.childHeightScale("timezone_text") },
                Translate { x: digitalFace.childOffsetX("timezone_text"); y: digitalFace.childOffsetY("timezone_text") }
            ]
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
