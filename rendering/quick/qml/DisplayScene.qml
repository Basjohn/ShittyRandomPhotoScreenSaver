import QtQuick
import QtQuick.Effects

Item {
    id: displayScene
    objectName: "displaySceneRoot"
    property string runtimeRole: "display-scene"
    property int screenIndex: -1
    property var runtimeGeneration: null
    property bool dimmingEnabled: false
    property real dimmingOpacity: 0.0
    property real pixelShiftX: 0.0
    property real pixelShiftY: 0.0
    property var contextMenuModel: null
    property bool contextMenuShadowEnabled: true
    property color contextMenuShadowColor: "#c4000000"
    property real contextMenuShadowBlur: 18.0
    property real contextMenuShadowOffsetX: 4.0
    property real contextMenuShadowOffsetY: 4.0
    property real contextMenuShadowExtendLeft: 0.0
    property real contextMenuShadowExtendTop: 0.0
    property real contextMenuShadowExtendRight: 0.0
    property real contextMenuShadowExtendBottom: 0.0
    property color contextMenuSurfaceColor: "#f21b1d24"
    property color contextMenuBorderColor: "#d8f3ff"
    property color contextMenuTextColor: "#f6f8ff"
    property color contextMenuSelectedSurfaceColor: "#4f77b9e8"
    property color contextMenuSeparatorColor: "#59778a"
    property color contextMenuIndicatorBorderColor: "#b9eaff"
    property color contextMenuIndicatorFillColor: "#82cdff"
    property color contextMenuArrowColor: "#d8f3ff"
    property color contextSubmenuSurfaceColor: "#f21b1d24"
    property color contextSubmenuBorderColor: "#d8f3ff"
    property color contextSubmenuTextColor: "#f6f8ff"
    property color contextSubmenuSelectedSurfaceColor: "#4f77b9e8"
    property color contextSubmenuCheckedTextColor: "#b9eaff"
    property color contextSubmenuCheckedSurfaceColor: "#334e718b"
    property color contextSubmenuIndicatorBorderColor: "#b9eaff"
    property color contextSubmenuIndicatorFillColor: "#82cdff"
    // Card surface materials: the Context Menu's material (Widget Theme baseline) and
    // the display's shared backdrop, bound by the scene controller only while some
    // surface is not Normal. The backdrop item itself is parented here by Python at z 2.
    property string contextMenuSurfaceMaterial: "normal"
    property var contextMenuSurfaceBackdrop: null
    property bool perfHudEnabled: false
    property string perfHudText: ""

    // Expanded Visualizer (plan 01 M3, §F): one display-local transient visual policy over the ordinary widget
    // lanes (their cards and their card shadows) while this display's Visualizer is display-wide. Python sets it at
    // the takeover's event edges only (the coordinator, through the scene controller); QML owns only the fade. It
    // multiplies (as an ancestor's opacity) with every family fade and the startup gate and never writes them, so a
    // root created while covered joins already covered. The Visualizer card, its shadow and the OSD foreground lane
    // are outside it. Fully covered, the lanes are invisible (no paint, no hit, no hover); input stops at the cover
    // edge (enabled), not at the end of the fade. Nothing here runs at rest: the Behavior animates only on a change.
    property bool ordinaryWidgetsCovered: false
    // 0 snaps (a restore before reveal, Edit's immediate collapse); otherwise the Visualizer's own fade half.
    property int ordinaryWidgetsCoverFadeMs: 0
    property real ordinaryWidgetsCoverOpacity: ordinaryWidgetsCovered ? 0.0 : 1.0
    Behavior on ordinaryWidgetsCoverOpacity {
        enabled: displayScene.ordinaryWidgetsCoverFadeMs > 0
        NumberAnimation {
            duration: displayScene.ordinaryWidgetsCoverFadeMs
            easing.type: Easing.InOutSine
        }
    }

    // Wall-time wallpaper transitions are rendered by BackgroundRenderItem,
    // not by an animating QML property. FrameAnimation supplies Qt Quick's
    // native animation-driver tick; this per-display gate requests the custom
    // render item only when this display's own refresh interval is due.
    // No Python timer/callback and no frameSwapped feedback loop participates.
    //
    // The transition samples wall time on every frame this window renders, so
    // a Visualizer presenting on this display carries it: while Visualizer
    // frames keep arriving, the transition requests none of its own. Its own
    // ticks (a ~115 Hz system timer, unaligned with the Visualizer's 90 Hz)
    // used to add ~120 frames a second that redrew an unchanged Visualizer state
    // and showed its motion unevenly (Bubble micro-flicker, 2026-10-03). Within
    // transitionVisualizerFillS of the last Visualizer frame the gate waits;
    // once Visualizer frames stop (pause, mode change) it fills in at the
    // display's rate, so a transition never stalls on the Visualizer.
    property bool transitionFrameDriverActive: false
    property real transitionFrameTargetHz: 60.0
    property var transitionRenderItem: null
    property real transitionFrameNextDueS: 0.0
    property real transitionFrameAnimationTicks: 0
    property real transitionFrameUpdateRequests: 0
    // Bumped by the scene controller per Visualizer frame request, only while
    // this display's transition driver runs.
    property real transitionVisualizerFrames: 0
    property real transitionVisualizerFramesSeen: 0
    property real transitionVisualizerLastS: -1.0
    property real transitionFrameRiddenTicks: 0
    readonly property real transitionVisualizerFillS: 0.025

    // One native tick's decision, pure so it is testable: returns the gate's
    // next state and whether this tick requests a transition frame.
    function transitionFrameGate(gate, elapsedS, targetHz, visualizerFrames, fillS) {
        var lastVisualizerS = gate.lastVisualizerS
        var seen = gate.seenVisualizerFrames
        if (visualizerFrames !== seen) {
            seen = visualizerFrames
            lastVisualizerS = elapsedS
        }
        if (lastVisualizerS >= 0.0 && elapsedS - lastVisualizerS < fillS) {
            // A Visualizer frame carries the transition; the own deadline
            // restarts when the Visualizer stops.
            return { request: false, ridden: true, nextDueS: 0.0,
                     lastVisualizerS: lastVisualizerS, seenVisualizerFrames: seen }
        }
        const intervalS = 1.0 / Math.max(1.0, targetHz)
        var nextDueS = gate.nextDueS
        if (nextDueS <= 0.0)
            nextDueS = elapsedS
        if (elapsedS + 0.0000005 < nextDueS)
            return { request: false, ridden: false, nextDueS: nextDueS,
                     lastVisualizerS: lastVisualizerS, seenVisualizerFrames: seen }
        // Never repay missed intervals as a burst. One native animation tick
        // may request at most one scene update; wall-time progress is sampled
        // by TransitionRun, so skipping late opportunities is safe.
        const behindS = Math.max(0.0, elapsedS - nextDueS)
        const intervalsPassed = Math.floor(behindS / intervalS) + 1
        return { request: true, ridden: false, nextDueS: nextDueS + intervalsPassed * intervalS,
                 lastVisualizerS: lastVisualizerS, seenVisualizerFrames: seen }
    }

    onTransitionFrameTargetHzChanged: {
        // A display retarget changes the cadence contract immediately. Discard
        // any deadline derived from the previous screen instead of carrying one
        // stale 60/165 Hz interval across the hop.
        transitionFrameNextDueS = 0.0
    }

    FrameAnimation {
        id: transitionFrameAnimation
        running: displayScene.transitionFrameDriverActive
            && displayScene.transitionRenderItem !== null

        onRunningChanged: {
            displayScene.transitionFrameNextDueS = 0.0
            displayScene.transitionVisualizerLastS = -1.0
            displayScene.transitionVisualizerFramesSeen =
                displayScene.transitionVisualizerFrames
            if (running)
                reset()
        }

        onTriggered: {
            displayScene.transitionFrameAnimationTicks += 1
            const gate = displayScene.transitionFrameGate({
                    nextDueS: displayScene.transitionFrameNextDueS,
                    lastVisualizerS: displayScene.transitionVisualizerLastS,
                    seenVisualizerFrames: displayScene.transitionVisualizerFramesSeen
                }, elapsedTime, displayScene.transitionFrameTargetHz,
                displayScene.transitionVisualizerFrames,
                displayScene.transitionVisualizerFillS)
            displayScene.transitionFrameNextDueS = gate.nextDueS
            displayScene.transitionVisualizerLastS = gate.lastVisualizerS
            displayScene.transitionVisualizerFramesSeen = gate.seenVisualizerFrames
            if (gate.ridden)
                displayScene.transitionFrameRiddenTicks += 1
            if (!gate.request)
                return
            displayScene.transitionFrameUpdateRequests += 1
            displayScene.transitionRenderItem.update()
        }
    }

    // Restored healthy background topology: BackgroundRenderItem is parented
    // directly to this scene root by Python at z 0. No texture layer or capture
    // sits between the transition renderer and the window. A card surface
    // backdrop, when one exists, only reads the already-drawn frame from z 2.
    Rectangle {
        id: backgroundDimming
        objectName: "backgroundDimming"
        anchors.fill: parent
        color: "black"
        opacity: displayScene.dimmingEnabled
            ? Math.max(0.0, Math.min(1.0, displayScene.dimmingOpacity))
            : 0.0
        visible: opacity > 0.0
        enabled: false
        z: 1
    }

    CustomLayoutGuideUnderlay {
        id: customLayoutGuideUnderlay
        anchors.fill: parent
        z: 4
    }

    Item {
        id: pixelShiftLayer
        objectName: "pixelShiftLayer"
        anchors.fill: parent
        z: 5
        transform: Translate {
            id: pixelShiftPaintTranslation
            x: displayScene.pixelShiftX
            y: displayScene.pixelShiftY
        }
        // Subscribe to the applied transform, not to pixelShiftX/Y inputs
        // which may notify before this Translate has updated its paint matrix.
        readonly property string customEditMappingDependency: [
            pixelShiftPaintTranslation.x, pixelShiftPaintTranslation.y
        ].join("|")

        Item {
            id: ordinaryWidgetShadowHost
            objectName: "ordinaryWidgetShadowHost"
            anchors.fill: parent
            clip: false
            enabled: false
            z: 0

            // The Visualizer card is painted later in the foreground lane, but
            // its shadow belongs with every other card shadow beneath all widget
            // surfaces. Keeping the blur here prevents it from landing over Media
            // (or any other ordinary widget) when their rectangles overlap. This
            // is card-shell chrome only: frameless/freeform 3D renderer/object
            // shadows remain inside their renderer and never enter this lane.
            RectangularShadow {
                id: visualizerCardShadowUnderlay
                objectName: "visualizerCardShadowUnderlay"
                readonly property var sourceRoot: visualizerPresentationLoader.item
                readonly property real baseLeft: sourceRoot
                    ? Math.max(0.0, -Number(sourceRoot.cardShadowOffsetX)) : 0.0
                readonly property real baseTop: sourceRoot
                    ? Math.max(0.0, -Number(sourceRoot.cardShadowOffsetY)) : 0.0
                readonly property real baseRight: sourceRoot
                    ? Math.max(0.0, Number(sourceRoot.cardShadowOffsetX)) : 0.0
                readonly property real baseBottom: sourceRoot
                    ? Math.max(0.0, Number(sourceRoot.cardShadowOffsetY)) : 0.0
                readonly property real extendLeft: sourceRoot
                    ? Math.max(0.0, Number(sourceRoot.cardShadowExtendLeft)) : 0.0
                readonly property real extendTop: sourceRoot
                    ? Math.max(0.0, Number(sourceRoot.cardShadowExtendTop)) : 0.0
                readonly property real extendRight: sourceRoot
                    ? Math.max(0.0, Number(sourceRoot.cardShadowExtendRight)) : 0.0
                readonly property real extendBottom: sourceRoot
                    ? Math.max(0.0, Number(sourceRoot.cardShadowExtendBottom)) : 0.0
                x: visualizerPresentationLoader.x - baseLeft - extendLeft
                y: visualizerPresentationLoader.y - baseTop - extendTop
                width: visualizerPresentationLoader.width
                    + baseLeft + baseRight + extendLeft + extendRight
                height: visualizerPresentationLoader.height
                    + baseTop + baseBottom + extendTop + extendBottom
                visible: !!sourceRoot
                    && sourceRoot.visible
                    && sourceRoot.cardShellEnabled
                    && sourceRoot.cardShadowEnabled
                    && width > 0.0 && height > 0.0
                opacity: sourceRoot ? Number(sourceRoot.opacity) : 0.0
                color: sourceRoot ? sourceRoot.cardShadowColor : "transparent"
                blur: sourceRoot ? Number(sourceRoot.cardShadowBlur) : 0.0
                radius: sourceRoot ? Number(sourceRoot.cardCornerRadius) : 0.0
                spread: sourceRoot ? Number(sourceRoot.cardShadowSpread) : 0.0
                offset: Qt.vector2d(0.0, 0.0)
                cached: true
            }

            // Every ordinary card shadow is parented here (after the Visualizer's, so the paint order is
            // unchanged), so the Expanded Visualizer cover fades the ordinary shadows with their cards while the
            // Visualizer card keeps its own shadow.
            Item {
                id: ordinaryWidgetShadowLane
                objectName: "ordinaryWidgetShadowLane"
                anchors.fill: parent
                clip: false
                enabled: false
                opacity: displayScene.ordinaryWidgetsCoverOpacity
                visible: opacity > 0.0
            }
        }

        Item {
            id: ordinaryWidgetHost
            objectName: "ordinaryWidgetHost"
            anchors.fill: parent
            clip: false
            z: 10
            opacity: displayScene.ordinaryWidgetsCoverOpacity
            visible: opacity > 0.0
            enabled: !displayScene.ordinaryWidgetsCovered
        }

        Loader {
            id: visualizerPresentationLoader
            objectName: "visualizerPresentationLoader"
            active: false
            asynchronous: false
            source: "VisualizerPresentation.qml"
            z: 20
            onLoaded: {
                if (item) {
                    item.externalCardShadow = true
                    // The full-display overlays (M3b) step aside for a showing OSD: hand over its lane once.
                    item.expandedOverlayOsdHost = systemAudioOSDForegroundHost
                }
            }
        }

        // One existing-host foreground admission lane for the optional OSD.
        // These are inert Item containers when the OSD is disabled. Keeping
        // them in pixelShiftLayer preserves identical display coordinates and
        // CUSTOM editing while painting above all visualizer families. The
        // context menu remains a scene-root sibling above this entire layer.
        Item {
            id: systemAudioOSDShadowHost
            objectName: "systemAudioOSDShadowHost"
            anchors.fill: parent
            enabled: false
            clip: false
            z: 29
        }
        Item {
            id: systemAudioOSDForegroundHost
            objectName: "systemAudioOSDForegroundHost"
            anchors.fill: parent
            clip: false
            z: 30
        }
    }

    CustomLayoutOverlay {
        id: customLayoutOverlay
        anchors.fill: parent
        // Edit chrome owns a neutral graphite palette. Do not inherit the
        // context-menu accent palette here: that made Edit controls turn cyan/
        // blue whenever the active Widget Theme used those accents.
        z: 100
    }

    ContextMenu {
        id: retainedContextMenu
        contextMenuModel: displayScene.contextMenuModel
        shadowEnabled: displayScene.contextMenuShadowEnabled
        shadowColor: displayScene.contextMenuShadowColor
        shadowBlur: displayScene.contextMenuShadowBlur
        shadowOffsetX: displayScene.contextMenuShadowOffsetX
        shadowOffsetY: displayScene.contextMenuShadowOffsetY
        shadowExtendLeft: displayScene.contextMenuShadowExtendLeft
        shadowExtendTop: displayScene.contextMenuShadowExtendTop
        shadowExtendRight: displayScene.contextMenuShadowExtendRight
        shadowExtendBottom: displayScene.contextMenuShadowExtendBottom
        surfaceColor: displayScene.contextMenuSurfaceColor
        borderColor: displayScene.contextMenuBorderColor
        textColor: displayScene.contextMenuTextColor
        selectedSurfaceColor: displayScene.contextMenuSelectedSurfaceColor
        separatorColor: displayScene.contextMenuSeparatorColor
        indicatorBorderColor: displayScene.contextMenuIndicatorBorderColor
        indicatorFillColor: displayScene.contextMenuIndicatorFillColor
        arrowColor: displayScene.contextMenuArrowColor
        submenuSurfaceColor: displayScene.contextSubmenuSurfaceColor
        submenuBorderColor: displayScene.contextSubmenuBorderColor
        submenuTextColor: displayScene.contextSubmenuTextColor
        submenuSelectedSurfaceColor: displayScene.contextSubmenuSelectedSurfaceColor
        submenuCheckedTextColor: displayScene.contextSubmenuCheckedTextColor
        submenuCheckedSurfaceColor: displayScene.contextSubmenuCheckedSurfaceColor
        submenuIndicatorBorderColor: displayScene.contextSubmenuIndicatorBorderColor
        submenuIndicatorFillColor: displayScene.contextSubmenuIndicatorFillColor
        surfaceMaterial: displayScene.contextMenuSurfaceMaterial
        surfaceBackdrop: displayScene.contextMenuSurfaceBackdrop
        z: 300
    }

    Rectangle {
        id: perfHud
        objectName: "perfHud"
        visible: displayScene.perfHudEnabled && displayScene.perfHudText.length > 0
        // Centre the read-only diagnostic HUD so it does not cover the upper
        // left of screenshots; keep its original 8px top breathing space.
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 8
        width: perfHudLabel.implicitWidth + 12
        height: perfHudLabel.implicitHeight + 8
        radius: 3
        color: "#99000000"
        border.color: "#80ffffff"
        border.width: 1
        z: 1000
        enabled: false

        Text {
            id: perfHudLabel
            anchors.centerIn: parent
            text: displayScene.perfHudText
            color: "white"
            font.family: "Consolas"
            font.pixelSize: 11
            renderType: Text.NativeRendering
        }
    }
}
