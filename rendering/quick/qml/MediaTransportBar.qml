import QtQuick
import QtQuick.Effects
import "SurfaceContrast.js" as SurfaceContrast

// Media's transport bar: the rounded bar (its fill or the card's surface material, its outline and its shadow) with
// previous | play-pause | next in three equal segments split by two thin separators, each a MediaTransportGlyph
// (pause while playing). Disabled segments dim; hover and press grow a segment. The one bar, drawn by the Media card
// (MediaPresentation.qml, at the card's size, with its mute button as a child) and, small, by the Expanded
// Visualizer's Now Playing (ExpandedVisualizerOverlays.qml). The caller sizes it, sets its outline (border width and
// colour, radius) and feeds the model's state; a press emits transportRequested("previous" | "play" | "next").
Rectangle {
    id: bar
    objectName: "mediaTransportBar"

    // ---- state (the Media model's)
    property bool canPrevious: false
    property bool canPlayPause: false
    property bool canNext: false
    property bool interactionEnabled: false
    property bool playing: false
    property bool transportVisible: true
    // Fullscreen's floating choice retains these exact glyphs and action handlers.
    property bool floatingGlyphs: false

    // ---- look
    // The original transport colour remains the Normal override's fill. Material
    // mode instead follows the same semantic colour/alpha as the Media volume
    // track; both drawing locations get these resolved values from one model.
    property color surfaceColor: "#b3101010"
    property color materialFillColor: "#b3101010"
    readonly property color effectiveSurfaceColor:
        materialMode === "normal" ? surfaceColor : materialFillColor
    property color iconColor: "#ffffffff"
    // Legacy caller property kept for compatibility; the single outline is
    // the actual ink authority for both bar dividers.
    property color separatorColor: "#66ffffff"
    property real separatorWidth: 1.5
    // One semantic border ink for the outline and the internal dividers. Paint
    // them above the material together, not a parent border hidden under it.
    property color outlineColor: "#66ffffff"
    property real outlineWidth: 1.5
    property bool shadowEnabled: false
    property color shadowColor: "#00000000"
    property real shadowBlur: 0.0
    property real shadowOffsetX: 0.0
    property real shadowOffsetY: 0.0
    // Both bar locations receive an existing, shared backdrop from their host.
    // The bar is a standalone child material: it does not depend on whether the
    // outer Media card shell is visible, and never initiates a new capture.
    property var materialBackdrop: null
    property string inheritedMaterial: "normal"
    property real materialOpacityAdjust: 0.0
    property real materialChildOpacityAdjust: 0.0
    readonly property color adjustedFlatSurfaceColor: Qt.rgba(
        effectiveSurfaceColor.r, effectiveSurfaceColor.g, effectiveSurfaceColor.b,
        SurfaceContrast.adjustedDensity(effectiveSurfaceColor.a, materialChildOpacityAdjust))
    property color materialTextColor: "#ffffffff"
    // "inherit" (default) follows the theme; "normal" keeps the authored flat fill.
    // This applies to the bar alone, never the Media widget or floating glyphs.
    property string materialMode: "inherit"
    // Room kept clear at the bar's right end for a child the caller places there (the card's mute button).
    property real transportReserve: 0.0

    // ---- input. false: the card's pointer handlers. true: each segment holds its press exclusively, a double-click's
    // second press included (a MouseArea declaring consumesDoubleClick: QuickDisplayWindow._double_click_owned_by_control),
    // for a bar over a surface whose own double-click means something else (the Visualizer's mode cycle).
    property bool exclusivePress: false

    // ---- object names (the callers' test and capture hooks)
    property alias materialObjectName: material.objectName
    property alias transportObjectName: transport.objectName
    property string previousObjectName: "mediaPreviousButton"
    property string playPauseObjectName: "mediaPlayPauseButton"
    property string nextObjectName: "mediaNextButton"

    signal transportRequested(string key)

    radius: 12.0
    // On a surface material the bar is material too, tinted by its fill.
    color: floatingGlyphs || material.active ? "transparent" : bar.adjustedFlatSurfaceColor
    border.width: 0.0
    clip: false

    // Transport bar uses the same global direction with 15% more
    // displacement and a deliberately small cached blur.
    RectangularShadow {
        anchors.fill: parent
        visible: bar.shadowEnabled && !bar.floatingGlyphs
        color: bar.shadowColor
        blur: bar.shadowBlur
        radius: parent.radius
        spread: 0.0
        offset: Qt.vector2d(bar.shadowOffsetX * 1.15, bar.shadowOffsetY * 1.15)
        cached: true
        z: -1
    }

    ChildMaterialSurface {
        id: material
        visible: !bar.floatingGlyphs
        objectName: "mediaControlsRowMaterial"
        sourceBackdrop: bar.materialBackdrop
        sourceMaterial: bar.materialMode !== "inherit" && bar.materialMode !== "normal"
            ? bar.materialMode : bar.inheritedMaterial
        sourceOpacityAdjust: bar.materialOpacityAdjust
        additionalOpacityAdjust: bar.materialChildOpacityAdjust
        sourceTextColor: bar.materialTextColor
        forceFlat: bar.materialMode === "normal"
        fillColor: bar.effectiveSurfaceColor
        cornerRadius: bar.radius
        // Volume child behaviour: no text panel and 40% semantic tint alpha.
        // The outer Media widget, its contrast guard, and every other child
        // retain their own independent material settings.
        tintAlphaScale: 0.4
        legibilityPanel: false
    }

    // The body and the material render below both ink elements. The outline and
    // separators are identical Qt Rectangles with the same semantic RGBA; the
    // topmost outline is not buried underneath an opaque material ShaderEffect.
    Rectangle {
        id: outline
        objectName: "mediaTransportOutline"
        anchors.fill: parent
        radius: bar.radius
        color: "transparent"
        border.color: bar.outlineColor
        border.width: bar.floatingGlyphs ? 0.0 : bar.outlineWidth
        visible: !bar.floatingGlyphs && bar.outlineWidth > 0.0
        z: 2
    }

    Row {
        id: transport
        objectName: "mediaTransportControls"
        visible: bar.transportVisible
        x: 0.0
        y: 0.0
        width: Math.max(1.0, parent.width - bar.transportReserve)
        height: parent.height
        z: 1

        TransportButton {
            objectName: bar.previousObjectName
            glyphKind: "previous"
            available: bar.canPrevious
            interactionEnabled: bar.interactionEnabled
            exclusivePress: bar.exclusivePress
            glyphColor: bar.iconColor
            onRequested: bar.transportRequested("previous")
        }

        Rectangle {
            width: bar.separatorWidth
            height: Math.max(0.0, parent.height - 2.0 * bar.outlineWidth)
            y: bar.outlineWidth
            color: bar.floatingGlyphs ? "transparent" : bar.outlineColor
        }

        TransportButton {
            objectName: bar.playPauseObjectName
            glyphKind: bar.playing ? "pause" : "play"
            available: bar.canPlayPause
            interactionEnabled: bar.interactionEnabled
            exclusivePress: bar.exclusivePress
            glyphColor: bar.iconColor
            onRequested: bar.transportRequested("play")
        }

        Rectangle {
            width: bar.separatorWidth
            height: Math.max(0.0, parent.height - 2.0 * bar.outlineWidth)
            y: bar.outlineWidth
            color: bar.floatingGlyphs ? "transparent" : bar.outlineColor
        }

        TransportButton {
            objectName: bar.nextObjectName
            glyphKind: "next"
            available: bar.canNext
            interactionEnabled: bar.interactionEnabled
            exclusivePress: bar.exclusivePress
            glyphColor: bar.iconColor
            onRequested: bar.transportRequested("next")
        }
    }

    // One segment: a third of the transport row, its glyph centred in it.
    component TransportButton: Item {
        id: button

        property string glyphKind: "play"
        property bool available: false
        property bool interactionEnabled: false
        property bool exclusivePress: false
        property color glyphColor: "#ffffffff"
        signal requested()

        readonly property bool inputEnabled: interactionEnabled && available
        readonly property bool pressed: input.item !== null && input.item.pressed === true
        readonly property bool hovered: input.item !== null && input.item.hovered === true

        // Two separators take their actual (possibly scaled) width, rather
        // than assuming the former 1 px size and spilling past the end cap.
        width: Math.max(0.0, (parent.width - 2.0 * bar.separatorWidth) / 3.0)
        height: parent.height
        opacity: available ? (interactionEnabled ? 1.0 : 0.68) : 0.25
        scale: pressed ? 1.10 : (hovered && inputEnabled ? 1.055 : 1.0)

        MediaTransportGlyph {
            anchors.centerIn: parent
            // One box for the whole set, from the bar's height.
            width: Math.max(10.0, Math.min(parent.height * 0.5, parent.width * 0.4))
            kind: button.glyphKind
            glyphColor: button.glyphColor
        }

        // Exactly one input kind exists per segment (never an idle handler of the other kind).
        Loader {
            id: input
            anchors.fill: parent
            sourceComponent: button.exclusivePress ? exclusiveInput : sharedInput
        }

        // The card's pointer handlers: a non-blocking hover (pointer cursor) and a tap.
        Component {
            id: sharedInput
            Item {
                readonly property bool pressed: tap.pressed
                readonly property bool hovered: hover.hovered

                HoverHandler {
                    id: hover
                    enabled: tap.enabled
                    blocking: false
                    cursorShape: Qt.PointingHandCursor
                }

                TapHandler {
                    id: tap
                    enabled: button.inputEnabled
                    acceptedButtons: Qt.LeftButton
                    onTapped: button.requested()
                }
            }
        }

        // An exclusive press area: the segment consumes every press of its own, a double-click's second included.
        Component {
            id: exclusiveInput
            MouseArea {
                readonly property bool hovered: containsMouse
                enabled: button.inputEnabled
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                propagateComposedEvents: false
                readonly property bool consumesDoubleClick: true   // QuickDisplayWindow._double_click_owned_by_control
                onPressed: function(mouse) { mouse.accepted = true }
                onDoubleClicked: function(mouse) { mouse.accepted = true }
                onClicked: function(mouse) {
                    mouse.accepted = true
                    button.requested()
                }
            }
        }
    }
}
