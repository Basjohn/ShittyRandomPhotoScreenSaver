import QtQuick

// A child control's own surface material (Docs/Architecture/Card_Surface_Materials.md 3.3):
// Media's transport bar, mute button and volume track take their card's material, tinted by
// their own fill, through their own rounded shape. Placed inside the control at a negative z,
// so it paints beneath the control's outline and content; the control drops its fill while
// this is active. The control's outline is its only border: the material draws no inner rim
// (its legibility panel covers the whole face). On Normal (or before the card's backdrop is
// bound) it is an inactive Loader: no item, no scene-graph node.
Loader {
    id: child
    objectName: "childMaterialSurface"

    // The OverlayWidget whose card material this control follows.
    property Item card: null
    property color fillColor: "#b3101010"
    property real cornerRadius: 8.0
    // The tint's share of the fill's alpha (below 1 lets more backdrop read through).
    property real tintAlphaScale: 1.0
    // Controls with glyphs keep the darker legibility panel; a textless track passes false.
    property bool legibilityPanel: true

    anchors.fill: parent
    active: card !== null && card.cardSurfaceMaterialActive === true && visible
        && width > 0 && height > 0
    z: -0.5
    sourceComponent: MaterialSurface {
        backdrop: child.card.cardSurfaceBackdrop
        material: child.card.cardSurfaceMaterial
        cornerRadius: child.cornerRadius
        contentInset: 0.0
        // Negative: the panel spans the whole face, so there is no inner rim (the shaders'
        // plateInset); the control's own outline is the border.
        borderWidth: -1.0
        legibilityPanel: child.legibilityPanel
        normalColor: child.fillColor
        tintColor: Qt.rgba(child.fillColor.r, child.fillColor.g, child.fillColor.b,
                           child.fillColor.a * child.tintAlphaScale)
        textColor: child.card.cardSurfaceTextColor
    }
}
