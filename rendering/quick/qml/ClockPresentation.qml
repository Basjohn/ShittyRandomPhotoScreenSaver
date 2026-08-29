import QtQuick

OverlayWidget {
    id: clockRoot
    objectName: "clockPresentation"

    required property var clockModel
    semanticDoubleClickEnabled: true
    signal toggleModeRequested()

    // Report the active face's intrinsic/config-derived content size (plus the
    // shell inset) up to the display owner, which owns anchor/clamp/outer rect.
    readonly property bool _isDigital: clockRoot.clockModel.displayMode === "digital"
    preferredContentWidth: (
        _isDigital ? digitalFace.preferredContentWidth : analogueFace.preferredContentWidth
    ) + clockRoot.shellInset
    preferredContentHeight: (
        _isDigital ? digitalFace.preferredContentHeight : analogueFace.preferredContentHeight
    ) + clockRoot.shellInset

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
