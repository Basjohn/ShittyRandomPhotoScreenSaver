import QtQuick

OverlayWidget {
    id: clockRoot
    objectName: "clockPresentation"

    required property var clockModel
    semanticDoubleClickEnabled: true
    signal toggleModeRequested()

    // Report the active face's content size up to the display owner, which owns
    // anchor/clamp/outer rect. Digital is content-driven text, so it adds the
    // shell inset around the intrinsic content; analogue reports its authored
    // natural outer footprint directly (its geometry policy is the whole-widget
    // size, not inner content).
    readonly property bool _isDigital: clockRoot.clockModel.displayMode === "digital"
    preferredContentWidth: _isDigital
        ? digitalFace.preferredContentWidth + clockRoot.shellInset
        : analogueFace.preferredContentWidth
    preferredContentHeight: _isDigital
        ? digitalFace.preferredContentHeight + clockRoot.shellInset
        : analogueFace.preferredContentHeight


    // Analogue exposes one center-owned face: ring, markers, numerals and hands.
    // The rejected independent numeral editor must never shadow face selection.
    // Digital's text and the optional footer elements retain their own roles.
    customEditableChildRoles: {
        const roles = []
        const normW = Math.max(1.0, clockRoot.preferredContentWidth)
        const normH = Math.max(1.0, clockRoot.preferredContentHeight)
        if (_isDigital) {
            roles.push({ "roleId": "time_text", "target": digitalFace.customTimeTarget })
            if (clockRoot.clockModel.showSeparator)
                roles.push({ "roleId": "separator", "target": digitalFace.customSeparatorTarget })
            if (clockRoot.clockModel.calendarText.length > 0)
                roles.push({ "roleId": "calendar_text", "target": digitalFace.customCalendarTarget })
            if (clockRoot.clockModel.timezoneText.length > 0)
                roles.push({ "roleId": "timezone_text", "target": digitalFace.customTimezoneTarget })
        } else {
            roles.push({
                "roleId": "clock_face",
                "target": analogueFace.customFaceTarget,
                "centeredResize": true,

                "containmentTarget": analogueFace,
                "geometryDependencies": [analogueFace]
            })
            if (clockRoot.clockModel.showSeparator)
                roles.push({ "roleId": "separator", "target": analogueFace.customSeparatorTarget })
            if (clockRoot.clockModel.calendarText.length > 0)
                roles.push({ "roleId": "calendar_text", "target": analogueFace.customCalendarTarget })
            if (clockRoot.clockModel.timezoneText.length > 0)
                roles.push({ "roleId": "timezone_text", "target": analogueFace.customTimezoneTarget })
        }
        for (let i = 0; i < roles.length; ++i) {
            roles[i].normalizationWidth = normW
            roles[i].normalizationHeight = normH
        }
        return roles
    }

    ClockDigitalFace {
        id: digitalFace
        objectName: "clockDigitalFace"
        anchors.fill: parent
        clockModel: clockRoot.clockModel
        visible: clockRoot.clockModel.displayMode === "digital"
    }

    ClockAnalogueFace {
        id: analogueFace
        objectName: "clockAnalogueFace"
        anchors.fill: parent
        clockModel: clockRoot.clockModel
        visible: clockRoot.clockModel.displayMode === "analog"
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: clockRoot.toggleModeRequested()
    }
}
