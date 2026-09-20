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
        if (_isDigital) {
            roles.push({ "roleId": "time_text", "target": digitalFace.customTimeTarget })
            roles.push({ "roleId": "separator", "target": digitalFace.customSeparatorTarget })
            roles.push({ "roleId": "calendar_text", "target": digitalFace.customCalendarTarget })
            roles.push({ "roleId": "timezone_text", "target": digitalFace.customTimezoneTarget })
        } else {
            roles.push({
                "roleId": "clock_face",
                "target": analogueFace.customFaceTarget,
                "centeredResize": true,

                "containmentTarget": analogueFace,
                "geometryDependencies": [analogueFace]
            })
            roles.push({ "roleId": "separator", "target": analogueFace.customSeparatorTarget })
            roles.push({ "roleId": "calendar_text", "target": analogueFace.customCalendarTarget })
            roles.push({ "roleId": "timezone_text", "target": analogueFace.customTimezoneTarget })
        }
        for (let i = 0; i < roles.length; ++i) {
            // The actual preferred extent may change as the intrinsic digital
            // text changes. Observe it on the *delegate*, not on this list:
            // rebuilding the list would retire the in-flight Edit gesture.
            roles[i].normalizationTarget = clockRoot
            roles[i].normalizationWidthProperty = "preferredContentWidth"
            roles[i].normalizationHeightProperty = "preferredContentHeight"
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
