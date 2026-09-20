import QtQuick

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
    property bool perfHudEnabled: false
    property string perfHudText: ""

    // Wall-time wallpaper transitions are rendered by BackgroundRenderItem,
    // not by an animating QML property. FrameAnimation supplies Qt Quick's
    // native animation-driver tick; this per-display gate requests the custom
    // render item only when this display's own refresh interval is due.
    // No Python timer/callback and no frameSwapped feedback loop participates.
    property bool transitionFrameDriverActive: false
    property real transitionFrameTargetHz: 60.0
    property var transitionRenderItem: null
    property real transitionFrameNextDueS: 0.0
    property real transitionFrameAnimationTicks: 0
    property real transitionFrameUpdateRequests: 0

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
            if (running)
                reset()
        }

        onTriggered: {
            displayScene.transitionFrameAnimationTicks += 1
            const targetHz = Math.max(1.0, displayScene.transitionFrameTargetHz)
            const intervalS = 1.0 / targetHz
            var nextDueS = displayScene.transitionFrameNextDueS
            if (nextDueS <= 0.0)
                nextDueS = elapsedTime
            if (elapsedTime + 0.0000005 < nextDueS) {
                displayScene.transitionFrameNextDueS = nextDueS
                return
            }

            // Never repay missed intervals as a burst. One native animation
            // tick may request at most one scene update; wall-time progress is
            // sampled by TransitionRun, so skipping late opportunities is safe.
            const behindS = Math.max(0.0, elapsedTime - nextDueS)
            const intervalsPassed = Math.floor(behindS / intervalS) + 1
            displayScene.transitionFrameNextDueS =
                nextDueS + intervalsPassed * intervalS
            displayScene.transitionFrameUpdateRequests += 1
            displayScene.transitionRenderItem.update()
        }
    }

    // Restored healthy background topology: BackgroundRenderItem is parented
    // directly to this scene root by Python. No texture layer/capture/material
    // owner sits between the transition renderer and the window.
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
        }

        Item {
            id: ordinaryWidgetHost
            objectName: "ordinaryWidgetHost"
            anchors.fill: parent
            clip: false
            z: 10
        }

        Loader {
            id: visualizerPresentationLoader
            objectName: "visualizerPresentationLoader"
            active: false
            asynchronous: false
            source: "VisualizerPresentation.qml"
            z: 20
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
        transferButtonColor: displayScene.contextMenuSurfaceColor
        transferButtonHoverColor: displayScene.contextMenuSelectedSurfaceColor
        transferButtonBorderColor: displayScene.contextMenuBorderColor
        transferButtonGlyphColor: displayScene.contextMenuArrowColor
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
        z: 300
    }

    Rectangle {
        id: perfHud
        objectName: "perfHud"
        visible: displayScene.perfHudEnabled && displayScene.perfHudText.length > 0
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 8
        width: perfHudLabel.implicitWidth + 12
        height: perfHudLabel.implicitHeight + 8
        radius: 3
        color: "#b8000000"
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
