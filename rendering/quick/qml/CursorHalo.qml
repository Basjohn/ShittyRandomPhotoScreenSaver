import QtQuick

Item {
    id: haloRoot
    objectName: "cursorHalo"

    required property bool haloEnabled
    required property bool pointerActive
    required property real pointerX
    required property real pointerY
    required property string haloShape
    property bool motionVisible: false

    function notePointerMotion() {
        if (!haloEnabled || !pointerActive)
            return
        motionVisible = true
        inactivityTimer.restart()
    }

    function hideForInactivity() {
        motionVisible = false
        inactivityTimer.stop()
    }

    readonly property bool pointerShape: haloShape === "cursor_light"
        || haloShape === "cursor_dark"
    readonly property real pointerScale: Math.min(
        (width - 8.0) / 106.3,
        (height - 8.0) / 141.62
    )
    readonly property real pointerWidth: 106.3 * pointerScale
    readonly property real pointerHeight: 141.62 * pointerScale
    readonly property real anchorOffsetX: pointerShape
        ? ((5.0 / 106.3) - 0.5) * pointerWidth
        : 0.0
    readonly property real anchorOffsetY: pointerShape
        ? ((3.42 / 141.62) - 0.5) * pointerHeight
        : 0.0

    width: 38
    height: 38
    x: pointerX - width / 2.0 - anchorOffsetX
    y: pointerY - height / 2.0 - anchorOffsetY
    opacity: haloEnabled && pointerActive && motionVisible ? 1.0 : 0.0
    visible: opacity > 0.001 || (haloEnabled && pointerActive && motionVisible)
    enabled: false

    Behavior on opacity {
        // Semantic suppression (context menu / interaction exit) must not
        // leave a fading second cursor beside the native pointer.  The long
        // fade remains only for ordinary motion inactivity while admitted.
        enabled: haloRoot.haloEnabled
        NumberAnimation {
            duration: (haloRoot.haloEnabled && haloRoot.motionVisible) ? 600 : 1200
            easing.type: Easing.OutQuad
        }
    }

    Timer {
        id: inactivityTimer
        interval: 2000
        repeat: false
        onTriggered: haloRoot.motionVisible = false
    }

    onPointerXChanged: notePointerMotion()
    onPointerYChanged: notePointerMotion()
    onPointerActiveChanged: {
        if (pointerActive)
            notePointerMotion()
        else
            hideForInactivity()
    }
    onHaloEnabledChanged: {
        if (!haloEnabled)
            hideForInactivity()
    }

    Canvas {
        id: haloCanvas
        objectName: "cursorHaloCanvas"
        anchors.fill: parent
        antialiasing: true

        function polygon(context, points, fill, stroke, lineWidth) {
            context.beginPath()
            context.moveTo(points[0][0], points[0][1])
            for (var i = 1; i < points.length; ++i)
                context.lineTo(points[i][0], points[i][1])
            context.closePath()
            if (fill.length > 0) {
                context.fillStyle = fill
                context.fill()
            }
            if (stroke.length > 0) {
                context.strokeStyle = stroke
                context.lineWidth = lineWidth
                context.lineJoin = "miter"
                context.stroke()
            }
        }

        function project(points, left, top, projectedWidth, projectedHeight) {
            var projected = []
            for (var i = 0; i < points.length; ++i) {
                projected.push([
                    left + points[i][0] * projectedWidth,
                    top + points[i][1] * projectedHeight
                ])
            }
            return projected
        }

        onPaint: {
            var context = getContext("2d")
            context.reset()
            var centerX = width / 2.0
            var centerY = height / 2.0
            var diameter = Math.min(width, height) - 8.0
            var radius = diameter / 2.0
            var shape = haloRoot.haloShape

            function strokeCircle(lineWidth, color) {
                context.beginPath()
                context.arc(centerX, centerY, radius, 0.0, Math.PI * 2.0)
                context.lineWidth = lineWidth
                context.strokeStyle = color
                context.stroke()
            }

            function centerDot(dotRadius) {
                var dot = context.createRadialGradient(
                    centerX, centerY, 0.0,
                    centerX, centerY, dotRadius
                )
                dot.addColorStop(0.0, "rgba(255,255,255,0.94)")
                dot.addColorStop(1.0, "rgba(130,205,255,0.78)")
                context.fillStyle = dot
                context.beginPath()
                context.arc(centerX, centerY, dotRadius, 0.0, Math.PI * 2.0)
                context.fill()
            }

            if (shape === "cursor_light" || shape === "cursor_dark") {
                var projectedWidth = haloRoot.pointerWidth
                var projectedHeight = haloRoot.pointerHeight
                var left = centerX - projectedWidth / 2.0
                var top = centerY - projectedHeight / 2.0
                var shadow = [
                    [17.13 / 106.3, 8.38 / 141.62],
                    [14.07 / 106.3, 137.38 / 141.62],
                    [13.84 / 106.3, 141.59 / 141.62],
                    [57.0 / 106.3, 94.22 / 141.62],
                    [1.0, 93.0 / 141.62]
                ]
                var main = [
                    [5.0 / 106.3, 3.42 / 141.62],
                    [2.0 / 106.3, 132.45 / 141.62],
                    [1.77 / 106.3, 136.66 / 141.62],
                    [44.91 / 106.3, 89.26 / 141.62],
                    [94.22 / 106.3, 88.08 / 141.62]
                ]
                polygon(
                    context,
                    project(shadow, left, top, projectedWidth, projectedHeight),
                    "rgba(0,0,0,0.60)",
                    "",
                    0.0
                )
                var dark = shape === "cursor_dark"
                polygon(
                    context,
                    project(main, left, top, projectedWidth, projectedHeight),
                    dark ? "#000000" : "#fcfcfc",
                    dark ? "#fcfcfc" : "#000000",
                    Math.max(1.0, haloRoot.pointerScale * 3.0)
                )
                return
            }

            if (shape === "crosshair") {
                context.lineCap = "round"
                context.lineWidth = 3.0
                var gap = Math.max(3.0, diameter / 8.0)
                var half = diameter / 2.0
                var segments = [
                    [centerX - half, centerY, centerX - gap, centerY],
                    [centerX + gap, centerY, centerX + half, centerY],
                    [centerX, centerY - half, centerX, centerY - gap],
                    [centerX, centerY + gap, centerX, centerY + half]
                ]
                for (var pass = 0; pass < 2; ++pass) {
                    var offset = pass === 0 ? 2.0 : 0.0
                    context.strokeStyle = pass === 0
                        ? "rgba(12,14,28,0.63)"
                        : "rgba(246,248,255,0.92)"
                    for (var segment = 0; segment < segments.length; ++segment) {
                        context.beginPath()
                        context.moveTo(
                            segments[segment][0] + offset,
                            segments[segment][1] + offset
                        )
                        context.lineTo(
                            segments[segment][2] + offset,
                            segments[segment][3] + offset
                        )
                        context.stroke()
                    }
                }
                return
            }

            if (shape === "diamond") {
                var diamond = [
                    [centerX, centerY - radius],
                    [centerX + radius, centerY],
                    [centerX, centerY + radius],
                    [centerX - radius, centerY]
                ]
                var shadowDiamond = []
                for (var diamondIndex = 0; diamondIndex < diamond.length; ++diamondIndex) {
                    shadowDiamond.push([
                        diamond[diamondIndex][0] + 2.0,
                        diamond[diamondIndex][1] + 2.0
                    ])
                }
                polygon(context, shadowDiamond, "", "rgba(12,14,28,0.63)", 3.0)
                polygon(context, diamond, "", "rgba(246,248,255,0.92)", 3.0)
                centerDot(2.0)
                return
            }

            if (shape === "dot") {
                centerDot(Math.max(4.0, diameter / 6.0))
                return
            }

            var shadowGradient = context.createRadialGradient(
                centerX + 2.0, centerY + 2.0, 0.0,
                centerX + 2.0, centerY + 2.0, radius
            )
            shadowGradient.addColorStop(0.0, "rgba(0,0,0,0.0)")
            shadowGradient.addColorStop(1.0, "rgba(12,14,28,0.63)")
            context.fillStyle = shadowGradient
            context.beginPath()
            context.arc(centerX, centerY, radius, 0.0, Math.PI * 2.0)
            context.fill()
            strokeCircle(shape === "ring" ? 3.0 : 5.0, "rgba(246,248,255,0.92)")
            strokeCircle(3.5, "#ffffff")
            if (shape !== "ring")
                centerDot(Math.max(2.0, diameter / 12.0))
        }

        Component.onCompleted: requestPaint()
    }

    onHaloShapeChanged: haloCanvas.requestPaint()
}
