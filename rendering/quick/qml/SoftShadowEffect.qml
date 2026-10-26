import QtQuick.Effects

// The one light-palette soft silhouette profile. Item layers retain their
// source texture and update it only when source paint/geometry changes.
MultiEffect {
    property real softOffsetX: 0.0
    property real softOffsetY: 0.0
    // Diffuse the silhouette beyond its displacement, so small glyphs do not
    // read as a second line of text. This never changes the actual offset.
    readonly property real softRadius: Math.max(8.0, Math.min(32.0,
        Math.max(Math.abs(softOffsetX), Math.abs(softOffsetY)) * 3.0))
    // Keep the small kernel/shader fixed. Multiplier broadens this diffuse
    // silhouette without adding texture lookups when authored offsets change.
    readonly property int softBlurMax: 8
    readonly property real softBlur: 1.0
    readonly property real softBlurMultiplier: softRadius / softBlurMax - 1.0
    blurEnabled: true
    blurMax: softBlurMax
    blur: softBlur
    blurMultiplier: softBlurMultiplier
    autoPaddingEnabled: true
}
