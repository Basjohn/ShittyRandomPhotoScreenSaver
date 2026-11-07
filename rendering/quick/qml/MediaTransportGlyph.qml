import QtQuick

// One Media transport glyph (previous, next, play, pause) drawn as a vector in a square box.
// Every glyph has the same ink height (0.64 of the box plus one stroke) and the same stroke
// weight, and is optically centred in its box, so previous | pause | next read as one set at
// any DPR. Placed centred in its segment by the caller. Replaces the font characters
// ("←", "||", "▶", "→") the controls used since d8a643a4: those took the card's font, whose
// fallback arrows are hairline and sit on the text baseline rather than the segment's centre.
Canvas {
    id: glyph
    objectName: "mediaTransportGlyph"

    // "previous", "next", "play" or "pause".
    property string kind: "pause"
    property color glyphColor: "white"
    // One stroke weight for the whole set (logical px).
    readonly property real strokeWidth: Math.max(2.0, width * 0.13)
    // Ink extents in this box (logical px), shared by every kind.
    readonly property real inkHeight: width * 0.64 + strokeWidth
    readonly property real inkWidth: kind === "pause" ? width * 0.44 + strokeWidth
        : kind === "play" ? width * 0.56 + strokeWidth : width * 0.76 + strokeWidth

    width: 16
    height: width
    antialiasing: true
    onKindChanged: requestPaint()
    onGlyphColorChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var context = getContext("2d")
        context.reset()
        var s = width
        var w = strokeWidth
        context.strokeStyle = glyphColor
        context.fillStyle = glyphColor
        context.lineWidth = w
        context.lineCap = "round"
        context.lineJoin = "round"
        var top = s * 0.18
        var bottom = s * 0.82
        var mid = s * 0.5
        if (kind === "previous" || kind === "next") {
            var tip = kind === "previous" ? s * 0.12 : s * 0.88
            var tail = kind === "previous" ? s * 0.88 : s * 0.12
            var barb = kind === "previous" ? tip + s * 0.32 : tip - s * 0.32
            context.beginPath()
            context.moveTo(tail, mid)
            context.lineTo(tip, mid)
            context.moveTo(barb, top)
            context.lineTo(tip, mid)
            context.lineTo(barb, bottom)
            context.stroke()
        } else if (kind === "play") {
            // Centred between its box and its centroid, so it does not sit left.
            context.beginPath()
            context.moveTo(s * 0.24, top)
            context.lineTo(s * 0.80, mid)
            context.lineTo(s * 0.24, bottom)
            context.closePath()
            context.fill()
            context.stroke()
        } else {
            // Pause: two bars of one stroke-and-a-half each, ink ends rounded like the arrows.
            var bar = w * 1.5
            var gap = s * 0.44 + w - 2.0 * bar
            var left = (s - (2.0 * bar + gap)) / 2.0
            // The wider round caps reach (bar - w) / 2 further: pull the ends in by that much
            // so the ink height matches the arrows'.
            var trim = (bar - w) / 2.0
            context.lineWidth = bar
            context.beginPath()
            context.moveTo(left + bar / 2.0, top + trim)
            context.lineTo(left + bar / 2.0, bottom - trim)
            context.moveTo(left + bar * 1.5 + gap, top + trim)
            context.lineTo(left + bar * 1.5 + gap, bottom - trim)
            context.stroke()
        }
    }
}
