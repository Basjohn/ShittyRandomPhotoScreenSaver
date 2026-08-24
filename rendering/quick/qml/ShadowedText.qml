import QtQuick
import QtQuick.Effects

// Presentation-only text with authored text-shadow semantics. The shadow is a
// retained duplicate glyph layer at a signed offset; blur is applied through a
// single bounded effect that stays dormant (layer disabled) until a positive
// blur is authored, so static text performs no per-frame effect work. This is a
// shared E3 primitive and exposes only explicit presentation properties.
Item {
    id: shadowedText
    objectName: "shadowedText"

    property string text: ""
    property font font
    property color color: "#ffffffff"
    property int horizontalAlignment: Text.AlignLeft
    property int verticalAlignment: Text.AlignTop
    property bool wrap: false

    property bool shadowEnabled: true
    property color shadowColor: "#96000000"
    // Signed offsets: negative values move the shadow up/left and must not clip.
    property real shadowOffsetX: 0.0
    property real shadowOffsetY: 2.0
    property real shadowBlur: 0.0

    clip: false
    implicitWidth: mainText.implicitWidth
    implicitHeight: mainText.implicitHeight

    Text {
        id: shadowGlyph
        objectName: "shadowedTextShadow"
        width: shadowedText.width
        height: shadowedText.height
        x: shadowedText.shadowOffsetX
        y: shadowedText.shadowOffsetY
        visible: shadowedText.shadowEnabled
        text: shadowedText.text
        font: shadowedText.font
        color: shadowedText.shadowColor
        horizontalAlignment: shadowedText.horizontalAlignment
        verticalAlignment: shadowedText.verticalAlignment
        wrapMode: shadowedText.wrap ? Text.WordWrap : Text.NoWrap
        z: 0
        layer.enabled: shadowedText.shadowEnabled && shadowedText.shadowBlur > 0
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: 1.0
            blurMax: Math.max(1, Math.ceil(shadowedText.shadowBlur))
        }
    }

    Text {
        id: mainText
        objectName: "shadowedTextMain"
        width: shadowedText.width
        height: shadowedText.height
        text: shadowedText.text
        font: shadowedText.font
        color: shadowedText.color
        horizontalAlignment: shadowedText.horizontalAlignment
        verticalAlignment: shadowedText.verticalAlignment
        wrapMode: shadowedText.wrap ? Text.WordWrap : Text.NoWrap
        z: 1
    }
}
