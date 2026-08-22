import QtQuick

Item {
    id: displayScene
    objectName: "displaySceneRoot"
    property string runtimeRole: "display-scene"
    property int screenIndex: -1
    property var runtimeGeneration: null

    Loader {
        id: visualizerPresentationLoader
        objectName: "visualizerPresentationLoader"
        active: false
        asynchronous: false
        source: "VisualizerPresentation.qml"
        z: 10
    }
}
