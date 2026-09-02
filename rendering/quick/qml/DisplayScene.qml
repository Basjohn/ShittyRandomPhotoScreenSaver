import QtQuick


Item {
    id: displayScene
    objectName: "displaySceneRoot"
    property string runtimeRole: "display-scene"
    property int screenIndex: -1
    property var runtimeGeneration: null
    property bool dimmingEnabled: false
    property real dimmingOpacity: 0.0
    property real pixelShiftX: 0.0
    property real pixelShiftY: 0.0
    // One renderer-facing material enum for the entire retained display generation.
    // Normal keeps the expensive material Loader dormant; Glass/Acrylic share one
    // lazy display-wide capture/blur and differ only in cheap local tint.
    property string cardMaterialMode: "normal"
    property var materialBackdropSourceItem: null
    property var contextMenuModel: null
    property bool contextMenuShadowEnabled: true
    property color contextMenuShadowColor: "#c4000000"
    property real contextMenuShadowBlur: 18.0
    property real contextMenuShadowOffsetX: 4.0
    property real contextMenuShadowOffsetY: 4.0
    property real contextMenuShadowExtendLeft: 0.0
    property real contextMenuShadowExtendTop: 0.0
    property real contextMenuShadowExtendRight: 0.0
    property real contextMenuShadowExtendBottom: 0.0
    property color contextMenuSurfaceColor: "#f21b1d24"
    property color contextMenuBorderColor: "#d8f3ff"
    property color contextMenuTextColor: "#f6f8ff"
    property color contextMenuSelectedSurfaceColor: "#4f77b9e8"
    property color contextMenuSeparatorColor: "#59778a"
    property color contextMenuIndicatorBorderColor: "#b9eaff"
    property color contextMenuIndicatorFillColor: "#82cdff"
    property color contextMenuArrowColor: "#d8f3ff"
    property color contextSubmenuSurfaceColor: "#f21b1d24"
    property color contextSubmenuBorderColor: "#d8f3ff"
    property color contextSubmenuTextColor: "#f6f8ff"
    property color contextSubmenuSelectedSurfaceColor: "#4f77b9e8"
    property color contextSubmenuCheckedTextColor: "#b9eaff"
    property color contextSubmenuCheckedSurfaceColor: "#334e718b"
    property color contextSubmenuIndicatorBorderColor: "#b9eaff"
    property color contextSubmenuIndicatorFillColor: "#82cdff"
    property bool perfHudEnabled: false
    property string perfHudText: ""

    // The custom BackgroundRenderItem is parented into this host by Python.
    // Dimming lives in the same below-widgets presentation so the material
    // capture sees the exact displayed backdrop rather than an undimmed clone.
    Item {
        id: backgroundPresentationHost
        objectName: "backgroundPresentationHost"
        anchors.fill: parent
        z: 0

        Rectangle {
            id: backgroundDimming
            objectName: "backgroundDimming"
            anchors.fill: parent
            color: "black"
            opacity: displayScene.dimmingEnabled
                ? Math.max(0.0, Math.min(1.0, displayScene.dimmingOpacity))
                : 0.0
            visible: opacity > 0.0
            enabled: false
            z: 1
        }
    }

    // One full-display alpha mask shared by every Glass/Acrylic consumer. The
    // ordinary child host receives cheap rounded geometry items from Python.
    // Visualizer/Context Menu contribute declarative masks because they are not
    // ordinary-family host children. The mask itself is a single layer/FBO per
    // display and is only enabled when the material renderer is active.
    Item {
        id: cardMaterialMaskSource
        objectName: "cardMaterialMaskSource"
        anchors.fill: parent
        visible: false
        enabled: false
        layer.enabled: cardMaterialBackdropLoader.active
        layer.smooth: true
        z: 2

        Item {
            id: ordinaryCardMaterialMaskHost
            objectName: "ordinaryCardMaterialMaskHost"
            anchors.fill: parent
            x: displayScene.pixelShiftX
            y: displayScene.pixelShiftY
        }

        Rectangle {
            id: visualizerCardMaterialMask
            color: "white"
            x: visualizerPresentationLoader.x + displayScene.pixelShiftX
            y: visualizerPresentationLoader.y + displayScene.pixelShiftY
            width: visualizerPresentationLoader.width
            height: visualizerPresentationLoader.height
            radius: visualizerPresentationLoader.item
                ? Number(visualizerPresentationLoader.item.cardCornerRadius)
                : 0.0
            visible: displayScene.cardMaterialMode !== "normal"
                && visualizerPresentationLoader.active
                && visualizerPresentationLoader.item !== null
                && visualizerPresentationLoader.item.visible
                && visualizerPresentationLoader.item.cardShellEnabled
            enabled: false
        }

        Rectangle {
            id: contextMenuMaterialMask
            color: "white"
            x: retainedContextMenu.materialSurfaceX
            y: retainedContextMenu.materialSurfaceY
            width: retainedContextMenu.materialSurfaceWidth
            height: retainedContextMenu.materialSurfaceHeight
            radius: retainedContextMenu.materialSurfaceRadius
            visible: displayScene.cardMaterialMode !== "normal"
                && retainedContextMenu.visible
            enabled: false
        }

        Rectangle {
            id: contextSubmenuMaterialMask
            color: "white"
            x: retainedContextMenu.materialSubmenuX
            y: retainedContextMenu.materialSubmenuY
            width: retainedContextMenu.materialSubmenuWidth
            height: retainedContextMenu.materialSubmenuHeight
            radius: retainedContextMenu.materialSubmenuRadius
            visible: displayScene.cardMaterialMode !== "normal"
                && retainedContextMenu.materialSubmenuVisible
            enabled: false
        }
    }

    readonly property bool cardMaterialBackdropNeeded:
        cardMaterialMode !== "normal"
        && (ordinaryCardMaterialMaskHost.children.length > 0
            || visualizerCardMaterialMask.visible
            || contextMenuMaterialMask.visible
            || contextSubmenuMaterialMask.visible)

    Loader {
        id: cardMaterialBackdropLoader
        objectName: "cardMaterialBackdropLoader"
        anchors.fill: parent
        active: displayScene.cardMaterialBackdropNeeded
        asynchronous: false
        source: "CardMaterialBackdrop.qml"
        z: 3
        onLoaded: {
            item.sourceItem = Qt.binding(function() {
                return displayScene.materialBackdropSourceItem
            })
            item.maskSource = Qt.binding(function() {
                return cardMaterialMaskSource
            })
            item.materialMode = Qt.binding(function() {
                return displayScene.cardMaterialMode
            })
        }
    }

    Item {
        id: pixelShiftLayer
        objectName: "pixelShiftLayer"
        anchors.fill: parent
        z: 5
        transform: Translate {
            x: displayScene.pixelShiftX
            y: displayScene.pixelShiftY
        }

        // All ordinary card shadows live in a shared underlay below every card.
        // A shadow nested inside one widget subtree can otherwise overpaint an
        // earlier sibling even with z < 0, because sibling subtree order wins.
        Item {
            id: ordinaryWidgetShadowHost
            objectName: "ordinaryWidgetShadowHost"
            anchors.fill: parent
            clip: false
            enabled: false
            z: 0
        }

        // Per-display retained ordinary-widget presentation host. The Python
        // QuickSceneController owns creation/retirement of the OverlayWidget
        // items parented here; pixel shift remains one shared transform.
        Item {
            id: ordinaryWidgetHost
            objectName: "ordinaryWidgetHost"
            anchors.fill: parent
            clip: false
            z: 10
        }

        Loader {
            id: visualizerPresentationLoader
            objectName: "visualizerPresentationLoader"
            active: false
            asynchronous: false
            source: "VisualizerPresentation.qml"
            z: 20
        }
    }

    CustomLayoutOverlay {
        id: customLayoutOverlay
        anchors.fill: parent
        z: 100
    }

    ContextMenu {
        id: retainedContextMenu
        contextMenuModel: displayScene.contextMenuModel
        shadowEnabled: displayScene.contextMenuShadowEnabled
        shadowColor: displayScene.contextMenuShadowColor
        shadowBlur: displayScene.contextMenuShadowBlur
        shadowOffsetX: displayScene.contextMenuShadowOffsetX
        shadowOffsetY: displayScene.contextMenuShadowOffsetY
        shadowExtendLeft: displayScene.contextMenuShadowExtendLeft
        shadowExtendTop: displayScene.contextMenuShadowExtendTop
        shadowExtendRight: displayScene.contextMenuShadowExtendRight
        shadowExtendBottom: displayScene.contextMenuShadowExtendBottom
        surfaceColor: displayScene.contextMenuSurfaceColor
        borderColor: displayScene.contextMenuBorderColor
        textColor: displayScene.contextMenuTextColor
        selectedSurfaceColor: displayScene.contextMenuSelectedSurfaceColor
        separatorColor: displayScene.contextMenuSeparatorColor
        indicatorBorderColor: displayScene.contextMenuIndicatorBorderColor
        indicatorFillColor: displayScene.contextMenuIndicatorFillColor
        arrowColor: displayScene.contextMenuArrowColor
        submenuSurfaceColor: displayScene.contextSubmenuSurfaceColor
        submenuBorderColor: displayScene.contextSubmenuBorderColor
        submenuTextColor: displayScene.contextSubmenuTextColor
        submenuSelectedSurfaceColor: displayScene.contextSubmenuSelectedSurfaceColor
        submenuCheckedTextColor: displayScene.contextSubmenuCheckedTextColor
        submenuCheckedSurfaceColor: displayScene.contextSubmenuCheckedSurfaceColor
        submenuIndicatorBorderColor: displayScene.contextSubmenuIndicatorBorderColor
        submenuIndicatorFillColor: displayScene.contextSubmenuIndicatorFillColor
        materialMode: displayScene.cardMaterialMode
        z: 300
    }

    Rectangle {
        id: perfHud
        objectName: "perfHud"
        visible: displayScene.perfHudEnabled && displayScene.perfHudText.length > 0
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 8
        width: perfHudLabel.implicitWidth + 12
        height: perfHudLabel.implicitHeight + 8
        radius: 3
        color: "#b8000000"
        border.color: "#80ffffff"
        border.width: 1
        z: 1000
        enabled: false

        Text {
            id: perfHudLabel
            anchors.centerIn: parent
            text: displayScene.perfHudText
            color: "white"
            font.family: "Consolas"
            font.pixelSize: 11
            renderType: Text.NativeRendering
        }
    }
}
