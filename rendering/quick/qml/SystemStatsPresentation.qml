import QtQuick

OverlayWidget {
    id: statsRoot
    objectName: "systemStatsPresentation"


    required property var systemStatsModel
    uniformScaleTransform: true
    preferredContentWidth: systemStatsModel.authoredWidth
    preferredContentHeight: systemStatsModel.authoredHeight

    // Three CUSTOM edit roles: header, separator and one metric stack. The
    // repeated metric internals remain authored QML, not separately movable
    // ghost targets: moving the stack moves every enabled panel together.
    readonly property real childNormalizationWidth: systemStatsModel.baseAuthoredWidth
    readonly property real childNormalizationHeight: systemStatsModel.baseAuthoredHeight
    readonly property var childGeometry: systemStatsModel.customChildGeometry
    function childRecord(roleId) {
        return childGeometry ? childGeometry[roleId] : null
    }
    function childWidthScale(roleId) {
        const value = childRecord(roleId)
        return value && value.width_scale !== undefined ? Number(value.width_scale) : 1.0
    }
    function childHeightScale(roleId) {
        const value = childRecord(roleId)
        return value && value.height_scale !== undefined ? Number(value.height_scale) : 1.0
    }
    function childOffsetX(roleId) {
        const value = childRecord(roleId)
        return (value && value.x_offset !== undefined ? Number(value.x_offset) : 0.0)
            * childNormalizationWidth
    }
    function childOffsetY(roleId) {
        const value = childRecord(roleId)
        return (value && value.y_offset !== undefined ? Number(value.y_offset) : 0.0)
            * childNormalizationHeight
    }
    function childAlignment(roleId, fallback) {
        const value = childRecord(roleId)
        return value && value.alignment !== undefined
            ? String(value.alignment) : String(fallback || "left")
    }
    readonly property bool headerFlipped: childAlignment("header", "left") === "right"
    // One family-authored left/right rail projection for the painted metric
    // internals. The only editable metric role is their common outer stack.
    // No mirror transforms, scene lookup, polling or second layout authority.
    function metricRoleX(roleId, panelWidth, roleWidth) {
        if (roleId === "metric_accents")
            return headerFlipped ? panelWidth - roleWidth : 0.0
        if (roleId === "metric_labels" || roleId === "metric_details")
            return headerFlipped ? panelWidth - 18.0 - roleWidth : 18.0
        if (roleId === "metric_values")
            return headerFlipped ? 16.0 : panelWidth - 16.0 - valueLaneWidth
        // Tracks remain a full-width authored rail in either orientation.
        return 18.0
    }
    function childAnchor(roleId) {
        const value = childRecord(roleId)
        return value && value.anchor !== undefined ? String(value.anchor) : ""
    }

    readonly property int visibleMetricCount: systemStatsModel.enabledMetricCount
    readonly property real metricAreaTop: 88.0
    readonly property real metricAreaBottomMargin: 18.0
    readonly property real canonicalMetricGap: visibleMetricCount > 1
        ? Math.min(16.0, 9.0 + Math.max(0.0, statsRoot.systemStatsModel.authoredHeight - 430.0) * 0.018)
        : 0.0
    // The single metric-stack resize scales panel height AND inter-panel gaps.
    // Its painted bottom now follows the handle exactly instead of lagging
    // whenever the source owner changes height_scale.
    readonly property real metricGap: canonicalMetricGap * childHeightScale("metric_panels")
    readonly property real canonicalMetricPanelWidth: Math.max(
        1.0, statsRoot.systemStatsModel.authoredWidth - 32.0
    )
    readonly property real canonicalMetricPanelHeight: visibleMetricCount > 0
        ? Math.max(58.0, (statsRoot.systemStatsModel.authoredHeight - metricAreaTop - metricAreaBottomMargin
            - canonicalMetricGap * (visibleMetricCount - 1)) / visibleMetricCount)
        : 0.0
    readonly property real metricPanelWidth: canonicalMetricPanelWidth
        * childWidthScale("metric_panels")
    readonly property real metricPanelHeight: canonicalMetricPanelHeight
        * childHeightScale("metric_panels")
    readonly property real metricPanelX: 16.0 + childOffsetX("metric_panels")
    readonly property real metricPanelYOffset: childOffsetY("metric_panels")
    readonly property real metricStep: metricPanelHeight + metricGap
    readonly property real valueLaneWidth: Math.min(
        190.0,
        118.0 + Math.max(0.0, metricPanelWidth + 32.0 - 520.0) * 0.20
    )
    readonly property real representativePanelY: metricAreaTop + metricPanelYOffset

    // Keep only useful, physically meaningful Edit surfaces. The metric role
    // covers the ENTIRE stack of enabled cards, including their shared gaps.
    // Neither sample changes nor edit motion instantiate per-row proxy roles.
    customEditableChildRoles: [
        {
            "roleId": "header",
            "normalizationTarget": statsRoot,
            "target": headerFrame,
            "semanticCornerInsetX": 16.0,
            "semanticCornerInsetY": 14.0,
            "semanticInsetUsesUniformCard": true
        },
        {
            "roleId": "header_separator",
            "normalizationTarget": statsRoot,
            "target": headerSeparatorEditTarget,
            "occupiedTarget": headerSeparator
        },
        {
            "roleId": "metric_panels",
            "normalizationTarget": statsRoot,
            "target": customMetricPanelRoleTarget
        }
    ]

    BrandedHeader {
        id: headerFrame
        frameObjectName: "systemStatsHeaderFrame"
        logoObjectName: "systemStatsToolsIcon"
        textObjectName: "systemStatsHeaderText"
        transformOrigin: Item.TopLeft
        scale: statsRoot.childWidthScale("header")
        readonly property string customAnchor: statsRoot.childAnchor("header")
        property real customEditPlacementCompensationX: customAnchor.length > 0
                || statsRoot.headerFlipped
            ? x - (16.0 + statsRoot.childOffsetX("header")) : 0.0
        property real customEditPlacementCompensationY: customAnchor.length > 0
            ? y - (14.0 + statsRoot.childOffsetY("header")) : 0.0
        x: customAnchor.endsWith("right")
            ? statsRoot.systemStatsModel.authoredWidth - 16.0 - width * scale
            : (customAnchor.endsWith("left")
                ? 16.0
                : (statsRoot.headerFlipped
                    ? statsRoot.systemStatsModel.authoredWidth - 16.0 - width * scale
                    : 16.0) + statsRoot.childOffsetX("header"))
        y: customAnchor.startsWith("bottom")
            ? statsRoot.systemStatsModel.authoredHeight - 14.0 - height * scale
            : (customAnchor.startsWith("top")
                ? 14.0 : 14.0 + statsRoot.childOffsetY("header"))
        contentReversed: statsRoot.childAlignment("header", "left") === "right"
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
        id: headerSeparator
        objectName: "systemStatsHeaderSeparator"
        x: 16.0 + statsRoot.childOffsetX("header_separator")
        y: 75.0 + statsRoot.childOffsetY("header_separator")
        width: Math.max(1.0, (statsRoot.systemStatsModel.authoredWidth - 32.0)
            * statsRoot.childWidthScale("header_separator"))
        height: Math.max(0.5, statsRoot.scaleAwareStrokeWidth(1.0)
            * statsRoot.childHeightScale("header_separator"))
        color: statsRoot.systemStatsModel.metricBorderColor
    }

    Item {
        id: headerSeparatorEditTarget
        objectName: "systemStatsHeaderSeparatorEditTarget"
        visible: headerSeparator.visible
        enabled: false
        x: headerSeparator.x
        y: headerSeparator.y - (height - headerSeparator.height) / 2.0
        width: headerSeparator.width
        height: Math.max(6.0, headerSeparator.height)
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

        width: statsRoot.metricPanelWidth
        height: statsRoot.metricPanelHeight
        radius: 10.0
        color: statsRoot.systemStatsModel.metricSurfaceColor
        border.color: Qt.rgba(
            accentColor.r, accentColor.g, accentColor.b, 0.55
        )
        border.width: statsRoot.scaleAwareStrokeWidth(1.25)

        Rectangle {
            objectName: panel.objectPrefix + "Accent"
            x: statsRoot.metricRoleX("metric_accents", panel.width, width)
            y: 0.0
            width: 5.0
            height: panel.height
            radius: Math.min(width / 2.0, 2.5)
            color: panel.accentColor
        }

        ShadowedText {
            objectName: panel.objectPrefix + "Label"
            readonly property real baseY: Math.min(
                18.0, 9.0 + Math.max(0.0, panel.height - 72.0) * 0.10
            )
            readonly property real baseWidth: Math.max(
                180.0, parent.width - statsRoot.valueLaneWidth - 54.0
            )
            x: statsRoot.metricRoleX("metric_labels", panel.width, width)
            y: baseY
            width: Math.max(1.0, baseWidth)
            height: Math.max(1.0, 22.0)
            text: panel.metricLabel
            color: panel.accentColor
            font.family: statsRoot.systemStatsModel.fontFamily
            font.pointSize: statsRoot.systemStatsModel.fontSize * 0.80
            font.bold: true
            horizontalAlignment: statsRoot.headerFlipped
                ? Text.AlignRight : Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            shadowEnabled: statsRoot.systemStatsModel.textShadowEnabled
            shadowColor: statsRoot.systemStatsModel.textShadowColor
            shadowOffsetX: statsRoot.systemStatsModel.textShadowOffsetX
            shadowOffsetY: statsRoot.systemStatsModel.textShadowOffsetY
        }

        ShadowedText {
            objectName: panel.objectPrefix + "Detail"
            readonly property real baseY: Math.min(
                parent.height - 31.0,
                31.0 + Math.max(0.0, panel.height - 72.0) * 0.30
            )
            readonly property real baseWidth: Math.max(
                100.0, parent.width - statsRoot.valueLaneWidth - 54.0
            )
            x: statsRoot.metricRoleX("metric_details", panel.width, width)
            y: baseY
            width: Math.max(1.0, baseWidth)
            height: Math.max(1.0, 22.0)
            text: panel.metricDetail
            color: statsRoot.systemStatsModel.mutedTextColor
            font.family: statsRoot.systemStatsModel.fontFamily
            font.pointSize: statsRoot.systemStatsModel.fontSize * 0.70
            horizontalAlignment: statsRoot.headerFlipped
                ? Text.AlignRight : Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            shadowEnabled: statsRoot.systemStatsModel.textShadowEnabled
            shadowColor: statsRoot.systemStatsModel.textShadowColor
            shadowOffsetX: statsRoot.systemStatsModel.textShadowOffsetX
            shadowOffsetY: statsRoot.systemStatsModel.textShadowOffsetY
        }

        ShadowedText {
            objectName: panel.objectPrefix + "Value"
            readonly property real baseY: Math.min(
                17.0, 8.0 + Math.max(0.0, panel.height - 72.0) * 0.10
            )
            x: statsRoot.metricRoleX("metric_values", panel.width, width)
            y: baseY
            width: Math.max(1.0, statsRoot.valueLaneWidth)
            height: Math.max(1.0, 37.0)
            text: panel.metricValue
            color: statsRoot.systemStatsModel.textColor
            font.family: statsRoot.systemStatsModel.fontFamily
            font.pointSize: statsRoot.systemStatsModel.fontSize * 1.58
            font.bold: true
            horizontalAlignment: !statsRoot.headerFlipped
                ? Text.AlignRight : Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
            fontSizeMode: Text.HorizontalFit
            minimumPointSize: 9.0
            shadowEnabled: statsRoot.systemStatsModel.textShadowEnabled
            shadowColor: statsRoot.systemStatsModel.textShadowColor
            shadowOffsetX: statsRoot.systemStatsModel.textShadowOffsetX
            shadowOffsetY: statsRoot.systemStatsModel.textShadowOffsetY
        }

        Rectangle {
            id: metricTrack
            objectName: panel.objectPrefix + "Track"
            readonly property real baseBottomMargin: Math.min(
                14.0, 8.0 + Math.max(0.0, panel.height - 72.0) * 0.08
            )
            readonly property real baseY: panel.height - baseBottomMargin - 6.0
            visible: panel.showTrack
            x: statsRoot.metricRoleX("metric_tracks", panel.width, width)
            y: baseY
            width: Math.max(1.0, parent.width - 34.0)
            height: Math.max(1.0, 6.0)
            radius: height / 2.0
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
        id: cpuPanel
        objectName: "systemStatsCpuPanel"
        objectPrefix: "systemStatsCpu"
        x: statsRoot.metricPanelX
        y: statsRoot.metricAreaTop + statsRoot.metricPanelYOffset
        visible: statsRoot.systemStatsModel.showCpu
        metricLabel: "CPU LOAD"
        metricValue: statsRoot.systemStatsModel.cpuValue
        metricDetail: statsRoot.systemStatsModel.cpuDetail
        metricPercent: statsRoot.systemStatsModel.cpuPercent
        accentColor: statsRoot.systemStatsModel.cpuAccentColor
    }

    MetricPanel {
        id: ramPanel
        objectName: "systemStatsRamPanel"
        objectPrefix: "systemStatsRam"
        x: statsRoot.metricPanelX
        y: statsRoot.metricAreaTop + statsRoot.metricPanelYOffset
            + (statsRoot.systemStatsModel.showCpu ? statsRoot.metricStep : 0.0)
        visible: statsRoot.systemStatsModel.showMemory
        metricLabel: "MEMORY"
        metricValue: statsRoot.systemStatsModel.ramValue
        metricDetail: statsRoot.systemStatsModel.ramDetail
        metricPercent: statsRoot.systemStatsModel.ramPercent
        accentColor: statsRoot.systemStatsModel.ramAccentColor
    }

    MetricPanel {
        id: uptimePanel
        objectName: "systemStatsUptimePanel"
        objectPrefix: "systemStatsUptime"
        x: statsRoot.metricPanelX
        y: statsRoot.metricAreaTop + statsRoot.metricPanelYOffset + (
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
        id: networkPanel
        objectName: "systemStatsNetworkPanel"
        objectPrefix: "systemStatsNetwork"
        x: statsRoot.metricPanelX
        y: statsRoot.metricAreaTop + statsRoot.metricPanelYOffset + (
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

    // Exactly ONE Edit target for the whole visible metric stack. Its top-left
    // and width are the actual first panel's; its bottom reaches the last
    // enabled panel. Group movement/resize uses the existing metric_panels
    // geometry record already consumed by all four MetricPanels above.
    Item {
        id: customMetricPanelRoleTarget
        objectName: "systemStatsCustomMetricPanelRoleTarget"
        visible: statsRoot.visibleMetricCount > 0
        enabled: false
        x: statsRoot.metricPanelX
        y: statsRoot.representativePanelY
        width: statsRoot.metricPanelWidth
        height: Math.max(1.0, statsRoot.visibleMetricCount * statsRoot.metricPanelHeight
            + Math.max(0, statsRoot.visibleMetricCount - 1) * statsRoot.metricGap)
    }
}
