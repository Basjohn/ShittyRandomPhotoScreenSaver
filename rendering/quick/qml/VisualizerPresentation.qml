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
    signal appVolumeStepRequested(int direction)
    property bool cameraResetAvailable: false
    signal cameraResetRequested()
    // Expanded Visualizer (plan 01 §B1): offered for a capable mode outside Edit; the takeover coordinator
    // publishes both values at its event edges. expandedDisplay turns the glyph into the collapse.
    property bool expandGlyphAvailable: false
    property bool expandedDisplay: false
    signal expandGlyphRequested(bool expand)
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
    // Fullscreen Edit (M3c): the Edit session is open on the overlays; they show to be grabbed and report geometry.
    property bool expandedOverlayEditing: false
    signal expandedOverlayEditGeometryChanged()
    // The left edge of the right-hand controls' column (stable: from the card's size and the tips' text, never from
    // hover or admission), so an overlay moved into it keeps clear of the controls vertically.
    TextMetrics {
        id: presetTipMetrics
        font.pixelSize: 11
        font.weight: Font.Medium
        text: "PREVIOUS PRESET"
    }
    readonly property real expandedOverlayControlsLeft: Math.min(
        expandTooltip.x,
        controlHintsAvailable && show3DControlHints
            ? width - controlHintImage.inset - expandGlyph.width - 6 - controlHintImage.width : width,
        cameraResetGlyph.x - 5 - presetControls.width + cameraResetGlyph.width - (presetTipMetrics.advanceWidth + 18)
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
        && cardShellEnabled && visible
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

    opacity: authoredSceneOpacity * startupRevealOpacity
    visible: presentationActive && customLayoutWorkingVisible && opacity > 0.0

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
        color: visualizerPresentationRoot.cardBackgroundColor
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
            // The card's own controls: the collapse glyph, its tip and the 3D control hint (top right); Reset Camera,
            // the preset steps and their tip (bottom right).
            topRightReserve: Math.max(expandTooltip.y + expandTooltip.height,
                                      controlHintImage.y + controlHintImage.height) + 10.0
            bottomRightReserve: visualizerPresentationRoot.height - cameraResetTooltip.y + 10.0
            rightControlsLeft: visualizerPresentationRoot.expandedOverlayControlsLeft
            editing: visualizerPresentationRoot.expandedOverlayEditing
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

    Rectangle {
        id: cameraResetGlyph
        objectName: "visualizerCameraResetGlyph"
        width: 26
        height: 26
        x: Math.max(6, parent.width - width - 12)
        y: Math.max(6, parent.height - height - 12)
        radius: width / 2
        z: 12
        color: "#bb20262c"
        border.width: 1
        border.color: "#c2ffffff"
        visible: visualizerPresentationRoot.cameraResetAvailable
            && visualizerPresentationRoot.widgetGlowAdmitted
            && visualizerPresentationRoot.visible
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
                visualizerPresentationRoot.cameraActionTipX = cameraResetGlyph.x + cameraResetGlyph.width
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

    // Expand / collapse: a vector diagonal arrow in the upper-right corner, a distinct semantic action (not an
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
    Rectangle {
        id: expandGlyph
        objectName: "visualizerExpandGlyph"
        width: 26
        height: 26
        readonly property real inset: Math.max(10, visualizerPresentationRoot.cardBorderWidth + 6)
        x: Math.max(6, parent.width - width - inset)
        y: inset
        radius: width / 2
        z: 12
        color: "#bb20262c"
        border.width: 1
        border.color: "#c2ffffff"
        visible: visualizerPresentationRoot.expandGlyphAvailable
            && visualizerPresentationRoot.widgetGlowAdmitted
            && visualizerPresentationRoot.visible
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
        onEnabledChanged: if (!enabled) {
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
            onCollapseChanged: requestPaint()
            onPaint: {
                const ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                ctx.save()
                // Expand points up-right; collapse is the same arrow turned to point down-left.
                if (collapse) { ctx.translate(width, height); ctx.rotate(Math.PI) }
                ctx.strokeStyle = "#f2f4f7"
                ctx.lineWidth = 2.0
                ctx.lineCap = "round"
                ctx.lineJoin = "round"
                ctx.beginPath()
                ctx.moveTo(4.5, 13.5)
                ctx.lineTo(13.5, 4.5)
                ctx.moveTo(7.5, 4.5)
                ctx.lineTo(13.5, 4.5)
                ctx.lineTo(13.5, 10.5)
                ctx.stroke()
                ctx.restore()
            }
        }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            propagateComposedEvents: false
            onEntered: expandTipReveal.restart()
            onExited: {
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
    Rectangle {
        id: expandTooltip
        objectName: "visualizerExpandTooltip"
        visible: expandGlyph.visible && opacity > 0.0
        opacity: Math.max(0.0, Math.min(1.0,
            (visualizerPresentationRoot.expandTipProgress - 0.56) / 0.44))
        width: expandTooltipText.implicitWidth + 16
        height: expandTooltipText.implicitHeight + 8
        x: Math.max(3, expandGlyph.x + expandGlyph.width - width)
        y: expandGlyph.y + expandGlyph.height + 7
        radius: 4
        z: 13
        enabled: false
        color: "#e61b1e23"
        border.width: 1
        border.color: "#bdc38e88"
        Text {
            id: expandTooltipText
            anchors.centerIn: parent
            text: visualizerPresentationRoot.expandedDisplay ? "EXIT FULL DISPLAY" : "FULL DISPLAY"
            color: "#f6f6f8"
            font.pixelSize: 11
            font.weight: Font.Medium
        }
    }

    Row {
        id: presetControls
        objectName: "visualizerPresetControls"
        x: Math.max(6, (cameraResetGlyph.visible ? cameraResetGlyph.x : parent.width - 12) - width - 5)
        y: cameraResetGlyph.y
        spacing: 5
        z: 12
        visible: visualizerPresentationRoot.widgetGlowAdmitted && visualizerPresentationRoot.visible
            && visualizerPresentationRoot.volumeWheelEnabled
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
                        visualizerPresentationRoot.cameraActionTipX = presetControls.x + parent.x + parent.width
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

    Rectangle {
        id: cameraResetTooltip
        objectName: "visualizerPresetTooltip"
        z: 14
        enabled: false
        visible: presetControls.enabled && opacity > 0.0
        opacity: Math.max(0.0, Math.min(1.0,
            (visualizerPresentationRoot.cameraResetTipProgress - 0.56) / 0.44))
        width: resetTooltipText.implicitWidth + 18
        height: resetTooltipText.implicitHeight + 12
        x: Math.max(6, visualizerPresentationRoot.cameraActionTipX - width)
        y: Math.max(3, cameraResetGlyph.y - height - 7)
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
        // Keep the safe zone of the expand glyph clear (plan 01 §B1).
        anchors.rightMargin: inset + (expandGlyph.visible ? expandGlyph.width + 6 : 0)
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
