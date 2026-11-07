import QtQuick

// A child control's own surface material (Docs/Architecture/Card_Surface_Materials.md 3.3):
// Media's volume track and mute button take their card's material, tinted by their own fill,
// through their own rounded shape. Placed inside the control at a negative z, so it paints
// beneath the control's border and content; the control drops its fill while this is
// active. On Normal (or before the card's backdrop is bound) it is an inactive Loader: no
// item, no scene-graph node.
Loader {
    id: child
    objectName: "childMaterialSurface"

    // The OverlayWidget whose card material this control follows.
    property Item card: null
    property color fillColor: "#b3101010"
    property real cornerRadius: 8.0
    property real borderWidth: 0.0

    anchors.fill: parent
    active: card !== null && card.cardSurfaceMaterialActive === true && visible
        && width > 0 && height > 0
    z: -0.5
    sourceComponent: MaterialSurface {
        backdrop: child.card.cardSurfaceBackdrop
        material: child.card.cardSurfaceMaterial
        cornerRadius: child.cornerRadius
        contentInset: 0.0
        borderWidth: child.borderWidth
        normalColor: child.fillColor
        tintColor: child.fillColor
        textColor: child.card.cardSurfaceTextColor
    }
}
