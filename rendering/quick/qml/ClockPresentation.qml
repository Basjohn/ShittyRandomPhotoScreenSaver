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

    // With the digital card shell disabled there is no visible card perimeter to
    // glow. Follow the intrinsic text stack (+ a small breathing margin) instead
    // of outlining the invisible outer allocation. Analogue keeps its authored
    // presentation bounds.
    readonly property real _digitalGlowMargin: 4.0
    interactionGlowWidth: (_isDigital && !cardShellEnabled)
        ? Math.min(authoredCardWidth, digitalFace.preferredContentWidth + 2.0 * _digitalGlowMargin)
        : authoredCardWidth
    interactionGlowHeight: (_isDigital && !cardShellEnabled)
        ? Math.min(authoredLayoutHeight, digitalFace.preferredContentHeight + 2.0 * _digitalGlowMargin)
        : authoredLayoutHeight
    interactionGlowX: authoredCardX + (authoredCardWidth - interactionGlowWidth) * 0.5
    interactionGlowY: (authoredLayoutHeight - interactionGlowHeight) * 0.5
    interactionGlowCornerRadius: (_isDigital && !cardShellEnabled)
        ? Math.min(8.0, interactionGlowHeight * 0.18)
        : cardCornerRadius

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
