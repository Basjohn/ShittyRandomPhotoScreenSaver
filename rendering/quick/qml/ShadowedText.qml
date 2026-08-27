import QtQuick

// Presentation-only text with the surviving SRPSS text-shadow semantic: a
// retained duplicate glyph drawn behind the main text at a signed offset, with
// its own color/alpha. Current text-shadow source authority exposes no authored
// ordinary-text blur, so there is deliberately no MultiEffect, no layer capture
// and no shadowBlur property here — a static label performs no per-frame work.
// The signed offset is resolved from the global shadow direction in Python
// before it reaches this component. This is a shared E4 primitive and exposes
// only explicit presentation properties.
Item {
    id: shadowedText
    objectName: "shadowedText"

    property string text: ""
    property font font
    property color color: "#ffffffff"
    property int horizontalAlignment: Text.AlignLeft
    property int verticalAlignment: Text.AlignTop
    property bool wrap: false
    property int elide: Text.ElideNone
    property int fontSizeMode: Text.FixedSize
    property real minimumPointSize: 6.0
    property int maximumLineCount: 2147483647

    property bool shadowEnabled: true
    property color shadowColor: "#96000000"
    // Signed offsets: negative values move the shadow up/left and must not clip.
    property real shadowOffsetX: 0.0
    property real shadowOffsetY: 2.0

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
        font: shadowedText.font
        color: shadowedText.color
        horizontalAlignment: shadowedText.horizontalAlignment
        verticalAlignment: shadowedText.verticalAlignment
        wrapMode: shadowedText.wrap ? Text.WordWrap : Text.NoWrap
        elide: shadowedText.elide
        fontSizeMode: shadowedText.fontSizeMode
        minimumPointSize: shadowedText.minimumPointSize
        maximumLineCount: shadowedText.maximumLineCount
        z: 1
    }
}
