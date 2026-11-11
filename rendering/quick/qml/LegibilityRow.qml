import QtQuick

// One rounded legibility row inside a control's own filled panel on a card surface material
// (Docs/Architecture/Card_Surface_Materials.md, 3.3): Feed grid tiles, Friend Pulse rows and
// tiles, Games You Follow story tiles, System Stats metric panels, Achievement capsules. The
// card itself has one legibility panel (the material's whole face, up to the border); a row is
// only for text that sits on a further fill, which the site passes as `underlayColor`, with
// that panel's inner radius. It holds the contrast floor for the line's run colours
// (`primaryColor`, `secondaryColor`, `tertiaryColor`). On Normal (or before the card's
// material is bound) it is an inactive Loader: no item, no scene-graph node.
Loader {
    id: row
    objectName: "legibilityRow"

    property color primaryColor: "#ffffffff"
    property color secondaryColor: primaryColor
    property color tertiaryColor: primaryColor
    // A row filling its own rounded panel passes the panel's inner radius; < 0 = automatic
    // (concentric with the card).
    property real radius: -1.0
    // A row inside its own filled panel passes that fill (it is composited over the card
    // surface before the contrast is measured); transparent on the card itself.
    property color underlayColor: "transparent"
    // Rows hold the small-text floor (4.5:1) unless the site says the line is large.
    property real pixelSize: 14.0

    function _findSurfaceCard(item) {
        for (var candidate = item; candidate; candidate = candidate.parent) {
            if (candidate.surfaceMaterialActive !== undefined)
                return candidate
        }
        return null
    }
    // The row's position in its card (the walk reads each ancestor's x/y, so a reflow that
    // moves the row re-evaluates it; nothing runs per frame).
    function _offsetInCard(card) {
        var x = 0.0
        var y = 0.0
        for (var item = row; item && item !== card; item = item.parent) {
            x += item.x
            y += item.y
        }
        return Qt.point(x, y)
    }
    readonly property Item surfaceCard: _findSurfaceCard(row.parent)

    active: surfaceCard !== null && surfaceCard.surfaceMaterialActive && visible
        && width > 0 && height > 0
    z: -1
    sourceComponent: TextLegibilityPlate {
        card: row.surfaceCard
        cardOrigin: row._offsetInCard(row.surfaceCard)
        runColor: row.primaryColor
        secondaryRunColor: row.secondaryColor
        tertiaryRunColor: row.tertiaryColor
        radiusOverride: row.radius
        underlayColor: row.underlayColor
        runPixelSize: row.pixelSize
    }
}
