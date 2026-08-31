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
    property bool haloVisible: false
    property real haloX: 0.0
    property real haloY: 0.0
    property string haloShape: "cursor_light"
    property var contextMenuModel: null
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

        // Per-display retained ordinary-widget presentation host. The Python
        // QuickSceneController owns creation/retirement of the OverlayWidget
        // items parented here; pixel shift remains one shared transform.
        Item {
            id: ordinaryWidgetHost
            objectName: "ordinaryWidgetHost"
            anchors.fill: parent
            clip: false
            z: 0
        }

        Loader {
            id: visualizerPresentationLoader
            objectName: "visualizerPresentationLoader"
            active: false
            asynchronous: false
            source: "VisualizerPresentation.qml"
            z: 5
        }
    }

    CustomLayoutOverlay {
        id: customLayoutOverlay
        anchors.fill: parent
        z: 100
    }

    CursorHalo {
        id: cursorHalo
        haloVisible: displayScene.haloVisible
        pointerX: displayScene.haloX
        pointerY: displayScene.haloY
        haloShape: displayScene.haloShape
        z: 200
    }

    ContextMenu {
        id: retainedContextMenu
        contextMenuModel: displayScene.contextMenuModel
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
