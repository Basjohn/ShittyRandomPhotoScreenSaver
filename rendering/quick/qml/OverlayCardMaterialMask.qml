import QtQuick

// Cheap per-card geometry only.  This item never captures or blurs anything;
// it contributes one rounded white shape to the ONE per-display material mask.
Rectangle {
    id: materialMask
    objectName: "overlayCardMaterialMask"

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
    radius: sourceWidget
        ? Math.max(0.0, Number(sourceWidget.cardCornerRadius) * sourceScale)
        : 0.0
    color: "white"
    visible: !!sourceWidget
        && sourceWidget.visible
        && sourceWidget.cardShellEnabled
        && sourceWidget.cardMaterialMode !== "normal"
        && sourceVisualWidth > 0.0
        && sourceVisualHeight > 0.0
    enabled: false
}
