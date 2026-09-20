import QtQuick

Item {
    id: analogueFace
    required property var clockModel
    readonly property real fontResizeFactor: clockModel.fontResizeFactor

    readonly property bool hasCalendar: clockModel.calendarText.length > 0
    readonly property bool hasTimezone: clockModel.timezoneText.length > 0
    readonly property real footerHeight:
        (clockModel.showSeparator ? 10.0 * fontResizeFactor : 0.0)
        + (hasCalendar ? Math.max(20.0, clockModel.calendarFontSize * 1.4) * fontResizeFactor : 0.0)
        + (hasTimezone ? Math.max(18.0 * fontResizeFactor, clockModel.secondaryFontSize * 1.4) : 0.0)
        + ((hasCalendar && hasTimezone) ? 6.0 * fontResizeFactor : 0.0)
    readonly property real faceSide: Math.max(
        1.0,
        Math.min(width, height - footerHeight - 8.0 * fontResizeFactor)
    )
    readonly property real faceRadius: Math.max(12.0 * fontResizeFactor, faceSide * 0.34)
    readonly property real markerLength: Math.max(6.0 * fontResizeFactor, faceRadius * 0.10)
    readonly property real markerWidth: Math.max(2.0 * fontResizeFactor, faceRadius / 60.0)
    readonly property real numeralRadius: faceRadius + Math.max(12.0 * fontResizeFactor, faceSide * 0.055)
    readonly property real numeralSize: Math.max(8.0 * fontResizeFactor, Math.min(clockModel.fontSize * 0.20, faceSide / 18.0))
    // The edit box should enclose the *painted* face, not the unused outer
    // square. This preserves room for centered enlargement inside the card.
    readonly property real faceInkRadius: Math.max(
        faceRadius * 1.15,
        clockModel.showNumerals ? numeralRadius + numeralSize * 1.35 : 0.0
    )

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
            * preferredContentWidth
    }
    function childOffsetY(roleId) {
        const value = childGeometry ? childGeometry[roleId] : null
        return (value && value.y_offset !== undefined ? Number(value.y_offset) : 0.0)
            * preferredContentHeight
    }
    property alias customFaceTarget: faceCoreEditTarget
    property alias customSeparatorTarget: analogueSeparator
    property alias customCalendarTarget: analogueCalendar
    property alias customTimezoneTarget: analogueTimezone

    // Preferred content size (H option A): preserve the authored pre-F analogue
    // natural geometry policy exactly - width = max(160, font * 4.5), height =
    // max(width, width * 1.3) (the 1.3 factor accounts for the calendar/timezone
    // footer band). Config-derived, never a function of the assigned width (no
    // feedback). J refines eyes-on parity only.
    readonly property real preferredContentWidth: Math.max(160.0, clockModel.fontSize * 4.5)
    readonly property real preferredContentHeight: Math.max(
        preferredContentWidth, preferredContentWidth * 1.3
    )

    Item {
        id: staticFace
        objectName: "clockAnalogueStaticFace"
        width: analogueFace.faceSide
        height: analogueFace.faceSide
        x: (analogueFace.width - width) / 2.0
        y: 0.0

        readonly property real centerX: width / 2.0
        readonly property real centerY: height / 2.0

        // The complete face is center-owned. One radius change must never
        // detach numerals, markers or hands or move the authored center.
        Item {
            id: faceCoreEditTarget
            objectName: "clockAnalogueFaceCoreEditTarget"
            width: Math.max(1.0, Math.min(staticFace.width, analogueFace.faceInkRadius * 2.0))
            height: width
            x: staticFace.centerX - width / 2.0
            y: staticFace.centerY - height / 2.0
            opacity: 0.0
            readonly property string customEditMappingDependency: [
                analogueFaceCoreAppliedScale.xScale, analogueFaceCoreAppliedScale.yScale,
                analogueFaceCoreAppliedScale.origin.x, analogueFaceCoreAppliedScale.origin.y
            ].join("|")
            transform: [
                Scale { id: analogueFaceCoreAppliedScale; origin.x: faceCoreEditTarget.width / 2.0; origin.y: faceCoreEditTarget.height / 2.0; xScale: analogueFace.childWidthScale("clock_face"); yScale: analogueFace.childHeightScale("clock_face") }
            ]
        }

        Item {
            id: faceCoreUnderlay
            anchors.fill: parent
            transform: [
                Scale { origin.x: staticFace.centerX; origin.y: staticFace.centerY; xScale: analogueFace.childWidthScale("clock_face"); yScale: analogueFace.childHeightScale("clock_face") }
            ]
            Rectangle {
                id: ringShadow
                objectName: "clockAnalogueRingShadow"
                width: analogueFace.faceRadius * 2.0
                height: width
                x: staticFace.centerX - width / 2.0 + analogueFace.clockModel.analogRingOffsetX
                y: staticFace.centerY - height / 2.0 + analogueFace.clockModel.analogRingOffsetY
                radius: width / 2.0
                color: "transparent"
                border.color: analogueFace.clockModel.analogShadowColor
                border.width: Math.max(4.4 * analogueFace.fontResizeFactor, analogueFace.faceRadius * 0.0462)
                visible: analogueFace.clockModel.analogFaceShadow
            }

            Repeater {
                model: 12
                delegate: Item {
                    x: staticFace.centerX + analogueFace.clockModel.analogRingOffsetX
                    y: staticFace.centerY + analogueFace.clockModel.analogRingOffsetY
                    width: 0.0
                    height: 0.0
                    rotation: index * 30.0
                    visible: analogueFace.clockModel.analogFaceShadow

                    Rectangle {
                        width: Math.max(2.2 * analogueFace.fontResizeFactor, analogueFace.faceRadius * 0.01584)
                        height: analogueFace.markerLength
                        x: -width / 2.0
                        y: -analogueFace.faceRadius
                        radius: width / 2.0
                        color: analogueFace.clockModel.analogShadowColor
                    }
                }
            }

            Rectangle {
                objectName: "clockAnalogueRing"
                width: analogueFace.faceRadius * 2.0
                height: width
                x: staticFace.centerX - width / 2.0
                y: staticFace.centerY - height / 2.0
                radius: width / 2.0
                color: "transparent"
                border.color: analogueFace.clockModel.textColor
                border.width: Math.max(2.0 * analogueFace.fontResizeFactor, analogueFace.faceRadius * 0.032)
            }

            Repeater {
                model: 12
                delegate: Item {
                    x: staticFace.centerX
                    y: staticFace.centerY
                    width: 0.0
                    height: 0.0
                    rotation: index * 30.0

                    Rectangle {
                        width: analogueFace.markerWidth
                        height: analogueFace.markerLength
                        x: -width / 2.0
                        y: -analogueFace.faceRadius
                        radius: width / 2.0
                        color: analogueFace.clockModel.textColor
                    }
                }
            }

        }

        Item {
            id: numeralGroup
            objectName: "clockAnalogueNumeralGroup"
            anchors.fill: parent
            transform: [
                Scale { origin.x: staticFace.centerX; origin.y: staticFace.centerY; xScale: analogueFace.childWidthScale("clock_face"); yScale: analogueFace.childHeightScale("clock_face") }
            ]
            Repeater {
                id: numeralRepeater
                objectName: "clockAnalogueNumerals"
                model: ["XII", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]

                delegate: Item {
                    id: numeral
                    required property string modelData
                    required property int index
                    objectName: "clockAnalogueNumeral" + index
                    visible: analogueFace.clockModel.showNumerals
                    width: visibleNumeral.implicitWidth
                    height: visibleNumeral.implicitHeight
                    readonly property real angle: index * Math.PI / 6.0
                    x: staticFace.centerX + Math.sin(angle) * analogueFace.numeralRadius - width / 2.0
                    y: staticFace.centerY - Math.cos(angle) * analogueFace.numeralRadius - height / 2.0

                    Text {
                        id: numeralMainShadow
                        objectName: "clockAnalogueNumeralMainShadow" + numeral.index
                        x: analogueFace.clockModel.analogNumeralMainOffsetX
                        y: analogueFace.clockModel.analogNumeralMainOffsetY
                        text: numeral.modelData
                        color: analogueFace.clockModel.analogShadowColor
                        font.family: analogueFace.clockModel.fontFamily
                        font.pointSize: analogueFace.numeralSize
                        font.weight: Font.Black
                        visible: analogueFace.clockModel.analogFaceShadow
                    }

                    Text {
                        id: numeralContactShadow
                        objectName: "clockAnalogueNumeralContactShadow" + numeral.index
                        x: analogueFace.clockModel.analogNumeralContactOffsetX
                        y: analogueFace.clockModel.analogNumeralContactOffsetY
                        text: numeral.modelData
                        color: Qt.rgba(
                            analogueFace.clockModel.analogShadowColor.r,
                            analogueFace.clockModel.analogShadowColor.g,
                            analogueFace.clockModel.analogShadowColor.b,
                            analogueFace.clockModel.analogShadowColor.a * 0.84
                        )
                        font.family: analogueFace.clockModel.fontFamily
                        font.pointSize: analogueFace.numeralSize
                        font.weight: Font.Black
                        visible: analogueFace.clockModel.analogFaceShadow
                    }

                    Text {
                        id: visibleNumeral
                        objectName: "clockAnalogueNumeralVisible" + numeral.index
                        text: numeral.modelData
                        color: analogueFace.clockModel.textColor
                        font.family: analogueFace.clockModel.fontFamily
                        font.pointSize: analogueFace.numeralSize
                        font.weight: Font.Black
                    }
                }
            }

        }

        Item {
            id: faceCoreHands
            anchors.fill: parent
            transform: [
                Scale { origin.x: staticFace.centerX; origin.y: staticFace.centerY; xScale: analogueFace.childWidthScale("clock_face"); yScale: analogueFace.childHeightScale("clock_face") }
            ]
            ClockHand {
                objectName: "clockAnalogueHourHand"
                centerX: staticFace.centerX
                centerY: staticFace.centerY
                handLength: analogueFace.faceRadius * 0.52
                handWidth: Math.max(3.0 * analogueFace.fontResizeFactor, analogueFace.faceRadius / 15.0)
                handAngle: analogueFace.clockModel.hourAngle
                handColor: analogueFace.clockModel.textColor
                shadowEnabled: analogueFace.clockModel.analogFaceShadow
                shadowColor: analogueFace.clockModel.analogShadowColor
                shadowOffsetX: analogueFace.clockModel.analogHandOffsetX
                shadowOffsetY: analogueFace.clockModel.analogHandOffsetY
            }

            ClockHand {
                objectName: "clockAnalogueMinuteHand"
                centerX: staticFace.centerX
                centerY: staticFace.centerY
                handLength: analogueFace.faceRadius * 0.72
                handWidth: Math.max(2.0 * analogueFace.fontResizeFactor, analogueFace.faceRadius / 20.0)
                handAngle: analogueFace.clockModel.minuteAngle
                handColor: analogueFace.clockModel.textColor
                shadowEnabled: analogueFace.clockModel.analogFaceShadow
                shadowColor: analogueFace.clockModel.analogShadowColor
                shadowOffsetX: analogueFace.clockModel.analogHandOffsetX
                shadowOffsetY: analogueFace.clockModel.analogHandOffsetY
            }

            ClockHand {
                objectName: "clockAnalogueSecondHand"
                centerX: staticFace.centerX
                centerY: staticFace.centerY
                handLength: analogueFace.faceRadius * 0.85
                handWidth: 1.0 * analogueFace.fontResizeFactor
                handAngle: analogueFace.clockModel.secondAngle
                handColor: analogueFace.clockModel.textColor
                shadowEnabled: analogueFace.clockModel.analogFaceShadow && analogueFace.clockModel.showSeconds
                shadowColor: analogueFace.clockModel.analogShadowColor
                shadowOffsetX: analogueFace.clockModel.analogHandOffsetX
                shadowOffsetY: analogueFace.clockModel.analogHandOffsetY
                visible: analogueFace.clockModel.showSeconds
            }
        }

    }

    Column {
        id: footer
        objectName: "clockAnalogueFooter"
        width: parent.width
        y: staticFace.height + 4.0 * analogueFace.fontResizeFactor
        spacing: 4.0 * analogueFace.fontResizeFactor

        Item {
            width: footer.width
            height: visible ? 10.0 * analogueFace.fontResizeFactor : 0.0
            visible: analogueFace.clockModel.showSeparator

            Separator {
                id: analogueSeparator
                objectName: "clockAnalogueSeparator"
                readonly property string customEditMappingDependency: [
                    analogueSeparatorAppliedScale.xScale, analogueSeparatorAppliedScale.yScale,
                    analogueSeparatorAppliedTranslation.x, analogueSeparatorAppliedTranslation.y
                ].join("|")
                transform: [
                    Scale { id: analogueSeparatorAppliedScale; origin.x: 0.0; origin.y: 0.0; xScale: analogueFace.childWidthScale("separator"); yScale: analogueFace.childHeightScale("separator") },
                    Translate { id: analogueSeparatorAppliedTranslation; x: analogueFace.childOffsetX("separator"); y: analogueFace.childOffsetY("separator") }
                ]
                width: parent.width * 0.77
                height: analogueFace.clockModel.separatorThickness * analogueFace.fontResizeFactor
                anchors.centerIn: parent
                thickness: analogueFace.clockModel.separatorThickness * analogueFace.fontResizeFactor
                lineColor: analogueFace.clockModel.separatorColor
                shadowEnabled: analogueFace.clockModel.textShadowEnabled
                shadowColor: analogueFace.clockModel.textShadowColor
                shadowOffsetX: analogueFace.clockModel.textShadowOffsetX
                shadowOffsetY: analogueFace.clockModel.textShadowOffsetY
            }
        }

        ShadowedText {
            id: analogueCalendar
            objectName: "clockAnalogueCalendar"
            readonly property string customEditMappingDependency: [
                analogueCalendarAppliedScale.xScale, analogueCalendarAppliedScale.yScale,
                analogueCalendarAppliedTranslation.x, analogueCalendarAppliedTranslation.y
            ].join("|")
            transform: [
                Scale { id: analogueCalendarAppliedScale; origin.x: 0.0; origin.y: 0.0; xScale: analogueFace.childWidthScale("calendar_text"); yScale: analogueFace.childHeightScale("calendar_text") },
                Translate { id: analogueCalendarAppliedTranslation; x: analogueFace.childOffsetX("calendar_text"); y: analogueFace.childOffsetY("calendar_text") }
            ]
            width: footer.width
            height: visible ? implicitHeight : 0.0
            visible: text.length > 0
            text: analogueFace.clockModel.calendarText
            color: analogueFace.clockModel.textColor
            font.family: analogueFace.clockModel.fontFamily
            font.pointSize: analogueFace.clockModel.calendarFontSize * analogueFace.fontResizeFactor
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            shadowEnabled: analogueFace.clockModel.textShadowEnabled
            shadowColor: analogueFace.clockModel.textShadowColor
            shadowOffsetX: analogueFace.clockModel.textShadowOffsetX
            shadowOffsetY: analogueFace.clockModel.textShadowOffsetY
        }

        ShadowedText {
            id: analogueTimezone
            objectName: "clockAnalogueTimezone"
            readonly property string customEditMappingDependency: [
                analogueTimezoneAppliedScale.xScale, analogueTimezoneAppliedScale.yScale,
                analogueTimezoneAppliedTranslation.x, analogueTimezoneAppliedTranslation.y
            ].join("|")
            transform: [
                Scale { id: analogueTimezoneAppliedScale; origin.x: 0.0; origin.y: 0.0; xScale: analogueFace.childWidthScale("timezone_text"); yScale: analogueFace.childHeightScale("timezone_text") },
                Translate { id: analogueTimezoneAppliedTranslation; x: analogueFace.childOffsetX("timezone_text"); y: analogueFace.childOffsetY("timezone_text") }
            ]
            width: footer.width
            height: visible ? implicitHeight : 0.0
            visible: text.length > 0
            text: analogueFace.clockModel.timezoneText
            color: analogueFace.clockModel.textColor
            font.family: analogueFace.clockModel.fontFamily
            // secondaryFontSize tracks the resized primary font already;
            // multiplying again would double-apply the clock_font ratio.
            font.pointSize: analogueFace.clockModel.secondaryFontSize
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            shadowEnabled: analogueFace.clockModel.textShadowEnabled
            shadowColor: analogueFace.clockModel.textShadowColor
            shadowOffsetX: analogueFace.clockModel.textShadowOffsetX
            shadowOffsetY: analogueFace.clockModel.textShadowOffsetY
        }
    }
}
