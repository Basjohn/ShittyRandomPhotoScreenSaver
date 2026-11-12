import QtQuick

// One full-display overlay (plan 01 §G, M3b): its placement in the expanded card's safe area, its event-driven
// visibility and its optional themed card. The content (the preset toast's line, Now Playing's artwork and text) is
// the caller's, as children; the caller sets naturalWidth/naturalHeight from it and swaps it on swapContent().
//
// Visibility is one-shot from an event: reveal() runs one finite animation (fade in, hold, fade out; Always Show
// holds at full) and a newer event restarts it from where it is (latest wins). An overlay already showing swaps its
// content by fading the content out, swapping while it is invisible and fading it back in (the overlay and its card
// stay up: nothing pops). conceal() fades it out. No Timer, no polling, nothing per frame at rest: once the fade ends
// the item is invisible and nothing runs.
//
// Fullscreen Edit (M3c): while the stage is editing, a revealed overlay holds (as if Always Show) so it can be grabbed,
// its size and stacking follow at once (no easing that would lag the Edit frame), the OSD does not push it aside, and
// every geometry change is reported to the stage (Python re-reads the Edit frames from it). endEdit() returns it to
// its authored visibility with a fade.
Item {
    id: slot

    // The overlay stage (ExpandedVisualizerOverlays.qml): safe area, reserves, chrome, OSD test.
    property Item stage: null
    // This overlay's options: corner, alwaysShow, card, offsetX, offsetY, scale, textWidth, textHeight (Settings'
    // canonical values).
    property var options: ({})
    property string defaultCorner: "top_left"
    property int fadeInMs: 800
    property int holdMs: 3000
    property int fadeOutMs: 1400
    property int swapOutMs: 450
    property int swapInMs: 600
    property real naturalWidth: 0
    property real naturalHeight: 0
    default property alias content: body.data
    signal swapContent()

    readonly property var corners: ["top_left", "top_right", "bottom_left", "bottom_right"]
    readonly property string corner: corners.indexOf(String(options.corner)) >= 0 ? String(options.corner)
                                                                                 : defaultCorner
    readonly property bool alwaysShow: options.alwaysShow === true
    readonly property bool editing: stage ? stage.editing === true : false
    // The pointer rests where the overlay is placed (Now Playing's Show On Hover; the stage's HoverHandler edges set
    // it through hoverEnter/hoverExit).
    property bool hoverHeld: false
    // Holds at full once revealed: Always Show, Fullscreen Edit, or the pointer resting on it.
    readonly property bool holding: alwaysShow || editing || hoverHeld
    readonly property bool cardOn: options.card === true
    readonly property real unit: {
        const value = Number(options.scale)
        return isFinite(value) && value > 0 ? Math.max(0.5, Math.min(3.0, value)) : 1.0
    }
    readonly property real offsetX: isFinite(Number(options.offsetX)) ? Number(options.offsetX) : 0.0
    readonly property real offsetY: isFinite(Number(options.offsetY)) ? Number(options.offsetY) : 0.0
    readonly property bool rightSide: corner === "top_right" || corner === "bottom_right"
    readonly property bool bottomSide: corner === "bottom_left" || corner === "bottom_right"
    readonly property real fontSize: stage ? stage.fontSize * unit : 30.0
    // Text on the overlay's own card reads like a widget card's (the theme's card text); on the bare Visualizer it is
    // white (operator, 8 Nov).
    readonly property color textColor: cardOn && stage ? stage.cardTextColor : "#ffffffff"
    readonly property real padding: cardOn && stage ? Math.round(fontSize * 0.5) + stage.cardBorderWidth : 0.0
    // The widest an overlay grows: under half the safe area, so a left and a right overlay never meet and a left one
    // never reaches the right-hand controls.
    readonly property real maxContentWidth: stage ? Math.max(48.0, stage.safeWidth * 0.45 - 2.0 * padding) : 48.0

    // The parent's box extents in ems of this overlay's font (zero = natural size), set by its Fullscreen Edit side
    // handles: the preset toast's text box; Now Playing's block (its caller reads them: its height, and its width beyond
    // the natural artwork column; plan 1C.3). The box may use the safe area.
    readonly property real setTextWidth: {
        const value = Number(options.textWidth)
        return isFinite(value) && value > 0 ? value * fontSize : 0.0
    }
    readonly property real setTextHeight: {
        const value = Number(options.textHeight)
        return isFinite(value) && value > 0 ? value * fontSize : 0.0
    }
    readonly property real maxBoxWidth: stage ? Math.max(1.0, stage.safeWidth - 2.0 * padding) : 1.0
    readonly property real maxBoxHeight: stage ? Math.max(1.0, stage.safeHeight - 2.0 * padding) : 1.0
    // The narrowest a set text width draws (a word's start and its ellipsis).
    readonly property real minimumTextWidth: Math.round(fontSize * 2.5)

    // ---------------------------------------------------------------------------------------------- placement
    // The frame follows the content's size; on a visible card it eases to a new size behind a content swap.
    property real frameWidth: naturalWidth + 2.0 * padding
    property real frameHeight: naturalHeight + 2.0 * padding
    Behavior on frameWidth { enabled: slot.cardOn && slot.presence > 0.0 && !slot.editing
        NumberAnimation { duration: slot.resizeMs; easing.type: Easing.InOutSine } }
    Behavior on frameHeight { enabled: slot.cardOn && slot.presence > 0.0 && !slot.editing
        NumberAnimation { duration: slot.resizeMs; easing.type: Easing.InOutSine } }
    property int resizeMs: 380
    width: frameWidth
    height: frameHeight

    // Distance from the corner's edge an older overlay in the same corner keeps for a newer one (the stage sets it).
    property real stackShift: 0.0
    Behavior on stackShift { enabled: slot.presence > 0.0 && !slot.editing
        NumberAnimation { duration: slot.stackGlideMs; easing.type: Easing.InOutSine } }
    property int stackGlideMs: 650

    // Right-hand corners anchor clear of the card's controls (the collapse glyph and 3D hints above, Reset Camera,
    // the preset steps and their tips below). The anchor is the corner's; the offset (Fullscreen Edit) moves the
    // overlay from it within the safe area.
    readonly property real cornerTop: stage ? (rightSide ? Math.max(stage.safeInset, stage.topRightReserve)
                                                         : stage.safeInset) : 0.0
    readonly property real cornerBottom: stage ? (rightSide ? Math.max(stage.safeInset, stage.bottomRightReserve)
                                                            : stage.safeInset) : 0.0
    readonly property real anchoredX: stage ? (rightSide ? stage.width - stage.safeInset - width : stage.safeInset)
                                            : 0.0
    readonly property real anchoredY: stage ? (bottomSide ? stage.height - cornerBottom - height - stackShift
                                                          : cornerTop + stackShift) : 0.0
    function clamp(value, low, high) { return Math.max(low, Math.min(Math.max(low, high), value)) }
    x: stage ? clamp(anchoredX + offsetX * stage.safeWidth, stage.safeInset,
                     stage.width - stage.safeInset - width) : 0.0
    // Wherever an overlay reaches into the column of the card's right-hand controls (from any corner), it keeps
    // clear of them vertically: no overlay ever sits under the collapse glyph, Reset Camera or the preset steps.
    readonly property bool reachesControls: stage ? x + width > stage.rightControlsLeft : false
    readonly property real topBound: stage ? (reachesControls ? Math.max(stage.safeInset, stage.topRightReserve)
                                                              : stage.safeInset) : 0.0
    readonly property real bottomBound: stage ? (reachesControls ? Math.max(stage.safeInset, stage.bottomRightReserve)
                                                                 : stage.safeInset) : 0.0
    y: stage ? clamp(anchoredY + offsetY * stage.safeHeight, topBound,
                     stage.height - bottomBound - height) : 0.0
    onXChanged: if (editing) stage.noteEditGeometry()
    onYChanged: if (editing) stage.noteEditGeometry()
    onWidthChanged: if (editing) stage.noteEditGeometry()
    onHeightChanged: if (editing) stage.noteEditGeometry()

    // --------------------------------------------------------------------------------------------- visibility
    property real presence: 0.0
    property real contentOpacity: 1.0
    // An actual track/preset event crossfades content; a replay/hover must never swap unchanged artwork.
    property bool swapOnCycle: true
    // Holds this overlay's place in its corner from its reveal until its fade-out ends.
    property bool shown: false
    // Appearance order (a newer overlay sits nearer the corner's edge); set when it appears, not on a content swap.
    property int order: 0
    // The OSD keeps priority: an overlay under a showing OSD steps aside (fades) until it hides (not in Fullscreen
    // Edit, where it stays to be grabbed).
    readonly property bool osdBlocked: stage && !editing ? stage.osdCovers(slot) : false
    property real osdYield: osdBlocked ? 0.0 : 1.0
    Behavior on osdYield { NumberAnimation { duration: 350; easing.type: Easing.InOutSine } }
    opacity: presence * osdYield
    visible: opacity > 0.0
    // Its controls take input only while it is plainly there.
    readonly property bool interactive: presence > 0.6 && osdYield > 0.6 && !!stage && stage.inputAdmitted

    function reveal() {
        editPresenceFade.stop()
        editContentFade.stop()
        cycle.stop()
        hideAnimation.stop()
        swapOnCycle = true
        swapOut.to = 0.0
        // Read the stage, not the derived binding: an edit edge reveals from the stage's own handler, possibly before
        // this slot's ``editing`` binding has re-evaluated.
        const holding = alwaysShow || hoverHeld || (!!stage && stage.editing === true)
        const showing = presence > 0.001
        if (!showing) {
            order = stage ? stage.nextRevealOrder() : order + 1
        }
        shown = true
        // A hidden overlay whose corner holds a showing one waits while that one makes room.
        const makeRoom = !showing && !!stage && stage.cornerPeerShowing(slot)
        swapOut.duration = showing ? Math.round(swapOutMs * contentOpacity) : 0
        settle.duration = showing && cardOn ? resizeMs : (makeRoom ? stackGlideMs : 0)
        fadeIn.duration = Math.round(fadeInMs * (1.0 - Math.min(1.0, presence)))
        contentIn.duration = showing ? swapInMs : 0
        hold.duration = holding ? 0 : holdMs
        fadeOut.to = holding ? 1.0 : 0.0
        fadeOut.duration = holding ? 0 : fadeOutMs
        cycle.start()
    }

    // Fullscreen Edit is a visibility hold, NOT a new track or preset event.  Re-running reveal()
    // would fade the already-visible artwork to zero through swapOut and then fade it back in.
    // Keep its latched content and current opacity when it is already showing; complete a partial fade
    // without resetting it. A hidden or stale overlay still uses the normal reveal to latch its content.
    function holdForEdit(needsContentSwap) {
        if (presence <= 0.001 || !shown || needsContentSwap) {
            reveal()
            return
        }
        cycle.stop()
        hideAnimation.stop()
        editPresenceFade.stop()
        editContentFade.stop()
        shown = true
        if (presence < 1.0) {
            editPresenceFade.duration = Math.max(1, Math.round(fadeInMs * (1.0 - presence)))
            editPresenceFade.start()
        }
        if (contentOpacity < 1.0) {
            editContentFade.duration = Math.max(1, Math.round(swapInMs * (1.0 - contentOpacity)))
            editContentFade.start()
        }
    }

    // Playback resumed: show again like an event, without swapping the (unchanged) content. An overlay already up
    // keeps showing: Always Show is untouched, a showing one just holds its window again from now.
    function resume() {
        if (holding && presence > 0.001)
            return
        _showAgain()
    }

    // Show Again from where it is, without swapping the content: the reveal's own one finite cycle (fade in, hold,
    // fade out), holding at full instead while something holds it (Always Show, Edit, the pointer resting on it).
    function _showAgain() {
        editPresenceFade.stop()
        editContentFade.stop()
        cycle.stop()
        hideAnimation.stop()
        const showing = presence > 0.001
        if (!showing) {
            order = stage ? stage.nextRevealOrder() : order + 1
            contentOpacity = 1.0
        }
        shown = true
        swapOnCycle = false
        swapOut.to = contentOpacity  // keep the existing latched art/text; no zero-opacity transition
        const holdsNow = alwaysShow || hoverHeld || (!!stage && stage.editing === true)
        const makeRoom = !showing && !!stage && stage.cornerPeerShowing(slot)
        swapOut.duration = 0
        settle.duration = makeRoom ? stackGlideMs : 0
        fadeIn.duration = Math.round(fadeInMs * (1.0 - Math.min(1.0, presence)))
        contentIn.duration = showing ? Math.round(swapInMs * (1.0 - contentOpacity)) : 0
        hold.duration = holdsNow ? 0 : holdMs
        fadeOut.to = holdsNow ? 1.0 : 0.0
        fadeOut.duration = holdsNow ? 0 : fadeOutMs
        cycle.start()
    }

    // Show On Hover (Now Playing, operator 8 Nov): the pointer arrived where the overlay is placed (the stage's
    // HoverHandler edge; never while editing). It fades back in from wherever it is and holds while the pointer rests.
    // Always Show is untouched.
    function hoverEnter() {
        if (hoverHeld)
            return
        hoverHeld = true
        if (alwaysShow)
            return
        _showAgain()
    }

    // The pointer left: from where it is, the reveal's own rest of the fade-in, hold and fade-out (the same window as
    // after a track change).
    // ``hasContent`` false (the track went): conceal() already fades it; nothing else runs.
    function hoverExit(hasContent) {
        if (!hoverHeld)
            return
        hoverHeld = false
        if (alwaysShow || !hasContent || !shown || (!!stage && stage.editing === true))
            return
        _showAgain()
    }

    // Fullscreen Edit ended: back to the authored visibility. Always Show (with content) stays; under a resting
    // pointer (Show On Hover) it holds as hovered; anything else fades.
    function endEdit(hasContent) {
        if (alwaysShow && hasContent)
            return
        if (hoverHeld && hasContent) {
            _showAgain()
            return
        }
        conceal()
    }

    function conceal() {
        editPresenceFade.stop()
        editContentFade.stop()
        cycle.stop()
        if (presence <= 0.0) {
            shown = false
            return
        }
        hideAnimation.duration = Math.max(1, Math.round(fadeOutMs * presence))
        hideAnimation.start()
    }

    function _swap() {
        if (presence <= 0.001)
            contentOpacity = 1.0      // an appearing overlay fades in whole; only a showing one fades its content
        swapContent()
    }

    function _settled() {
        if (presence <= 0.0)
            shown = false
    }

    NumberAnimation {
        id: editPresenceFade
        target: slot
        property: "presence"
        to: 1.0
        easing.type: Easing.InOutSine
    }
    NumberAnimation {
        id: editContentFade
        target: slot
        property: "contentOpacity"
        to: 1.0
        easing.type: Easing.InOutSine
    }

    SequentialAnimation {
        id: cycle
        NumberAnimation { id: swapOut; target: slot; property: "contentOpacity"; to: 0.0
            easing.type: Easing.InOutSine }
        ScriptAction { script: { if (slot.swapOnCycle) slot._swap() } }
        PauseAnimation { id: settle }
        ParallelAnimation {
            NumberAnimation { id: fadeIn; target: slot; property: "presence"; to: 1.0
                easing.type: Easing.InOutSine }
            NumberAnimation { id: contentIn; target: slot; property: "contentOpacity"; to: 1.0
                easing.type: Easing.InOutSine }
        }
        PauseAnimation { id: hold }
        NumberAnimation { id: fadeOut; target: slot; property: "presence"; easing.type: Easing.InOutSine }
        ScriptAction { script: slot._settled() }
    }

    NumberAnimation {
        id: hideAnimation
        target: slot
        property: "presence"
        to: 0.0
        easing.type: Easing.InOutSine
        onFinished: slot._settled()
    }

    // ------------------------------------------------------------------------------------------- the card
    // Optional (Card, default off): the widget cards' own card (OverlayCard: the themed border colour, the shared
    // border width, the card radius and the active Widget Theme's surface material), wrapping the whole overlay.
    Loader {
        id: cardLoader
        objectName: "expandedOverlayCard"
        anchors.fill: parent
        active: slot.cardOn && !!slot.stage
        z: 0
        sourceComponent: OverlayCard {
            shellEnabled: true
            padding: 0.0
            backgroundColor: slot.stage.cardColor
            borderColor: slot.stage.borderColor
            borderWidth: slot.stage.cardBorderWidth
            cornerRadius: slot.stage.cornerRadius
            surfaceMaterial: slot.stage.surfaceMaterial
            surfaceBackdrop: slot.stage.surfaceBackdrop
            surfaceTextColor: slot.textColor
            shadowEnabled: slot.stage.cardShadowEnabled
            shadowColor: slot.stage.cardShadowColor
            shadowBlur: slot.stage.cardShadowBlur
            shadowOffsetX: slot.stage.cardShadowOffsetX
            shadowOffsetY: slot.stage.cardShadowOffsetY
        }
    }

    Item {
        id: body
        objectName: "expandedOverlayContent"
        // Anchored to the corner's sides, so a card easing to a new size never moves the content.
        x: slot.rightSide ? slot.width - slot.padding - slot.naturalWidth : slot.padding
        y: slot.bottomSide ? slot.height - slot.padding - slot.naturalHeight : slot.padding
        width: slot.naturalWidth
        height: slot.naturalHeight
        opacity: slot.contentOpacity
        z: 1
        // ShadowedText looks up its card's material here: on a material card the card's legibility panel carries the
        // contrast and the text drops its soft halo, as on every widget card.
        readonly property bool surfaceMaterialActive: cardLoader.item ? cardLoader.item.surfaceMaterialActive : false
    }
}
