import QtQuick

Item {
    id: displayScene
    objectName: "displaySceneRoot"
    property string runtimeRole: "display-scene"
    property int screenIndex: -1
    property var runtimeGeneration: null

    // Per-display retained ordinary-widget presentation host. The Python
    // QuickSceneController owns creation/retirement of the OverlayWidget items
    // parented here; the scene itself stays free of any per-widget if/elif
    // dispatch. It sits above the background render item and below the
    // visualizer presentation.
    Item {
        id: ordinaryWidgetHost
        objectName: "ordinaryWidgetHost"
        anchors.fill: parent
        clip: false
        z: 5
    }

    Loader {
        id: visualizerPresentationLoader
        objectName: "visualizerPresentationLoader"
        active: false
        asynchronous: false
        source: "VisualizerPresentation.qml"
        z: 10
    }
}
