.pragma library

// The Media card's authored artwork rule: one owner, drawn by the Media card (MediaPresentation.qml) and by the
// Expanded Visualizer's Now Playing block (ExpandedVisualizerOverlays.qml; plan 1C.3, operator 11 Nov: "X/Y artwork
// should adjust, media does this well").
//
// The artwork's height is the vertical room its owner gives it. Its width is its base width plus a share of the width
// given beyond the owner's reference width (a negative share when width is taken), never under the owner's floor,
// always leaving the metadata its room, and never wider than the owner's widest shape allows (``maxAspect``, width over
// height, from the owner's own spec: the Media card's artwork is never wider than tall, 1; Now Playing's may go
// landscape up to 16:9). So a side handle that gives or takes width or height changes the artwork's size and shape, and
// a uniform scale (a corner) scales it whole. The image inside is cropped (PreserveAspectCrop), never distorted. Every
// input is the owner's geometry; nothing here reads content (a track's text never sizes the artwork).

// The share of the extra width the artwork takes (the rest goes to the metadata beside it).
var widthShare = 0.35

// The artwork's width before its height bounds it. An owner that passes its vertical room (``heightRoom``, the least
// height the artwork can have) and its ``maxAspect`` lets the artwork widen to the shape its height asks for (a
// square for the Media card) as soon as the card has the room, instead of only by the share of the extra width: a
// tall card otherwise leaves a narrow strip beside a wide empty text column.
function provisionalWidth(baseWidth, extraWidth, contentWidth, metadataRoom, floorWidth, heightRoom, maxAspect) {
    var wanted = baseWidth + extraWidth * widthShare
    if (heightRoom > 0.0 && maxAspect > 0.0)
        wanted = Math.max(wanted, heightRoom * maxAspect)
    return Math.min(Math.max(floorWidth, wanted),
                    Math.max(1.0, contentWidth - metadataRoom))
}

// The artwork's width: never wider than ``maxAspect`` times the vertical room (its height).
function authoredWidth(provisional, referenceHeight, maxAspect) {
    return Math.min(provisional, referenceHeight * maxAspect)
}
