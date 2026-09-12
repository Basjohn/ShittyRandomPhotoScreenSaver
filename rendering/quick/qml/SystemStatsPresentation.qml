import QtQuick

OverlayWidget {
    id: statsRoot
    objectName: "systemStatsPresentation"

    required property var systemStatsModel
    uniformScaleTransform: true
    preferredContentWidth: systemStatsModel.authoredWidth
    preferredContentHeight: systemStatsModel.authoredHeight

    BrandedHeader {
        id: headerFrame
        frameObjectName: "systemStatsHeaderFrame"
        logoObjectName: "systemStatsToolsIcon"
        textObjectName: "systemStatsHeaderText"
        x: 16.0
        y: 14.0
        label: statsRoot.systemStatsModel.headerText
        logoSource: statsRoot.systemStatsModel.iconSource
        logoTintEnabled: true
        logoTintColor: statsRoot.systemStatsModel.cpuAccentColor
        fillColor: statsRoot.systemStatsModel.headerFillColor
        borderColor: statsRoot.systemStatsModel.headerBorderColor
        borderWidth: statsRoot.scaleAwareStrokeWidth(
            statsRoot.systemStatsModel.headerBorderWidth
        )
        textColor: statsRoot.systemStatsModel.headerTextColor
        fontFamily: statsRoot.systemStatsModel.fontFamily
        textShadowEnabled: statsRoot.systemStatsModel.textShadowEnabled
        textShadowColor: statsRoot.systemStatsModel.textShadowColor
        textShadowOffsetX: statsRoot.systemStatsModel.textShadowOffsetX
        textShadowOffsetY: statsRoot.systemStatsModel.textShadowOffsetY
        shadowEnabled: statsRoot.cardShadowEnabled
        shadowColor: Qt.rgba(
            statsRoot.cardShadowColor.r,
            statsRoot.cardShadowColor.g,
            statsRoot.cardShadowColor.b,
            statsRoot.cardShadowColor.a * 0.42
        )
        shadowBlur: Math.max(2.0, Math.min(6.0, statsRoot.cardShadowBlur * 0.25))
        shadowOffsetX: statsRoot.cardShadowOffsetX * 1.15
        shadowOffsetY: statsRoot.cardShadowOffsetY * 1.15
    }

    ShadowedText {
        x: 298.0
        y: 20.0
        width: statsRoot.systemStatsModel.authoredWidth - x - 18.0
        height: 26.0
        text: statsRoot.systemStatsModel.cadenceText
        color: statsRoot.systemStatsModel.mutedTextColor
        font.family: statsRoot.systemStatsModel.fontFamily
        font.pointSize: statsRoot.systemStatsModel.fontSize * 0.68
        font.bold: true
        horizontalAlignment: Text.AlignRight
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        shadowEnabled: statsRoot.systemStatsModel.textShadowEnabled
        shadowColor: statsRoot.systemStatsModel.textShadowColor
        shadowOffsetX: statsRoot.systemStatsModel.textShadowOffsetX
        shadowOffsetY: statsRoot.systemStatsModel.textShadowOffsetY
    }

    Row {
        x: statsRoot.systemStatsModel.authoredWidth - 55.0
        y: 52.0
        spacing: 5.0
        Repeater {
            model: 3
            delegate: Rectangle {
                required property int index
                width: 5.0
                height: 5.0
                radius: 2.5
                color: index === 0
                    ? statsRoot.systemStatsModel.cpuAccentColor
                    : (index === 1
                        ? statsRoot.systemStatsModel.ramAccentColor
                        : statsRoot.systemStatsModel.metricBorderColor)
                opacity: 0.82 - index * 0.16
            }
        }
    }

    Rectangle {
        x: 16.0
        y: 75.0
        width: statsRoot.systemStatsModel.authoredWidth - 32.0
        height: statsRoot.scaleAwareStrokeWidth(1.0)
        color: statsRoot.systemStatsModel.metricBorderColor
    }

    component MetricPanel: Rectangle {
        id: panel
        required property string objectPrefix
        required property string metricLabel
        required property string metricValue
        required property string metricDetail
        required property real metricPercent
        required property color accentColor

        width: statsRoot.systemStatsModel.authoredWidth - 32.0
        height: 72.0
        radius: 10.0
        color: statsRoot.systemStatsModel.metricSurfaceColor
        border.color: Qt.rgba(
            accentColor.r, accentColor.g, accentColor.b, 0.55
        )
        border.width: statsRoot.scaleAwareStrokeWidth(1.0)

        Rectangle {
            x: 0.0
            y: 0.0
            width: 5.0
            height: parent.height
            radius: 2.5
            color: panel.accentColor
        }

        ShadowedText {
            x: 18.0
            y: 9.0
            width: 220.0
            height: 22.0
            text: panel.metricLabel
            color: panel.accentColor
            font.family: statsRoot.systemStatsModel.fontFamily
            font.pointSize: statsRoot.systemStatsModel.fontSize * 0.80
            font.bold: true
            verticalAlignment: Text.AlignVCenter
            shadowEnabled: statsRoot.systemStatsModel.textShadowEnabled
            shadowColor: statsRoot.systemStatsModel.textShadowColor
            shadowOffsetX: statsRoot.systemStatsModel.textShadowOffsetX
            shadowOffsetY: statsRoot.systemStatsModel.textShadowOffsetY
        }

        ShadowedText {
            objectName: panel.objectPrefix + "Detail"
            x: 18.0
            y: 31.0
            width: Math.max(100.0, parent.width - 168.0)
            height: 22.0
            text: panel.metricDetail
            color: statsRoot.systemStatsModel.mutedTextColor
            font.family: statsRoot.systemStatsModel.fontFamily
            font.pointSize: statsRoot.systemStatsModel.fontSize * 0.70
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            shadowEnabled: statsRoot.systemStatsModel.textShadowEnabled
            shadowColor: statsRoot.systemStatsModel.textShadowColor
            shadowOffsetX: statsRoot.systemStatsModel.textShadowOffsetX
            shadowOffsetY: statsRoot.systemStatsModel.textShadowOffsetY
        }

        ShadowedText {
            objectName: panel.objectPrefix + "Value"
            anchors.right: parent.right
            anchors.rightMargin: 16.0
            y: 8.0
            width: 118.0
            height: 37.0
            text: panel.metricValue
            color: statsRoot.systemStatsModel.textColor
            font.family: statsRoot.systemStatsModel.fontFamily
            font.pointSize: statsRoot.systemStatsModel.fontSize * 1.58
            font.bold: true
            horizontalAlignment: Text.AlignRight
            verticalAlignment: Text.AlignVCenter
            fontSizeMode: Text.HorizontalFit
            minimumPointSize: 9.0
            shadowEnabled: statsRoot.systemStatsModel.textShadowEnabled
            shadowColor: statsRoot.systemStatsModel.textShadowColor
            shadowOffsetX: statsRoot.systemStatsModel.textShadowOffsetX
            shadowOffsetY: statsRoot.systemStatsModel.textShadowOffsetY
        }

        Rectangle {
            x: 18.0
            y: 58.0
            width: parent.width - 34.0
            height: 6.0
            radius: 3.0
            color: statsRoot.systemStatsModel.trackColor
            border.color: statsRoot.systemStatsModel.metricBorderColor
            border.width: statsRoot.scaleAwareStrokeWidth(1.0)

            Rectangle {
                width: Math.max(
                    0.0,
                    Math.min(parent.width, parent.width * panel.metricPercent / 100.0)
                )
                height: parent.height
                radius: parent.radius
                color: panel.accentColor

                Behavior on width {
                    NumberAnimation {
                        duration: 420
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }
    }

    MetricPanel {
        objectName: "systemStatsCpuPanel"
        objectPrefix: "systemStatsCpu"
        x: 16.0
        y: 88.0
        metricLabel: "CPU LOAD"
        metricValue: statsRoot.systemStatsModel.cpuValue
        metricDetail: statsRoot.systemStatsModel.cpuDetail
        metricPercent: statsRoot.systemStatsModel.cpuPercent
        accentColor: statsRoot.systemStatsModel.cpuAccentColor
    }

    MetricPanel {
        objectName: "systemStatsRamPanel"
        objectPrefix: "systemStatsRam"
        x: 16.0
        y: 169.0
        metricLabel: "MEMORY"
        metricValue: statsRoot.systemStatsModel.ramValue
        metricDetail: statsRoot.systemStatsModel.ramDetail
        metricPercent: statsRoot.systemStatsModel.ramPercent
        accentColor: statsRoot.systemStatsModel.ramAccentColor
    }

    ShadowedText {
        x: 18.0
        y: statsRoot.systemStatsModel.authoredHeight - 23.0
        width: statsRoot.systemStatsModel.authoredWidth - 36.0
        height: 16.0
        text: "SPARSE SAMPLE  •  NO HISTORY  •  CPU + RAM"
        color: statsRoot.systemStatsModel.mutedTextColor
        font.family: statsRoot.systemStatsModel.fontFamily
        font.pointSize: statsRoot.systemStatsModel.fontSize * 0.58
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        shadowEnabled: statsRoot.systemStatsModel.textShadowEnabled
        shadowColor: statsRoot.systemStatsModel.textShadowColor
        shadowOffsetX: statsRoot.systemStatsModel.textShadowOffsetX
        shadowOffsetY: statsRoot.systemStatsModel.textShadowOffsetY
    }
}
