import QtQuick

OverlayWidget {
    id: weatherRoot
    objectName: "weatherPresentation"

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

    // Content-driven outer size (H option A). Width honours the historical
    // ordinary-card minimum footprint (BaseOverlayWidget.DEFAULT_CARD_MIN_WIDTH =
    // 600) and only enlarges above it when the intrinsic text/icon content
    // genuinely requires it - it must never silently shrink below the authored
    // floor. Height is content/layout driven. Intrinsic sources only (no
    // width<->preferredWidth feedback). J refines eyes-on parity.
    preferredContentWidth: Math.max(
        600.0,
        (weatherModel.showConditionIcon ? weatherModel.iconSize + 12.0 : 0.0)
            + Math.max(locationText.implicitWidth, conditionText.implicitWidth)
            + weatherRoot.shellInset
            + 2.0 * weatherRoot.legacyHorizontalInset
            + 2.0 * weatherRoot.legacyTextInset
    )
    preferredContentHeight: Math.max(
        60.0, readyColumn.childrenRect.height
    ) + weatherRoot.shellInset

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

                    ShadowedText {
                        id: locationText
                        objectName: "weatherLocationText"
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
                        width: primaryText.width
                        height: implicitHeight
                        text: weatherRoot.weatherModel.conditionText
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
                objectName: "weatherDetailsBand"
                width: readyColumn.width
                height: visible ? detailsColumn.implicitHeight : 0.0
                visible: weatherRoot.weatherModel.showDetails

                Column {
                    id: detailsColumn
                    width: parent.width
                    spacing: 4.0

                    Separator {
                        width: parent.width
                        height: weatherRoot.scaleAwareStrokeWidth(1.0)
                        thickness: weatherRoot.scaleAwareStrokeWidth(1.0)
                        lineColor: weatherRoot.weatherModel.separatorColor
                    }

                    Row {
                        id: detailsRow
                        objectName: "weatherDetailsRow"
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
                objectName: "weatherForecastBand"
                width: readyColumn.width
                height: visible ? forecastColumn.implicitHeight : 0.0
                visible: weatherRoot.weatherModel.showForecast

                Column {
                    id: forecastColumn
                    width: parent.width
                    spacing: 8.0

                    Separator {
                        width: parent.width
                        height: weatherRoot.scaleAwareStrokeWidth(1.0)
                        thickness: weatherRoot.scaleAwareStrokeWidth(1.0)
                        lineColor: weatherRoot.weatherModel.separatorColor
                    }

                    ShadowedText {
                        objectName: "weatherForecastText"
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
                objectName: "weatherStatusTitle"
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
