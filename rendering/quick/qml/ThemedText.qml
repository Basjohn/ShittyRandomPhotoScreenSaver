import QtQuick

// Text with the same single glyph renderer and geometry as Text. Its complete
// source font remains authored by the caller; typography is a presentation copy.
Text {
    id: themedText
    property font sourceFont: Qt.font({})
    font: typeof widgetThemeTypography !== "undefined" && widgetThemeTypography.light
        ? widgetThemeTypography.adjustedFont(themedText.sourceFont) : themedText.sourceFont
}
