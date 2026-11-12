import QtQuick
import QtQuick.Effects

Item {
    id: visualizerPresentationRoot
    objectName: "visualizerPresentationRoot"

    property bool presentationActive: false
    property bool customLayoutWorkingVisible: true
    property bool volumeWheelEnabled: true
    // Read-only, item-local projected scene reach for CUSTOM Edit chrome.
    // The retained renderer/CPU reach authority supplies it; it never changes
    // this stage's saved rectangle, snapping or input ownership.
    property var editContentEnvelope: ({ admitted: false })
    // Where the card is drawn (``resolve_card_drawn_rect``, in the loader's parent coordinates: display-local),
    // published by the scene with the loader's geometry so Edit's outline and handles sit on the drawn card. Empty
    // while no record places the card.
    property rect drawnCardRect: Qt.rect(0, 0, 0, 0)
    signal appVolumeStepRequested(int direction)
    property bool cameraResetAvailable: false
    property bool studioGlyphAvailable: false
    property bool contentRotateGlyphAvailable: false
    signal cameraResetRequested()
    // Expanded Visualizer (plan 01 §B1): offered for a capable mode outside Edit; the takeover coordinator
    // publishes both values at its event edges. expandedDisplay turns the glyph into the collapse.
    property bool expandGlyphAvailable: false
    property bool expandedDisplay: false
    signal expandGlyphRequested(bool expand)
    // Full display relative to the Visualizer's display (plan 1B.12, operator 11 Nov): the Up arrow is full display
    // on this display (the Down arrow, its collapse, while expanded); the up-left and up-right arrows are full display
    // on the display to the left and to the right (while expanded they move the view there). The display manager
    // publishes whether a display lies on each side (from the displays' arrangement, never their index) and resolves
    // a side press to a display; only the applicable arrows show.
    property bool expandLeftAvailable: false
    property bool expandRightAvailable: false
    signal expandToSideRequested(int side)
    // This display's arrow, in degrees clockwise from Up (the one place its look is chosen): 0 is the Up arrow; 45
    // would be the up-right arrow (a single-display-only variant: "expandLeftAvailable || expandRightAvailable ? 0 : 45").
    readonly property real expandHereArrowDegrees: 0
    // Each side glyph's place fades in and out (its slot grows and shrinks with it), so the row never jumps.
    property real expandLeftPresence: expandLeftAvailable ? 1.0 : 0.0
    Behavior on expandLeftPresence { NumberAnimation { duration: 600; easing.type: Easing.InOutSine } }
    property real expandRightPresence: expandRightAvailable ? 1.0 : 0.0
    Behavior on expandRightPresence { NumberAnimation { duration: 600; easing.type: Easing.InOutSine } }
    // Which glyph the full-display tip names (-1: up-left, 0: this display, 1: up-right).
    property int expandTipGlyph: 0
    function expandTipText(side) {
        if (side < 0) return "FULL DISPLAY ON THE DISPLAY TO THE LEFT"
        if (side > 0) return "FULL DISPLAY ON THE DISPLAY TO THE RIGHT"
        if (expandedDisplay) return "EXIT FULL DISPLAY"
        return (expandLeftAvailable || expandRightAvailable) ? "FULL DISPLAY ON THIS DISPLAY" : "FULL DISPLAY"
    }
    // The full-display arrows' one painter: a 2.0 px round-capped arrow, its shaft the diagonal of a 9 px square,
    // its two 6 px head strokes at 45 degrees, centred and turned ``degrees`` clockwise from Up. The diagonals are
    // exactly this arrow turned by 45 degrees, so the Up and Down arrows are the same family.
    function paintFullDisplayArrow(ctx, size, degrees) {
        const half = 4.5 * Math.SQRT2
        const arm = 3.0 * Math.SQRT2
        ctx.clearRect(0, 0, size, size)
        ctx.save()
        ctx.translate(size / 2, size / 2)
        ctx.rotate(degrees * Math.PI / 180)
        ctx.strokeStyle = "#f2f4f7"
        ctx.lineWidth = 2.0
        ctx.lineCap = "round"
        ctx.lineJoin = "round"
        ctx.beginPath()
        ctx.moveTo(0, half)
        ctx.lineTo(0, -half)
        ctx.moveTo(-arm, -half + arm)
        ctx.lineTo(0, -half)
        ctx.lineTo(arm, -half + arm)
        ctx.stroke()
        ctx.restore()
    }
    // Full-display overlays (plan 01 §G, M3b): the preset toast and Now Playing. The owner sets
    // expandedOverlaysDrawn exactly while the display-wide card is drawn (and the displays are on); otherwise the
    // overlay Loader below is inactive and nothing of them exists. The rest are retained inputs the display manager
    // publishes at its edges (options per generation, the preset's name at activations, the Media model the
    // Visualizer already binds); DisplayScene hands over the OSD lane once.
    property bool expandedOverlaysDrawn: false
    property var expandedOverlayConfig: ({})
    property string expandedOverlayPresetName: ""
    property int expandedOverlayPresetSerial: 0
    property var expandedOverlayMediaModel: null
    property Item expandedOverlayOsdHost: null
    signal expandedOverlayTransportRequested(string key)
    signal expandedOverlaySeekRequested(real fraction)
    // Fullscreen Edit (M3c): the Edit session is open on the overlays; they show to be grabbed and report geometry.
    property bool expandedOverlayEditing: false
    signal expandedOverlayEditGeometryChanged()
    // The bottom-right glyph row (operator, 8 Nov: "the rotate glyph should be on the same line as the bottom right
    // glyphs, heck let's put expansion there too"). One Row (glyphRow below) places every card control of that
    // corner, on the ordinary and the display-wide card alike. Left to right: the preset steps,
    // Studio, Rotate Content, Reset Camera and expand / collapse at the far corner. Edit owns a separate
    // rotation control on its draft card and suppresses these two normal-mode actions.
    // A member takes its place while it is offered (its own availability) and the row skips the rest, so there is
    // never a gap; the shared input admission is the row's, so admission never moves a member and hover only fades.
    // These values are the row's one geometry source: Edit's controls on this card read them too.
    readonly property real glyphSize: 26
    readonly property real glyphSpacing: 5
    readonly property real glyphRowInset: Math.max(12, cardBorderWidth + 6)
    // Worst case: preset steps + Studio + Rotate + camera reset + expand (+ each side glyph offered, counted as its
    // place fades, so the fit eases with it; one display keeps its row exactly). The same one-row fit rule scales it
    // uniformly on narrow cards, rather than clipping or overlapping its glyph hitboxes.
    readonly property real glyphRowSlots: 6 + expandLeftPresence + expandRightPresence
    readonly property real glyphRowFullWidth: glyphRowSlots * glyphSize + (glyphRowSlots - 1) * glyphSpacing
    readonly property real glyphRowScale: Math.max(0.0, Math.min(1.0,
        (width - 2 * glyphRowInset) / glyphRowFullWidth, (height - 2 * glyphRowInset) / glyphSize))
    readonly property real glyphRowRight: width - glyphRowInset
    readonly property real glyphRowBottom: height - glyphRowInset
    readonly property real glyphRowTop: glyphRowBottom - glyphSize * glyphRowScale
    // How far left of glyphRowRight the card's own offered members reach (Edit continues the row left of it).
    readonly property real glyphRowCardWidth: glyphRow.width * glyphRowScale
    // A point of a member (the row's own x) in this card's coordinates.
    function glyphRowPointX(rowX) {
        return glyphRow.x + glyphRow.width + (rowX - glyphRow.width) * glyphRow.scale
    }
    // The left edge of the right-hand controls' column (stable: from the card's size and the tips' text, never from
    // hover or admission), so an overlay moved into it keeps clear of the controls vertically: the widest row (its
    // leftmost step's tip included) and the expand tip below, the 3D hint above.
    TextMetrics {
        id: presetTipMetrics
        font.pixelSize: 11
        font.weight: Font.Medium
        text: "PREVIOUS PRESET"
    }
    // The full-display tip's widest text among the offered glyphs (never the hovered one, so nothing moves on hover).
    TextMetrics {
        id: expandHereTipMetrics
        font: expandTooltipText.font
        text: visualizerPresentationRoot.expandTipText(0)
    }
    TextMetrics {
        id: expandSideTipMetrics
        font: expandTooltipText.font
        text: visualizerPresentationRoot.expandTipText(visualizerPresentationRoot.expandRightAvailable ? 1 : -1)
    }
    readonly property real expandTipWidestWidth: Math.max(expandHereTipMetrics.advanceWidth,
        (expandLeftAvailable || expandRightAvailable) ? expandSideTipMetrics.advanceWidth : 0) + 16
    readonly property real expandedOverlayControlsLeft: Math.min(
        glyphRowRight - expandTipWidestWidth,
        controlHintsAvailable && show3DControlHints
            ? width - controlHintImage.inset - controlHintImage.width : width,
        glyphRowRight - glyphRowFullWidth * glyphRowScale,
        glyphRowRight - (glyphRowFullWidth - glyphSize) * glyphRowScale - (presetTipMetrics.advanceWidth + 18)
    ) - 10.0
    signal presetStepRequested(int direction)
    property real authoredSceneOpacity: 1.0
    property real startupRevealOpacity: 1.0
    property bool cardShellEnabled: true
    property color cardBackgroundColor: "#4c232323"
    property color cardBorderColor: "#ffffffff"
    property real cardBorderWidth: 4.0
    property real cardCornerRadius: 8.0
    property bool cardShadowEnabled: true
    // DisplayScene externalizes the live Visualizer card shadow into the shared
    // widget-shadow underlay so its blur can never paint over another widget.
    // This externalizes only card-shell chrome; freeform 3D scene/object shadows
    // are renderer-owned. Standalone/preview uses keep the local card shadow unless hosted.
    property bool externalCardShadow: false
    property bool widgetGlowAdmitted: false
    property bool alwaysShowGlyphs: true
    property bool show3DControlHints: true
    property bool controlHintsAvailable: false
    readonly property bool controlHintEligible: show3DControlHints && controlHintsAvailable
        && cardShellEnabled && widgetGlowAdmitted && visible && volumeWheelEnabled
    // Keep the same passive observer alive through menu/Ctrl suppression so a
    // visit ends only when the pointer leaves, not when action admission changes.
    readonly property bool controlHintVisitTracking: show3DControlHints && controlHintsAvailable
        && cardShellEnabled && visible && !prepareOnly
    readonly property bool controlHintHovered: controlHintEligible
        && controlHintVisitObserver.item !== null && controlHintVisitObserver.item.insideCard
    property bool controlHintVisitStarted: false
    property real controlHintOpacity: 0.0
    onControlHintVisitTrackingChanged: {
        if (!controlHintVisitTracking) {
            controlHintVisitStarted = false
            controlHintReveal.stop()
            controlHintLeave.stop()
            controlHintOpacity = 0.0
        }
    }
    onControlHintHoveredChanged: {
        if (controlHintHovered && !controlHintVisitStarted) {
            controlHintVisitStarted = true
            controlHintLeave.stop()
            controlHintReveal.restart()
        }
    }
    signal hoverEditGlyphRequested(string action)
    signal displayTransferHoverChanged(string action, bool hovered)
    property bool displayTransferLeftAvailable: false
    property bool displayTransferRightAvailable: false
    property bool widgetGlowOnHover: false
    property bool widgetGlowOnClick: false
    property bool widgetGlowClicked: false
    property real widgetGlowIntensity: 1.0
    property real widgetGlowDistance: 14.0
    property color widgetGlowColor: "transparent"
    property bool widgetGlowJediMode: false
    readonly property bool interactionGlowEligible: cardShellEnabled
    signal jediModeRequested(string trigger)
    onCardShellEnabledChanged: {
        if (!cardShellEnabled)
            widgetGlowClicked = false
    }
    property color cardShadowColor: "#96000000"
    property real cardShadowBlur: 18.0
    property real cardShadowOffsetX: 0.0
    property real cardShadowOffsetY: 4.0
    property real cardShadowSpread: 0.0
    property real cardShadowExtendLeft: 0.0
    property real cardShadowExtendTop: 0.0
    property real cardShadowExtendRight: 0.0
    property real cardShadowExtendBottom: 0.0
    readonly property real cardShadowBaseLeft: Math.max(0.0, -cardShadowOffsetX)
    readonly property real cardShadowBaseTop: Math.max(0.0, -cardShadowOffsetY)
    readonly property real cardShadowBaseRight: Math.max(0.0, cardShadowOffsetX)
    readonly property real cardShadowBaseBottom: Math.max(0.0, cardShadowOffsetY)
    property bool perfHudEnabled: false
    property string perfHudText: ""

    // A display move's target while its renderer prepares (1C.2): drawn at a sub-visible opacity whatever Edit shows
    // on this display, and transparent to input, so a press there reaches what lies below.
    property bool prepareOnly: false
    enabled: !prepareOnly
    opacity: authoredSceneOpacity * startupRevealOpacity
    visible: presentationActive && (customLayoutWorkingVisible || prepareOnly) && opacity > 0.0

    Loader {
        id: visualizerInteractionGlowLoader
        objectName: "visualizerInteractionGlowLoader"
        anchors.fill: parent
        z: 2.8
        active: visualizerPresentationRoot.interactionGlowEligible
            && visualizerPresentationRoot.widgetGlowAdmitted
            && visualizerPresentationRoot.visible
            && visualizerPresentationRoot.widgetGlowIntensity > 0.0
            && (visualizerPresentationRoot.widgetGlowOnHover
                || visualizerPresentationRoot.widgetGlowOnClick)
        sourceComponent: WidgetInteractionGlow {
            hoverEnabled: visualizerPresentationRoot.widgetGlowOnHover
            clickEnabled: visualizerPresentationRoot.widgetGlowOnClick
            hovered: visualizerInteractionHover.hovered
            clicked: visualizerPresentationRoot.widgetGlowClicked
            intensityScale: visualizerPresentationRoot.widgetGlowIntensity
            distancePx: visualizerPresentationRoot.widgetGlowDistance
            glowColor: visualizerPresentationRoot.widgetGlowColor
            cornerRadius: visualizerPresentationRoot.cardCornerRadius
        }
    }

    HoverHandler {
        id: visualizerInteractionHover
        enabled: (visualizerPresentationRoot.interactionGlowEligible
            && visualizerPresentationRoot.widgetGlowOnHover
            && (visualizerInteractionGlowLoader.active
                || (visualizerPresentationRoot.widgetGlowJediMode
                    && visualizerPresentationRoot.widgetGlowAdmitted
                    && visualizerPresentationRoot.visible)))
            || (visualizerPresentationRoot.alwaysShowGlyphs
                && visualizerPresentationRoot.widgetGlowAdmitted
                && visualizerPresentationRoot.visible)
        blocking: false
        onHoveredChanged: {
            if (hovered && visualizerPresentationRoot.widgetGlowOnHover
                    && visualizerPresentationRoot.interactionGlowEligible
                    && visualizerPresentationRoot.widgetGlowJediMode
                    && visualizerPresentationRoot.widgetGlowAdmitted)
                visualizerPresentationRoot.jediModeRequested("hover")
        }
    }

    WheelHandler {
        target: null
        enabled: visualizerPresentationRoot.presentationActive
            && visualizerPresentationRoot.customLayoutWorkingVisible
            && visualizerPresentationRoot.volumeWheelEnabled
        onWheel: function(wheel) {
            if (wheel.angleDelta.y === 0)
                return
            visualizerPresentationRoot.appVolumeStepRequested(
                wheel.angleDelta.y > 0 ? 1 : -1
            )
            wheel.accepted = true
        }
    }

    RectangularShadow {
        id: cardShadow
        x: cardBackground.x
            - visualizerPresentationRoot.cardShadowBaseLeft
            - visualizerPresentationRoot.cardShadowExtendLeft
        y: cardBackground.y
            - visualizerPresentationRoot.cardShadowBaseTop
            - visualizerPresentationRoot.cardShadowExtendTop
        width: cardBackground.width
            + visualizerPresentationRoot.cardShadowBaseLeft
            + visualizerPresentationRoot.cardShadowBaseRight
            + visualizerPresentationRoot.cardShadowExtendLeft
            + visualizerPresentationRoot.cardShadowExtendRight
        height: cardBackground.height
            + visualizerPresentationRoot.cardShadowBaseTop
            + visualizerPresentationRoot.cardShadowBaseBottom
            + visualizerPresentationRoot.cardShadowExtendTop
            + visualizerPresentationRoot.cardShadowExtendBottom
        visible: visualizerPresentationRoot.cardShellEnabled
            && visualizerPresentationRoot.cardShadowEnabled
            && !visualizerPresentationRoot.externalCardShadow
        color: visualizerPresentationRoot.cardShadowColor
        blur: visualizerPresentationRoot.cardShadowBlur
        radius: visualizerPresentationRoot.cardCornerRadius
        spread: visualizerPresentationRoot.cardShadowSpread
        // Card direction is one-sided surface extrusion, never effect
        // translation. This preserves opposite-edge coverage at large Extra
        // Offset values just like the shared ordinary-widget OverlayCard.
        offset: Qt.vector2d(0.0, 0.0)
        cached: true
        z: 0
    }

    // Card surface material (Docs/Architecture/Card_Surface_Materials.md 3.4): the Widget
    // Theme baseline, like every ordinary card. The Visualizer-authored Fill is its tint (its
    // alpha moves the tint within the material's own range), so the glass reads under the
    // mode's pixels. One static quad below the content host: it samples the shared backdrop
    // (captured below z 20, never the Visualizer's pixels) and nothing runs per Visualizer
    // frame. Normal keeps this Loader inactive: no item, no node, the authored fill as before.
    property string cardSurfaceMaterial: "normal"
    property real cardSurfaceOpacityAdjust: 0.0
    property color cardNormalSurfaceColor: cardBackgroundColor
    property var cardSurfaceBackdrop: null
    property color cardSurfaceTextColor: "#ffffffff"
    readonly property bool cardSurfaceMaterialActive: cardShellEnabled
        && cardSurfaceMaterial !== "normal" && cardSurfaceBackdrop !== null

    Loader {
        id: cardSurfaceMaterialLoader
        objectName: "visualizerCardSurfaceMaterial"
        anchors.fill: parent
        active: visualizerPresentationRoot.cardSurfaceMaterialActive
        visible: active
        z: 1
        sourceComponent: MaterialSurface {
            backdrop: visualizerPresentationRoot.cardSurfaceBackdrop
            material: visualizerPresentationRoot.cardSurfaceMaterial
            opacityAdjust: visualizerPresentationRoot.cardSurfaceOpacityAdjust
            cornerRadius: visualizerPresentationRoot.cardCornerRadius
            contentInset: 0.0
            borderWidth: visualizerPresentationRoot.cardBorderWidth
            normalColor: visualizerPresentationRoot.cardBackgroundColor
            tintColor: visualizerPresentationRoot.cardBackgroundColor
            textColor: visualizerPresentationRoot.cardSurfaceTextColor
        }
    }

    Rectangle {
        id: cardBackground
        objectName: "visualizerCardBackground"
        anchors.fill: parent
        visible: visualizerPresentationRoot.cardShellEnabled
            && !visualizerPresentationRoot.cardSurfaceMaterialActive
        color: visualizerPresentationRoot.cardNormalSurfaceColor
        radius: visualizerPresentationRoot.cardCornerRadius
        z: 1
    }

    Item {
        id: visualizerContentHost
        objectName: "visualizerContentHost"
        anchors.fill: parent
        z: 2
    }

    Rectangle {
        id: cardFrame
        objectName: "visualizerCardFrame"
        anchors.fill: parent
        visible: visualizerPresentationRoot.cardShellEnabled
        color: "transparent"
        radius: visualizerPresentationRoot.cardCornerRadius
        border.color: visualizerPresentationRoot.cardBorderColor
        border.width: visualizerPresentationRoot.cardBorderWidth
        z: 3
    }

    // Full-display overlays (plan 01 §G, M3b): above the content and frame, below every control of the card (z 10+),
    // the OSD lane and the context menu. Only text and artwork plus the optional Media Controls: nothing else takes
    // input, so double-click, middle-click, wheel and orbit drags reach the card as before.
    Loader {
        id: expandedOverlayLoader
        objectName: "visualizerExpandedOverlays"
        anchors.fill: parent
        z: 6
        active: visualizerPresentationRoot.expandedOverlaysDrawn && visualizerPresentationRoot.presentationActive
        sourceComponent: ExpandedVisualizerOverlays {
            config: visualizerPresentationRoot.expandedOverlayConfig
            presetName: visualizerPresentationRoot.expandedOverlayPresetName
            presetSerial: visualizerPresentationRoot.expandedOverlayPresetSerial
            mediaModel: visualizerPresentationRoot.expandedOverlayMediaModel
            osdHost: visualizerPresentationRoot.expandedOverlayOsdHost
            revealOpen: visualizerPresentationRoot.startupRevealOpacity > 0.0
            inputAdmitted: visualizerPresentationRoot.widgetGlowAdmitted
                && visualizerPresentationRoot.volumeWheelEnabled
            borderColor: visualizerPresentationRoot.cardBorderColor
            borderWidth: visualizerPresentationRoot.cardBorderWidth
            cornerRadius: visualizerPresentationRoot.cardCornerRadius
            cardColor: visualizerPresentationRoot.cardBackgroundColor
            surfaceMaterial: visualizerPresentationRoot.cardSurfaceMaterial
            surfaceBackdrop: visualizerPresentationRoot.cardSurfaceBackdrop
            cardShadowEnabled: visualizerPresentationRoot.cardShadowEnabled
            cardShadowColor: visualizerPresentationRoot.cardShadowColor
            cardShadowBlur: visualizerPresentationRoot.cardShadowBlur
            cardShadowOffsetX: visualizerPresentationRoot.cardShadowOffsetX
            cardShadowOffsetY: visualizerPresentationRoot.cardShadowOffsetY
            // The card's own controls: the 3D control hint (top right); the glyph row (the preset steps, Edit's
            // Rotate Widget Content, Reset Camera, the collapse glyph) and their tips (bottom right).
            topRightReserve: controlHintImage.y + controlHintImage.height + 10.0
            bottomRightReserve: visualizerPresentationRoot.height
                - Math.min(cameraResetTooltip.y, expandTooltip.y) + 10.0
            rightControlsLeft: visualizerPresentationRoot.expandedOverlayControlsLeft
            editing: visualizerPresentationRoot.expandedOverlayEditing
            onSeekRequested: function(fraction) {
                visualizerPresentationRoot.expandedOverlaySeekRequested(fraction)
            }
            onTransportRequested: function(key) {
                visualizerPresentationRoot.expandedOverlayTransportRequested(key)
            }
            onEditGeometryChanged: visualizerPresentationRoot.expandedOverlayEditGeometryChanged()
        }
    }

    HoverHandler {
        id: cameraResetHover
        enabled: visualizerPresentationRoot.alwaysShowGlyphs
            && visualizerPresentationRoot.widgetGlowAdmitted
        blocking: false
    }

    // One-shot hover animation for the camera reset glyph. No Timer/polling;
    // the first 1008ms are entirely invisible, independent of card hover glow.
    property real cameraResetTipProgress: 0.0
    property string cameraActionTip: "RESET CAMERA"
    property real cameraActionTipX: 0
    onWidgetGlowAdmittedChanged: {
        if (!widgetGlowAdmitted) {
            cameraResetTipReveal.stop()
            cameraResetTipProgress = 0.0
        }
    }
    NumberAnimation {
        id: cameraResetTipReveal
        target: visualizerPresentationRoot
        property: "cameraResetTipProgress"
        from: 0.0
        to: 1.0
        duration: 1800
        easing.type: Easing.Linear
    }

    // Expand / collapse: a vector diagonal arrow at the glyph row's far corner, a distinct semantic action (not an
    // Edit glyph). Same admission and hover fade as Reset Camera; it consumes all of its own presses.
    property real expandTipProgress: 0.0
    NumberAnimation {
        id: expandTipReveal
        target: visualizerPresentationRoot
        property: "expandTipProgress"
        from: 0.0
        to: 1.0
        duration: 1800
        easing.type: Easing.Linear
    }
    Row {
        id: glyphRow
        objectName: "visualizerGlyphRow"
        // Anchored at the card's bottom-right inset; it grows leftwards over its offered members only.
        x: visualizerPresentationRoot.glyphRowRight - width
        y: visualizerPresentationRoot.glyphRowBottom - visualizerPresentationRoot.glyphSize
        spacing: visualizerPresentationRoot.glyphSpacing
        scale: visualizerPresentationRoot.glyphRowScale
        transformOrigin: Item.BottomRight
        z: 12

        // In the row outside Edit (Edit draws its own steps in its continuation of the row).
        Item {
            id: presetSlot
            objectName: "visualizerPresetSlot"
            visible: visualizerPresentationRoot.volumeWheelEnabled
            width: presetControls.width
            height: visualizerPresentationRoot.glyphSize
            Row {
                id: presetControls
                objectName: "visualizerPresetControls"
                spacing: visualizerPresentationRoot.glyphSpacing
                // The shared input admission (widgetGlowAdmitted, the card shown); its slot is its place in the row.
                visible: visualizerPresentationRoot.widgetGlowAdmitted && visualizerPresentationRoot.visible
                opacity: (visualizerPresentationRoot.alwaysShowGlyphs && cameraResetHover.hovered) ? 0.92 : 0.0
                enabled: visible && visualizerPresentationRoot.alwaysShowGlyphs
                    && cameraResetHover.hovered && opacity > 0.05
                Behavior on opacity {
                    NumberAnimation { duration: cameraResetHover.hovered ? 700 : 1200; easing.type: Easing.InOutSine }
                }
                Repeater {
                    model: [-1, 1]
                    delegate: Rectangle {
                        required property int modelData
                        objectName: modelData < 0 ? "visualizerPreviousPresetGlyph" : "visualizerNextPresetGlyph"
                        width: cameraResetGlyph.width
                        height: cameraResetGlyph.height
                        radius: width / 2
                        color: cameraResetGlyph.color
                        border.width: cameraResetGlyph.border.width
                        border.color: cameraResetGlyph.border.color
                        Canvas {
                            anchors.centerIn: parent
                            width: 20
                            height: 20
                            onPaint: {
                                const ctx = getContext("2d")
                                ctx.clearRect(0, 0, width, height)
                                ctx.save()
                                if (modelData < 0) { ctx.translate(20, 0); ctx.scale(-1, 1) }
                                ctx.strokeStyle = "white"
                                ctx.lineWidth = 1.8
                                ctx.lineCap = "round"
                                ctx.lineJoin = "round"
                                ctx.beginPath()
                                ctx.moveTo(4, 10)
                                ctx.lineTo(16, 10)
                                ctx.moveTo(11, 5)
                                ctx.lineTo(16, 10)
                                ctx.lineTo(11, 15)
                                ctx.stroke()
                                ctx.restore()
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            propagateComposedEvents: false
                            onEntered: {
                                visualizerPresentationRoot.cameraActionTip = modelData < 0 ? "PREVIOUS PRESET" : "NEXT PRESET"
                                visualizerPresentationRoot.cameraActionTipX = visualizerPresentationRoot.glyphRowPointX(
                                    presetSlot.x + parent.x + parent.width)
                                cameraResetTipReveal.restart()
                            }
                            onExited: {
                                if (visualizerPresentationRoot.cameraActionTip !== (modelData < 0 ? "PREVIOUS PRESET" : "NEXT PRESET")) return
                                cameraResetTipReveal.stop()
                                visualizerPresentationRoot.cameraResetTipProgress = 0.0
                            }
                            onPressed: function(mouse) { mouse.accepted = true }
                            readonly property bool consumesDoubleClick: true   // QuickDisplayWindow._double_click_owned_by_control
                            onDoubleClicked: function(mouse) { mouse.accepted = true }
                            onClicked: function(mouse) {
                                mouse.accepted = true
                                visualizerPresentationRoot.presetStepRequested(modelData)
                            }
                        }
                    }
                }
            }
        }

        // Normal and expanded modes share the same controls. Studio and Rotate are NOT
        // ordinary-card hover Edit glyphs: those are intentionally absent when expanded.
        Item {
            id: studioActionsSlot
            objectName: "visualizerStudioActionsSlot"
            visible: visualizerPresentationRoot.volumeWheelEnabled
                && visualizerPresentationRoot.widgetGlowAdmitted
                && visualizerPresentationRoot.visible
                && (visualizerPresentationRoot.studioGlyphAvailable
                    || visualizerPresentationRoot.contentRotateGlyphAvailable)
            width: studioActions.width
            height: visualizerPresentationRoot.glyphSize
            Row {
                id: studioActions
                objectName: "visualizerStudioActions"
                spacing: visualizerPresentationRoot.glyphSpacing
                Repeater {
                    model: ["studio", "rotate"]
                    delegate: Rectangle {
                        required property string modelData
                        readonly property string actionKind: modelData
                        readonly property string tipText: actionKind === "studio"
                            ? "OPEN VISUALIZER STUDIO" : "ROTATE WIDGET CONTENT"
                        objectName: actionKind === "studio"
                            ? "visualizerStudioGlyph" : "visualizerRotateGlyph"
                        visible: actionKind === "studio"
                            ? visualizerPresentationRoot.studioGlyphAvailable
                            : visualizerPresentationRoot.contentRotateGlyphAvailable
                        width: visible ? visualizerPresentationRoot.glyphSize : 0
                        height: visualizerPresentationRoot.glyphSize
                        radius: width / 2
                        color: cameraResetGlyph.color
                        border.width: cameraResetGlyph.border.width
                        border.color: cameraResetGlyph.border.color
                        opacity: (visualizerPresentationRoot.alwaysShowGlyphs && cameraResetHover.hovered)
                            ? 0.92 : 0.0
                        enabled: visible && visualizerPresentationRoot.volumeWheelEnabled
                            && visualizerPresentationRoot.widgetGlowAdmitted
                            && visualizerPresentationRoot.alwaysShowGlyphs
                            && cameraResetHover.hovered && opacity > 0.05
                        Behavior on opacity {
                            NumberAnimation { duration: cameraResetHover.hovered ? 700 : 1200;
                                              easing.type: Easing.InOutSine }
                        }
                        Canvas {
                            anchors.centerIn: parent
                            width: 20
                            height: 20
                            readonly property color ink: "#f2f4f7"
                            onInkChanged: requestPaint()
                            onPaint: {
                                const ctx = getContext("2d")
                                ctx.reset()
                                ctx.strokeStyle = ink
                                ctx.lineCap = "square"
                                ctx.lineJoin = "miter"
                                if (modelData === "studio") {
                                    // Smaller, blocky S, five strictly straight strokes. Centre stays (10,10).
                                    ctx.lineWidth = 2.6
                                    ctx.beginPath()
                                    ctx.moveTo(14.3, 5.4)
                                    ctx.lineTo(5.9, 5.4)
                                    ctx.lineTo(5.9, 9.8)
                                    ctx.lineTo(14.1, 9.8)
                                    ctx.lineTo(14.1, 14.6)
                                    ctx.lineTo(5.8, 14.6)
                                    ctx.stroke()
                                } else {
                                    // Reuse Edit's stylized quarter-turn pictogram, centred at 20px.
                                    ctx.lineWidth = 1.65
                                    ctx.strokeRect(4, 9, 7, 8)
                                    ctx.beginPath()
                                    ctx.moveTo(4, 6)
                                    ctx.bezierCurveTo(10, 0, 18, 4, 17, 11)
                                    ctx.moveTo(14, 8)
                                    ctx.lineTo(17, 11)
                                    ctx.lineTo(19, 7)
                                    ctx.stroke()
                                }
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            enabled: parent.enabled
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            propagateComposedEvents: false
                            readonly property bool consumesDoubleClick: true
                            onEntered: {
                                visualizerPresentationRoot.cameraActionTip = tipText
                                visualizerPresentationRoot.cameraActionTipX = visualizerPresentationRoot.glyphRowPointX(
                                    studioActionsSlot.x + parent.x + parent.width)
                                cameraResetTipReveal.restart()
                            }
                            onExited: {
                                if (visualizerPresentationRoot.cameraActionTip !== tipText) return
                                cameraResetTipReveal.stop()
                                visualizerPresentationRoot.cameraResetTipProgress = 0.0
                            }
                            onPressed: function(mouse) { mouse.accepted = true }
                            onDoubleClicked: function(mouse) { mouse.accepted = true }
                            onClicked: function(mouse) {
                                mouse.accepted = true
                                visualizerPresentationRoot.hoverEditGlyphRequested(actionKind)
                            }
                        }
                    }
                }
            }
        }

        // In the row while offered.
        Item {
            id: cameraResetSlot
            objectName: "visualizerCameraResetSlot"
            visible: visualizerPresentationRoot.cameraResetAvailable
            width: visualizerPresentationRoot.glyphSize
            height: visualizerPresentationRoot.glyphSize
            Rectangle {
                id: cameraResetGlyph
                objectName: "visualizerCameraResetGlyph"
                anchors.fill: parent
                radius: width / 2
                color: "#bb20262c"
                border.width: 1
                border.color: "#c2ffffff"
                // The shared input admission (widgetGlowAdmitted, the card shown); its slot is its place in the row.
                visible: visualizerPresentationRoot.widgetGlowAdmitted && visualizerPresentationRoot.visible
                opacity: (visualizerPresentationRoot.alwaysShowGlyphs
                          && cameraResetHover.hovered) ? 0.92 : 0.0
                enabled: visible && visualizerPresentationRoot.alwaysShowGlyphs
                    && cameraResetHover.hovered && opacity > 0.05
                Behavior on opacity {
                    NumberAnimation {
                        duration: cameraResetHover.hovered ? 700 : 1200
                        easing.type: Easing.InOutSine
                    }
                }
                Text {
                    anchors.centerIn: parent
                    text: "↺"
                    color: "white"
                    font.pixelSize: 19
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    propagateComposedEvents: false
                    onEntered: {
                        visualizerPresentationRoot.cameraActionTip = "RESET CAMERA"
                        visualizerPresentationRoot.cameraActionTipX = visualizerPresentationRoot.glyphRowPointX(
                            cameraResetSlot.x + cameraResetSlot.width)
                        cameraResetTipReveal.restart()
                    }
                    onExited: {
                        if (visualizerPresentationRoot.cameraActionTip !== "RESET CAMERA") return
                        cameraResetTipReveal.stop()
                        visualizerPresentationRoot.cameraResetTipProgress = 0.0
                    }
                    onPressed: function(mouse) { mouse.accepted = true }
                    // An in-card control consumes every press of its own, the second press of a double-click
                    // included: it never reaches the card's double-click mode cycle.
                    readonly property bool consumesDoubleClick: true   // QuickDisplayWindow._double_click_owned_by_control
                    onDoubleClicked: function(mouse) { mouse.accepted = true }
                    onClicked: function(mouse) {
                        mouse.accepted = true
                        visualizerPresentationRoot.cameraResetRequested()
                    }
                }
            }
        }

        // In the row while offered: the up-left glyph, this display's glyph, the up-right glyph at the far corner.
        Item {
            id: expandSlot
            objectName: "visualizerExpandSlot"
            visible: visualizerPresentationRoot.expandGlyphAvailable
            // Each side glyph takes its place inside this slot as it fades in, and gives it up as it fades out
            // (plan 1B.12), so the row never jumps by a whole member.
            width: visualizerPresentationRoot.glyphSize
                + (visualizerPresentationRoot.expandLeftPresence + visualizerPresentationRoot.expandRightPresence)
                * (visualizerPresentationRoot.glyphSize + visualizerPresentationRoot.glyphSpacing)
            height: visualizerPresentationRoot.glyphSize
            // This display: the Up arrow (full display here); the Down arrow while expanded (the collapse).
            Rectangle {
                id: expandGlyph
                objectName: "visualizerExpandGlyph"
                x: visualizerPresentationRoot.expandLeftPresence
                    * (visualizerPresentationRoot.glyphSize + visualizerPresentationRoot.glyphSpacing)
                width: visualizerPresentationRoot.glyphSize
                height: visualizerPresentationRoot.glyphSize
                radius: width / 2
                color: "#bb20262c"
                border.width: 1
                border.color: "#c2ffffff"
                // The shared input admission (widgetGlowAdmitted, the card shown); its slot is its place in the row.
                visible: visualizerPresentationRoot.widgetGlowAdmitted && visualizerPresentationRoot.visible
                opacity: (visualizerPresentationRoot.alwaysShowGlyphs
                          && cameraResetHover.hovered) ? 0.92 : 0.0
                enabled: visible && visualizerPresentationRoot.alwaysShowGlyphs
                    && cameraResetHover.hovered && opacity > 0.05
                Behavior on opacity {
                    NumberAnimation {
                        duration: cameraResetHover.hovered ? 700 : 1200
                        easing.type: Easing.InOutSine
                    }
                }
                onEnabledChanged: if (!enabled && visualizerPresentationRoot.expandTipGlyph === 0) {
                    expandTipReveal.stop()
                    visualizerPresentationRoot.expandTipProgress = 0.0
                }
                Canvas {
                    id: expandArrow
                    objectName: "visualizerExpandGlyphArrow"
                    anchors.centerIn: parent
                    width: 18
                    height: 18
                    readonly property bool collapse: visualizerPresentationRoot.expandedDisplay
                    // Collapse is the same arrow turned to point the other way (Up becomes Down).
                    readonly property real degrees: visualizerPresentationRoot.expandHereArrowDegrees + (collapse ? 180 : 0)
                    onDegreesChanged: requestPaint()
                    onPaint: visualizerPresentationRoot.paintFullDisplayArrow(getContext("2d"), width, degrees)
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    propagateComposedEvents: false
                    onEntered: {
                        visualizerPresentationRoot.expandTipGlyph = 0
                        expandTipReveal.restart()
                    }
                    onExited: {
                        if (visualizerPresentationRoot.expandTipGlyph !== 0) return
                        expandTipReveal.stop()
                        visualizerPresentationRoot.expandTipProgress = 0.0
                    }
                    onPressed: function(mouse) { mouse.accepted = true }
                    readonly property bool consumesDoubleClick: true   // QuickDisplayWindow._double_click_owned_by_control
                    onDoubleClicked: function(mouse) { mouse.accepted = true }
                    onClicked: function(mouse) {
                        mouse.accepted = true
                        visualizerPresentationRoot.expandGlyphRequested(!visualizerPresentationRoot.expandedDisplay)
                    }
                }
            }
            // The display to the left (-1) and to the right (+1): the same arrow turned 45 degrees each way, offered
            // only while a display lies on that side. While expanded they move the view there (it stays expanded).
            Repeater {
                model: [-1, 1]
                delegate: Rectangle {
                    id: sideGlyph
                    required property int modelData
                    readonly property int side: modelData
                    readonly property bool offered: side < 0 ? visualizerPresentationRoot.expandLeftAvailable
                                                             : visualizerPresentationRoot.expandRightAvailable
                    readonly property real presence: side < 0 ? visualizerPresentationRoot.expandLeftPresence
                                                              : visualizerPresentationRoot.expandRightPresence
                    objectName: side < 0 ? "visualizerExpandLeftGlyph" : "visualizerExpandRightGlyph"
                    x: side < 0 ? 0 : expandGlyph.x + visualizerPresentationRoot.glyphSize
                        + visualizerPresentationRoot.glyphSpacing
                    width: visualizerPresentationRoot.glyphSize
                    height: visualizerPresentationRoot.glyphSize
                    radius: width / 2
                    color: expandGlyph.color
                    border.width: expandGlyph.border.width
                    border.color: expandGlyph.border.color
                    visible: expandGlyph.visible && presence > 0.0
                    opacity: expandGlyph.opacity * presence
                    enabled: visible && expandGlyph.enabled && offered
                    onEnabledChanged: if (!enabled && visualizerPresentationRoot.expandTipGlyph === side) {
                        expandTipReveal.stop()
                        visualizerPresentationRoot.expandTipProgress = 0.0
                    }
                    Canvas {
                        objectName: sideGlyph.side < 0 ? "visualizerExpandLeftGlyphArrow" : "visualizerExpandRightGlyphArrow"
                        anchors.centerIn: parent
                        width: 18
                        height: 18
                        readonly property real degrees: 45 * sideGlyph.side
                        onPaint: visualizerPresentationRoot.paintFullDisplayArrow(getContext("2d"), width, degrees)
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: sideGlyph.enabled
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        propagateComposedEvents: false
                        onEntered: {
                            visualizerPresentationRoot.expandTipGlyph = sideGlyph.side
                            expandTipReveal.restart()
                        }
                        onExited: {
                            if (visualizerPresentationRoot.expandTipGlyph !== sideGlyph.side) return
                            expandTipReveal.stop()
                            visualizerPresentationRoot.expandTipProgress = 0.0
                        }
                        onPressed: function(mouse) { mouse.accepted = true }
                        readonly property bool consumesDoubleClick: true   // QuickDisplayWindow._double_click_owned_by_control
                        onDoubleClicked: function(mouse) { mouse.accepted = true }
                        onClicked: function(mouse) {
                            mouse.accepted = true
                            visualizerPresentationRoot.expandToSideRequested(sideGlyph.side)
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        id: expandTooltip
        objectName: "visualizerExpandTooltip"
        visible: expandGlyph.visible && opacity > 0.0
        opacity: Math.max(0.0, Math.min(1.0,
            (visualizerPresentationRoot.expandTipProgress - 0.56) / 0.44))
        width: expandTooltipText.implicitWidth + 16
        height: expandTooltipText.implicitHeight + 8
        // Above the row like the other tips, its right edge on the hovered glyph's (up-left at the slot's start,
        // this display's glyph after it, up-right after that).
        readonly property real namedGlyphRight: visualizerPresentationRoot.glyphSize
            + (visualizerPresentationRoot.expandTipGlyph < 0 ? 0.0 : expandGlyph.x)
            + (visualizerPresentationRoot.expandTipGlyph > 0
               ? visualizerPresentationRoot.glyphSize + visualizerPresentationRoot.glyphSpacing : 0.0)
        x: Math.max(3, visualizerPresentationRoot.glyphRowPointX(expandSlot.x + namedGlyphRight) - width)
        y: Math.max(3, visualizerPresentationRoot.glyphRowTop - height - 7)
        radius: 4
        z: 13
        enabled: false
        color: "#e61b1e23"
        border.width: 1
        border.color: "#bdc38e88"
        Text {
            id: expandTooltipText
            anchors.centerIn: parent
            // What the glyph does relative to the Visualizer's display (never a display number).
            text: visualizerPresentationRoot.expandTipText(visualizerPresentationRoot.expandTipGlyph)
            color: "#f6f6f8"
            font.pixelSize: 11
            font.weight: Font.Medium
        }
    }

    Rectangle {
        id: cameraResetTooltip
        objectName: "visualizerPresetTooltip"
        z: 14
        enabled: false
        visible: visualizerPresentationRoot.widgetGlowAdmitted && opacity > 0.0
            && (presetControls.enabled || studioActionsSlot.visible || cameraResetGlyph.enabled)
        opacity: Math.max(0.0, Math.min(1.0,
            (visualizerPresentationRoot.cameraResetTipProgress - 0.56) / 0.44))
        width: resetTooltipText.implicitWidth + 18
        height: resetTooltipText.implicitHeight + 12
        x: Math.max(6, visualizerPresentationRoot.cameraActionTipX - width)
        y: Math.max(3, visualizerPresentationRoot.glyphRowTop - height - 7)
        radius: 7
        color: "#e51d2634"
        border.width: 1
        border.color: "#bdc38e88"
        Text {
            id: resetTooltipText
            anchors.centerIn: parent
            text: visualizerPresentationRoot.cameraActionTip
            color: "#f6f6f8"
            font.pixelSize: 11
            font.weight: Font.Medium
        }
    }

    Loader {
        objectName: "visualizerHoverGlyphLoader"
        anchors.fill: parent
        z: 11
        // Edit glyphs edit the ordinary card; a display-wide view offers none of them.
        active: visualizerPresentationRoot.alwaysShowGlyphs
            && visualizerPresentationRoot.widgetGlowAdmitted
            && visualizerPresentationRoot.presentationActive
            && !visualizerPresentationRoot.expandedDisplay
            && !visualizerPresentationRoot.prepareOnly
        sourceComponent: WidgetHoverEditGlyphs {
            objectName: "visualizerHoverEditGlyphs"
            anchors.fill: parent
            admitted: true
            hovered: visualizerInteractionHover.hovered
            canRestore: true
            canRotate: false
            canTransferLeft: visualizerPresentationRoot.displayTransferLeftAvailable
            canTransferRight: visualizerPresentationRoot.displayTransferRightAvailable
            canLock: false
            onActionRequested: function(action) {
                visualizerPresentationRoot.hoverEditGlyphRequested(action)
            }
            onTransferHoverChanged: function(action, hovered) {
                visualizerPresentationRoot.displayTransferHoverChanged(action, hovered)
            }
        }
    }

    // Observe at the common scene ancestor: a menu layered over the card must
    // not manufacture a leave/re-entry. Loader owns and retires this passive
    // handler even though its event parent is the window content item.
    Loader {
        id: controlHintVisitObserver
        objectName: "visualizerControlHintVisitObserver"
        active: visualizerPresentationRoot.controlHintVisitTracking
            && visualizerPresentationRoot.Window.window !== null
        sourceComponent: HoverHandler {
            objectName: "visualizerControlHintWindowHover"
            parent: visualizerPresentationRoot.Window.window ? visualizerPresentationRoot.Window.window.contentItem : null
            enabled: visualizerPresentationRoot.controlHintVisitTracking
                && visualizerPresentationRoot.Window.window !== null
            blocking: false
            readonly property point cardPosition: visualizerPresentationRoot.mapFromItem(parent, point.position)
            readonly property bool insideCard: hovered
                && cardPosition.x >= 0 && cardPosition.y >= 0
                && cardPosition.x < visualizerPresentationRoot.width
                && cardPosition.y < visualizerPresentationRoot.height
            onInsideCardChanged: {
                if (!insideCard && visualizerPresentationRoot.controlHintVisitTracking) {
                    visualizerPresentationRoot.controlHintVisitStarted = false
                    controlHintReveal.stop()
                    controlHintLeave.restart()
                }
            }
        }
    }

    // One animation per entry. Pointer movement never restarts the five-second
    // visit, and the artwork has no pointer handler or action hitbox.
    SequentialAnimation {
        id: controlHintReveal
        NumberAnimation {
            target: visualizerPresentationRoot
            property: "controlHintOpacity"
            to: 0.90
            duration: 700
            easing.type: Easing.InOutSine
        }
        PauseAnimation { duration: 4300 }
        NumberAnimation {
            target: visualizerPresentationRoot
            property: "controlHintOpacity"
            to: 0.0
            duration: 900
            easing.type: Easing.InOutSine
        }
    }
    NumberAnimation {
        id: controlHintLeave
        target: visualizerPresentationRoot
        property: "controlHintOpacity"
        to: 0.0
        duration: 350
        easing.type: Easing.InOutSine
    }
    Image {
        id: controlHintImage
        objectName: "visualizerControlHint"
        anchors.top: parent.top
        anchors.right: parent.right
        readonly property real inset: Math.max(12, visualizerPresentationRoot.cardBorderWidth + 6)
        anchors.margins: inset
        // The upper-right corner is the hint's alone: the expand glyph sits at the bottom-right glyph row's corner.
        width: Math.min(Math.max(0, parent.width - 2 * inset),
                        Math.max(0, parent.height - 2 * inset) * artworkAspect,
                        Math.round(Math.max(48, Math.min(84, Math.min(parent.width, parent.height) * 0.085))))
        readonly property real artworkAspect: implicitHeight > 0 ? implicitWidth / implicitHeight : 0
        height: artworkAspect > 0 ? width / artworkAspect : 0
        source: visualizerPresentationRoot.controlHintsAvailable && visualizerPresentationRoot.show3DControlHints
                ? "qrc:/srpss/widgets/visualizer/control_hint.png" : ""
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
        enabled: false
        visible: visualizerPresentationRoot.controlHintEligible && opacity > 0.0
        opacity: visualizerPresentationRoot.controlHintOpacity
        z: 10
    }

    Rectangle {
        id: visualizerPerfHud
        objectName: "visualizerPerfHud"
        visible: visualizerPresentationRoot.perfHudEnabled
            && visualizerPresentationRoot.perfHudText.length > 0
        // Place the visualizer counter BELOW its original 6px top inset.
        // Its independent 12px inset is not inherited from the screen HUD.
        // Retain the added 1px of internal vertical padding per side.
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 12
        width: visualizerPerfHudLabel.implicitWidth + 10
        height: visualizerPerfHudLabel.implicitHeight + 8
        radius: 3
        color: "#80000000"
        border.color: "#80ffffff"
        border.width: 1
        z: 20
        enabled: false

        Text {
            id: visualizerPerfHudLabel
            anchors.centerIn: parent
            text: visualizerPresentationRoot.perfHudText
            color: "white"
            font.family: "Consolas"
            font.pixelSize: 10
            renderType: Text.NativeRendering
        }
    }
}
