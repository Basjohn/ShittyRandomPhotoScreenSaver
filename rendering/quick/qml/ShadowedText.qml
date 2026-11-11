import QtQuick

// Presentation-only text with the surviving SRPSS text-shadow semantic: a
// retained duplicate glyph drawn behind the main text at a signed offset, with
// its own color/alpha. The explicit global light-palette modifier filters only
// that retained shadow glyph. The foreground, signed displacement and alpha
// stay authored. Dark/hard shadows create no layer/effect instance.
// The signed offset is resolved from the global shadow direction in Python
// before it reaches this component. This is a shared E4 primitive and exposes
// only explicit presentation properties.
Item {
    id: shadowedText
    objectName: "shadowedText"

    property string text: ""
    property int textFormat: Text.AutoText
    property font font
    // A standalone primitive keeps its supplied font; production factories
    // supply one generation-scoped semantic typography adapter.
    readonly property font effectiveFont: typeof widgetThemeTypography !== "undefined" && widgetThemeTypography.light
        ? widgetThemeTypography.adjustedFont(shadowedText.font) : shadowedText.font
    property color color: "#ffffffff"
    property int horizontalAlignment: Text.AlignLeft
    property int verticalAlignment: Text.AlignTop
    property bool wrap: false
    // Also break inside a word when one word is wider than the line, so a long
    // name shrinks and wraps instead of spilling past its box.
    property bool breakLongWords: false
    property int elide: Text.ElideNone
    property int fontSizeMode: Text.FixedSize
    property real minimumPointSize: 6.0
    property int maximumLineCount: 2147483647

    property bool shadowEnabled: true
    property bool shadowSoft: false
    property color shadowColor: "#96000000"
    // Signed offsets: negative values move the shadow up/left and must not clip.
    property real shadowOffsetX: 0.0
    property real shadowOffsetY: 2.0
    // The light-theme soft shadow sits at half the authored offset (Contracts: Shadow authority); its blur
    // still sizes from the authored offset. Dark/hard shadows keep the full offset.
    readonly property real shadowOffsetScale: shadowSoft ? 0.5 : 1.0

    // Card surface materials (Docs/Architecture/Card_Surface_Materials.md, 3.3). On a card
    // whose material is active the card's own legibility panel (2.5 px inside the border,
    // concentric with the card) holds the contrast floor, so a run adds no plate of its own;
    // it only drops the light-theme soft halo, which goes muddy over a colourful blur.
    // Normal cards: nothing changes.
    function _findSurfaceCard(item) {
        for (var candidate = item; candidate; candidate = candidate.parent) {
            if (candidate.surfaceMaterialActive !== undefined)
                return candidate
        }
        return null
    }
    readonly property Item surfaceCard: _findSurfaceCard(shadowedText.parent)
    readonly property bool onSurfaceMaterial: surfaceCard !== null && surfaceCard.surfaceMaterialActive
    // On a material card with dark ink (light themes) the panel is bounded rather than
    // whitened, and the run's own ink is corrected at its real alpha (the card's
    // surfaceInkSolution); otherwise exactly the authored colour. A run whose own opacity
    // keeps even black from reading over the bounded panel takes a text-local plate.
    readonly property real _pixelSize: effectiveFont.pixelSize > 0 ? effectiveFont.pixelSize
        : effectiveFont.pointSize * 96.0 / 72.0
    readonly property var _inkSolution: onSurfaceMaterial
        && typeof surfaceCard.surfaceInkSolution === "function"
        ? surfaceCard.surfaceInkSolution(shadowedText.color, shadowedText.opacity, _pixelSize < 18.0) : null
    readonly property color inkColor: _inkSolution === null ? shadowedText.color
        : Qt.rgba(_inkSolution[0], _inkSolution[1], _inkSolution[2], _inkSolution[3])
    readonly property bool inkNeedsPlate: _inkSolution !== null && !_inkSolution[4]

    function _offsetInCard(card) {
        var x = 0.0
        var y = 0.0
        for (var item = shadowedText; item && item !== card; item = item.parent) {
            x += item.x
            y += item.y
        }
        return Qt.point(x, y)
    }

    clip: false
    implicitWidth: mainText.implicitWidth
    implicitHeight: mainText.implicitHeight

    Component {
        id: softShadowEffect
        SoftShadowEffect {
            objectName: "shadowedTextSoftEffect"
            softOffsetX: shadowedText.shadowOffsetX
            softOffsetY: shadowedText.shadowOffsetY
        }
    }

    Text {
        id: shadowGlyph
        objectName: "shadowedTextShadow"
        width: shadowedText.width
        height: shadowedText.height
        x: shadowedText.shadowOffsetX * shadowedText.shadowOffsetScale
        y: shadowedText.shadowOffsetY * shadowedText.shadowOffsetScale
        visible: shadowedText.shadowEnabled
            && !(shadowedText.shadowSoft && shadowedText.onSurfaceMaterial)
        layer.enabled: shadowedText.shadowEnabled && shadowedText.shadowSoft
            && !shadowedText.onSurfaceMaterial
        layer.effect: shadowedText.shadowSoft ? softShadowEffect : null
        // Only the diffuse shadow capture is downsampled. Main glyphs retain
        // their native full-resolution text renderer and all logical geometry.
        layer.textureSize: shadowedText.shadowSoft
            ? Qt.size(Math.max(1, Math.ceil(width * Screen.devicePixelRatio * 0.5)),
                      Math.max(1, Math.ceil(height * Screen.devicePixelRatio * 0.5)))
            : Qt.size(0, 0)
        layer.smooth: true
        text: shadowedText.text
        textFormat: shadowedText.textFormat
        font: shadowedText.effectiveFont
        color: shadowedText.shadowColor
        horizontalAlignment: shadowedText.horizontalAlignment
        verticalAlignment: shadowedText.verticalAlignment
        wrapMode: !shadowedText.wrap ? Text.NoWrap
            : shadowedText.breakLongWords ? Text.WrapAtWordBoundaryOrAnywhere : Text.WordWrap
        elide: shadowedText.elide
        fontSizeMode: shadowedText.fontSizeMode
        minimumPointSize: shadowedText.minimumPointSize
        maximumLineCount: shadowedText.maximumLineCount
        z: 0
    }

    // Text-local plate (Card_Surface_Materials.md 3.3), only for a run whose ink correction
    // cannot reach the floor (inkNeedsPlate: dark ink faded by its own opacity on a bounded
    // light panel). It hugs the painted text and draws only where the surface under it
    // misses the floor; never on Normal, light ink or a run that reads.
    Loader {
        id: inkPlate
        objectName: "shadowedTextInkPlate"
        readonly property real pad: 3.0
        readonly property real paintedWidth: Math.min(mainText.contentWidth,
            shadowedText.width > 0 ? shadowedText.width : mainText.contentWidth)
        active: shadowedText.inkNeedsPlate && shadowedText.visible && paintedWidth > 0
        visible: active
        x: (shadowedText.horizontalAlignment === Text.AlignRight ? shadowedText.width - paintedWidth
            : shadowedText.horizontalAlignment === Text.AlignHCenter ? (shadowedText.width - paintedWidth) / 2.0
            : 0.0) - pad
        y: -1.0
        width: paintedWidth + 2.0 * pad
        height: Math.min(mainText.contentHeight, shadowedText.height > 0 ? shadowedText.height
                                                                         : mainText.contentHeight) + 2.0
        z: -1
        sourceComponent: TextLegibilityPlate {
            card: shadowedText.surfaceCard
            cardOrigin: {
                var origin = shadowedText._offsetInCard(shadowedText.surfaceCard)
                return Qt.point(origin.x + inkPlate.x, origin.y + inkPlate.y)
            }
            runColor: Qt.rgba(shadowedText.inkColor.r, shadowedText.inkColor.g, shadowedText.inkColor.b,
                              shadowedText.inkColor.a * shadowedText.opacity)
            runPixelSize: shadowedText._pixelSize
            radiusOverride: inkPlate.height / 2.0
            ownOpacity: shadowedText.opacity
        }
    }

    Text {
        id: mainText
        objectName: "shadowedTextMain"
        width: shadowedText.width
        height: shadowedText.height
        text: shadowedText.text
        textFormat: shadowedText.textFormat
        font: shadowedText.effectiveFont
        color: shadowedText.inkColor
        horizontalAlignment: shadowedText.horizontalAlignment
        verticalAlignment: shadowedText.verticalAlignment
        wrapMode: !shadowedText.wrap ? Text.NoWrap
            : shadowedText.breakLongWords ? Text.WrapAtWordBoundaryOrAnywhere : Text.WordWrap
        elide: shadowedText.elide
        fontSizeMode: shadowedText.fontSizeMode
        minimumPointSize: shadowedText.minimumPointSize
        maximumLineCount: shadowedText.maximumLineCount
        z: 1
    }
}
