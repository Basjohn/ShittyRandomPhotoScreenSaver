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
    property var maskItem: null
    property string materialMode: "normal"
    property real blurAmount: 0.90
    property real blurMax: 32.0

    readonly property bool materialActive: materialMode === "glass"
        || materialMode === "acrylic"

    visible: materialActive && sourceItem !== null && maskItem !== null
    enabled: false
    clip: true

    // The display background host is layer-backed only while a material is
    // admitted. Feed that texture directly to MultiEffect instead of creating a
    // second ShaderEffectSource/FBO. This is the single per-display background
    // texture authority for Glass/Acrylic; Normal keeps the layer and this lazy
    // component fully dormant.

    // Explicit single display-wide mask capture. Keeping this capture inside the
    // lazy material component means Normal instantiates no mask FBO either. The
    // source geometry itself remains a cheap retained QML item tree.
    ShaderEffectSource {
        id: materialMaskCapture
        objectName: "cardMaterialMaskCapture"
        anchors.fill: parent
        sourceItem: materialBackdrop.maskItem
        live: materialBackdrop.visible
        recursive: false
        // The mask geometry must stay logically visible so descendant visibility
        // bindings survive. Suppress it from the main scene here instead of
        // setting the mask-tree parent visible=false.
        hideSource: true
        smooth: true
        mipmap: false
        visible: false
    }

    // One shared blur representation.  Glass and Acrylic deliberately share the
    // same shared blur; their visible difference is cheap card-local tint strength.
    // v3 physical validation finally showed the effect path, but at roughly half
    // the desired visual strength. 32px is Qt MultiEffect's normal blurMax
    // baseline and remains far below the documented 64px high-blur ceiling.
    MultiEffect {
        id: sharedBlur
        objectName: "cardMaterialSharedBlur"
        anchors.fill: parent
        source: materialBackdrop.sourceItem
        visible: materialBackdrop.visible
        blurEnabled: true
        blur: materialBackdrop.blurAmount
        blurMax: materialBackdrop.blurMax
        autoPaddingEnabled: false
        maskEnabled: true
        maskSource: materialMaskCapture
    }
}
