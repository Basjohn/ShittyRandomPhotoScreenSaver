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
