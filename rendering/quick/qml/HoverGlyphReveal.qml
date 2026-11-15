import QtQuick

// One per card (plan 1D.12 B): the shared dwell fade of the card's hover glyph set (Show Glyphs). Every glyph of the
// card multiplies its own hover opacity by `level`; nothing else owns a glyph's dwell.
//
// It copies Now Playing's Show On Hover feel (ExpandedOverlaySlot.qml: fade in 800 ms, hold 3000 ms, fade out
// 1400 ms, InOutSine; a resting pointer holds it at full). The card's hover edge reveals the set from wherever it
// is; after the hold with no glyph under the pointer the set fades out slowly while the card stays hovered. The
// pointer over any glyph fades the whole set back in and holds it while a glyph is hovered; leaving that glyph runs
// the hold and fade-out again. Leaving the card stops the cycle and keeps `level` where it is: each glyph's own
// hover fade takes it out, as before. A glyph's hit area never depends on `level`, so a faded glyph stays live.
//
// Edge-started finite animation only: no Timer, no polling. Once the fade-out ends, or while a glyph holds the set,
// nothing runs.
Item {
    id: reveal
    visible: false
    width: 0
    height: 0

    // The card is hovered (its passive HoverHandler) with its glyph set admitted.
    property bool cardHovered: false
    // The pointer is over one of the card's glyphs.
    property bool glyphHovered: false
    property int fadeInMs: 800
    property int holdMs: 3000
    property int fadeOutMs: 1400
    // The multiplier every glyph of the card applies to its own hover opacity.
    property real level: 1.0
    // True only while the one finite cycle runs (fade in, hold, fade out).
    readonly property bool animating: cycle.running

    onCardHoveredChanged: {
        if (cardHovered)
            _show()
        else
            cycle.stop()
    }
    onGlyphHoveredChanged: {
        if (cardHovered)
            _show()
    }

    function _show() {
        cycle.stop()
        const holds = glyphHovered
        fadeIn.duration = Math.round(fadeInMs * (1.0 - Math.max(0.0, Math.min(1.0, level))))
        hold.duration = holds ? 0 : holdMs
        fadeOut.to = holds ? 1.0 : 0.0
        fadeOut.duration = holds ? 0 : fadeOutMs
        cycle.start()
    }

    SequentialAnimation {
        id: cycle
        NumberAnimation { id: fadeIn; target: reveal; property: "level"; to: 1.0; easing.type: Easing.InOutSine }
        PauseAnimation { id: hold }
        NumberAnimation { id: fadeOut; target: reveal; property: "level"; easing.type: Easing.InOutSine }
    }
}
