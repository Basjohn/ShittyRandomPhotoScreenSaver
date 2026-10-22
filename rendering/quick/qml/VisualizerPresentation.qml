import QtQuick
import QtQuick.Window
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
    property real authoredSceneOpacity: 1.0
    property real startupRevealOpacity: 1.0
    property bool cardShellEnabled: true
    property color cardBackgroundColor: "#4c232323"
    property color cardBorderColor: "#ffffffff"
    property real cardBorderWidth: 4.0
    property real cardCornerRadius: 8.0
    property bool cardShadowEnabled: true
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

    Rectangle {
        id: cardBackground
        objectName: "visualizerCardBackground"
        anchors.fill: parent
        visible: visualizerPresentationRoot.cardShellEnabled
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

    HoverHandler {
        id: cameraResetHover
        enabled: visualizerPresentationRoot.cameraResetAvailable
            && visualizerPresentationRoot.alwaysShowGlyphs
            && visualizerPresentationRoot.widgetGlowAdmitted
        blocking: false
    }

    // One-shot hover animation for the camera reset glyph. No Timer/polling;
    // the first 1008ms are entirely invisible, independent of card hover glow.
    property real cameraResetTipProgress: 0.0
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
            onEntered: cameraResetTipReveal.restart()
            onExited: {
                cameraResetTipReveal.stop()
                visualizerPresentationRoot.cameraResetTipProgress = 0.0
            }
            onPressed: function(mouse) { mouse.accepted = true }
            onClicked: function(mouse) {
                mouse.accepted = true
                visualizerPresentationRoot.cameraResetRequested()
            }
        }
    }

    Rectangle {
        id: cameraResetTooltip
        z: 14
        enabled: false
        visible: cameraResetGlyph.enabled && opacity > 0.0
        opacity: Math.max(0.0, Math.min(1.0,
            (visualizerPresentationRoot.cameraResetTipProgress - 0.56) / 0.44))
        width: resetTooltipText.implicitWidth + 18
        height: resetTooltipText.implicitHeight + 12
        x: Math.max(6, cameraResetGlyph.x + cameraResetGlyph.width - width)
        y: Math.max(3, cameraResetGlyph.y - height - 7)
        radius: 7
        color: "#e51d2634"
        border.width: 1
        border.color: "#bdc38e88"
        Text {
            id: resetTooltipText
            anchors.centerIn: parent
            text: "RESET CAMERA"
            color: "#f6f6f8"
            font.pixelSize: 11
            font.weight: Font.Medium
        }
    }

    Loader {
        objectName: "visualizerHoverGlyphLoader"
        anchors.fill: parent
        z: 11
        active: visualizerPresentationRoot.alwaysShowGlyphs
            && visualizerPresentationRoot.widgetGlowAdmitted
            && visualizerPresentationRoot.presentationActive
        sourceComponent: WidgetHoverEditGlyphs {
            objectName: "visualizerHoverEditGlyphs"
            anchors.fill: parent
            admitted: true
            hovered: visualizerInteractionHover.hovered
            canRestore: true
            canRotate: false
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
        objectName: "visualizerControlHint"
        anchors.top: parent.top
        anchors.right: parent.right
        readonly property real inset: Math.max(12, visualizerPresentationRoot.cardBorderWidth + 6)
        anchors.margins: inset
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
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 6
        width: visualizerPerfHudLabel.implicitWidth + 10
        height: visualizerPerfHudLabel.implicitHeight + 6
        radius: 3
        color: "#b8000000"
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
