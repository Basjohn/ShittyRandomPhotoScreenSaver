import QtQuick
import QtQuick.Effects

// One lazy per-display material backdrop.  The expensive capture/blur objects
// exist only while the display has at least one Glass/Acrylic consumer.  All
// cards and the retained Context Menu reveal this ONE shared blurred background
// through the display-wide mask; no card owns a ShaderEffectSource, FBO or blur.
Item {
    id: materialBackdrop
    objectName: "cardMaterialBackdrop"

    property var sourceItem: null
    property var maskSource: null
    property string materialMode: "normal"
    property real downsampleScale: 0.25
    property real blurAmount: 0.72
    property real blurMax: 24.0

    readonly property bool materialActive: materialMode === "glass"
        || materialMode === "acrylic"

    visible: materialActive && sourceItem !== null && maskSource !== null
    enabled: false
    clip: true

    // Deliberately reduced-resolution, display-wide source.  This is the only
    // card-material capture owner on the display.  The normal path never loads
    // this component at all, so it retains the historical cheap card cost.
    ShaderEffectSource {
        id: backdropCapture
        objectName: "cardMaterialBackdropCapture"
        anchors.fill: parent
        sourceItem: materialBackdrop.sourceItem
        live: materialBackdrop.visible
        recursive: false
        hideSource: false
        smooth: true
        mipmap: false
        textureSize: Qt.size(
            Math.max(1, Math.round(width * materialBackdrop.downsampleScale)),
            Math.max(1, Math.round(height * materialBackdrop.downsampleScale))
        )
        visible: false
    }

    // One shared blur representation.  Glass and Acrylic deliberately share the
    // same blur; their visible difference is cheap card-local tint strength.
    MultiEffect {
        id: sharedBlur
        objectName: "cardMaterialSharedBlur"
        anchors.fill: parent
        source: backdropCapture
        visible: materialBackdrop.visible
        blurEnabled: true
        blur: materialBackdrop.blurAmount
        blurMax: materialBackdrop.blurMax
        autoPaddingEnabled: false
        maskEnabled: true
        maskSource: materialBackdrop.maskSource
    }
}
