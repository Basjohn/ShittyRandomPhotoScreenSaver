import QtQuick

// Shared ordinary-card feedback. OverlayWidget observes input at the common
// ancestor of family controls; this item owns pixels only. Nothing runs at rest.
Item {
    id: glow
    objectName: "widgetInteractionGlow"
    property bool hoverEnabled: false
    property bool clickEnabled: false
    property bool hovered: false
    property color glowColor: "transparent"
    property real cornerRadius: 8.0
    property real hoverLevel: 0.0
    property real clickLevel: 0.0
    readonly property bool animating: hoverPulse.running || clickPulse.running
    readonly property real intensity: Math.max(hoverLevel, clickLevel)

    function stopFeedback() {
        hoverPulse.stop()
        clickPulse.stop()
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

    function updateHover() {
        hoverPulse.stop()
        hoverPulse.to = hoverEnabled && hovered ? 0.35 : 0.0
        if (hoverLevel === hoverPulse.to)
            return
        hoverPulse.restart()
    }
    onHoverEnabledChanged: updateHover()
    onHoveredChanged: updateHover()
    onClickEnabledChanged: {
        if (!clickEnabled) {
            clickPulse.stop()
            clickLevel = 0.0
        }
    }

    function pulseClick() {
        if (!clickEnabled)
            return
        clickPulse.stop()
        glow.clickLevel = 1.0
        clickPulse.restart()
    }

    NumberAnimation {
        id: hoverPulse
        target: glow
        property: "hoverLevel"
        duration: 180
        easing.type: Easing.OutCubic
    }
    NumberAnimation {
        id: clickPulse
        target: glow
        property: "clickLevel"
        to: 0.0
        duration: 420
        easing.type: Easing.OutCubic
    }

    // One analytical hollow glow, no captured source or offscreen blur texture.
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
}
