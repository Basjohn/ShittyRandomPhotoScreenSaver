import QtQuick
import QtQuick.Window

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
        x: shadowedText.shadowOffsetX
        y: shadowedText.shadowOffsetY
        visible: shadowedText.shadowEnabled
        layer.enabled: shadowedText.shadowEnabled && shadowedText.shadowSoft
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
