import QtQuick
import QtQuick.Effects

// Presentation-only card shell: background, border, corner radius, padding and
// a signed-offset-safe rectangular drop shadow. This is a shared E3 primitive:
// it exposes only explicit presentation properties and holds no model, service,
// settings or QWidget reference. Content/background alpha, border alpha and
// shadow alpha are deliberately independent of one another and of the
// whole-widget root fade opacity applied by OverlayWidget.
Item {
    id: card
    objectName: "overlayCard"

    property bool shellEnabled: true
    property color backgroundColor: "#b3101010"
    property color borderColor: "#e6ffffff"
    property real borderWidth: 2.0
    property real cornerRadius: 8.0
    property real padding: 8.0

    property bool shadowEnabled: true
    property color shadowColor: "#96000000"
    property real shadowBlur: 18.0
    // Signed card-direction magnitudes. These are deliberately NOT forwarded to
    // RectangularShadow.offset: Qt offset translates the complete blurred
    // surface and can expose the opposite card edge. Card direction is instead
    // represented as one-sided shadow-surface extrusion below. Text shadows keep
    // genuine displacement semantics in ShadowedText.qml.
    property real shadowOffsetX: 0.0
    property real shadowOffsetY: 4.0
    property real shadowSpread: 0.0
    // Frame Extra Offset extends only the selected far edge(s); it never
    // translates the complete shadow away from the opposite corner.
    property real shadowExtendLeft: 0.0
    property real shadowExtendTop: 0.0
    property real shadowExtendRight: 0.0
    property real shadowExtendBottom: 0.0

    // The authored base direction (normally 4 px) is also geometry, not Qt
    // effect translation. Folding it into the same extrusion contract makes the
    // opposite edge invariant structural rather than dependent on effect bounds.
    readonly property real shadowBaseLeft: Math.max(0.0, -shadowOffsetX)
    readonly property real shadowBaseTop: Math.max(0.0, -shadowOffsetY)
    readonly property real shadowBaseRight: Math.max(0.0, shadowOffsetX)
    readonly property real shadowBaseBottom: Math.max(0.0, shadowOffsetY)

    // The card must never clip its own shadow blur or negative offsets.
    clip: false

    // Callers compose shell primitives (text, separators, rows) into the padded
    // content area rather than subclassing a god-object base.
    default property alias content: contentArea.data

    // Shell inset each family adds around its intrinsic content when declaring a
    // preferred content size. Exposed so a family can compute preferred size as
    // (intrinsic content + shell inset) without reading its own assigned width
    // (which would create a width<->preferredWidth feedback loop).
    readonly property real shellInset: 2 * padding

    RectangularShadow {
        id: cardShadow
        objectName: "overlayCardShadow"
        x: background.x - card.shadowBaseLeft - card.shadowExtendLeft
        y: background.y - card.shadowBaseTop - card.shadowExtendTop
        width: background.width
            + card.shadowBaseLeft + card.shadowBaseRight
            + card.shadowExtendLeft + card.shadowExtendRight
        height: background.height
            + card.shadowBaseTop + card.shadowBaseBottom
            + card.shadowExtendTop + card.shadowExtendBottom
        visible: card.shellEnabled && card.shadowEnabled
        color: card.shadowColor
        blur: card.shadowBlur
        radius: card.cornerRadius
        spread: card.shadowSpread
        // Never translate a card shadow surface: direction/Extra Offset are
        // represented entirely by asymmetric geometry above.
        offset: Qt.vector2d(0.0, 0.0)
        // SRPSS card shadows are overwhelmingly static: cache by default so a
        // whole-widget fade (root opacity) never rebuilds blur/spread, while a
        // style/geometry/direction change still invalidates the cache naturally.
        cached: true
        z: -1
    }

    Rectangle {
        id: background
        objectName: "overlayCardBackground"
        anchors.fill: parent
        visible: card.shellEnabled
        color: card.backgroundColor
        radius: card.cornerRadius
        border.color: card.borderColor
        border.width: card.borderWidth
        z: 0
    }

    Item {
        id: contentArea
        objectName: "overlayCardContent"
        anchors.fill: parent
        anchors.margins: card.padding
        clip: false
        z: 1
    }
}
