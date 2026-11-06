import QtQuick

// The local legibility layer under one text run on a card surface material
// (Docs/Architecture/Card_Surface_Materials.md, 3.3). It samples the display's one shared
// backdrop (no capture of its own), estimates the card surface beneath this run and draws
// only the overlay this run's own colour needs to reach its contrast floor: 4.5:1 for
// small text, 3:1 for large. Where the surface already meets it, it draws nothing.
// Loaded by ShadowedText only while its card's material is active.
ShaderEffect {
    id: plate
    objectName: "textLegibilityPlate"

    property var card: null
    // This plate's top-left in the card's own coordinates (ShadowedText walks the parents).
    property point cardOrigin: Qt.point(0, 0)
    property color runColor: "#ffffffff"
    property real runPixelSize: 14.0
    // Below this a run is small text and needs 4.5:1 (WCAG AA body text).
    readonly property real smallTextPx: 18.0

    readonly property var source: card ? card.surfaceBackdrop : null
    readonly property vector2d itemSize: Qt.vector2d(width, height)
    readonly property real feather: 3.0
    readonly property real floorRatio: runPixelSize < smallTextPx ? 4.5 : 3.0
    readonly property color tintColor: card ? card.backgroundColor : "transparent"
    readonly property color textColor: card ? card.surfaceTextColor : "#ffffffff"
    readonly property vector2d cardSize: card ? Qt.vector2d(card.width, card.height) : Qt.vector2d(1, 1)
    readonly property vector2d cardOffset: Qt.vector2d(cardOrigin.x, cardOrigin.y)
    readonly property real cornerRadius: card ? card.cornerRadius : 0.0
    readonly property real contentInset: card ? card.padding : 0.0
    readonly property real borderWidth: card ? card.borderWidth : 0.0
    readonly property var parameters: card ? card.surfaceMaterialParameters : null
    readonly property vector4d blurTint: parameters ? parameters[0] : Qt.vector4d(0, 0, 0, 1)
    readonly property vector4d lightNoise: parameters ? parameters[1] : Qt.vector4d(0, 0, 0, 0)
    readonly property vector4d glassLegibility: parameters ? parameters[2] : Qt.vector4d(0, 0, 0, 1)

    blending: true
    vertexShader: "shaders/text_legibility.vert.qsb"
    fragmentShader: "shaders/text_legibility.frag.qsb"
}
