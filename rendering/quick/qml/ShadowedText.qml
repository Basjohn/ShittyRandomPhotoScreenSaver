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
    // whose material is active this run gets a local legibility plate (only the overlay its
    // own colour needs, nothing where the surface already meets it) and drops the light-theme
    // soft halo, which goes muddy over a colourful blur. Normal cards: nothing changes.
    // A run drawn on its own fill (a header pill, a stats panel) opts out.
    property bool surfacePlateEnabled: true
    function _findSurfaceCard(item) {
        for (var candidate = item; candidate; candidate = candidate.parent) {
            if (candidate.surfaceMaterialActive !== undefined)
                return candidate
        }
        return null
    }
    readonly property Item surfaceCard: _findSurfaceCard(shadowedText.parent)
    readonly property bool onSurfaceMaterial: surfaceCard !== null && surfaceCard.surfaceMaterialActive
    // This run's position in its card (the walk reads each ancestor's x/y, so a reflow that
    // moves the run re-evaluates it; nothing runs per frame).
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

    // A run on its own: one rounded box with one even tone (not a feathered pill per
    // glyph). A run (nearly) as wide as its card's content is a line and its row spans
    // the run's whole box; a shorter one gets a box around its glyphs. Runs that share
    // a line or a panel with others opt out and that LegibilityRow holds the floor.
    Loader {
        id: legibilityPlate
        objectName: "shadowedTextLegibilityPlate"
        readonly property real padX: 4.0
        readonly property real padY: 3.0
        readonly property real glyphWidth: Math.min(shadowedText.width, mainText.contentWidth)
        readonly property real glyphHeight: Math.min(shadowedText.height, mainText.contentHeight)
        readonly property bool fullLine: shadowedText.surfaceCard !== null
            && shadowedText.width >= 0.85 * (shadowedText.surfaceCard.width
                - 2.0 * shadowedText.surfaceCard.padding)
        active: shadowedText.onSurfaceMaterial && shadowedText.surfacePlateEnabled
            && shadowedText.text.length > 0
        visible: active
        x: (fullLine ? 0.0
                : shadowedText.horizontalAlignment === Text.AlignRight
                    ? shadowedText.width - glyphWidth
                    : shadowedText.horizontalAlignment === Text.AlignHCenter
                        ? (shadowedText.width - glyphWidth) / 2.0 : 0.0) - padX
        y: (shadowedText.verticalAlignment === Text.AlignBottom
                ? shadowedText.height - glyphHeight
                : shadowedText.verticalAlignment === Text.AlignVCenter
                    ? (shadowedText.height - glyphHeight) / 2.0 : 0.0) - padY
        width: (fullLine ? shadowedText.width : glyphWidth) + padX * 2.0
        height: glyphHeight + padY * 2.0
        z: -1
        sourceComponent: TextLegibilityPlate {
            card: shadowedText.surfaceCard
            cardOrigin: {
                const origin = shadowedText._offsetInCard(shadowedText.surfaceCard)
                return Qt.point(origin.x + legibilityPlate.x, origin.y + legibilityPlate.y)
            }
            // A run faded by its own opacity (a muted state label) is that much
            // closer to the surface; the row holds the floor for what is drawn.
            runColor: Qt.rgba(shadowedText.color.r, shadowedText.color.g, shadowedText.color.b,
                              shadowedText.color.a * shadowedText.opacity)
            runPixelSize: mainText.fontInfo.pixelSize
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
        color: shadowedText.color
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
