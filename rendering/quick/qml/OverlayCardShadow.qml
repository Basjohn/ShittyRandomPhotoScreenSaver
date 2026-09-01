import QtQuick
import QtQuick.Effects

// Display-level ordinary-card shadow underlay. The visual card stays in its
// widget subtree, but its shadow is parented beneath *all* ordinary widgets so
// one later-created card can never paint its blur over an earlier sibling.
// Geometry/style remain owned by the source OverlayWidget; this item has no
// settings/model authority of its own.
Item {
    id: shadowUnderlay
    objectName: "overlayCardShadowUnderlay"

    property var sourceWidget: null

    readonly property real sourceScale: sourceWidget
        ? Math.max(0.0, Number(sourceWidget.presentationScale))
        : 1.0
    readonly property real sourceVisualX: sourceWidget
        ? Number(sourceWidget.cardShadowVisualX)
        : 0.0
    readonly property real sourceVisualY: sourceWidget
        ? Number(sourceWidget.cardShadowVisualY)
        : 0.0
    readonly property real sourceVisualWidth: sourceWidget
        ? Number(sourceWidget.cardShadowVisualWidth)
        : 0.0
    readonly property real sourceVisualHeight: sourceWidget
        ? Number(sourceWidget.cardShadowVisualHeight)
        : 0.0

    x: sourceWidget ? Number(sourceWidget.x) + sourceVisualX : 0.0
    y: sourceWidget ? Number(sourceWidget.y) + sourceVisualY : 0.0
    width: sourceVisualWidth
    height: sourceVisualHeight
    visible: !!sourceWidget
        && sourceWidget.visible
        && sourceWidget.cardShellEnabled
        && sourceWidget.cardShadowEnabled
        && sourceVisualWidth > 0.0
        && sourceVisualHeight > 0.0
    // The underlay no longer inherits the source subtree's opacity, so mirror
    // the authored whole-widget fade explicitly. No blur/effect is rebuilt just
    // because opacity changes.
    opacity: sourceWidget ? Number(sourceWidget.opacity) : 0.0
    enabled: false
    clip: false

    readonly property real baseLeft: sourceWidget
        ? Math.max(0.0, -Number(sourceWidget.cardShadowOffsetX)) * sourceScale
        : 0.0
    readonly property real baseTop: sourceWidget
        ? Math.max(0.0, -Number(sourceWidget.cardShadowOffsetY)) * sourceScale
        : 0.0
    readonly property real baseRight: sourceWidget
        ? Math.max(0.0, Number(sourceWidget.cardShadowOffsetX)) * sourceScale
        : 0.0
    readonly property real baseBottom: sourceWidget
        ? Math.max(0.0, Number(sourceWidget.cardShadowOffsetY)) * sourceScale
        : 0.0
    readonly property real extendLeft: sourceWidget
        ? Math.max(0.0, Number(sourceWidget.cardShadowExtendLeft)) * sourceScale
        : 0.0
    readonly property real extendTop: sourceWidget
        ? Math.max(0.0, Number(sourceWidget.cardShadowExtendTop)) * sourceScale
        : 0.0
    readonly property real extendRight: sourceWidget
        ? Math.max(0.0, Number(sourceWidget.cardShadowExtendRight)) * sourceScale
        : 0.0
    readonly property real extendBottom: sourceWidget
        ? Math.max(0.0, Number(sourceWidget.cardShadowExtendBottom)) * sourceScale
        : 0.0

    RectangularShadow {
        id: cardShadow
        objectName: "overlayCardShadow"
        x: -shadowUnderlay.baseLeft - shadowUnderlay.extendLeft
        y: -shadowUnderlay.baseTop - shadowUnderlay.extendTop
        width: shadowUnderlay.width
            + shadowUnderlay.baseLeft + shadowUnderlay.baseRight
            + shadowUnderlay.extendLeft + shadowUnderlay.extendRight
        height: shadowUnderlay.height
            + shadowUnderlay.baseTop + shadowUnderlay.baseBottom
            + shadowUnderlay.extendTop + shadowUnderlay.extendBottom
        visible: shadowUnderlay.visible
        color: shadowUnderlay.sourceWidget
            ? shadowUnderlay.sourceWidget.cardShadowColor
            : "transparent"
        blur: shadowUnderlay.sourceWidget
            ? Number(shadowUnderlay.sourceWidget.cardShadowBlur) * shadowUnderlay.sourceScale
            : 0.0
        radius: shadowUnderlay.sourceWidget
            ? Number(shadowUnderlay.sourceWidget.cardCornerRadius) * shadowUnderlay.sourceScale
            : 0.0
        spread: shadowUnderlay.sourceWidget
            ? Number(shadowUnderlay.sourceWidget.cardShadowSpread) * shadowUnderlay.sourceScale
            : 0.0
        // Card direction/Extra Offset are one-sided geometry. Never translate
        // the complete blurred surface and steal coverage from the opposite edge.
        offset: Qt.vector2d(0.0, 0.0)
        cached: true
    }
}
