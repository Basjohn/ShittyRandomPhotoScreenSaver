import QtQuick

OverlayWidget {
    id: weatherRoot
    objectName: "weatherPresentation"
    uniformScaleTransform: true

    required property var weatherModel
    semanticDoubleClickEnabled: weatherModel.viewState !== "missing"
    signal settingsRequested(string target)
    signal refreshRequested()

    // The QWidget Weather card's effective horizontal content edge was its
    // 4 px frame plus 20 px root-layout margin. OverlayCard already contributes
    // 14 px, so retain the missing 10 px here rather than globally perturbing
    // every ordinary-widget family.
    readonly property real legacyHorizontalInset: 10.0
    readonly property real legacyTextInset: 6.0
    // The centred ready column otherwise fills the card content box exactly, so
    // the top row hugs the frame and bottom-row descenders escape the lower
    // border. Reserve a small symmetric top/bottom breathing margin.
    readonly property real legacyVerticalInset: 8.0
    // A committed CUSTOM rect deliberately owns outer geometry and therefore
    // ignores preferredContentHeight.  If that fixed rect is slightly shorter
    // than Weather's intrinsic column, fit the *whole* ready presentation just
    // enough to preserve the same authored head/foot inset rather than letting
    // forecast descenders escape the card.  This is a retained binding only:
    // no timer, no polling, and anchored/non-CUSTOM cards remain exactly 1.0.
    readonly property real readyContentFitScale: {
        const intrinsic = Math.max(1.0, readyColumn.childrenRect.height)
        const available = Math.max(1.0, weatherContent.height
            - 2.0 * weatherRoot.legacyVerticalInset)
        return Math.min(1.0, available / intrinsic)
    }

    // CUSTOM child geometry remains one normalized payload owned by the shared
    // edit session. Weather only projects those retained factors onto its
    // existing presentation items; provider/runtime cadence is untouched.
    readonly property real childNormalizationWidth: 600.0
    readonly property real childNormalizationHeight: 220.0
    readonly property var childGeometry: weatherModel.customChildGeometry
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
            * childNormalizationWidth
    }
    function childOffsetY(roleId) {
        const value = childGeometry ? childGeometry[roleId] : null
        return (value && value.y_offset !== undefined ? Number(value.y_offset) : 0.0)
            * childNormalizationHeight
    }

    customEditableChildRoles: {
        const roles = []
        if (weatherModel.viewState === "ready") {
            roles.push({ "roleId": "location_text", "target": locationText })
            roles.push({ "roleId": "condition_text", "target": conditionText })
            if (leftConditionIcon.visible || rightConditionIcon.visible) {
                roles.push({
                    "roleId": "condition_icon",
                    "target": leftConditionIcon.visible ? leftConditionIcon : rightConditionIcon
                })
            }
            if (detailsBand.visible) {
                roles.push({ "roleId": "details_separator", "target": detailsSeparator })
                roles.push({ "roleId": "details_metrics", "target": detailsRow })
            }
            if (forecastBand.visible) {
                roles.push({ "roleId": "forecast_separator", "target": forecastSeparator })
                roles.push({ "roleId": "forecast_text", "target": forecastText })
            }
            if (extendedForecastBand.visible) {
                roles.push({ "roleId": "extended_separator", "target": extendedSeparator })
                roles.push({ "roleId": "extended_label", "target": extendedForecastLabel })
                roles.push({ "roleId": "extended_text", "target": extendedForecastText })
            }
        } else {
            roles.push({ "roleId": "location_text", "target": statusTitle })
            roles.push({ "roleId": "condition_text", "target": statusAction })
        }
        for (let i = 0; i < roles.length; ++i) {
            roles[i].normalizationWidth = childNormalizationWidth
            roles[i].normalizationHeight = childNormalizationHeight
        }
        return roles
    }

    // Content-driven outer size (H option A). Width honours the historical
    // ordinary-card minimum footprint (BaseOverlayWidget.DEFAULT_CARD_MIN_WIDTH =
    // 600) and only enlarges above it when the intrinsic text/icon content
    // genuinely requires it - it must never silently shrink below the authored
    // floor. Height is content/layout driven. Intrinsic sources only (no
    // width<->preferredWidth feedback). J refines eyes-on parity.
    readonly property real intrinsicContentWidth: Math.max(
        600.0,
        (weatherModel.showConditionIcon ? weatherModel.iconSize + 12.0 : 0.0)
            + Math.max(locationText.implicitWidth, conditionText.implicitWidth)
            + weatherRoot.shellInset
            + 2.0 * weatherRoot.legacyHorizontalInset
            + 2.0 * weatherRoot.legacyTextInset
    )
    readonly property real compactReadyContentHeight:
        primaryRow.height
        + (detailsBand.visible ? readyColumn.spacing + detailsBand.height : 0.0)
        + (forecastBand.visible ? readyColumn.spacing + forecastBand.height : 0.0)
    readonly property real compactIntrinsicContentHeight: Math.max(
        60.0, compactReadyContentHeight
    ) + weatherRoot.shellInset
        + 2.0 * weatherRoot.legacyVerticalInset
    readonly property real extendedForecastRequiredHeight:
        compactIntrinsicContentHeight
        + readyColumn.spacing
        + extendedForecastColumn.implicitHeight
    readonly property bool extendedForecastVisible:
        weatherModel.extendedForecastAvailable
        && weatherModel.contentExtentActive
        && weatherModel.contentExtentHeight >= extendedForecastRequiredHeight
    readonly property real intrinsicContentHeight: Math.max(
        // Intrinsic Column layout only; its positioned child bounding box must
        // not become a feedback source during CUSTOM geometry changes.
        60.0, readyColumn.implicitHeight
    ) + weatherRoot.shellInset
        + 2.0 * weatherRoot.legacyVerticalInset
    preferredContentWidth: weatherModel.contentExtentActive
        ? weatherModel.contentExtentWidth : intrinsicContentWidth
    preferredContentHeight: weatherModel.contentExtentActive
        ? weatherModel.contentExtentHeight : intrinsicContentHeight

    TapHandler {
        enabled: weatherRoot.weatherModel.viewState !== "missing"
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: weatherRoot.refreshRequested()
    }

    Item {
        id: weatherContent
        objectName: "weatherContent"
        anchors.fill: parent

        Column {
            id: readyColumn
            objectName: "weatherReadyContent"
            width: Math.max(1.0, parent.width - 2.0 * weatherRoot.legacyHorizontalInset)
            anchors.centerIn: parent
            transformOrigin: Item.Center
            scale: weatherRoot.readyContentFitScale
            spacing: 4.0
            visible: weatherRoot.weatherModel.viewState === "ready"

            Item {
                id: primaryRow
                objectName: "weatherPrimaryRow"
                width: readyColumn.width
                height: Math.max(
                    weatherRoot.weatherModel.showConditionIcon
                        ? weatherRoot.weatherModel.iconSize : 0.0,
                    primaryText.implicitHeight
                )

                Item {
                    id: leftConditionIcon
                    objectName: "weatherConditionIconLeft"
                    transform: [
                        Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("condition_icon"); yScale: weatherRoot.childHeightScale("condition_icon") },
                        Translate { x: weatherRoot.childOffsetX("condition_icon"); y: weatherRoot.childOffsetY("condition_icon") }
                    ]
                    visible: weatherRoot.weatherModel.showConditionIcon
                        && weatherRoot.weatherModel.iconAlignment === "LEFT"
                    width: visible ? weatherRoot.weatherModel.iconSize : 0.0
                    height: width
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter

                    Image {
                        anchors.fill: parent
                        anchors.margins: 4.0
                        source: leftConditionIcon.visible
                            ? weatherRoot.weatherModel.conditionIconSource : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: false
                        cache: true
                    }
                }

                Column {
                    id: primaryText
                    objectName: "weatherPrimaryText"
                    anchors.left: leftConditionIcon.visible
                        ? leftConditionIcon.right : parent.left
                    anchors.leftMargin: leftConditionIcon.visible
                        ? 16.0 + weatherRoot.legacyTextInset
                        : weatherRoot.legacyTextInset
                    anchors.right: rightConditionIcon.visible
                        ? rightConditionIcon.left : parent.right
                    anchors.rightMargin: rightConditionIcon.visible
                        ? 16.0 + weatherRoot.legacyTextInset
                        : weatherRoot.legacyTextInset
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2.0

                    // Align visible glyph edges, not differing font side bearings.
                    // Right-aligned text retains the existing icon-left layout.
                    TextMetrics {
                        id: locationInk
                        font: locationText.font
                        text: weatherRoot.weatherModel.locationText
                    }
                    TextMetrics {
                        id: temperatureInk
                        font.family: conditionText.font.family
                        font.bold: conditionText.font.bold
                        font.pointSize: weatherRoot.weatherModel.temperatureFontSize
                        text: weatherRoot.weatherModel.temperatureText
                    }

                    ShadowedText {
                        id: locationText
                        objectName: "weatherLocationText"
                        transform: [
                            Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("location_text"); yScale: weatherRoot.childHeightScale("location_text") },
                            Translate { x: weatherRoot.childOffsetX("location_text"); y: weatherRoot.childOffsetY("location_text") }
                        ]
                        x: leftConditionIcon.visible ? 0.0 : -locationInk.tightBoundingRect.x
                        width: primaryText.width
                        height: implicitHeight
                        text: weatherRoot.weatherModel.locationText
                        color: weatherRoot.weatherModel.textColor
                        font.family: weatherRoot.weatherModel.fontFamily
                        font.pointSize: weatherRoot.weatherModel.fontSize
                        font.bold: true
                        horizontalAlignment: leftConditionIcon.visible
                            ? Text.AlignRight : Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                        shadowEnabled: weatherRoot.weatherModel.textShadowEnabled
                        shadowColor: weatherRoot.weatherModel.textShadowColor
                        shadowOffsetX: weatherRoot.weatherModel.textShadowOffsetX
                        shadowOffsetY: weatherRoot.weatherModel.textShadowOffsetY
                    }

                    ShadowedText {
                        id: conditionText
                        objectName: "weatherConditionText"
                        transform: [
                            Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("condition_text"); yScale: weatherRoot.childHeightScale("condition_text") },
                            Translate { x: weatherRoot.childOffsetX("condition_text"); y: weatherRoot.childOffsetY("condition_text") }
                        ]
                        x: leftConditionIcon.visible ? 0.0 : -temperatureInk.tightBoundingRect.x
                        width: primaryText.width
                        height: implicitHeight
                        text: weatherRoot.weatherModel.conditionMarkup
                        textFormat: Text.RichText
                        color: weatherRoot.weatherModel.textColor
                        font.family: weatherRoot.weatherModel.fontFamily
                        font.pointSize: weatherRoot.weatherModel.conditionFontSize
                        font.bold: true
                        horizontalAlignment: leftConditionIcon.visible
                            ? Text.AlignRight : Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                        wrap: true
                        shadowEnabled: weatherRoot.weatherModel.textShadowEnabled
                        shadowColor: weatherRoot.weatherModel.textShadowColor
                        shadowOffsetX: weatherRoot.weatherModel.textShadowOffsetX
                        shadowOffsetY: weatherRoot.weatherModel.textShadowOffsetY
                    }
                }

                Item {
                    id: rightConditionIcon
                    objectName: "weatherConditionIconRight"
                    transform: [
                        Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("condition_icon"); yScale: weatherRoot.childHeightScale("condition_icon") },
                        Translate { x: weatherRoot.childOffsetX("condition_icon"); y: weatherRoot.childOffsetY("condition_icon") }
                    ]
                    visible: weatherRoot.weatherModel.showConditionIcon
                        && weatherRoot.weatherModel.iconAlignment === "RIGHT"
                    width: visible ? weatherRoot.weatherModel.iconSize : 0.0
                    height: width
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter

                    Image {
                        anchors.fill: parent
                        anchors.margins: 4.0
                        source: rightConditionIcon.visible
                            ? weatherRoot.weatherModel.conditionIconSource : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: false
                        cache: true
                    }
                }
            }

            Item {
                id: detailsBand
                objectName: "weatherDetailsBand"
                width: readyColumn.width
                height: visible ? detailsColumn.implicitHeight : 0.0
                visible: weatherRoot.weatherModel.showDetails

                Column {
                    id: detailsColumn
                    width: parent.width
                    spacing: 4.0

                    Separator {
                        id: detailsSeparator
                        objectName: "weatherDetailsSeparator"
                        width: parent.width
                        height: 1.0
                        thickness: weatherRoot.scaleAwareStrokeWidth(1.0)
                        lineColor: weatherRoot.weatherModel.separatorColor
                        transform: [
                            Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("details_separator"); yScale: weatherRoot.childHeightScale("details_separator") },
                            Translate { x: weatherRoot.childOffsetX("details_separator"); y: weatherRoot.childOffsetY("details_separator") }
                        ]
                    }

                    Row {
                        id: detailsRow
                        objectName: "weatherDetailsRow"
                        transform: [
                            Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("details_metrics"); yScale: weatherRoot.childHeightScale("details_metrics") },
                            Translate { x: weatherRoot.childOffsetX("details_metrics"); y: weatherRoot.childOffsetY("details_metrics") }
                        ]
                        width: parent.width
                        // Rebuild the pre-migration detail-row breathing room.
                        // The icons/text remain compact and centred; the band owns
                        // the vertical air rather than inflating the glyphs.
                        height: Math.max(
                            68.0,
                            weatherRoot.weatherModel.detailIconSize + 38.0,
                            weatherRoot.weatherModel.detailFontSize * 3.2
                        )

                        Repeater {
                            model: [
                                {
                                    "name": "rain",
                                    "icon": weatherRoot.weatherModel.rainIconSource,
                                    "text": weatherRoot.weatherModel.rainText
                                },
                                {
                                    "name": "humidity",
                                    "icon": weatherRoot.weatherModel.humidityIconSource,
                                    "text": weatherRoot.weatherModel.humidityText
                                },
                                {
                                    "name": "wind",
                                    "icon": weatherRoot.weatherModel.windIconSource,
                                    "text": weatherRoot.weatherModel.windText
                                }
                            ]

                            Item {
                                required property var modelData
                                width: detailsRow.width / 3.0
                                height: detailsRow.height

                                Item {
                                    id: metricContent
                                    width: metricIcon.width + 1.0 + metricText.implicitWidth
                                    height: Math.max(metricIcon.height, metricText.implicitHeight)
                                    anchors.centerIn: parent

                                    Image {
                                        id: metricIcon
                                        source: modelData.icon
                                        width: weatherRoot.weatherModel.detailIconSize
                                        height: width
                                        anchors.left: parent.left
                                        anchors.verticalCenter: parent.verticalCenter
                                        fillMode: Image.PreserveAspectFit
                                        asynchronous: false
                                        cache: true
                                    }

                                    ShadowedText {
                                        id: metricText
                                        width: implicitWidth
                                        height: implicitHeight
                                        anchors.left: metricIcon.right
                                        anchors.leftMargin: 1.0
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData.text
                                        color: weatherRoot.weatherModel.textColor
                                        font.family: weatherRoot.weatherModel.fontFamily
                                        font.pointSize: weatherRoot.weatherModel.detailFontSize
                                        verticalAlignment: Text.AlignVCenter
                                        shadowEnabled: weatherRoot.weatherModel.textShadowEnabled
                                        shadowColor: weatherRoot.weatherModel.textShadowColor
                                        shadowOffsetX: weatherRoot.weatherModel.textShadowOffsetX
                                        shadowOffsetY: weatherRoot.weatherModel.textShadowOffsetY
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Item {
                id: forecastBand
                objectName: "weatherForecastBand"
                width: readyColumn.width
                height: visible ? forecastColumn.implicitHeight : 0.0
                visible: weatherRoot.weatherModel.showForecast

                Column {
                    id: forecastColumn
                    width: parent.width
                    spacing: 8.0

                    Separator {
                        id: forecastSeparator
                        objectName: "weatherForecastSeparator"
                        width: parent.width
                        height: 1.0
                        thickness: weatherRoot.scaleAwareStrokeWidth(1.0)
                        lineColor: weatherRoot.weatherModel.separatorColor
                        transform: [
                            Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("forecast_separator"); yScale: weatherRoot.childHeightScale("forecast_separator") },
                            Translate { x: weatherRoot.childOffsetX("forecast_separator"); y: weatherRoot.childOffsetY("forecast_separator") }
                        ]
                    }

                    ShadowedText {
                        id: forecastText
                        objectName: "weatherForecastText"
                        transform: [
                            Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("forecast_text"); yScale: weatherRoot.childHeightScale("forecast_text") },
                            Translate { x: weatherRoot.childOffsetX("forecast_text"); y: weatherRoot.childOffsetY("forecast_text") }
                        ]
                        width: parent.width
                        height: implicitHeight
                        text: weatherRoot.weatherModel.forecastText
                        color: weatherRoot.weatherModel.textColor
                        font.family: weatherRoot.weatherModel.fontFamily
                        font.pointSize: weatherRoot.weatherModel.detailFontSize
                        font.italic: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrap: true
                        shadowEnabled: weatherRoot.weatherModel.textShadowEnabled
                        shadowColor: weatherRoot.weatherModel.textShadowColor
                        shadowOffsetX: weatherRoot.weatherModel.textShadowOffsetX
                        shadowOffsetY: weatherRoot.weatherModel.textShadowOffsetY
                    }
                }
            }

            Item {
                id: extendedForecastBand
                objectName: "weatherExtendedForecastBand"
                width: readyColumn.width
                height: visible ? extendedForecastColumn.implicitHeight : 0.0
                visible: weatherRoot.extendedForecastVisible

                Column {
                    id: extendedForecastColumn
                    width: parent.width
                    spacing: 6.0

                    Separator {
                        id: extendedSeparator
                        objectName: "weatherExtendedForecastSeparator"
                        width: parent.width
                        height: 1.0
                        thickness: weatherRoot.scaleAwareStrokeWidth(1.0)
                        lineColor: weatherRoot.weatherModel.separatorColor
                        transform: [
                            Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("extended_separator"); yScale: weatherRoot.childHeightScale("extended_separator") },
                            Translate { x: weatherRoot.childOffsetX("extended_separator"); y: weatherRoot.childOffsetY("extended_separator") }
                        ]
                    }

                    ShadowedText {
                        id: extendedForecastLabel
                        objectName: "weatherExtendedForecastLabel"
                        transform: [
                            Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("extended_label"); yScale: weatherRoot.childHeightScale("extended_label") },
                            Translate { x: weatherRoot.childOffsetX("extended_label"); y: weatherRoot.childOffsetY("extended_label") }
                        ]
                        width: parent.width
                        height: implicitHeight
                        text: "5-DAY FORECAST"
                        color: weatherRoot.weatherModel.textColor
                        font.family: weatherRoot.weatherModel.fontFamily
                        font.pointSize: weatherRoot.weatherModel.detailFontSize * 0.78
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        shadowEnabled: weatherRoot.weatherModel.textShadowEnabled
                        shadowColor: weatherRoot.weatherModel.textShadowColor
                        shadowOffsetX: weatherRoot.weatherModel.textShadowOffsetX
                        shadowOffsetY: weatherRoot.weatherModel.textShadowOffsetY
                    }

                    ShadowedText {
                        id: extendedForecastText
                        objectName: "weatherExtendedForecastText"
                        transform: [
                            Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("extended_text"); yScale: weatherRoot.childHeightScale("extended_text") },
                            Translate { x: weatherRoot.childOffsetX("extended_text"); y: weatherRoot.childOffsetY("extended_text") }
                        ]
                        width: parent.width
                        height: implicitHeight
                        text: weatherRoot.weatherModel.extendedForecastText
                        color: weatherRoot.weatherModel.textColor
                        font.family: weatherRoot.weatherModel.fontFamily
                        font.pointSize: weatherRoot.weatherModel.detailFontSize
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrap: true
                        shadowEnabled: weatherRoot.weatherModel.textShadowEnabled
                        shadowColor: weatherRoot.weatherModel.textShadowColor
                        shadowOffsetX: weatherRoot.weatherModel.textShadowOffsetX
                        shadowOffsetY: weatherRoot.weatherModel.textShadowOffsetY
                    }
                }
            }
        }

        Column {
            id: statusColumn
            objectName: "weatherStatusContent"
            width: Math.max(
                1.0,
                parent.width - 2.0 * weatherRoot.legacyHorizontalInset - 12.0
            )
            anchors.centerIn: parent
            spacing: 6.0
            visible: weatherRoot.weatherModel.viewState !== "ready"

            ShadowedText {
                id: statusTitle
                objectName: "weatherStatusTitle"
                transform: [
                    Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("location_text"); yScale: weatherRoot.childHeightScale("location_text") },
                    Translate { x: weatherRoot.childOffsetX("location_text"); y: weatherRoot.childOffsetY("location_text") }
                ]
                width: statusColumn.width
                height: implicitHeight
                text: weatherRoot.weatherModel.locationText
                color: weatherRoot.weatherModel.textColor
                font.family: weatherRoot.weatherModel.fontFamily
                font.pointSize: weatherRoot.weatherModel.fontSize * 0.82
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                wrap: true
                shadowEnabled: weatherRoot.weatherModel.textShadowEnabled
                shadowColor: weatherRoot.weatherModel.textShadowColor
                shadowOffsetX: weatherRoot.weatherModel.textShadowOffsetX
                shadowOffsetY: weatherRoot.weatherModel.textShadowOffsetY
            }

            ShadowedText {
                id: statusAction
                objectName: "weatherStatusAction"
                transform: [
                    Scale { origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("condition_text"); yScale: weatherRoot.childHeightScale("condition_text") },
                    Translate { x: weatherRoot.childOffsetX("condition_text"); y: weatherRoot.childOffsetY("condition_text") }
                ]
                width: statusColumn.width
                height: implicitHeight
                text: weatherRoot.weatherModel.conditionText
                color: weatherRoot.weatherModel.viewState === "missing"
                    ? "#eb67c1f5" : weatherRoot.weatherModel.textColor
                font.family: weatherRoot.weatherModel.fontFamily
                font.pointSize: weatherRoot.weatherModel.fontSize * 0.65
                font.bold: true
                font.underline: weatherRoot.weatherModel.viewState === "missing"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                wrap: true
                shadowEnabled: weatherRoot.weatherModel.textShadowEnabled
                shadowColor: weatherRoot.weatherModel.textShadowColor
                shadowOffsetX: weatherRoot.weatherModel.textShadowOffsetX
                shadowOffsetY: weatherRoot.weatherModel.textShadowOffsetY

                TapHandler {
                    enabled: weatherRoot.weatherModel.viewState === "missing"
                    acceptedButtons: Qt.LeftButton
                    onTapped: weatherRoot.settingsRequested("weather_location")
                }
            }
        }
    }
}
