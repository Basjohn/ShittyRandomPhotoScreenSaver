import QtQuick

OverlayWidget {
    id: statsRoot
    objectName: "systemStatsPresentation"

    required property var systemStatsModel
    uniformScaleTransform: true
    preferredContentWidth: systemStatsModel.authoredWidth
    preferredContentHeight: systemStatsModel.authoredHeight

    readonly property int visibleMetricCount: systemStatsModel.enabledMetricCount
    readonly property real metricAreaTop: 88.0
    readonly property real metricAreaBottomMargin: 18.0
    readonly property real metricGap: visibleMetricCount > 1
        ? Math.min(16.0, 9.0 + Math.max(0.0, statsRoot.systemStatsModel.authoredHeight - 430.0) * 0.018)
        : 0.0
    readonly property real metricPanelHeight: visibleMetricCount > 0
        ? Math.max(58.0, (statsRoot.systemStatsModel.authoredHeight - metricAreaTop - metricAreaBottomMargin
            - metricGap * (visibleMetricCount - 1)) / visibleMetricCount)
        : 0.0
    readonly property real metricStep: metricPanelHeight + metricGap
    readonly property real valueLaneWidth: Math.min(190.0,
        118.0 + Math.max(0.0, statsRoot.systemStatsModel.authoredWidth - 520.0) * 0.20)

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
        borderWidth: statsRoot.scaleAwareHeaderStrokeWidth(
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
        property bool showTrack: true

        width: statsRoot.systemStatsModel.authoredWidth - 32.0
        height: statsRoot.metricPanelHeight
        radius: 10.0
        color: statsRoot.systemStatsModel.metricSurfaceColor
        border.color: Qt.rgba(
            accentColor.r, accentColor.g, accentColor.b, 0.55
        )
        border.width: statsRoot.scaleAwareStrokeWidth(1.25)

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
            y: Math.min(18.0, 9.0 + Math.max(0.0, panel.height - 72.0) * 0.10)
            width: Math.max(180.0, parent.width - statsRoot.valueLaneWidth - 54.0)
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
            y: Math.min(parent.height - 31.0,
                31.0 + Math.max(0.0, panel.height - 72.0) * 0.30)
            width: Math.max(100.0, parent.width - statsRoot.valueLaneWidth - 54.0)
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
            y: Math.min(17.0, 8.0 + Math.max(0.0, panel.height - 72.0) * 0.10)
            width: statsRoot.valueLaneWidth
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
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Math.min(14.0,
                8.0 + Math.max(0.0, panel.height - 72.0) * 0.08)
            visible: panel.showTrack
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
        y: statsRoot.metricAreaTop
        visible: statsRoot.systemStatsModel.showCpu
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
        y: statsRoot.metricAreaTop
            + (statsRoot.systemStatsModel.showCpu ? statsRoot.metricStep : 0.0)
        visible: statsRoot.systemStatsModel.showMemory
        metricLabel: "MEMORY"
        metricValue: statsRoot.systemStatsModel.ramValue
        metricDetail: statsRoot.systemStatsModel.ramDetail
        metricPercent: statsRoot.systemStatsModel.ramPercent
        accentColor: statsRoot.systemStatsModel.ramAccentColor
    }

    MetricPanel {
        objectName: "systemStatsUptimePanel"
        objectPrefix: "systemStatsUptime"
        x: 16.0
        y: statsRoot.metricAreaTop + (
            (statsRoot.systemStatsModel.showCpu ? 1 : 0)
            + (statsRoot.systemStatsModel.showMemory ? 1 : 0)
        ) * statsRoot.metricStep
        visible: statsRoot.systemStatsModel.showUptime
        metricLabel: "UPTIME"
        metricValue: statsRoot.systemStatsModel.uptimeValue
        metricDetail: statsRoot.systemStatsModel.uptimeDetail
        metricPercent: 0.0
        accentColor: statsRoot.systemStatsModel.uptimeAccentColor
        showTrack: false
    }

    MetricPanel {
        objectName: "systemStatsNetworkPanel"
        objectPrefix: "systemStatsNetwork"
        x: 16.0
        y: statsRoot.metricAreaTop + (
            (statsRoot.systemStatsModel.showCpu ? 1 : 0)
            + (statsRoot.systemStatsModel.showMemory ? 1 : 0)
            + (statsRoot.systemStatsModel.showUptime ? 1 : 0)
        ) * statsRoot.metricStep
        visible: statsRoot.systemStatsModel.showNetwork
        metricLabel: "NETWORK"
        metricValue: statsRoot.systemStatsModel.networkValue
        metricDetail: statsRoot.systemStatsModel.networkDetail
        metricPercent: 0.0
        accentColor: statsRoot.systemStatsModel.networkAccentColor
        showTrack: false
    }


}
