.pragma library

// The Media card's authored artwork rule: one owner, drawn by the Media card (MediaPresentation.qml) and by the
// Expanded Visualizer's Now Playing block (ExpandedVisualizerOverlays.qml; plan 1C.3, operator 11 Nov: "X/Y artwork
// should adjust, media does this well").
//
// The artwork's height is the vertical room its owner gives it. Its width is its base width plus a share of the width
// given beyond the owner's canonical width (a negative share when width is taken), never under the owner's floor,
// always leaving the metadata its room, and never wider than tall. So a side handle that gives or takes width or
// height changes the artwork's size and shape, and a uniform scale (a corner) scales it whole. The image inside is
// cropped (PreserveAspectCrop), never distorted.

// The share of the extra width the artwork takes (the rest goes to the metadata beside it).
var widthShare = 0.35

// The artwork's width before its height bounds it.
function provisionalWidth(baseWidth, extraWidth, contentWidth, metadataRoom, floorWidth) {
    return Math.min(Math.max(floorWidth, baseWidth + extraWidth * widthShare),
                    Math.max(1.0, contentWidth - metadataRoom))
}

// The artwork's width: never wider than the vertical room (its height).
function authoredWidth(provisional, referenceHeight) {
    return Math.min(provisional, referenceHeight)
}
