import QtQuick

// One fitting policy for Media metadata, including the fullscreen presentation.
// The caller owns font, row width and allotted lines; fitting never changes provider truth.
ShadowedText {
    textFormat: Text.PlainText
    fontSizeMode: Text.HorizontalFit
    minimumPointSize: 6.0
    maximumLineCount: 1
    wrap: maximumLineCount > 1
    breakLongWords: true
    elide: Text.ElideRight
}
