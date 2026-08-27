import QtQuick

OverlayWidget {
    id: clockRoot
    objectName: "clockPresentation"

    required property var clockModel
    semanticDoubleClickEnabled: true
    signal toggleModeRequested()

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
