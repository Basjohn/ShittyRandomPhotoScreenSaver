import QtQuick

// Shared ordinary-card feedback. OverlayWidget observes input at the common
// ancestor of family controls; this item owns pixels only. Nothing runs at rest.
Item {
    id: glow
    objectName: "widgetInteractionGlow"
    property bool hoverEnabled: false
    property bool clickEnabled: false
    property bool hovered: false
    property bool clicked: false
    property color glowColor: "transparent"
    property real cornerRadius: 8.0
    // Settings-owned 0..1 multiplier. The authored hover/click relationship
    // stays local to this primitive; runtime input merely projects one scalar.
    property real intensityScale: 1.0
    property real hoverLevel: 0.0
    property real clickLevel: 0.0
    readonly property bool animating: hoverFade.running || clickFade.running
    readonly property real intensity: Math.min(
        1.0,
        Math.max(hoverLevel, clickLevel) * Math.max(0.0, intensityScale)
    )

    function stopFeedback() {
        hoverFade.stop()
        clickFade.stop()
        hoverLevel = 0.0
        clickLevel = 0.0
    }
    onParentChanged: {
        if (!parent)
            stopFeedback()
    }
    onVisibleChanged: {
        if (!visible)
            stopFeedback()
    }

    // Hover/click are state edges, not one-shot pulse clocks. Enter/selection
    // fades toward the authored level and then remains completely settled;
    // leaving/changing target is the only thing that begins the gentle decay.
    function updateHover() {
        hoverFade.stop()
        hoverFade.to = hoverEnabled && hovered ? 0.80 : 0.0
        hoverFade.duration = hoverFade.to > hoverLevel ? 180 : 620
        if (Math.abs(hoverLevel - hoverFade.to) < 0.0001) {
            hoverLevel = hoverFade.to
            return
        }
        hoverFade.restart()
    }
    function updateClick() {
        clickFade.stop()
        clickFade.to = clickEnabled && clicked ? 1.0 : 0.0
        clickFade.duration = clickFade.to > clickLevel ? 170 : 760
        if (Math.abs(clickLevel - clickFade.to) < 0.0001) {
            clickLevel = clickFade.to
            return
        }
        clickFade.restart()
    }
    onHoverEnabledChanged: updateHover()
    onHoveredChanged: updateHover()
    onClickEnabledChanged: updateClick()
    onClickedChanged: updateClick()

    NumberAnimation {
        id: hoverFade
        target: glow
        property: "hoverLevel"
        easing.type: Easing.OutCubic
    }
    NumberAnimation {
        id: clickFade
        target: glow
        property: "clickLevel"
        easing.type: Easing.OutCubic
    }

    // One analytical hollow glow, no captured source or offscreen blur texture.
    // Two bounded passes make 100% visibly emphatic without rebaking the shader
    // or adding any cadence. Both are inert whenever the event-held level is 0.
    ShaderEffect {
        x: -12.0
        y: -12.0
        width: glow.width + 24.0
        height: glow.height + 24.0
        property vector2d effectSize: Qt.vector2d(width, height)
        property vector2d cardSize: Qt.vector2d(glow.width, glow.height)
        property real cornerRadius: glow.cornerRadius
        property color glowColor: glow.glowColor
        opacity: glow.intensity
        visible: opacity > 0.0
        fragmentShader: "shaders/widget_glow.frag.qsb"
    }
    ShaderEffect {
        x: -12.0
        y: -12.0
        width: glow.width + 24.0
        height: glow.height + 24.0
        property vector2d effectSize: Qt.vector2d(width, height)
        property vector2d cardSize: Qt.vector2d(glow.width, glow.height)
        property real cornerRadius: glow.cornerRadius
        property color glowColor: glow.glowColor
        opacity: glow.intensity * 0.85
        visible: opacity > 0.0
        fragmentShader: "shaders/widget_glow.frag.qsb"
    }
}
