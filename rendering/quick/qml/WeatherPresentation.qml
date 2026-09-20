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
    // Each transformed painted child exposes the APPLIED Scale/Translate object
    // properties to the selected Edit mapper.  Watching childGeometry here would
    // invalidate mapToItem before the QML transform binding has actually updated.
    // Normal content flow remains owned by this presentation; no extra observer.
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

    // Declare semantic ready-content roles once, independently of provider
    // readiness or optional band visibility. A temporarily hidden target keeps
    // its identity but has no live Edit box until it paints again. Status text
    // is not silently substituted for the user's saved location-text target.
    customEditableChildRoles: {
        const roles = [
            { "roleId": "location_text", "target": locationText },
            { "roleId": "condition_text", "target": conditionText },
            // These are the two existing positions of the SAME semantic icon.
            // The shared selected-Edit mapper chooses the visible paint item
            // without rebuilding this descriptor on an orientation change.
            { "roleId": "condition_icon", "target": leftConditionIcon,
                "alternateTarget": rightConditionIcon },
            { "roleId": "details_separator", "target": detailsSeparator },
            { "roleId": "details_metrics", "target": detailsRow },
            { "roleId": "forecast_separator", "target": forecastSeparator },
            { "roleId": "forecast_text", "target": forecastText },
            { "roleId": "extended_separator", "target": extendedSeparator },
            { "roleId": "extended_label", "target": extendedForecastLabel },
            { "roleId": "extended_icons", "target": extendedIconRow },
            { "roleId": "extended_text", "target": extendedForecastText }
        ]
        for (let i = 0; i < roles.length; ++i) {
            // The ready presentation is centered and uniformly fitted. Its
            // ancestor transforms must invalidate edit-box mapping on reflow.
            // A child gesture cannot claim outer/screen growth; the outer card
            // controls are the only authority for Weather content extent.
            roles[i].geometryDependencies = [weatherContent, readyColumn,
                primaryRow, primaryText, detailsBand, forecastBand,
                extendedForecastBand]
            roles[i].containmentTarget = weatherContent
            roles[i].normalizationTarget = weatherRoot
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
    // Height-only admission. A horizontal-only edit cannot change these thresholds.
    // Every threshold depends on intrinsic child heights, never on a band that
    // depends on its own visibility or on positioned childrenRect geometry.
    readonly property real verticalBudget: weatherModel.contentExtentActive
        ? weatherModel.contentExtentHeight : Number.POSITIVE_INFINITY
    // Admission sizes are independent of line wrapping caused by X-only edits.
    readonly property real primaryRequiredHeight: Math.max(60.0,
        weatherModel.showConditionIcon ? weatherModel.iconSize : 0.0,
        weatherModel.fontSize * 2.8)
        + weatherRoot.shellInset + 2.0 * weatherRoot.legacyVerticalInset
    readonly property real tomorrowAdmissionHeight: 9.0
        + Math.max(20.0, weatherModel.detailFontSize * 1.9)
    readonly property bool detailsVisible: weatherModel.showDetails
        && verticalBudget >= Math.max(260.0, primaryRequiredHeight
            + readyColumn.spacing + detailsColumn.implicitHeight)
    readonly property real afterDetailsRequiredHeight: primaryRequiredHeight
        + (detailsVisible ? readyColumn.spacing + detailsColumn.implicitHeight : 0.0)
    readonly property bool tomorrowVisible: weatherModel.showForecast
        && verticalBudget >= Math.max(240.0, afterDetailsRequiredHeight
            + readyColumn.spacing + tomorrowAdmissionHeight)
    readonly property real compactReadyContentHeight:
        primaryRow.height
        + (detailsVisible ? readyColumn.spacing + detailsColumn.implicitHeight : 0.0)
        + (tomorrowVisible ? readyColumn.spacing + forecastColumn.implicitHeight : 0.0)
    readonly property real compactIntrinsicContentHeight: Math.max(
        60.0, compactReadyContentHeight
    ) + weatherRoot.shellInset
        + 2.0 * weatherRoot.legacyVerticalInset
    readonly property real extendedForecastRequiredHeight:
        afterDetailsRequiredHeight
        + (tomorrowVisible ? readyColumn.spacing + tomorrowAdmissionHeight : 0.0)
        + readyColumn.spacing + extendedForecastColumn.implicitHeight
    readonly property bool extendedForecastVisible:
        weatherModel.extendedForecastAvailable
        && verticalBudget >= extendedForecastRequiredHeight
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
                        Scale { id: paintScale0; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("condition_icon"); yScale: weatherRoot.childHeightScale("condition_icon") },
                        Translate { id: paintTranslate0; x: weatherRoot.childOffsetX("condition_icon"); y: weatherRoot.childOffsetY("condition_icon") }
                    ]
                    // Applied transform values, not the child-geometry inputs.
                    readonly property string customEditMappingDependency: [
                        paintScale0.xScale, paintScale0.yScale,
                        paintTranslate0.x, paintTranslate0.y
                    ].join("|")
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
                            Scale { id: paintScale1; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("location_text"); yScale: weatherRoot.childHeightScale("location_text") },
                            Translate { id: paintTranslate1; x: weatherRoot.childOffsetX("location_text"); y: weatherRoot.childOffsetY("location_text") }
                        ]
                        // Applied transform values, not the child-geometry inputs.
                        readonly property string customEditMappingDependency: [
                            paintScale1.xScale, paintScale1.yScale,
                            paintTranslate1.x, paintTranslate1.y
                        ].join("|")
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
                            Scale { id: paintScale2; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("condition_text"); yScale: weatherRoot.childHeightScale("condition_text") },
                            Translate { id: paintTranslate2; x: weatherRoot.childOffsetX("condition_text"); y: weatherRoot.childOffsetY("condition_text") }
                        ]
                        // Applied transform values, not the child-geometry inputs.
                        readonly property string customEditMappingDependency: [
                            paintScale2.xScale, paintScale2.yScale,
                            paintTranslate2.x, paintTranslate2.y
                        ].join("|")
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
                        Scale { id: paintScale3; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("condition_icon"); yScale: weatherRoot.childHeightScale("condition_icon") },
                        Translate { id: paintTranslate3; x: weatherRoot.childOffsetX("condition_icon"); y: weatherRoot.childOffsetY("condition_icon") }
                    ]
                    // Applied transform values, not the child-geometry inputs.
                    readonly property string customEditMappingDependency: [
                        paintScale3.xScale, paintScale3.yScale,
                        paintTranslate3.x, paintTranslate3.y
                    ].join("|")
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
                visible: weatherRoot.detailsVisible

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
                            Scale { id: paintScale4; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("details_separator"); yScale: weatherRoot.childHeightScale("details_separator") },
                            Translate { id: paintTranslate4; x: weatherRoot.childOffsetX("details_separator"); y: weatherRoot.childOffsetY("details_separator") }
                        ]
                        // Applied transform values, not the child-geometry inputs.
                        readonly property string customEditMappingDependency: [
                            paintScale4.xScale, paintScale4.yScale,
                            paintTranslate4.x, paintTranslate4.y
                        ].join("|")
                    }

                    Row {
                        id: detailsRow
                        objectName: "weatherDetailsRow"
                        transform: [
                            Scale { id: paintScale5; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("details_metrics"); yScale: weatherRoot.childHeightScale("details_metrics") },
                            Translate { id: paintTranslate5; x: weatherRoot.childOffsetX("details_metrics"); y: weatherRoot.childOffsetY("details_metrics") }
                        ]
                        // Applied transform values, not the child-geometry inputs.
                        readonly property string customEditMappingDependency: [
                            paintScale5.xScale, paintScale5.yScale,
                            paintTranslate5.x, paintTranslate5.y
                        ].join("|")
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
                visible: weatherRoot.tomorrowVisible

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
                            Scale { id: paintScale6; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("forecast_separator"); yScale: weatherRoot.childHeightScale("forecast_separator") },
                            Translate { id: paintTranslate6; x: weatherRoot.childOffsetX("forecast_separator"); y: weatherRoot.childOffsetY("forecast_separator") }
                        ]
                        // Applied transform values, not the child-geometry inputs.
                        readonly property string customEditMappingDependency: [
                            paintScale6.xScale, paintScale6.yScale,
                            paintTranslate6.x, paintTranslate6.y
                        ].join("|")
                    }

                    ShadowedText {
                        id: forecastText
                        objectName: "weatherForecastText"
                        transform: [
                            Scale { id: paintScale7; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("forecast_text"); yScale: weatherRoot.childHeightScale("forecast_text") },
                            Translate { id: paintTranslate7; x: weatherRoot.childOffsetX("forecast_text"); y: weatherRoot.childOffsetY("forecast_text") }
                        ]
                        // Applied transform values, not the child-geometry inputs.
                        readonly property string customEditMappingDependency: [
                            paintScale7.xScale, paintScale7.yScale,
                            paintTranslate7.x, paintTranslate7.y
                        ].join("|")
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
                            Scale { id: paintScale8; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("extended_separator"); yScale: weatherRoot.childHeightScale("extended_separator") },
                            Translate { id: paintTranslate8; x: weatherRoot.childOffsetX("extended_separator"); y: weatherRoot.childOffsetY("extended_separator") }
                        ]
                        // Applied transform values, not the child-geometry inputs.
                        readonly property string customEditMappingDependency: [
                            paintScale8.xScale, paintScale8.yScale,
                            paintTranslate8.x, paintTranslate8.y
                        ].join("|")
                    }

                    ShadowedText {
                        id: extendedForecastLabel
                        objectName: "weatherExtendedForecastLabel"
                        transform: [
                            Scale { id: paintScale9; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("extended_label"); yScale: weatherRoot.childHeightScale("extended_label") },
                            Translate { id: paintTranslate9; x: weatherRoot.childOffsetX("extended_label"); y: weatherRoot.childOffsetY("extended_label") }
                        ]
                        // Applied transform values, not the child-geometry inputs.
                        readonly property string customEditMappingDependency: [
                            paintScale9.xScale, paintScale9.yScale,
                            paintTranslate9.x, paintTranslate9.y
                        ].join("|")
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

                    // Two whole-strip edit roles: a single icon scale/offset and
                    // a single label/temperature scale/offset for all five days.
                    // Both strips use identical fifth-width cells, so a live
                    // resize cannot detach a day's text from its condition icon.
                    Row {
                        id: extendedIconRow
                        objectName: "weatherExtendedForecastIcons"
                        width: parent.width
                        height: 42.0
                        spacing: 0.0
                        transform: [
                            Scale { id: paintScale10; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("extended_icons"); yScale: weatherRoot.childHeightScale("extended_icons") },
                            Translate { id: paintTranslate10; x: weatherRoot.childOffsetX("extended_icons"); y: weatherRoot.childOffsetY("extended_icons") }
                        ]
                        // Applied transform values, not the child-geometry inputs.
                        readonly property string customEditMappingDependency: [
                            paintScale10.xScale, paintScale10.yScale,
                            paintTranslate10.x, paintTranslate10.y
                        ].join("|")

                        Repeater {
                            model: weatherRoot.weatherModel.forecastDayCards
                            delegate: Item {
                                required property var modelData
                                width: extendedIconRow.width / 5.0
                                height: extendedIconRow.height
                                Image {
                                    objectName: "weatherForecastDayIcon"
                                    anchors.centerIn: parent
                                    width: Math.min(38.0, Math.max(8.0, parent.width - 8.0))
                                    height: width
                                    source: modelData.icon
                                    fillMode: Image.PreserveAspectFit
                                    asynchronous: false
                                    cache: true
                                }
                            }
                        }
                    }

                    Row {
                        id: extendedForecastText
                        objectName: "weatherExtendedForecastText"
                        width: parent.width
                        height: Math.max(40.0, weatherRoot.weatherModel.detailFontSize * 3.6)
                        spacing: 0.0
                        transform: [
                            Scale { id: paintScale11; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("extended_text"); yScale: weatherRoot.childHeightScale("extended_text") },
                            Translate { id: paintTranslate11; x: weatherRoot.childOffsetX("extended_text"); y: weatherRoot.childOffsetY("extended_text") }
                        ]
                        // Applied transform values, not the child-geometry inputs.
                        readonly property string customEditMappingDependency: [
                            paintScale11.xScale, paintScale11.yScale,
                            paintTranslate11.x, paintTranslate11.y
                        ].join("|")

                        Repeater {
                            model: weatherRoot.weatherModel.forecastDayCards
                            delegate: Column {
                                required property var modelData
                                width: extendedForecastText.width / 5.0
                                height: extendedForecastText.height
                                spacing: 3.0
                                ShadowedText {
                                    objectName: "weatherForecastDayLabel"
                                    width: parent.width
                                    height: implicitHeight
                                    text: modelData.day
                                    color: weatherRoot.weatherModel.textColor
                                    font.family: weatherRoot.weatherModel.fontFamily
                                    font.pointSize: weatherRoot.weatherModel.detailFontSize
                                    font.bold: true
                                    horizontalAlignment: Text.AlignHCenter
                                    shadowEnabled: weatherRoot.weatherModel.textShadowEnabled
                                    shadowColor: weatherRoot.weatherModel.textShadowColor
                                    shadowOffsetX: weatherRoot.weatherModel.textShadowOffsetX
                                    shadowOffsetY: weatherRoot.weatherModel.textShadowOffsetY
                                }
                                ShadowedText {
                                    objectName: "weatherForecastDayTemperature"
                                    width: parent.width
                                    height: implicitHeight
                                    text: modelData.temperature
                                    color: weatherRoot.weatherModel.textColor
                                    font.family: weatherRoot.weatherModel.fontFamily
                                    font.pointSize: weatherRoot.weatherModel.detailFontSize * 0.83
                                    horizontalAlignment: Text.AlignHCenter
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
                    Scale { id: paintScale12; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("location_text"); yScale: weatherRoot.childHeightScale("location_text") },
                    Translate { id: paintTranslate12; x: weatherRoot.childOffsetX("location_text"); y: weatherRoot.childOffsetY("location_text") }
                ]
                // Applied transform values, not the child-geometry inputs.
                readonly property string customEditMappingDependency: [
                    paintScale12.xScale, paintScale12.yScale,
                    paintTranslate12.x, paintTranslate12.y
                ].join("|")
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
                    Scale { id: paintScale13; origin.x: 0.0; origin.y: 0.0; xScale: weatherRoot.childWidthScale("condition_text"); yScale: weatherRoot.childHeightScale("condition_text") },
                    Translate { id: paintTranslate13; x: weatherRoot.childOffsetX("condition_text"); y: weatherRoot.childOffsetY("condition_text") }
                ]
                // Applied transform values, not the child-geometry inputs.
                readonly property string customEditMappingDependency: [
                    paintScale13.xScale, paintScale13.yScale,
                    paintTranslate13.x, paintTranslate13.y
                ].join("|")
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
