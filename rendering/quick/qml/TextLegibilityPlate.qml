import QtQuick

// One rounded legibility row on a card surface material
// (Docs/Architecture/Card_Surface_Materials.md, 3.3): under a whole list line
// (LegibilityRow) or a single text run (ShadowedText). It samples the display's one
// shared backdrop (no capture of its own), evaluates the card surface along the row and
// draws one even overlay that brings every run colour in the row to its contrast floor:
// 4.5:1 for small text, 3:1 for large. Where the row already meets it, it draws nothing.
// Loaded only while its card's material is active.
ShaderEffect {
    id: plate
    objectName: "textLegibilityPlate"

    property var card: null
    // This plate's top-left in the card's own coordinates (the loader walks the parents).
    property point cardOrigin: Qt.point(0, 0)
    property color runColor: "#ffffffff"
    // Further run colours in the same row (a muted age tag beside a title, an accent
    // label); the row meets the floor for every one. They default to the primary.
    property color secondaryRunColor: runColor
    property color tertiaryRunColor: runColor
    // A row inside its own rounded panel passes that panel's inner radius; < 0 = automatic.
    property real radiusOverride: -1.0
    // The row's own panel fill (stats panel, tile, capsule) between the card surface and
    // this row: the floor is held against what the text actually sits on.
    property color underlayColor: "transparent"
    property real runPixelSize: 14.0
    // A plate inside a faded run (ShadowedText's ink plate) passes the run's own opacity, which
    // the overlay must not take; a row under a line leaves 1.
    property real ownOpacity: 1.0
    // Below this a run is small text and needs 4.5:1 (WCAG AA body text).
    readonly property real smallTextPx: 18.0

    readonly property var source: card ? card.surfaceBackdrop : null
    readonly property vector2d itemSize: Qt.vector2d(width, height)
    readonly property real floorRatio: runPixelSize < smallTextPx ? 4.5 : 3.0
    readonly property color tintColor: card ? card.backgroundColor : "transparent"
    readonly property color textColor: card ? card.surfaceTextColor : "#ffffffff"
    readonly property vector2d cardSize: card ? Qt.vector2d(card.width, card.height) : Qt.vector2d(1, 1)
    readonly property vector2d cardOffset: Qt.vector2d(cardOrigin.x, cardOrigin.y)
    readonly property real cornerRadius: card ? card.cornerRadius : 0.0
    readonly property real contentInset: card ? card.padding : 0.0
    readonly property real borderWidth: card ? card.borderWidth : 0.0
    // A row in its own panel passes that panel's inner radius (never under 2 px); otherwise its
    // corners follow the card's radius less its gap into the padding (concentric),
    // never sharper than 4 px.
    readonly property real rowRadius: Math.min(height / 2.0, radiusOverride >= 0.0 ? Math.max(2.0, radiusOverride)
        : Math.max(4.0, cornerRadius - Math.max(0.0, contentInset - 4.0)))
    readonly property var parameters: card ? card.surfaceMaterialParameters : null
    readonly property real opacityAdjust: card ? card.surfaceOpacityAdjust : 0.0
    readonly property vector4d panelLimits: card ? card.surfaceMaterialLimits : Qt.vector4d(0, 1, 1, 1)
    readonly property real panelCeiling: card ? card.surfaceMaterialCeiling : 1.0
    readonly property vector4d blurTint: parameters ? parameters[0] : Qt.vector4d(0, 0, 0, 1)
    readonly property vector4d lightNoise: parameters ? parameters[1] : Qt.vector4d(0, 0, 0, 0)
    readonly property vector4d glassLegibility: parameters ? parameters[2] : Qt.vector4d(0, 0, 0, 1)

    blending: true
    vertexShader: "shaders/text_legibility.vert.qsb"
    fragmentShader: "shaders/text_legibility.frag.qsb"
}
