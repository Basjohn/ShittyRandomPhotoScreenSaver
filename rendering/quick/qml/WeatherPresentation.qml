import QtQuick

OverlayWidget {
    id: weatherRoot
    objectName: "weatherPresentation"

    required property var weatherModel
    semanticDoubleClickEnabled: weatherModel.viewState !== "missing"
    signal settingsRequested(string target)
    signal refreshRequested()

    // Content-driven outer size (H option A): width from the intrinsic text
    // widths (implicitWidth) plus the optional condition icon; height from the
    // ready column's natural stacked height. Intrinsic sources only - no
    // dependency on the assigned width, so no width<->preferredWidth feedback.
    // J validates/refines exact spacing against eyes-on parity.
    preferredContentWidth: Math.max(
        140.0,
        (weatherModel.showConditionIcon ? weatherModel.iconSize + 12.0 : 0.0)
            + Math.max(locationText.implicitWidth, conditionText.implicitWidth)
    ) + weatherRoot.shellInset
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
            width: parent.width
            anchors.centerIn: parent
            spacing: 6.0
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

                Image {
                    id: leftConditionIcon
                    objectName: "weatherConditionIconLeft"
                    visible: weatherRoot.weatherModel.showConditionIcon
                        && weatherRoot.weatherModel.iconAlignment === "LEFT"
                    source: visible ? weatherRoot.weatherModel.conditionIconSource : ""
                    sourceSize.width: weatherRoot.weatherModel.iconSize
                    sourceSize.height: weatherRoot.weatherModel.iconSize
                    width: visible ? weatherRoot.weatherModel.iconSize : 0.0
                    height: width
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    fillMode: Image.PreserveAspectFit
                    asynchronous: false
                    cache: true
                }

                Column {
                    id: primaryText
                    objectName: "weatherPrimaryText"
                    anchors.left: leftConditionIcon.visible
                        ? leftConditionIcon.right : parent.left
                    anchors.leftMargin: leftConditionIcon.visible ? 14.0 : 0.0
                    anchors.right: rightConditionIcon.visible
                        ? rightConditionIcon.left : parent.right
                    anchors.rightMargin: rightConditionIcon.visible ? 14.0 : 0.0
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

                Image {
                    id: rightConditionIcon
                    objectName: "weatherConditionIconRight"
                    visible: weatherRoot.weatherModel.showConditionIcon
                        && weatherRoot.weatherModel.iconAlignment === "RIGHT"
                    source: visible ? weatherRoot.weatherModel.conditionIconSource : ""
                    sourceSize.width: weatherRoot.weatherModel.iconSize
                    sourceSize.height: weatherRoot.weatherModel.iconSize
                    width: visible ? weatherRoot.weatherModel.iconSize : 0.0
                    height: width
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    fillMode: Image.PreserveAspectFit
                    asynchronous: false
                    cache: true
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
                    spacing: 5.0

                    Separator {
                        width: parent.width
                        height: 1.0
                        thickness: 1.0
                        lineColor: weatherRoot.weatherModel.separatorColor
                    }

                    Row {
                        id: detailsRow
                        objectName: "weatherDetailsRow"
                        width: parent.width
                        height: Math.max(28.0, weatherRoot.weatherModel.detailIconSize + 4.0)

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

                                Row {
                                    anchors.centerIn: parent
                                    spacing: 2.0

                                    Image {
                                        source: modelData.icon
                                        sourceSize.width: weatherRoot.weatherModel.detailIconSize
                                        sourceSize.height: weatherRoot.weatherModel.detailIconSize
                                        width: weatherRoot.weatherModel.detailIconSize
                                        height: width
                                        fillMode: Image.PreserveAspectFit
                                        asynchronous: false
                                        cache: true
                                    }

                                    ShadowedText {
                                        width: implicitWidth
                                        height: implicitHeight
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
                    spacing: 5.0

                    Separator {
                        width: parent.width
                        height: 1.0
                        thickness: 1.0
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
            width: Math.max(1.0, parent.width - 12.0)
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
