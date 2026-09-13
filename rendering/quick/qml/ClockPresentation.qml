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
