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
    // Controls that must render independently of their outer card shell (Media's
    // transport bar in both ordinary and fullscreen views) can receive the
    // already-shared backdrop and material directly. Existing volume/mute child
    // controls retain their card binding.
    property var sourceBackdrop: null
    property string sourceMaterial: "normal"
    // Explicit child material, even when the card itself uses Normal. The
    // display host admits its shared backdrop from child-only material demand.
    property string materialOverride: "inherit"
    property real sourceOpacityAdjust: 0.0
    // Child-only density adjustment. Add to the inherited card adjustment;
    // zero is pixel-identical to the previous surface recipe.
    property real additionalOpacityAdjust: 0.0
    property color sourceTextColor: "#ffffffff"
    // Flat is a child-only override: it never changes its parent card's material.
    property bool forceFlat: false
    readonly property var resolvedBackdrop: card !== null ? card.cardSurfaceBackdrop : sourceBackdrop
    readonly property string resolvedMaterial: materialOverride !== "inherit"
        ? materialOverride : (card !== null ? card.cardSurfaceMaterial : sourceMaterial)
    readonly property real resolvedOpacityAdjust: card !== null ? card.cardSurfaceOpacityAdjust : sourceOpacityAdjust
    readonly property color resolvedTextColor: card !== null ? card.cardSurfaceTextColor : sourceTextColor
    property color fillColor: "#b3101010"
    property real cornerRadius: 8.0
    // The tint's share of the fill's alpha (below 1 lets more backdrop read through).
    property real tintAlphaScale: 1.0
    // Controls with glyphs keep the darker legibility panel; a textless track passes false.
    property bool legibilityPanel: true

    anchors.fill: parent
    active: !forceFlat && visible && width > 0 && height > 0
        && resolvedBackdrop !== null && resolvedMaterial !== "normal"
        && (card === null || card.cardSurfaceMaterialActive === true
            || materialOverride !== "inherit")
    z: -0.5
    sourceComponent: MaterialSurface {
        backdrop: child.resolvedBackdrop
        material: child.resolvedMaterial
        opacityAdjust: Math.max(-1.0, Math.min(1.0,
            child.resolvedOpacityAdjust + child.additionalOpacityAdjust))
        cornerRadius: child.cornerRadius
        contentInset: 0.0
        // Negative: the control's own outline is its border (the panel spans the whole face
        // of every surface since 1B.8 M2; the value is kept for the ring shading to read).
        borderWidth: -1.0
        legibilityPanel: child.legibilityPanel
        normalColor: child.fillColor
        tintColor: Qt.rgba(child.fillColor.r, child.fillColor.g, child.fillColor.b,
                           child.fillColor.a * child.tintAlphaScale)
        textColor: child.resolvedTextColor
        legibilityInk: child.resolvedTextColor
    }
}
