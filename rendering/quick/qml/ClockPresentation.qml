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


    // Variant-aware child roles. Analogue keeps the clock face and hands as one
    // alignment-preserving group while numerals remain independently editable.
    // Digital exposes its time block in place of analogue-only face geometry.
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
                "collisionIgnoreRoleIds": ["numerals"]
            })
            if (clockRoot.clockModel.showNumerals) {
                roles.push({
                    "roleId": "numerals",
                    "target": analogueFace.customNumeralsTarget,
                    "collisionIgnoreRoleIds": ["clock_face"]
                })
            }
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
